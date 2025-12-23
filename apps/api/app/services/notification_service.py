"""
Notification Service - handles in-app notifications.

Provides CRUD for notifications and trigger functions for case/task events.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import NotificationType, Role, OwnerType
from app.db.models import (
    Notification,
    UserNotificationSettings,
    Case,
    Membership,
    User,
)


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
    settings = db.query(UserNotificationSettings).filter(
        UserNotificationSettings.user_id == user_id,
        UserNotificationSettings.organization_id == org_id,
    ).first()
    
    if settings:
        return {
            "case_assigned": settings.case_assigned,
            "case_status_changed": settings.case_status_changed,
            "case_handoff": settings.case_handoff,
            "task_assigned": settings.task_assigned,
        }
    
    # Defaults (all ON)
    return {
        "case_assigned": True,
        "case_status_changed": True,
        "case_handoff": True,
        "task_assigned": True,
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
    settings = db.query(UserNotificationSettings).filter(
        UserNotificationSettings.user_id == user_id,
        UserNotificationSettings.organization_id == org_id,
    ).first()
    
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
) -> Optional[Notification]:
    """
    Create a notification.
    
    Dedupes by dedupe_key + org_id + user_id within 1 hour window.
    """
    # Check dedupe (scoped by org and user for safety)
    if dedupe_key:
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        existing = db.query(Notification).filter(
            Notification.dedupe_key == dedupe_key,
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
            Notification.created_at > one_hour_ago,
        ).first()
        
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
    
    return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()


def get_unread_count(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> int:
    """Get count of unread notifications."""
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.organization_id == org_id,
        Notification.read_at.is_(None),
    ).count()


def mark_read(
    db: Session,
    notification_id: UUID,
    user_id: UUID,
    org_id: UUID,
) -> Optional[Notification]:
    """Mark a notification as read (scoped by org for tenant isolation)."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
        Notification.organization_id == org_id,
    ).first()
    
    if notification and not notification.read_at:
        notification.read_at = datetime.utcnow()
        db.commit()
        db.refresh(notification)
    
    return notification


def mark_all_read(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> int:
    """Mark all notifications as read. Returns count updated."""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.organization_id == org_id,
        Notification.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()
    return count


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
    if case.owner_type == OwnerType.USER.value and case.owner_id and case.owner_id != actor_id:
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
    managers = db.query(Membership).filter(
        Membership.organization_id == case.organization_id,
        Membership.role.in_([Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER]),
    ).all()
    
    for membership in managers:
        if not should_notify(db, membership.user_id, case.organization_id, "case_handoff"):
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
    
    if not should_notify(db, case.created_by_user_id, case.organization_id, "case_handoff"):
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
    
    if not should_notify(db, case.created_by_user_id, case.organization_id, "case_handoff"):
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
