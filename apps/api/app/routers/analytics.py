"""
Analytics endpoints for manager dashboards.

Provides case statistics, trends, and Meta performance metrics.
"""
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES

from app.db.models import Case
from app.services import pipeline_service
from app.schemas.auth import UserSession


router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_permission(POLICIES["reports"].default))])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class AnalyticsSummary(BaseModel):
    total_cases: int
    new_this_period: int
    qualified_rate: float
    avg_time_to_qualified_hours: Optional[float]
    

class StatusCount(BaseModel):
    status: str
    count: int
    

class AssigneeCount(BaseModel):
    user_id: Optional[str]
    user_email: Optional[str]
    count: int


class TrendPoint(BaseModel):
    date: str
    count: int


class MetaPerformance(BaseModel):
    leads_received: int
    leads_qualified: int
    leads_converted: int
    qualification_rate: float
    conversion_rate: float
    avg_time_to_convert_hours: Optional[float]


class CampaignSpend(BaseModel):
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    reach: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class MetaSpendTimePoint(BaseModel):
    date_start: str
    date_stop: str
    spend: float
    impressions: int
    reach: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class MetaSpendBreakdown(BaseModel):
    breakdown_values: dict[str, str]
    spend: float
    impressions: int
    reach: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class MetaSpendSummary(BaseModel):
    total_spend: float
    total_impressions: int
    total_leads: int
    cost_per_lead: Optional[float]
    campaigns: list[CampaignSpend]
    time_series: list[MetaSpendTimePoint] = Field(default_factory=list)
    breakdowns: list[MetaSpendBreakdown] = Field(default_factory=list)


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    from_date: Optional[str] = Query(None, description="ISO date string"),
    to_date: Optional[str] = Query(None, description="ISO date string"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get high-level analytics summary."""
    from app.services import analytics_service

    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_analytics_summary(db, session.org_id, start, end)
    return AnalyticsSummary(**data)


@router.get("/cases/by-status", response_model=list[StatusCount])
def get_cases_by_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by status."""
    from app.services import analytics_service

    data = analytics_service.get_cases_by_status(db, session.org_id)
    return [StatusCount(**item) for item in data]


@router.get("/cases/by-assignee", response_model=list[AssigneeCount])
def get_cases_by_assignee(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by owner (user-owned cases only)."""
    from app.services import analytics_service

    data = analytics_service.get_cases_by_assignee(db, session.org_id)
    return [AssigneeCount(**item) for item in data]


@router.get("/cases/trend", response_model=list[TrendPoint])
def get_cases_trend(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    period: Literal["day", "week", "month"] = Query("day"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case creation trend over time."""
    from app.services import analytics_service

    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_cases_trend(
        db, session.org_id, start=start, end=end, group_by=period
    )
    return [TrendPoint(**item) for item in data]


@router.get("/meta/performance", response_model=MetaPerformance)
def get_meta_performance(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get Meta Lead Ads performance metrics.
    
    Qualified = Lead's case reached the "Qualified" stage or later.
    Converted = Lead's case reached the "Application Submitted" stage or later.
    """
    from app.services import analytics_service

    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_meta_performance(db, session.org_id, start, end)
    return MetaPerformance(**data)


@router.get("/meta/spend", response_model=MetaSpendSummary)
async def get_meta_spend(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    time_increment: Optional[int] = Query(
        None,
        description="Time increment in days for time series (e.g. 1, 7, 28)",
        ge=1,
        le=90,
    ),
    breakdowns: Optional[str] = Query(
        None,
        description="Comma-separated breakdowns (e.g. region,country)",
    ),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get Meta Ads spend data from Marketing API.
    
    Returns total spend, impressions, leads and cost per lead,
    broken down by campaign. Optional time series and breakdowns
    are included when requested via query params.
    """
    from app.services import analytics_service

    start, end = analytics_service.parse_date_range(from_date, to_date)
    breakdown_list = [item.strip() for item in breakdowns.split(",")] if breakdowns else []
    breakdown_list = [item for item in breakdown_list if item]

    data = await analytics_service.get_meta_spend_summary(
        start=start,
        end=end,
        time_increment=time_increment,
        breakdowns=breakdown_list or None,
    )

    return MetaSpendSummary(
        total_spend=data["total_spend"],
        total_impressions=data["total_impressions"],
        total_leads=data["total_leads"],
        cost_per_lead=data["cost_per_lead"],
        campaigns=[CampaignSpend(**item) for item in data.get("campaigns", [])],
        time_series=[MetaSpendTimePoint(**item) for item in data.get("time_series", [])],
        breakdowns=[MetaSpendBreakdown(**item) for item in data.get("breakdowns", [])],
    )


# =============================================================================
# New Analytics Endpoints (Phase A)
# =============================================================================

@router.get("/cases/by-state")
def get_cases_by_state(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get case count by US state for map visualization."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_cases_by_state(
        db, session.org_id, start.date() if start else None, end.date() if end else None, source
    )
    return {"data": data}


@router.get("/cases/by-source")
def get_cases_by_source(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get case count by lead source."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_cases_by_source(
        db, session.org_id, start.date() if start else None, end.date() if end else None
    )
    return {"data": data}


@router.get("/funnel")
def get_conversion_funnel(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get conversion funnel data."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_conversion_funnel(
        db, session.org_id, start.date() if start else None, end.date() if end else None
    )
    return {"data": data}


@router.get("/kpis")
def get_kpis(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get summary KPIs for dashboard cards."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_summary_kpis(
        db, session.org_id, start.date() if start else None, end.date() if end else None
    )
    return data


@router.get("/campaigns")
def get_campaigns(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get campaigns for filter dropdown."""
    from app.services import analytics_service
    
    data = analytics_service.get_campaigns(db, session.org_id)
    return {"data": data}


@router.get("/funnel/compare")
def get_funnel_compare(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_id: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get funnel with optional campaign filter for comparison."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_funnel_with_filter(
        db, session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        ad_id
    )
    return {"data": data}


@router.get("/cases/by-state/compare")
def get_cases_by_state_compare(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_id: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get cases by state with optional campaign filter."""
    from app.services import analytics_service
    
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_cases_by_state_with_filter(
        db, session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        ad_id
    )
    return {"data": data}


# =============================================================================
# Activity Feed
# =============================================================================

class ActivityFeedItem(BaseModel):
    """Single activity item for feed."""
    id: str
    activity_type: str
    case_id: str
    case_number: str | None
    case_name: str | None
    actor_name: str | None
    details: dict | None
    created_at: str


class ActivityFeedResponse(BaseModel):
    """Activity feed response."""
    items: list[ActivityFeedItem]
    has_more: bool


@router.get("/activity-feed", response_model=ActivityFeedResponse)
def get_activity_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    activity_type: Optional[str] = Query(None, description="Filter by activity type"),
    user_id: Optional[str] = Query(None, description="Filter by actor user ID"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> ActivityFeedResponse:
    """
    Get org-wide activity feed.
    
    Returns recent activities across all cases in the organization.
    Useful for managers to see what's happening across the team.
    """
    from app.db.models import CaseActivityLog, Case, User
    from sqlalchemy import desc
    
    # Build query
    query = db.query(
        CaseActivityLog,
        Case.case_number,
        Case.full_name.label("case_name"),
        User.display_name.label("actor_name"),
    ).join(
        Case, CaseActivityLog.case_id == Case.id
    ).outerjoin(
        User, CaseActivityLog.actor_user_id == User.id
    ).filter(
        CaseActivityLog.organization_id == session.org_id
    )
    
    # Apply filters
    if activity_type:
        query = query.filter(CaseActivityLog.activity_type == activity_type)
    
    if user_id:
        from uuid import UUID as PyUUID
        try:
            query = query.filter(CaseActivityLog.actor_user_id == PyUUID(user_id))
        except ValueError:
            pass  # Invalid UUID, ignore filter
    
    # Order and paginate
    query = query.order_by(desc(CaseActivityLog.created_at))
    total_query = query  # For has_more check
    query = query.offset(offset).limit(limit + 1)  # +1 to check has_more
    
    results = query.all()
    has_more = len(results) > limit
    items = results[:limit]
    
    return ActivityFeedResponse(
        items=[
            ActivityFeedItem(
                id=str(row.CaseActivityLog.id),
                activity_type=row.CaseActivityLog.activity_type,
                case_id=str(row.CaseActivityLog.case_id),
                case_number=row.case_number,
                case_name=row.case_name,
                actor_name=row.actor_name,
                details=row.CaseActivityLog.details,
                created_at=row.CaseActivityLog.created_at.isoformat(),
            )
            for row in items
        ],
        has_more=has_more,
    )


# =============================================================================
# PDF Export
# =============================================================================

@router.get("/export/pdf")
async def export_analytics_pdf(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Export analytics data as a PDF report.
    
    Generates a PDF containing:
    - Summary statistics
    - Cases by status breakdown
    - Cases by assignee breakdown
    - Meta leads performance (if any)
    - Recent trend data
    """
    from fastapi.responses import Response
    from app.db.models import Organization, Task
    from app.services import analytics_service
    from app.services.pdf_service import create_analytics_pdf
    
    org_id = session.org_id
    
    # Parse date range
    start_dt = None
    end_dt = None
    date_range_str = "All Time"
    
    if from_date:
        try:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    
    if to_date:
        try:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            pass
    
    if from_date and to_date:
        date_range_str = f"{from_date} to {to_date}"
    elif from_date:
        date_range_str = f"From {from_date}"
    elif to_date:
        date_range_str = f"Until {to_date}"
    
    # Build date filter
    date_filter = Case.is_archived == False
    if start_dt:
        date_filter = date_filter & (Case.created_at >= start_dt)
    if end_dt:
        date_filter = date_filter & (Case.created_at <= end_dt)
    
    # Get organization name
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_name = org.name if org else "Organization"
    
    # Get summary data
    total_cases = db.query(func.count(Case.id)).filter(
        Case.organization_id == org_id,
        date_filter
    ).scalar() or 0
    
    # New this period (last 7 days from end date or now)
    period_start = (end_dt or datetime.now(timezone.utc)) - timedelta(days=7)
    new_this_period = db.query(func.count(Case.id)).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.created_at >= period_start
    ).scalar() or 0
    
    # Get qualified rate
    from app.db.models import PipelineStage
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    
    qualified_rate = 0.0
    if qualified_stage and total_cases > 0:
        qualified_stage_ids = db.query(PipelineStage.id).filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.order >= qualified_stage.order,
            PipelineStage.is_active == True,
        )
        qualified_count = db.query(func.count(Case.id)).filter(
            Case.organization_id == org_id,
            Case.is_archived == False,
            Case.stage_id.in_(qualified_stage_ids),
        ).scalar() or 0
        qualified_rate = (qualified_count / total_cases) * 100
    
    # Task stats
    pending_tasks = db.query(func.count(Task.id)).filter(
        Task.organization_id == org_id,
        Task.is_completed == False
    ).scalar() or 0
    
    overdue_tasks = db.query(func.count(Task.id)).filter(
        Task.organization_id == org_id,
        Task.is_completed == False,
        Task.due_date < datetime.now(timezone.utc).date()
    ).scalar() or 0
    
    summary = {
        "total_cases": total_cases,
        "new_this_period": new_this_period,
        "qualified_rate": qualified_rate,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
    }
    
    cases_by_status = analytics_service.get_cases_by_status(db, org_id)
    cases_by_assignee = analytics_service.get_cases_by_assignee(
        db, org_id, label="display_name"
    )

    trend_start = datetime.now(timezone.utc) - timedelta(days=30)
    trend_data = analytics_service.get_cases_trend(
        db, org_id, start=trend_start, end=datetime.now(timezone.utc), group_by="day"
    )

    meta_start = start_dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
    meta_end = end_dt or datetime.now(timezone.utc)
    meta_performance = analytics_service.get_meta_performance(
        db, org_id, meta_start, meta_end
    )
    
    # Generate PDF
    pdf_bytes = create_analytics_pdf(
        summary=summary,
        cases_by_status=cases_by_status,
        cases_by_assignee=cases_by_assignee,
        trend_data=trend_data,
        meta_performance=meta_performance,
        org_name=org_name,
        date_range=date_range_str,
    )
    
    # Return PDF response
    filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
