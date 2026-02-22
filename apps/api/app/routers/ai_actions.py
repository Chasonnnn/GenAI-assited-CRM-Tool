"""AI action approval routes."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import ai_action_approval_service

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
    result = ai_action_approval_service.approve_action_for_session(
        db=db,
        approval_id=approval_id,
        session=session,
    )
    return ActionApprovalResponse(**result)


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
