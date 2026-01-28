"""Surrogate status change routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.surrogate import SurrogateStatusChange, SurrogateStatusChangeResponse
from app.services import surrogate_service

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
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Session = Depends(get_db),
):
    """Change surrogate stage (records history, respects access control)."""
    from datetime import date
    from app.services import pipeline_service, surrogate_status_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if surrogate.is_archived:
        raise HTTPException(status_code=400, detail="Cannot change status of archived surrogate")

    target_stage = pipeline_service.get_stage_by_id(db, data.stage_id)
    is_changing_to_delivered = target_stage and target_stage.slug == "delivered"

    try:
        result = surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=data.stage_id,
            user_id=session.user_id,
            user_role=session.role,
            reason=data.reason,
            effective_at=data.effective_at,
            emit_events=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if (
        result["status"] == "applied"
        and is_changing_to_delivered
        and result["surrogate"]
        and result["surrogate"].actual_delivery_date is None
    ):
        if data.effective_at:
            delivery_date = (
                data.effective_at.date() if hasattr(data.effective_at, "date") else date.today()
            )
        else:
            delivery_date = date.today()
        result["surrogate"].actual_delivery_date = delivery_date
        db.commit()
        db.refresh(result["surrogate"])

    surrogate_read = _surrogate_to_read(result["surrogate"], db) if result["surrogate"] else None
    return SurrogateStatusChangeResponse(
        status=result["status"],
        surrogate=surrogate_read,
        request_id=result.get("request_id"),
        message=result.get("message"),
    )
