"""Journey router - API endpoints for surrogate journey timeline."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import journey_service


router = APIRouter(
    prefix="/journey",
    tags=["journey"],
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
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
    featured_image_url: str | None = None  # Phase 2
    featured_image_id: str | None = None  # Phase 2


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
