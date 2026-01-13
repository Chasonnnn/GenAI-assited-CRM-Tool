"""
Notification Service - handles in-app notifications.

Provides CRUD for notifications and trigger functions for case/task events.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import asyncio
import logging
import threading
from sqlalchemy.orm import Session

from app.db.enums import NotificationType, Role, OwnerType
from app.db.models import (
    Notification,
    UserNotificationSettings,
    Case,
    Attachment,
    Membership,
)
from app.core.websocket import manager

logger = logging.getLogger(__name__)

# =============================================================================
# Notification Settings
# =============================================================================


def get_user_settings(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> dict:
    """
    Get user notification settings.

    Returns defaults (all ON) if no row exists.
    """
    settings = (
        db.query(UserNotificationSettings)
        .filter(
            UserNotificationSettings.user_id == user_id,
            UserNotificationSettings.organization_id == org_id,
        )
        .first()
    )

    if settings:
        return {
            "case_assigned": settings.case_assigned,
            "case_status_changed": settings.case_status_changed,
            "case_handoff": settings.case_handoff,
            "task_assigned": settings.task_assigned,
            "workflow_approvals": settings.workflow_approvals,
            "task_reminders": settings.task_reminders,
            "appointments": settings.appointments,
            "contact_reminder": settings.contact_reminder,
        }

    # Defaults (all ON)
    return {
        "case_assigned": True,
        "case_status_changed": True,
        "case_handoff": True,
        "task_assigned": True,
        "workflow_approvals": True,
        "task_reminders": True,
        "appointments": True,
        "contact_reminder": True,
    }


def update_user_settings(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    updates: dict,
) -> dict:
    """
    Update user notification settings.

    Creates row if it doesn't exist.
    """
    settings = (
        db.query(UserNotificationSettings)
        .filter(
            UserNotificationSettings.user_id == user_id,
            UserNotificationSettings.organization_id == org_id,
        )
        .first()
    )

    if not settings:
        settings = UserNotificationSettings(
            user_id=user_id,
            organization_id=org_id,
        )
        db.add(settings)

    # Update provided fields
    for key, value in updates.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

    return {
        "case_assigned": settings.case_assigned,
        "case_status_changed": settings.case_status_changed,
        "case_handoff": settings.case_handoff,
        "task_assigned": settings.task_assigned,
        "workflow_approvals": settings.workflow_approvals,
        "task_reminders": settings.task_reminders,
        "appointments": settings.appointments,
        "contact_reminder": settings.contact_reminder,
    }


def should_notify(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    setting_key: str,
) -> bool:
    """Check if user wants this notification type."""
    settings = get_user_settings(db, user_id, org_id)
    return settings.get(setting_key, True)


# =============================================================================
# Notification CRUD
# =============================================================================


def create_notification(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    type: NotificationType,
    title: str,
    body: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    dedupe_key: Optional[str] = None,
    dedupe_window_hours: int | None = 1,
) -> Optional[Notification]:
    """
    Create a notification.

    Dedupes by dedupe_key + org_id + user_id within a time window
    (or forever when dedupe_window_hours is None).
    """
    # Check dedupe (scoped by org and user for safety)
    if dedupe_key:
        query = db.query(Notification).filter(
            Notification.dedupe_key == dedupe_key,
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
        )
        if dedupe_window_hours is not None:
            window_start = datetime.now(timezone.utc) - timedelta(
                hours=dedupe_window_hours
            )
            query = query.filter(Notification.created_at > window_start)
        existing = query.first()

        if existing:
            return None  # Already notified

    notification = Notification(
        organization_id=org_id,
        user_id=user_id,
        type=type.value,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Best-effort realtime push for connected clients.
    unread_count = get_unread_count(db, user_id, org_id)
    _schedule_ws_send(_send_ws_updates(user_id, notification, unread_count))
    return notification


def get_notifications(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    unread_only: bool = False,
    notification_types: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Notification]:
    """Get notifications for user."""
    query = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.organization_id == org_id,
    )

    if unread_only:
        query = query.filter(Notification.read_at.is_(None))

    if notification_types:
        query = query.filter(Notification.type.in_(notification_types))

    return (
        query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    )


def get_unread_count(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> int:
    """Get count of unread notifications."""
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.organization_id == org_id,
            Notification.read_at.is_(None),
        )
        .count()
    )


def mark_read(
    db: Session,
    notification_id: UUID,
    user_id: UUID,
    org_id: UUID,
) -> Optional[Notification]:
    """Mark a notification as read (scoped by org for tenant isolation)."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.organization_id == org_id,
        )
        .first()
    )

    if notification and not notification.read_at:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        unread_count = get_unread_count(db, user_id, org_id)
        _schedule_ws_send(_send_ws_count_update(user_id, unread_count))

    return notification


