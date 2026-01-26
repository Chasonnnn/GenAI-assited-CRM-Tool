"""Notification dispatch facade.

Provides a stable boundary for domain services to trigger notifications
without depending on the underlying notification implementation.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import NotificationType
from app.db.models import IntendedParent, Match, StatusChangeRequest, Surrogate, Task
from app.services import notification_service


def notify_surrogate_assigned(
    db: Session,
    surrogate: Surrogate,
    assignee_id: UUID,
    actor_name: str,
) -> None:
    notification_service.notify_surrogate_assigned(
        db=db,
        surrogate=surrogate,
        assignee_id=assignee_id,
        actor_name=actor_name,
    )


def notify_surrogate_status_changed(
    db: Session,
    surrogate: Surrogate,
    from_status: str,
    to_status: str,
    actor_id: UUID,
    actor_name: str,
) -> None:
    notification_service.notify_surrogate_status_changed(
        db=db,
        surrogate=surrogate,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_name=actor_name,
    )


def notify_surrogate_ready_for_claim(
    db: Session,
    surrogate: Surrogate,
) -> None:
    notification_service.notify_surrogate_ready_for_claim(
        db=db,
        surrogate=surrogate,
    )


def notify_status_change_request_pending(
    db: Session,
    request: StatusChangeRequest,
    surrogate: Surrogate,
    target_stage_label: str,
    current_stage_label: str,
    requester_name: str,
) -> None:
    notification_service.notify_status_change_request_pending(
        db=db,
        request=request,
        surrogate=surrogate,
        target_stage_label=target_stage_label,
        current_stage_label=current_stage_label,
        requester_name=requester_name,
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
        db=db,
        request=request,
        surrogate=surrogate,
        approved=approved,
        resolver_name=resolver_name,
        reason=reason,
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
        db=db,
        request=request,
        intended_parent=intended_parent,
        approved=approved,
        resolver_name=resolver_name,
        reason=reason,
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
        db=db,
        request=request,
        match=match,
        approved=approved,
        resolver_name=resolver_name,
        reason=reason,
    )


def notify_task_assigned(
    db: Session,
    task_id: UUID,
    task_title: str,
    org_id: UUID,
    assignee_id: UUID,
    actor_name: str,
    surrogate_number: str | None = None,
) -> None:
    notification_service.notify_task_assigned(
        db=db,
        task_id=task_id,
        task_title=task_title,
        org_id=org_id,
        assignee_id=assignee_id,
        actor_name=actor_name,
        surrogate_number=surrogate_number,
    )


def notify_workflow_approval_expired(
    db: Session,
    task: Task,
) -> None:
    notification_service.create_notification(
        db=db,
        org_id=task.organization_id,
        user_id=task.owner_id,
        type=NotificationType.TASK_OVERDUE,
        title="Workflow Approval Expired",
        body=f"Approval task timed out: {task.title}",
        entity_type="task",
        entity_id=task.id,
    )
