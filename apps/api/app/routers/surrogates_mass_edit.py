"""Developer-only surrogate mass edit routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.surrogate_mass_edit import (
    SurrogateMassEditOptionsResponse,
    SurrogateMassEditStageApplyRequest,
    SurrogateMassEditStageApplyResponse,
    SurrogateMassEditStagePreviewRequest,
    SurrogateMassEditStagePreviewResponse,
)
from app.services import surrogate_mass_edit_service


router = APIRouter()


def _require_developer(session: UserSession) -> None:
    if session.role != Role.DEVELOPER:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{session.role.value}' not authorized for this action",
        )


@router.get(
    "/mass-edit/options",
    response_model=SurrogateMassEditOptionsResponse,
)
def get_mass_edit_options(
    db: Session = Depends(get_db),
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
):
    """Return distinct option values for mass edit filters (dev-only)."""
    _require_developer(session)
    return surrogate_mass_edit_service.get_filter_options(db=db, org_id=session.org_id)


@router.post(
    "/mass-edit/stage/preview",
    response_model=SurrogateMassEditStagePreviewResponse,
    dependencies=[Depends(require_csrf_header)],
)
def preview_mass_edit_stage(
    data: SurrogateMassEditStagePreviewRequest,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
):
    """Preview how many surrogates match the filters and return a small sample."""
    _require_developer(session)

    try:
        return surrogate_mass_edit_service.preview_stage_change(
            db=db,
            org_id=session.org_id,
            filters=data.filters,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/mass-edit/stage",
    response_model=SurrogateMassEditStageApplyResponse,
    dependencies=[Depends(require_csrf_header)],
)
def apply_mass_edit_stage(
    data: SurrogateMassEditStageApplyRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
):
    """Apply a stage change to all surrogates matching the given filters."""
    _require_developer(session)

    try:
        return surrogate_mass_edit_service.apply_stage_change(
            db=db,
            org_id=session.org_id,
            stage_id=data.stage_id,
            filters=data.filters,
            expected_total=data.expected_total,
            user_id=session.user_id,
            user_role=session.role,
            trigger_workflows=data.trigger_workflows,
            reason=data.reason,
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("Selection changed"):
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
