"""AI action approval routes."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_ai_enabled,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
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
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
def approve_action(
    approval_id: uuid.UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.AI_APPROVE_ACTIONS)
    ),
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
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> dict[str, object]:
    """Reject a proposed action."""
    return ai_action_approval_service.reject_action_for_session(
        db=db, approval_id=approval_id, session=session
    )


@router.get("/actions/pending")
def get_pending_actions(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(require_permission(P.AI_USE)),
) -> dict[str, object]:
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
