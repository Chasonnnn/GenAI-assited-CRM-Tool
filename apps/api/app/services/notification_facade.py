"""Notification facade for domain services.

This module provides a stable interface for event-style notification dispatch
so domain services don't depend directly on notification_service internals.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import NotificationType
from app.db.models import (
    Attachment,
    IntendedParent,
    Match,
    Notification,
    StatusChangeRequest,
    Surrogate,
)
from app.services import notification_service


# =============================================================================
# Settings / CRUD passthrough
# =============================================================================


def get_user_settings(db: Session, user_id: UUID, org_id: UUID) -> dict:
    return notification_service.get_user_settings(db, user_id, org_id)


def update_user_settings(db: Session, user_id: UUID, org_id: UUID, updates: dict) -> dict:
    return notification_service.update_user_settings(db, user_id, org_id, updates)


def should_notify(db: Session, user_id: UUID, org_id: UUID, setting_key: str) -> bool:
    return notification_service.should_notify(db, user_id, org_id, setting_key)


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
    return notification_service.create_notification(
        db=db,
        org_id=org_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
        dedupe_key=dedupe_key,
        dedupe_window_hours=dedupe_window_hours,
    )


# =============================================================================
# Domain event notifications (passthrough)
# =============================================================================


def notify_surrogate_assigned(
    db: Session,
    surrogate: Surrogate,
    assignee_id: UUID,
    actor_name: str,
) -> None:
    notification_service.notify_surrogate_assigned(db, surrogate, assignee_id, actor_name)


def notify_surrogate_status_changed(
    db: Session,
    surrogate: Surrogate,
    from_status: str,
    to_status: str,
    actor_id: UUID,
    actor_name: str,
) -> None:
    notification_service.notify_surrogate_status_changed(
        db, surrogate, from_status, to_status, actor_id, actor_name
    )


def notify_surrogate_ready_for_claim(db: Session, surrogate: Surrogate) -> None:
    notification_service.notify_surrogate_ready_for_claim(db, surrogate)


def notify_status_change_request_pending(
    db: Session,
    request: StatusChangeRequest,
    surrogate: Surrogate,
    target_stage_label: str,
    current_stage_label: str,
    requester_name: str,
) -> None:
    notification_service.notify_status_change_request_pending(
        db, request, surrogate, target_stage_label, current_stage_label, requester_name
    )


def notify_ip_status_change_request_pending(
    db: Session,
    request: StatusChangeRequest,
    intended_parent: IntendedParent,
    target_status_label: str,
    current_status_label: str,
    requester_name: str,
) -> None:
    notification_service.notify_ip_status_change_request_pending(
        db,
        request,
        intended_parent,
        target_status_label,
        current_status_label,
        requester_name,
    )


def notify_match_cancel_request_pending(
    db: Session,
    request: StatusChangeRequest,
    match: Match,
    surrogate: Surrogate,
    intended_parent: IntendedParent,
    requester_name: str,
) -> None:
    notification_service.notify_match_cancel_request_pending(
        db, request, match, surrogate, intended_parent, requester_name
    )


def notify_status_change_request_resolved(
    db: Session,
    request: StatusChangeRequest,
    surrogate: Surrogate,
    approved: bool,
    resolver_name: str,
    reason: str | None = None,
) -> None:
    notification_service.notify_status_change_request_resolved(
        db, request, surrogate, approved, resolver_name, reason
    )


def notify_ip_status_change_request_resolved(
    db: Session,
    request: StatusChangeRequest,
    intended_parent: IntendedParent,
    approved: bool,
    resolver_name: str,
    reason: str | None = None,
) -> None:
    notification_service.notify_ip_status_change_request_resolved(
        db, request, intended_parent, approved, resolver_name, reason
    )


def notify_match_cancel_request_resolved(
    db: Session,
    request: StatusChangeRequest,
    match: Match,
    approved: bool,
    resolver_name: str,
    reason: str | None = None,
) -> None:
    notification_service.notify_match_cancel_request_resolved(
        db, request, match, approved, resolver_name, reason
    )


def notify_task_assigned(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    actor_name: str,
    surrogate_number: Optional[str] = None,
) -> None:
    notification_service.notify_task_assigned(
        db, task_id, task_title, org_id, assignee_id, actor_name, surrogate_number
    )


def notify_workflow_approval_requested(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    surrogate_number: Optional[str] = None,
) -> None:
    notification_service.notify_workflow_approval_requested(
        db, task_id, task_title, org_id, assignee_id, surrogate_number
    )


def notify_task_due_soon(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    due_date: str,
    surrogate_number: Optional[str] = None,
) -> None:
    notification_service.notify_task_due_soon(
        db, task_id, task_title, org_id, assignee_id, due_date, surrogate_number
    )


def notify_task_overdue(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    due_date: str,
    surrogate_number: Optional[str] = None,
) -> None:
    notification_service.notify_task_overdue(
        db, task_id, task_title, org_id, assignee_id, due_date, surrogate_number
    )


def notify_appointment_requested(
    db: Session,
    org_id: UUID,
    staff_user_id: UUID,
    appointment_id: UUID,
    client_name: str,
    appointment_type: str,
    requested_time: str,
) -> None:
    notification_service.notify_appointment_requested(
        db,
        org_id,
        staff_user_id,
        appointment_id,
        client_name,
        appointment_type,
        requested_time,
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
    notification_service.notify_appointment_confirmed(
        db,
        org_id,
        staff_user_id,
        appointment_id,
        client_name,
        appointment_type,
        confirmed_time,
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
    notification_service.notify_appointment_cancelled(
        db,
        org_id,
        staff_user_id,
        appointment_id,
        client_name,
        appointment_type,
        cancelled_time,
    )


def notify_form_submission_received(
    db: Session,
    surrogate: Surrogate,
    submission_id: UUID,
) -> None:
    notification_service.notify_form_submission_received(db, surrogate, submission_id)


def notify_attachment_infected(db: Session, attachment: Attachment) -> None:
    notification_service.notify_attachment_infected(db, attachment)
