"""Surrogate status change routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.surrogate import SurrogateStatusChange, SurrogateStatusChangeResponse
from app.services import surrogate_service
from app.services.calendar_binding_service import CalendarAvailabilityUnavailable

from .surrogates_shared import _surrogate_to_read

router = APIRouter()


@router.patch(
    "/{surrogate_id:uuid}/status",
    response_model=SurrogateStatusChangeResponse,
    dependencies=[Depends(require_csrf_header)],
)
def change_status(
    surrogate_id: UUID,
    data: SurrogateStatusChange,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    """Change surrogate stage (records history, respects access control)."""
    from app.services import surrogate_status_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if surrogate.is_archived:
        raise HTTPException(status_code=400, detail="Cannot change status of archived surrogate")

    try:
        result = surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=data.stage_id,
            user_id=session.user_id,
            user_role=session.role,
            reason=data.reason,
            effective_at=data.effective_at,
            interview_scheduled_at=data.interview_scheduled_at,
            override_availability=data.override_availability,
            override_reason=data.override_reason,
            on_hold_follow_up_months=data.on_hold_follow_up_months,
            delivery_baby_gender=data.delivery_baby_gender,
            delivery_baby_weight=data.delivery_baby_weight,
            emit_events=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=503 if isinstance(e, CalendarAvailabilityUnavailable) else 403,
            detail=str(e),
        ) from e

    surrogate_read = _surrogate_to_read(result["surrogate"], db) if result["surrogate"] else None
    return SurrogateStatusChangeResponse(
        status=result["status"],
        surrogate=surrogate_read,
        request_id=result.get("request_id"),
        message=result.get("message"),
    )
