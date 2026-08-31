"""Dashboard router - API endpoints for dashboard widgets."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_all_permissions
from app.core.permissions import PermissionKey
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import dashboard_service, task_service

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
    donor_id: str | None = None
    donor_number: str | None = None
    donor_type: str | None = None
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
    donor_id: str | None = None
    donor_number: str | None = None
    donor_type: str | None = None


class StuckSurrogate(BaseModel):
    """Stuck surrogate for attention panel."""

    id: str
    surrogate_number: str
    stage_label: str
    days_in_stage: int
    last_stage_change: str | None


class StuckDonor(BaseModel):
    """Stuck donor for attention panel."""

    id: str
    donor_number: str
    donor_type: Literal["egg", "sperm"]
    stage_label: str
    days_in_stage: int
    last_stage_change: str | None


class StuckDonorCounts(BaseModel):
    egg: int = 0
    sperm: int = 0


class AttentionResponse(BaseModel):
    """Response for attention items endpoint."""

    unreached_leads: list[UnreachedLead]
    unreached_count: int
    overdue_tasks: list[OverdueTask]
    overdue_count: int
    stuck_surrogates: list[StuckSurrogate]
    stuck_count: int
    stuck_donors: list[StuckDonor]
    stuck_donor_count: int
    stuck_donor_counts: StuckDonorCounts = Field(default_factory=StuckDonorCounts)
    total_count: int


class DonorStatusCount(BaseModel):
    status: str
    stage_id: str
    count: int
    order: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/donors/by-status",
    response_model=list[DonorStatusCount],
    dependencies=[
        Depends(
            require_all_permissions(
                [PermissionKey.VIEW_DASHBOARD, PermissionKey.DONORS_VIEW]
            )
        )
    ],
)
def get_dashboard_donors_by_status(
    donor_type: Annotated[Literal["egg", "sperm"], Query()],
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
    pipeline_id: Annotated[UUID | None, Query()] = None,
    owner_id: Annotated[UUID | None, Query()] = None,
    state: Annotated[str | None, Query(max_length=100)] = None,
    include_archived: Annotated[bool, Query()] = False,
) -> list[DonorStatusCount]:
    """Get subtype pipeline distribution for the dashboard card."""
    from app.services import analytics_donor_service, analytics_service

    if (
        owner_id
        and owner_id != session.user_id
        and session.role not in (Role.ADMIN, Role.DEVELOPER, Role.CASE_MANAGER)
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view other users' analytics")

    start = end = None
    if from_date or to_date:
        start, end = analytics_service.parse_date_range(
            from_date,
            to_date,
            inclusive_date_end=True,
        )
    try:
        data = analytics_donor_service.get_cached_donors_by_status(
            db,
            session.org_id,
            donor_type,
            start=start,
            end=end,
            pipeline_id=pipeline_id,
            owner_id=owner_id,
            state=state,
            include_archived=include_archived,
        )
    except analytics_donor_service.DonorAnalyticsPipelineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pipeline not found") from exc
    return [DonorStatusCount(**item) for item in data]


@router.get(
    "/upcoming",
    response_model=UpcomingResponse,
    dependencies=[Depends(require_all_permissions([PermissionKey.VIEW_DASHBOARD]))],
)
def get_upcoming(
    request: Request,
    days: Annotated[int, "fastapi_param"] = Query(
        7, ge=1, le=14, description="Number of days to look ahead"
    ),
    include_overdue: Annotated[bool, "fastapi_param"] = Query(
        True, description="Include overdue tasks"
    ),
    assignee_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter upcoming items by assignee"
    ),
    pipeline_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by pipeline UUID"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
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
    can_view_donors = task_service.user_can_view_donors(
        db,
        session.org_id,
        session.user_id,
        session.role,
    )

    tasks, meetings = dashboard_service.get_upcoming_items(
        db=db,
        org_id=session.org_id,
        user_id=target_user_id,
        days=days,
        include_overdue=include_overdue,
        pipeline_id=pipeline_id,
        can_view_donors=can_view_donors,
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


@router.get(
    "/attention",
    response_model=AttentionResponse,
    dependencies=[Depends(require_all_permissions([PermissionKey.VIEW_DASHBOARD]))],
)
def get_attention(
    request: Request,
    days_unreached: Annotated[int, "fastapi_param"] = Query(
        7, ge=1, le=30, description="Days without contact or updates for unreached leads"
    ),
    days_stuck: Annotated[int, "fastapi_param"] = Query(
        dashboard_service.ATTENTION_STUCK_DAYS,
        ge=1,
        le=dashboard_service.ATTENTION_STUCK_DAYS,
        description="Days in same stage for stuck surrogates",
    ),
    pipeline_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by pipeline UUID"
    ),
    assignee_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by assignee UUID"
    ),
    limit: Annotated[int, "fastapi_param"] = Query(
        5, ge=1, le=20, description="Max items per category"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> AttentionResponse:
    """
    Get items needing attention for dashboard KPI.

    Returns:
    - unreached_leads: Surrogates in early intake stages with no contact or updates in X days
    - overdue_tasks: User's tasks past due date
    - stuck_surrogates: Surrogates that haven't moved stages in X days
    - stuck_donors: Donors that haven't moved stages in X days
    - total_count: Sum of all attention items
    """
    if assignee_id and assignee_id != session.user_id:
        if session.role not in (Role.ADMIN, Role.DEVELOPER, Role.CASE_MANAGER):
            raise HTTPException(
                status_code=403, detail="Not authorized to view other users' attention items"
            )

    can_view_donors = task_service.user_can_view_donors(
        db,
        session.org_id,
        session.user_id,
        session.role,
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
        can_view_donors=can_view_donors,
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
        stuck_donors=[StuckDonor(**item) for item in data["stuck_donors"]],
        stuck_donor_count=data["stuck_donor_count"],
        stuck_donor_counts=data.get(
            "stuck_donor_counts", {"egg": 0, "sperm": 0}
        ),
        total_count=data["total_count"],
    )
