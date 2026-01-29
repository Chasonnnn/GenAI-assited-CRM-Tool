"""AI action approval routes."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import Role, SurrogateActivityType
from app.schemas.auth import UserSession

router = APIRouter()


class ActionApprovalResponse(BaseModel):
    """Response for action approval."""

    success: bool
    action_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


@router.post(
    "/actions/{approval_id}/approve",
    response_model=ActionApprovalResponse,
    dependencies=[Depends(require_csrf_header)],
)
def approve_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_APPROVE_ACTIONS)),
) -> ActionApprovalResponse:
    """Approve and execute a proposed action.

    Requires: approve_ai_actions permission (plus action-specific permissions)
    """
    from app.services import ai_service, surrogate_service
    from app.services.ai_action_executor import execute_action

    # Get the approval with related data
    approval, message, conversation = ai_service.get_approval_with_conversation(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")

    # Get conversation to verify org access
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify user owns this conversation or has admin role
    is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
    if conversation.user_id != session.user_id and not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to approve this action")

    # Re-check surrogate access before executing actions
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

    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already processed (status: {approval.status})",
        )

    # Get user's permissions for action-specific checks
    from app.services import permission_service

    user_permissions = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )

    # Execute the action with permission checks
    result = execute_action(
        db=db,
        approval=approval,
        user_id=session.user_id,
        org_id=session.org_id,
        entity_id=conversation.entity_id,
        user_permissions=user_permissions,
    )

    # Surrogate activity log for AI-generated actions (surrogate context only)
    if result.get("success") and conversation.entity_type == "surrogate":
        from app.services import activity_service, pipeline_service

        surrogate_id = conversation.entity_id
        details_base = {
            "source": "ai",
            "approval_id": str(approval.id),
            "action_type": approval.action_type,
        }

        if approval.action_type == "add_note":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.NOTE_ADDED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "note_id": result.get("note_id"),
                },
            )
        elif approval.action_type == "send_email":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.EMAIL_SENT,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "provider": "gmail",
                },
            )
        elif approval.action_type == "update_status":
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
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.STATUS_CHANGED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "from": old_label,
                    "to": new_label,
                },
            )
        elif approval.action_type == "create_task":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.TASK_CREATED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "task_id": result.get("task_id"),
                    "title": result.get("title"),
                },
            )

    # Audit log - only log approved if actually successful
    from app.services import audit_service

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

    return ActionApprovalResponse(
        success=result.get("success", False),
        action_type=approval.action_type,
        status=approval.status,
        result=result if result.get("success") else None,
        error=result.get("error") if not result.get("success") else None,
    )


@router.post("/actions/{approval_id}/reject", dependencies=[Depends(require_csrf_header)])
def reject_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Reject a proposed action."""
    from app.services import ai_service, audit_service

    # Get the approval with related data
    approval, message, conversation = ai_service.get_approval_with_conversation(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")

    # Get conversation to verify org access
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify user owns this conversation or has admin role
    is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
    if conversation.user_id != session.user_id and not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to reject this action")

    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already processed (status: {approval.status})",
        )

    # Mark as rejected
    approval.status = "rejected"
    approval.executed_at = datetime.now(timezone.utc)

    # Audit log
    audit_service.log_ai_action_rejected(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        approval_id=approval.id,
        action_type=approval.action_type,
    )

    db.commit()

    return {
        "success": True,
        "action_type": approval.action_type,
        "status": "rejected",
    }


@router.get("/actions/pending")
def get_pending_actions(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> dict[str, Any]:
    """Get all pending actions for the current user."""
    from app.services import ai_service

    approvals = ai_service.list_pending_actions(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return {
        "pending_actions": [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "action_payload": a.action_payload,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ]
    }
