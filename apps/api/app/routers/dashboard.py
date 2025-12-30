"""Dashboard router - API endpoints for dashboard widgets."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.schemas.auth import UserSession
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# =============================================================================
# Schemas
# =============================================================================


class UpcomingTask(BaseModel):
    """Task item for upcoming widget."""

    id: str
    type: str = "task"
    title: str
    time: str | None  # HH:MM format or None for all-day
    case_id: str | None
    case_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool
    task_type: str


class UpcomingMeeting(BaseModel):
    """Meeting item for upcoming widget."""

    id: str
    type: str = "meeting"
    title: str
    time: str | None  # HH:MM format
    case_id: str | None
    case_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool = False
    join_url: str


class UpcomingResponse(BaseModel):
    """Response for upcoming widget."""

    tasks: list[UpcomingTask]
    meetings: list[UpcomingMeeting]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/upcoming", response_model=UpcomingResponse)
def get_upcoming(
    request: Request,
    days: int = Query(7, ge=1, le=14, description="Number of days to look ahead"),
    include_overdue: bool = Query(True, description="Include overdue tasks"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> UpcomingResponse:
    """
    Get user's upcoming tasks and meetings for dashboard.

    Returns tasks where user is assignee/owner and meetings user created.
    Scoped to cases the user has access to.
    """
    tasks, meetings = dashboard_service.get_upcoming_items(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        days=days,
        include_overdue=include_overdue,
    )

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="dashboard_upcoming",
        target_id=None,
        request=request,
        details={
            "days": days,
            "include_overdue": include_overdue,
            "tasks_count": len(tasks),
            "meetings_count": len(meetings),
        },
    )
    db.commit()

    return UpcomingResponse(
        tasks=[UpcomingTask(**item) for item in tasks],
        meetings=[UpcomingMeeting(**item) for item in meetings],
    )
