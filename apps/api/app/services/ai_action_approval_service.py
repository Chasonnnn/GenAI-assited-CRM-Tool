"""Service orchestration for approving AI actions."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.surrogate_access import check_surrogate_access
from app.db.enums import Role, SurrogateActivityType
from app.schemas.auth import UserSession


class ActionApprovalResult(TypedDict):
    success: bool
    action_type: str
    status: str
    result: dict[str, Any] | None
    error: str | None


def _log_surrogate_activity(
    db: Session,
    *,
    org_id,
    user_id,
    approval_id: uuid.UUID,
    action_type: str,
    surrogate_id,
    result: dict[str, Any],
) -> None:
    from app.services import activity_service, pipeline_service

    details_base = {
        "source": "ai",
        "approval_id": str(approval_id),
        "action_type": action_type,
    }

    if action_type == "add_note":
        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.NOTE_ADDED,
            actor_user_id=user_id,
            details={
                **details_base,
                "note_id": result.get("note_id"),
            },
        )
        return

    if action_type == "send_email":
        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.EMAIL_SENT,
            actor_user_id=user_id,
            details={
                **details_base,
                "provider": "gmail",
            },
        )
        return

    if action_type == "update_status":
        old_stage_id = result.get("old_stage_id")
        new_stage_id = result.get("new_stage_id")
        old_label = None
        new_label = None
        if old_stage_id:
            old_stage = pipeline_service.get_stage_by_id(db, uuid.UUID(old_stage_id))
            old_label = old_stage.label if old_stage else None
        if new_stage_id:
            new_stage = pipeline_service.get_stage_by_id(db, uuid.UUID(new_stage_id))
            new_label = new_stage.label if new_stage else None

        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.STATUS_CHANGED,
            actor_user_id=user_id,
            details={
                **details_base,
                "from": old_label,
                "to": new_label,
            },
        )
        return

    if action_type == "create_task":
        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.TASK_CREATED,
            actor_user_id=user_id,
            details={
                **details_base,
                "task_id": result.get("task_id"),
                "title": result.get("title"),
            },
        )


def approve_action_for_session(
    db: Session,
    *,
    approval_id: uuid.UUID,
    session: UserSession,
) -> ActionApprovalResult:
    """Approve and execute an AI action proposal for the current session."""
    from app.services import ai_service, audit_service, permission_service, surrogate_service
    from app.services.ai_action_executor import execute_action

    approval, message, conversation = ai_service.get_approval_with_conversation(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
    if conversation.user_id != session.user_id and not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to approve this action")

    if conversation.entity_type in ("surrogate", "case"):
        surrogate = surrogate_service.get_surrogate(db, session.org_id, conversation.entity_id)
        if not surrogate:
            raise HTTPException(status_code=404, detail="Surrogate not found")
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )

    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already processed (status: {approval.status})",
        )

    user_permissions = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )
    result = execute_action(
        db=db,
        approval=approval,
        user_id=session.user_id,
        org_id=session.org_id,
        entity_id=conversation.entity_id,
        user_permissions=user_permissions,
    )

    if result.get("success") and conversation.entity_type == "surrogate":
        _log_surrogate_activity(
            db,
            org_id=session.org_id,
            user_id=session.user_id,
            approval_id=approval.id,
            action_type=approval.action_type,
            surrogate_id=conversation.entity_id,
            result=result,
        )

    if result.get("success"):
        audit_service.log_ai_action_approved(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            approval_id=approval.id,
            action_type=approval.action_type,
        )
    else:
        error_code = result.get("error_code")
        if error_code == "permission_denied":
            audit_service.log_ai_action_denied(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                approval_id=approval.id,
                action_type=approval.action_type,
                reason=result.get("error"),
            )
        else:
            audit_service.log_ai_action_failed(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                approval_id=approval.id,
                action_type=approval.action_type,
                error=result.get("error"),
            )

    db.commit()
    return ActionApprovalResult(
        success=result.get("success", False),
        action_type=approval.action_type,
        status=approval.status,
        result=result if result.get("success") else None,
        error=result.get("error") if not result.get("success") else None,
    )
