"""Profile card API endpoints for case manager+ users."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access
from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
)
from app.db.enums import Role
from app.db.models import Case, FormSubmission
from app.schemas.auth import UserSession
from app.services import profile_service

router = APIRouter(prefix="/cases", tags=["profile"])


# Case manager+ role check
CASE_MANAGER_ROLES = {Role.CASE_MANAGER.value, Role.ADMIN.value, Role.DEVELOPER.value}


def _require_case_manager(session: UserSession) -> None:
    """Check if user has case_manager+ role."""
    if session.role not in CASE_MANAGER_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Profile card requires case_manager+ role"
        )


# =============================================================================
# Schemas
# =============================================================================


class ProfileDataResponse(BaseModel):
    """Response for profile data."""
    base_submission_id: UUID | None
    base_answers: dict[str, Any]
    overrides: dict[str, Any]
    hidden_fields: list[str]
    merged_view: dict[str, Any]
    schema_snapshot: dict | None


class SyncDiffItem(BaseModel):
    """Single field diff from sync."""
    field_key: str
    old_value: Any
    new_value: Any


class SyncDiffResponse(BaseModel):
    """Response for sync diff."""
    staged_changes: list[SyncDiffItem]
    latest_submission_id: UUID | None


class ProfileOverridesUpdate(BaseModel):
    """Update request for profile overrides."""
    overrides: dict[str, Any]
    new_base_submission_id: UUID | None = None


class ProfileHiddenUpdate(BaseModel):
    """Toggle hidden state for a field."""
    field_key: str = Field(..., min_length=1, max_length=255)
    hidden: bool


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/{case_id}/profile",
    response_model=ProfileDataResponse,
)
def get_profile(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get profile data for a case (case_manager+ only)."""
    _require_case_manager(session)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    data = profile_service.get_profile_data(db, session.org_id, case_id)
    return ProfileDataResponse(**data)


@router.post(
    "/{case_id}/profile/sync",
    response_model=SyncDiffResponse,
    dependencies=[Depends(require_csrf_header)],
)
def sync_profile(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get staged diff from latest submission (requires Save to persist)."""
    _require_case_manager(session)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    staged_changes = profile_service.get_sync_diff(db, session.org_id, case_id)

    # Get latest submission ID
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.case_id == case_id,
            FormSubmission.organization_id == session.org_id,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )

    return SyncDiffResponse(
        staged_changes=[SyncDiffItem(**c) for c in staged_changes],
        latest_submission_id=submission.id if submission else None,
    )


@router.put(
    "/{case_id}/profile/overrides",
    dependencies=[Depends(require_csrf_header)],
)
def save_profile_overrides(
    case_id: UUID,
    body: ProfileOverridesUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Save profile overrides (and optionally update base submission ID after sync)."""
    _require_case_manager(session)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        profile_service.save_profile_overrides(
            db=db,
            org_id=session.org_id,
            case_id=case_id,
            user_id=session.user_id,
            overrides=body.overrides,
            new_base_submission_id=body.new_base_submission_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved"}


@router.post(
    "/{case_id}/profile/hidden",
    dependencies=[Depends(require_csrf_header)],
)
def toggle_hidden_field(
    case_id: UUID,
    body: ProfileHiddenUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Toggle hidden state for a profile field."""
    _require_case_manager(session)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    profile_service.set_field_hidden(
        db=db,
        org_id=session.org_id,
        case_id=case_id,
        user_id=session.user_id,
        field_key=body.field_key,
        hidden=body.hidden,
    )
    return {"status": "updated", "field_key": body.field_key, "hidden": body.hidden}


@router.get(
    "/{case_id}/profile/export",
)
def export_profile_pdf(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export profile as PDF with hidden fields masked."""
    from fastapi.responses import Response
    from app.db.models import Organization
    from app.services import pdf_export_service

    _require_case_manager(session)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    # Get org name for header
    org = db.query(Organization).filter(Organization.id == session.org_id).first()
    org_name = org.name if org else ""

    # Case display name
    case_name = case.full_name or f"Case #{case.case_number or case.id}"

    try:
        pdf_bytes = pdf_export_service.export_profile_pdf(
            db=db,
            org_id=session.org_id,
            case_id=case_id,
            case_name=case_name,
            org_name=org_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"profile_{case.case_number or case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
