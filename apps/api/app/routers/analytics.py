"""
Analytics endpoints for manager dashboards.

Provides case statistics, trends, and Meta performance metrics.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES

from app.services import analytics_service
from app.schemas.auth import UserSession


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_permission(POLICIES["reports"].default))],
)


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
    breakdown_list = (
        [item.strip() for item in breakdowns.split(",")] if breakdowns else []
    )
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
        time_series=[
            MetaSpendTimePoint(**item) for item in data.get("time_series", [])
        ],
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
        db,
        session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        source,
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
        db,
        session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        ad_id,
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
        db,
        session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        ad_id,
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
    items, has_more = analytics_service.get_activity_feed(
        db=db,
        organization_id=session.org_id,
        limit=limit,
        offset=offset,
        activity_type=activity_type,
        user_id=user_id,
    )

    return ActivityFeedResponse(
        items=[
            ActivityFeedItem(
                id=item["id"],
                activity_type=item["activity_type"],
                case_id=item["case_id"],
                case_number=item["case_number"],
                case_name=item["case_name"],
                actor_name=item["actor_name"],
                details=item["details"],
                created_at=item["created_at"],
            )
            for item in items
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
    from app.services import analytics_service
    from app.services.pdf_service import create_analytics_pdf

    org_id = session.org_id

    # Parse date range
    start_dt = None
    end_dt = None
    date_range_str = "All Time"

    if from_date:
        try:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
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

    export_data = analytics_service.get_pdf_export_data(
        db=db,
        organization_id=org_id,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    # Generate PDF
    pdf_bytes = create_analytics_pdf(
        summary=export_data["summary"],
        cases_by_status=export_data["cases_by_status"],
        cases_by_assignee=export_data["cases_by_assignee"],
        trend_data=export_data["trend_data"],
        meta_performance=export_data["meta_performance"],
        org_name=export_data["org_name"],
        date_range=date_range_str,
    )

    # Return PDF response
    filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
