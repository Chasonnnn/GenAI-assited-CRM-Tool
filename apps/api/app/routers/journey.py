"""Journey router - API endpoints for surrogate journey timeline."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission, require_csrf_header
from app.core.policies import POLICIES
from app.core.security import decode_export_token
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import journey_service, surrogate_service


router = APIRouter(
    prefix="/journey",
    tags=["journey"],
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)

# Export router - token-based, no session dependency
export_router = APIRouter(
    prefix="/journey",
    tags=["journey"],
)


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================


class JourneyMilestoneResponse(BaseModel):
    """Journey milestone with computed status."""

    slug: str
    label: str
    description: str
    status: str  # "completed" | "current" | "upcoming"
    completed_at: datetime | None
    is_soft: bool
    default_image_url: str  # Absolute URL to default image
    featured_image_url: str | None = None  # Signed URL to custom featured image
    featured_image_id: str | None = None  # Attachment ID if featured image is set


class JourneyPhaseResponse(BaseModel):
    """Journey phase with milestones."""

    slug: str
    label: str
    milestones: list[JourneyMilestoneResponse]


class JourneyResponse(BaseModel):
    """Complete journey response."""

    surrogate_id: str
    surrogate_name: str
    journey_version: int
    is_terminal: bool
    terminal_message: str | None
    terminal_date: str | None  # ISO date
    phases: list[JourneyPhaseResponse]
    organization_name: str
    organization_logo_url: str | None


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/surrogates/{surrogate_id}", response_model=JourneyResponse)
def get_surrogate_journey(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> JourneyResponse:
    """
    Get the journey timeline for a surrogate.

    Returns phases and milestones with computed statuses based on current stage
    and status history. All status derivation happens server-side.
    """
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(
        surrogate=surrogate,
        user_role=session.role,
        user_id=session.user_id,
        db=db,
        org_id=session.org_id,
    )

    journey = journey_service.get_journey(db, session.org_id, surrogate_id)

    if not journey:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Convert dataclass response to Pydantic model
    phases = [
        JourneyPhaseResponse(
            slug=phase.slug,
            label=phase.label,
            milestones=[
                JourneyMilestoneResponse(
                    slug=m.slug,
                    label=m.label,
                    description=m.description,
                    status=m.status,
                    completed_at=m.completed_at,
                    is_soft=m.is_soft,
                    default_image_url=m.default_image_url,
                    featured_image_url=m.featured_image_url,
                    featured_image_id=m.featured_image_id,
                )
                for m in phase.milestones
            ],
        )
        for phase in journey.phases
    ]

    return JourneyResponse(
        surrogate_id=journey.surrogate_id,
        surrogate_name=journey.surrogate_name,
        journey_version=journey.journey_version,
        is_terminal=journey.is_terminal,
        terminal_message=journey.terminal_message,
        terminal_date=journey.terminal_date,
        phases=phases,
        organization_name=journey.organization_name,
        organization_logo_url=journey.organization_logo_url,
    )


@export_router.get("/surrogates/{surrogate_id}/export-view", response_model=JourneyResponse)
def get_surrogate_journey_export_view(
    surrogate_id: UUID,
    export_token: str = Query(..., alias="export_token"),
    db: Session = Depends(get_db),
) -> JourneyResponse:
    """
    Token-authenticated journey payload for export rendering.

    This endpoint is used by the frontend print route for PDF generation.
    """
    try:
        payload = decode_export_token(export_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid export token") from exc

    if payload.get("purpose") != "journey_export":
        raise HTTPException(status_code=401, detail="Invalid export token")

    if payload.get("surrogate_id") != str(surrogate_id):
        raise HTTPException(status_code=403, detail="Export token scope mismatch")

    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=401, detail="Invalid export token")

    variant = payload.get("variant")
    if variant and variant not in journey_service.EXPORT_VARIANTS:
        raise HTTPException(status_code=401, detail="Invalid export token")

    journey = journey_service.get_journey(db, org_id, surrogate_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    journey = journey_service.apply_export_variant(journey, variant)

    phases = [
        JourneyPhaseResponse(
            slug=phase.slug,
            label=phase.label,
            milestones=[
                JourneyMilestoneResponse(
                    slug=m.slug,
                    label=m.label,
                    description=m.description,
                    status=m.status,
                    completed_at=m.completed_at,
                    is_soft=m.is_soft,
                    default_image_url=m.default_image_url,
                    featured_image_url=m.featured_image_url,
                    featured_image_id=m.featured_image_id,
                )
                for m in phase.milestones
            ],
        )
        for phase in journey.phases
    ]

    return JourneyResponse(
        surrogate_id=journey.surrogate_id,
        surrogate_name=journey.surrogate_name,
        journey_version=journey.journey_version,
        is_terminal=journey.is_terminal,
        terminal_message=journey.terminal_message,
        terminal_date=journey.terminal_date,
        phases=phases,
        organization_name=journey.organization_name,
        organization_logo_url=journey.organization_logo_url,
    )


@router.get("/surrogates/{surrogate_id}/export")
def export_surrogate_journey(
    surrogate_id: UUID,
    variant: str | None = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export the journey timeline as a standalone PDF."""
    from fastapi.responses import Response
    from app.services import pdf_export_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    variant_value = variant or "internal"
    if variant_value not in journey_service.EXPORT_VARIANTS:
        raise HTTPException(status_code=400, detail="Invalid export variant")

    try:
        pdf_bytes = pdf_export_service.export_journey_pdf(
            db=db,
            org_id=session.org_id,
            surrogate_id=surrogate_id,
            variant=variant_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"journey_{surrogate.surrogate_number or surrogate_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# FEATURED IMAGE MANAGEMENT
# ============================================================================


class JourneyFeaturedImageUpdate(BaseModel):
    """Request body for updating milestone featured image."""

    attachment_id: UUID | None  # None to clear


class JourneyFeaturedImageResponse(BaseModel):
    """Response after updating featured image."""

    success: bool
    milestone_slug: str
    attachment_id: str | None


# Valid milestone slugs for validation
VALID_MILESTONE_SLUGS = {m.slug for m in journey_service.MILESTONES}


@router.patch(
    "/surrogates/{surrogate_id}/milestones/{milestone_slug}/featured-image",
    response_model=JourneyFeaturedImageResponse,
)
def update_milestone_featured_image(
    surrogate_id: UUID,
    milestone_slug: str,
    body: JourneyFeaturedImageUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: None = Depends(require_csrf_header),
) -> JourneyFeaturedImageResponse:
    """
    Update the featured image for a journey milestone.

    Requires case_manager or higher role.
    Set attachment_id to None to clear the featured image.
    """
    # Check role - require case_manager+
    if session.role not in (Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Validate milestone_slug
    if milestone_slug not in VALID_MILESTONE_SLUGS:
        raise HTTPException(status_code=400, detail=f"Invalid milestone slug: {milestone_slug}")

    # Verify surrogate exists and belongs to org
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    try:
        attachment_id = journey_service.update_milestone_featured_image(
            db=db,
            surrogate=surrogate,
            milestone_slug=milestone_slug,
            attachment_id=body.attachment_id,
            actor_user_id=session.user_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return JourneyFeaturedImageResponse(
        success=True,
        milestone_slug=milestone_slug,
        attachment_id=str(attachment_id) if attachment_id else None,
    )
