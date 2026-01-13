"""
Analytics endpoints for admin dashboards.

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


# =============================================================================
# Performance by User Schemas
# =============================================================================


class UserPerformanceData(BaseModel):
    """Performance metrics for a single user."""

    user_id: str
    user_name: str
    total_cases: int
    archived_count: int
    contacted: int
    qualified: int
    pending_match: int
    matched: int
    applied: int
    lost: int
    conversion_rate: float
    avg_days_to_match: Optional[float]
    avg_days_to_apply: Optional[float]


class UnassignedPerformanceData(BaseModel):
    """Performance metrics for unassigned cases."""

    total_cases: int
    archived_count: int
    contacted: int
    qualified: int
    pending_match: int
    matched: int
    applied: int
    lost: int


class PerformanceByUserResponse(BaseModel):
    """Response for /analytics/performance/by-user endpoint."""

    from_date: str
    to_date: str
    mode: Literal["cohort", "activity"]
    as_of: str
    pipeline_id: Optional[str]
    data: list[UserPerformanceData]
    unassigned: UnassignedPerformanceData


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
    data = analytics_service.get_cached_analytics_summary(
        db, session.org_id, start, end
    )
    return AnalyticsSummary(**data)


@router.get("/cases/by-status", response_model=list[StatusCount])
def get_cases_by_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by status."""
    from app.services import analytics_service

    data = analytics_service.get_cached_cases_by_status(db, session.org_id)
    return [StatusCount(**item) for item in data]