def mark_all_read(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> int:
    """Mark all notifications as read. Returns count updated."""
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.organization_id == org_id,
            Notification.read_at.is_(None),
        )
        .update({"read_at": datetime.now(timezone.utc)})
    )
    db.commit()
    unread_count = get_unread_count(db, user_id, org_id)
    _schedule_ws_send(_send_ws_count_update(user_id, unread_count))
    return count


def _schedule_ws_send(coro: asyncio.Future) -> None:
    """Schedule websocket sends without blocking the request cycle."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(coro)
        return

    def _runner() -> None:
        try:
            asyncio.run(coro)
        except Exception:
            logger.exception("Failed to push websocket notification")

    threading.Thread(target=_runner, daemon=True).start()


async def _send_ws_updates(
    user_id: UUID, notification: Notification, unread_count: int
) -> None:
    """Send realtime notification + unread count to websocket clients."""
    payload = {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "entity_type": notification.entity_type,
        "entity_id": str(notification.entity_id) if notification.entity_id else None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat(),
    }

    await manager.send_to_user(
        user_id,
        {
            "type": "notification",
            "data": payload,
        },
    )
    await manager.send_to_user(
        user_id,
        {
            "type": "count_update",
            "data": {"count": unread_count},
        },
    )


async def _send_ws_count_update(user_id: UUID, unread_count: int) -> None:
    """Send unread count updates to websocket clients."""
    await manager.send_to_user(
        user_id,
        {
            "type": "count_update",
            "data": {"count": unread_count},
        },
    )


# =============================================================================
# Notification Triggers (called from case/task services)
# =============================================================================


def notify_case_assigned(
    db: Session,
    case: Case,
    assignee_id: UUID,
    actor_name: str,
) -> None:
    """Notify user when a case is assigned to them."""
    if not assignee_id:
        return

    if not should_notify(db, assignee_id, case.organization_id, "case_assigned"):
        return

    dedupe_key = f"case_assigned:{case.id}:{assignee_id}"
    create_notification(
        db=db,
        org_id=case.organization_id,
        user_id=assignee_id,
        type=NotificationType.CASE_ASSIGNED,
        title=f"Case #{case.case_number} assigned to you",
        body=f"{actor_name} assigned case {case.full_name} to you",
        entity_type="case",
        entity_id=case.id,
        dedupe_key=dedupe_key,
    )


def notify_case_status_changed(
    db: Session,
    case: Case,
    from_status: str,
    to_status: str,
    actor_id: UUID,
    actor_name: str,
) -> None:
    """Notify assignee and creator when case status changes."""
    recipients = set()

    # Add owner if owned by user
    if (
        case.owner_type == OwnerType.USER.value
        and case.owner_id
        and case.owner_id != actor_id
    ):
        recipients.add(case.owner_id)

    # Add creator (if different from assignee and actor)
    if case.created_by_user_id and case.created_by_user_id != actor_id:
        recipients.add(case.created_by_user_id)

    for user_id in recipients:
        if not should_notify(db, user_id, case.organization_id, "case_status_changed"):
            continue

        dedupe_key = f"case_status:{case.id}:{to_status}:{user_id}"
        create_notification(
            db=db,
            org_id=case.organization_id,
            user_id=user_id,
            type=NotificationType.CASE_STATUS_CHANGED,
            title=f"Case #{case.case_number} status changed",
            body=f"{actor_name} changed status from {from_status} to {to_status}",
            entity_type="case",
            entity_id=case.id,
            dedupe_key=dedupe_key,
        )


def notify_case_handoff_ready(
    db: Session,
    case: Case,
) -> None:
    """Notify all case_manager+ when a case is ready for handoff."""
    # Get all case_manager+ in org
    managers = (
        db.query(Membership)
        .filter(
            Membership.organization_id == case.organization_id,
            Membership.role.in_([Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER]),
            Membership.is_active.is_(True),
        )
        .all()
    )

    for membership in managers:
        if not should_notify(
            db, membership.user_id, case.organization_id, "case_handoff"
        ):
            continue

        dedupe_key = f"case_handoff_ready:{case.id}:{membership.user_id}"
        create_notification(
            db=db,
            org_id=case.organization_id,
            user_id=membership.user_id,
            type=NotificationType.CASE_HANDOFF_READY,
            title=f"Case #{case.case_number} ready for handoff",
            body=f"Case {case.full_name} is pending handoff approval",
            entity_type="case",
            entity_id=case.id,
            dedupe_key=dedupe_key,
        )


def notify_case_handoff_accepted(
    db: Session,
    case: Case,
    actor_name: str,
) -> None:
    """Notify case creator when handoff is accepted."""
    if not case.created_by_user_id:
        return

    if not should_notify(
        db, case.created_by_user_id, case.organization_id, "case_handoff"
    ):
        return

    dedupe_key = f"case_handoff_accepted:{case.id}:{case.created_by_user_id}"
    create_notification(
        db=db,
        org_id=case.organization_id,
        user_id=case.created_by_user_id,
        type=NotificationType.CASE_HANDOFF_ACCEPTED,
        title=f"Case #{case.case_number} handoff accepted",
        body=f"{actor_name} accepted the handoff for case {case.full_name}",
        entity_type="case",
        entity_id=case.id,
        dedupe_key=dedupe_key,
    )


def notify_case_handoff_denied(
    db: Session,
    case: Case,
    actor_name: str,
    reason: Optional[str] = None,
) -> None:
    """Notify case creator when handoff is denied."""
    if not case.created_by_user_id:
        return

    if not should_notify(
        db, case.created_by_user_id, case.organization_id, "case_handoff"
    ):
        return

    body = f"{actor_name} denied the handoff for case {case.full_name}"
    if reason:
        body += f": {reason}"

    dedupe_key = f"case_handoff_denied:{case.id}:{case.created_by_user_id}"
    create_notification(
        db=db,
        org_id=case.organization_id,
        user_id=case.created_by_user_id,
        type=NotificationType.CASE_HANDOFF_DENIED,
        title=f"Case #{case.case_number} handoff denied",
        body=body,
        entity_type="case",
        entity_id=case.id,
        dedupe_key=dedupe_key,
    )


def notify_task_assigned(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    actor_name: str,
    case_number: Optional[str] = None,
) -> None:
    """Notify user when a task is assigned to them."""
    if not assignee_id:
        return

    if not should_notify(db, assignee_id, org_id, "task_assigned"):
        return

    title = f"Task assigned: {task_title[:50]}"
    body = f"{actor_name} assigned you a task"
    if case_number:
        body += f" for case #{case_number}"

    dedupe_key = f"task_assigned:{task_id}:{assignee_id}"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=assignee_id,
        type=NotificationType.TASK_ASSIGNED,
        title=title,
        body=body,
        entity_type="task",
        entity_id=task_id,
        dedupe_key=dedupe_key,
    )


def notify_workflow_approval_requested(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    case_number: Optional[str] = None,
) -> None:
    """Notify user when a workflow approval is requested."""
    if not assignee_id:
        return

    if not should_notify(db, assignee_id, org_id, "workflow_approvals"):
        return

    title = f"Approval needed: {task_title[:50]}"
    body = "A workflow action requires your approval"
    if case_number:
        body += f" for case #{case_number}"

    dedupe_key = f"workflow_approval:{task_id}:{assignee_id}"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=assignee_id,
        type=NotificationType.WORKFLOW_APPROVAL_REQUESTED,
        title=title,
        body=body,
        entity_type="task",
        entity_id=task_id,
        dedupe_key=dedupe_key,
    )


def notify_task_due_soon(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    due_date: str,
    case_number: Optional[str] = None,
) -> None:
    """Notify user when a task is due soon (within 24h). One-time notification."""
    if not assignee_id:
        return

    # Respect user settings for task reminders
    if not should_notify(db, assignee_id, org_id, "task_reminders"):
        return

    title = f"Task due soon: {task_title[:50]}"
    body = f"Due: {due_date}"
    if case_number:
        body += f" (Case #{case_number})"

    # One-time dedupe (no time bucket - dedupe forever)
    dedupe_key = f"task:{task_id}:due_soon"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=assignee_id,
        type=NotificationType.TASK_DUE_SOON,
        title=title,
        body=body,
        entity_type="task",
        entity_id=task_id,
        dedupe_key=dedupe_key,
        dedupe_window_hours=None,
    )


def notify_task_overdue(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    due_date: str,
    case_number: Optional[str] = None,
) -> None:
    """Notify user when a task is overdue. One-time notification."""
    if not assignee_id:
        return

    # Respect user settings for task reminders
    if not should_notify(db, assignee_id, org_id, "task_reminders"):
        return

    title = f"Task overdue: {task_title[:50]}"
    body = f"Was due: {due_date}"
    if case_number:
        body += f" (Case #{case_number})"

    # One-time dedupe (no time bucket - dedupe forever)
    dedupe_key = f"task:{task_id}:overdue"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=assignee_id,
        type=NotificationType.TASK_OVERDUE,
        title=title,
        body=body,
        entity_type="task",
        entity_id=task_id,
        dedupe_key=dedupe_key,
        dedupe_window_hours=None,
    )


# =============================================================================
# Appointment Notification Triggers
# =============================================================================


def notify_appointment_requested(
    db: Session,
    org_id: UUID,
    staff_user_id: UUID,
    appointment_id: UUID,
    client_name: str,
    appointment_type: str,
    requested_time: str,
) -> None:
    """Notify staff when a new appointment is requested."""
    if not staff_user_id:
        return

    # Respect user settings for appointments
    if not should_notify(db, staff_user_id, org_id, "appointments"):
        return

    title = f"New appointment request: {appointment_type}"
    body = f"{client_name} requested {requested_time}"

    dedupe_key = f"apt:{appointment_id}:requested"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=staff_user_id,
        type=NotificationType.APPOINTMENT_REQUESTED,
        title=title,
        body=body,
        entity_type="appointment",
        entity_id=appointment_id,
        dedupe_key=dedupe_key,
    )


def notify_appointment_confirmed(
    db: Session,
    org_id: UUID,
    staff_user_id: UUID,
    appointment_id: UUID,
    client_name: str,
    appointment_type: str,
    confirmed_time: str,
) -> None:
    """Notify staff when an appointment is confirmed."""
    if not staff_user_id:
        return

    # Respect user settings for appointments
    if not should_notify(db, staff_user_id, org_id, "appointments"):
        return

    title = f"Appointment confirmed: {appointment_type}"
    body = f"{confirmed_time} with {client_name}"

    dedupe_key = f"apt:{appointment_id}:confirmed"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=staff_user_id,
        type=NotificationType.APPOINTMENT_CONFIRMED,
        title=title,
        body=body,
        entity_type="appointment",
        entity_id=appointment_id,
        dedupe_key=dedupe_key,
    )


def notify_appointment_cancelled(
    db: Session,
    org_id: UUID,
    staff_user_id: UUID,
    appointment_id: UUID,
    client_name: str,
    appointment_type: str,
    cancelled_time: str,
) -> None:
    """Notify staff when an appointment is cancelled."""
    if not staff_user_id:
        return

    # Respect user settings for appointments
    if not should_notify(db, staff_user_id, org_id, "appointments"):
        return

    title = f"Appointment cancelled: {appointment_type}"
    body = f"{cancelled_time} with {client_name} was cancelled"

    dedupe_key = f"apt:{appointment_id}:cancelled"
    create_notification(
        db=db,
        org_id=org_id,
        user_id=staff_user_id,
        type=NotificationType.APPOINTMENT_CANCELLED,
        title=title,
        body=body,
        entity_type="appointment",
        entity_id=appointment_id,
        dedupe_key=dedupe_key,
    )


# =============================================================================
# Form Notification Triggers
# =============================================================================


def notify_form_submission_received(
    db: Session,
    case: Case,
    submission_id: UUID,
) -> None:
    """Notify case owner when application form is submitted."""
    # Only notify if case is owned by a user
    if case.owner_type != OwnerType.USER.value or not case.owner_id:
        return

    # Respect user settings (using case_status_changed as proxy for now)
    if not should_notify(db, case.owner_id, case.organization_id, "case_status_changed"):
        return

    dedupe_key = f"form_submission:{submission_id}:{case.owner_id}"
    create_notification(
        db=db,
        org_id=case.organization_id,
        user_id=case.owner_id,
        type=NotificationType.FORM_SUBMISSION_RECEIVED,
        title=f"Application submitted for Case #{case.case_number}",
        body=f"{case.full_name} submitted their application",
        entity_type="case",
        entity_id=case.id,
        dedupe_key=dedupe_key,
    )


# =============================================================================
# Attachment Notification Triggers
# =============================================================================


def notify_attachment_infected(
    db: Session,
    attachment: Attachment,
) -> None:
    """Notify uploader when an attachment fails virus scan."""
    if not attachment.uploaded_by_user_id:
        return

    case_id = attachment.case_id
    title = "Attachment quarantined"
    body = f"{attachment.filename} failed the virus scan and was quarantined."
    dedupe_key = f"attachment_infected:{attachment.id}"

    create_notification(
        db=db,
        org_id=attachment.organization_id,
        user_id=attachment.uploaded_by_user_id,
        type=NotificationType.ATTACHMENT_INFECTED,
        title=title,
        body=body,
        entity_type="case" if case_id else None,
        entity_id=case_id,
        dedupe_key=dedupe_key,
        dedupe_window_hours=None,
    )
