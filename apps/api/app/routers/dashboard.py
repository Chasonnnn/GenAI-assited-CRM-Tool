"""Dashboard router - API endpoints for dashboard widgets."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.schemas.auth import UserSession
from app.db.enums import Role
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
    surrogate_id: str | None
    surrogate_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool
    task_type: str


class UpcomingMeeting(BaseModel):
    """Meeting item for upcoming widget."""

    id: str
    type: str = "meeting"
    title: str
    time: str | None  # HH:MM format
    surrogate_id: str | None
    surrogate_number: str | None
    date: str  # YYYY-MM-DD
    is_overdue: bool = False
    join_url: str


class UpcomingResponse(BaseModel):
    """Response for upcoming widget."""

    tasks: list[UpcomingTask]
    meetings: list[UpcomingMeeting]


# -----------------------------------------------------------------------------
# Attention Schemas
# -----------------------------------------------------------------------------


class UnreachedLead(BaseModel):
    """Unreached lead for attention panel."""

    id: str
    surrogate_number: str
    stage_label: str
    days_since_contact: int
    created_at: str


class OverdueTask(BaseModel):
    """Overdue task for attention panel."""

    id: str
    title: str
    due_date: str | None
    days_overdue: int
    surrogate_id: str | None


class StuckSurrogate(BaseModel):
    """Stuck surrogate for attention panel."""

    id: str
    surrogate_number: str
    stage_label: str
    days_in_stage: int
    last_stage_change: str | None


class AttentionResponse(BaseModel):
    """Response for attention items endpoint."""

    unreached_leads: list[UnreachedLead]
    unreached_count: int
    overdue_tasks: list[OverdueTask]
    overdue_count: int
    stuck_surrogates: list[StuckSurrogate]
    stuck_count: int
    total_count: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/upcoming", response_model=UpcomingResponse)
def get_upcoming(
    request: Request,
    days: int = Query(7, ge=1, le=14, description="Number of days to look ahead"),
    include_overdue: bool = Query(True, description="Include overdue tasks"),
    assignee_id: UUID | None = Query(None, description="Filter upcoming items by assignee"),
    pipeline_id: UUID | None = Query(None, description="Filter by pipeline UUID"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> UpcomingResponse:
    """
    Get user's upcoming tasks and meetings for dashboard.

    Returns tasks where user is assignee/owner and meetings user created.
    Scoped to cases the user has access to.
    """
    if (
        assignee_id
        and assignee_id != session.user_id
        and session.role not in (Role.ADMIN, Role.DEVELOPER)
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to view other users' upcoming items"
        )

    target_user_id = assignee_id or session.user_id

    tasks, meetings = dashboard_service.get_upcoming_items(
        db=db,
        org_id=session.org_id,
        user_id=target_user_id,
        days=days,
        include_overdue=include_overdue,
        pipeline_id=pipeline_id,
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


@router.get("/attention", response_model=AttentionResponse)
def get_attention(
    request: Request,
    days_unreached: int = Query(
        7, ge=1, le=30, description="Days without contact for unreached leads"
    ),
    days_stuck: int = Query(14, ge=1, le=60, description="Days in same stage for stuck surrogates"),
    pipeline_id: UUID | None = Query(None, description="Filter by pipeline UUID"),
    assignee_id: UUID | None = Query(None, description="Filter by assignee UUID"),
    limit: int = Query(5, ge=1, le=20, description="Max items per category"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> AttentionResponse:
    """
    Get items needing attention for dashboard KPI.

    Returns:
    - unreached_leads: Surrogates in early intake stages with no contact in X days
    - overdue_tasks: User's tasks past due date
    - stuck_surrogates: Surrogates that haven't moved stages in X days
    - total_count: Sum of all attention items
    """
    if (
        assignee_id
        and assignee_id != session.user_id
        and session.role not in (Role.ADMIN, Role.DEVELOPER)
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to view other users' attention items"
        )

    data = dashboard_service.get_attention_items(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        user_role=session.role,
        days_unreached=days_unreached,
        days_stuck=days_stuck,
        pipeline_id=pipeline_id,
        assignee_id=assignee_id,
        limit=limit,
    )

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="dashboard_attention",
        target_id=None,
        request=request,
        details={
            "days_unreached": days_unreached,
            "days_stuck": days_stuck,
            "total_count": data["total_count"],
        },
    )
    db.commit()

    return AttentionResponse(
        unreached_leads=[UnreachedLead(**item) for item in data["unreached_leads"]],
        unreached_count=data["unreached_count"],
        overdue_tasks=[OverdueTask(**item) for item in data["overdue_tasks"]],
        overdue_count=data["overdue_count"],
        stuck_surrogates=[StuckSurrogate(**item) for item in data["stuck_surrogates"]],
        stuck_count=data["stuck_count"],
        total_count=data["total_count"],
    )