@router.get("/cases/by-assignee", response_model=list[AssigneeCount])
def get_cases_by_assignee(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by owner (user-owned cases only)."""
    from app.services import analytics_service

    data = analytics_service.get_cached_cases_by_assignee(db, session.org_id)
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
    data = analytics_service.get_cached_cases_trend(
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
    data = analytics_service.get_cached_meta_performance(db, session.org_id, start, end)
    return MetaPerformance(**data)


# =============================================================================
# Meta Stored Data Endpoints
# =============================================================================


class MetaAdAccountItem(BaseModel):
    """Ad account for dropdown/list."""

    id: str
    ad_account_external_id: str
    ad_account_name: str
    hierarchy_synced_at: Optional[str]
    spend_synced_at: Optional[str]


class SpendTotalsResponse(BaseModel):
    """Spend totals with sync status."""

    total_spend: float
    total_impressions: int
    total_clicks: int
    total_leads: int
    cost_per_lead: Optional[float]
    sync_status: str
    last_synced_at: Optional[str]
    ad_accounts_configured: int


class StoredCampaignSpendItem(BaseModel):
    """Spend data for a single campaign from stored data."""

    campaign_external_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class SpendBreakdownItem(BaseModel):
    """Spend data for a breakdown dimension."""

    breakdown_value: str
    spend: float
    impressions: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class SpendTrendPoint(BaseModel):
    """Daily spend data point."""

    date: str
    spend: float
    impressions: int
    clicks: int
    leads: int
    cost_per_lead: Optional[float]


class FormPerformanceItem(BaseModel):
    """Form performance metrics."""

    form_external_id: str
    form_name: str
    lead_count: int
    case_count: int
    qualified_count: int
    conversion_rate: float
    qualified_rate: float


class MetaCampaignListItem(BaseModel):
    """Campaign for filter dropdown."""

    campaign_external_id: str
    campaign_name: str
    status: str
    objective: Optional[str]


@router.get("/meta/ad-accounts")
def get_meta_ad_accounts(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get list of configured ad accounts for filter dropdown."""
    data = analytics_service.get_meta_ad_accounts(db, session.org_id)
    return {"data": [MetaAdAccountItem(**item).model_dump() for item in data]}


@router.get("/meta/spend/totals", response_model=SpendTotalsResponse)
def get_spend_totals(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_account_id: Optional[str] = Query(None, description="Filter by ad account UUID"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> SpendTotalsResponse:
    """
    Get spend totals with sync status.

    Returns aggregate metrics plus sync status to help UI show
    appropriate empty/pending states.
    """
    from uuid import UUID as _UUID

    start, end = analytics_service.parse_date_range(from_date, to_date)
    account_uuid = _UUID(ad_account_id) if ad_account_id else None

    data = analytics_service.get_spend_totals(
        db=db,
        organization_id=session.org_id,
        start_date=start.date() if start else None,
        end_date=end.date() if end else None,
        ad_account_id=account_uuid,
    )
    return SpendTotalsResponse(**data)


@router.get("/meta/spend/by-campaign")
def get_spend_by_campaign(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_account_id: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get spend aggregated by campaign from stored data."""
    from uuid import UUID as _UUID

    start, end = analytics_service.parse_date_range(from_date, to_date)
    account_uuid = _UUID(ad_account_id) if ad_account_id else None

    data = analytics_service.get_cached_spend_by_campaign(
        db=db,
        organization_id=session.org_id,
        start_date=start.date() if start else None,
        end_date=end.date() if end else None,
        ad_account_id=account_uuid,
    )
    return {"data": [StoredCampaignSpendItem(**item).model_dump() for item in data]}


@router.get("/meta/spend/by-breakdown")
def get_spend_by_breakdown(
    breakdown_type: Literal["publisher_platform", "platform_position", "age", "region"] = Query(
        ..., description="Breakdown dimension"
    ),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_account_id: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get spend aggregated by breakdown dimension.

    Breakdown types:
    - publisher_platform: facebook, instagram, audience_network
    - platform_position: feed, stories, reels, etc.
    - age: 18-24, 25-34, 35-44, etc.
    - region: US states
    """
    from uuid import UUID as _UUID

    start, end = analytics_service.parse_date_range(from_date, to_date)
    account_uuid = _UUID(ad_account_id) if ad_account_id else None

    data = analytics_service.get_cached_spend_by_breakdown(
        db=db,
        organization_id=session.org_id,
        start_date=start.date() if start else None,
        end_date=end.date() if end else None,
        breakdown_type=breakdown_type,
        ad_account_id=account_uuid,
    )
    return {"data": [SpendBreakdownItem(**item).model_dump() for item in data]}


@router.get("/meta/spend/trend")
def get_spend_trend(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    ad_account_id: Optional[str] = Query(None),
    campaign_external_id: Optional[str] = Query(None, description="Filter by campaign"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get daily spend time series from stored data."""
    from uuid import UUID as _UUID

    start, end = analytics_service.parse_date_range(from_date, to_date)
    account_uuid = _UUID(ad_account_id) if ad_account_id else None

    data = analytics_service.get_cached_spend_trend(
        db=db,
        organization_id=session.org_id,
        start_date=start.date() if start else None,
        end_date=end.date() if end else None,
        ad_account_id=account_uuid,
        campaign_external_id=campaign_external_id,
    )
    return {"data": [SpendTrendPoint(**item).model_dump() for item in data]}


@router.get("/meta/forms")
def get_form_performance(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get form performance metrics.

    Returns lead counts from meta_leads and conversion rates
    from joined Cases.
    """
    start, end = analytics_service.parse_date_range(from_date, to_date)

    data = analytics_service.get_cached_leads_by_form(
        db=db,
        organization_id=session.org_id,
        start_date=start.date() if start else None,
        end_date=end.date() if end else None,
    )
    return {"data": [FormPerformanceItem(**item).model_dump() for item in data]}


@router.get("/meta/campaigns")
def get_meta_campaign_list(
    ad_account_id: Optional[str] = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Get list of synced campaigns for filter dropdown."""
    from uuid import UUID as _UUID

    account_uuid = _UUID(ad_account_id) if ad_account_id else None

    data = analytics_service.get_meta_campaign_list(
        db=db,
        organization_id=session.org_id,
        ad_account_id=account_uuid,
    )
    return {"data": [MetaCampaignListItem(**item).model_dump() for item in data]}


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
    data = analytics_service.get_cached_cases_by_state(
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
    data = analytics_service.get_cached_cases_by_source(
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
    data = analytics_service.get_cached_conversion_funnel(
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
    data = analytics_service.get_cached_summary_kpis(
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

    data = analytics_service.get_cached_campaigns(db, session.org_id)
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
    data = analytics_service.get_cached_funnel_with_filter(
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
    data = analytics_service.get_cached_cases_by_state_with_filter(
        db,
        session.org_id,
        start.date() if start else None,
        end.date() if end else None,
        ad_id,
    )
    return {"data": data}


# =============================================================================
# Performance by User
# =============================================================================


@router.get("/performance/by-user", response_model=PerformanceByUserResponse)
def get_performance_by_user(
    from_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    to_date: Optional[str] = Query(None, description="End date (ISO format)"),
    mode: Literal["cohort", "activity"] = Query(
        "cohort",
        description="cohort: cases created in range; activity: status changes in range",
    ),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> PerformanceByUserResponse:
    """
    Get individual user performance metrics.

    **Modes:**
    - `cohort`: Analyze cases created within the date range, grouped by current owner.
      Shows how each user's assigned cases have progressed through stages.
    - `activity`: Analyze status transitions within the date range.
      Shows activity during a specific period regardless of when cases were created.

    **Metrics:**
    - `total_cases`: Number of cases (cohort: created in range; activity: with transitions in range)
    - `archived_count`: Cases that are archived
    - `contacted/qualified/pending_match/matched/applied`: Cases that reached each stage (via history)
    - `lost`: Cases that reached lost stage AND never reached applied
    - `conversion_rate`: (applied / total_cases) * 100
    - `avg_days_to_match`: Average days from creation to first match transition
    - `avg_days_to_apply`: Average days from creation to first applied transition

    **Credit Model:**
    All metrics are attributed to the current case owner. Cases without an owner
    are grouped in the `unassigned` bucket.
    """
    start, end = analytics_service.parse_date_range(from_date, to_date)
    data = analytics_service.get_cached_performance_by_user(
        db=db,
        organization_id=session.org_id,
        start_date=start,
        end_date=end,
        mode=mode,
    )

    return PerformanceByUserResponse(
        from_date=data["from_date"],
        to_date=data["to_date"],
        mode=data["mode"],
        as_of=data["as_of"],
        pipeline_id=data.get("pipeline_id"),
        data=[UserPerformanceData(**user) for user in data["data"]],
        unassigned=UnassignedPerformanceData(**data["unassigned"]),
    )


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
    Useful for admins to see what's happening across the team.
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
    from app.services import pdf_export_service

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

    # Generate PDF using Playwright-based service (async)
    pdf_bytes = await pdf_export_service.export_analytics_pdf_async(
        db=db,
        organization_id=org_id,
        start_dt=start_dt,
        end_dt=end_dt,
        date_range_str=date_range_str,
    )

    # Return PDF response
    filename = f"analytics_report_{datetime.now().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
