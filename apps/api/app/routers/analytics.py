"""
Analytics endpoints for manager dashboards.

Provides case statistics, trends, and Meta performance metrics.
"""
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES

from app.db.models import Case, MetaLead
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
# Helper Functions
# =============================================================================

def parse_date_range(from_date: str | None, to_date: str | None) -> tuple[datetime, datetime]:
    """Parse date range with defaults."""
    if to_date:
        end = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
    else:
        end = datetime.now(timezone.utc)
    
    if from_date:
        start = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
    else:
        start = end - timedelta(days=30)
    
    return start, end


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
    start, end = parse_date_range(from_date, to_date)
    org_id = session.org_id
    
    # Total non-archived cases
    total_cases = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    ).count()
    
    # New cases in period
    new_this_period = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.created_at >= start,
        Case.created_at < end,
    ).count()
    
    # Qualified rate = cases at "qualified" stage or later
    # This includes: Qualified, Applied, Under Review, Approved, etc.
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    if qualified_stage:
        qualified_stage_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]
    else:
        # Fallback: only post_approval and terminal stages count as qualified
        qualified_stage_ids = [
            s.id for s in stages if s.stage_type in ("post_approval", "terminal") and s.is_active
        ]
    qualified_count = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.stage_id.in_(qualified_stage_ids),
    ).count()
    qualified_rate = (qualified_count / total_cases * 100) if total_cases > 0 else 0.0
    
    # Average time to qualified (hours) from status history
    avg_time_to_qualified_hours = None
    if qualified_stage:
        avg_hours_result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - c.created_at)) / 3600) as avg_hours
                FROM cases c
                JOIN case_status_history csh ON c.id = csh.case_id
                WHERE c.organization_id = :org_id
                  AND c.is_archived = false
                  AND csh.to_stage_id = :qualified_stage_id
                  AND csh.changed_at >= :start
                  AND csh.changed_at < :end
            """),
            {"org_id": org_id, "start": start, "end": end, "qualified_stage_id": qualified_stage.id}
        )
        avg_hours_row = avg_hours_result.fetchone()
        avg_time_to_qualified_hours = round(avg_hours_row[0], 1) if avg_hours_row and avg_hours_row[0] else None
    
    return AnalyticsSummary(
        total_cases=total_cases,
        new_this_period=new_this_period,
        qualified_rate=round(qualified_rate, 1),
        avg_time_to_qualified_hours=avg_time_to_qualified_hours,
    )


@router.get("/cases/by-status", response_model=list[StatusCount])
def get_cases_by_status(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by status."""
    org_id = session.org_id
    
    result = db.execute(
        text("""
            SELECT status_label, COUNT(*) as count
            FROM cases
            WHERE organization_id = :org_id
              AND is_archived = false
            GROUP BY status_label
            ORDER BY count DESC
        """),
        {"org_id": org_id}
    )
    
    return [StatusCount(status=row[0], count=row[1]) for row in result]


@router.get("/cases/by-assignee", response_model=list[AssigneeCount])
def get_cases_by_assignee(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case counts grouped by owner (user-owned cases only)."""
    org_id = session.org_id
    
    result = db.execute(
        text("""
            SELECT c.owner_id, u.email, COUNT(*) as count
            FROM cases c
            LEFT JOIN users u ON c.owner_id = u.id
            WHERE c.organization_id = :org_id
              AND c.owner_type = 'user'
              AND c.is_archived = false
            GROUP BY c.owner_id, u.email
            ORDER BY count DESC
        """),
        {"org_id": org_id}
    )
    
    return [
        AssigneeCount(
            user_id=str(row[0]) if row[0] else None,
            user_email=row[1],
            count=row[2]
        ) 
        for row in result
    ]


@router.get("/cases/trend", response_model=list[TrendPoint])
def get_cases_trend(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    period: Literal["day", "week", "month"] = Query("day"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case creation trend over time."""
    start, end = parse_date_range(from_date, to_date)
    org_id = session.org_id
    
    # Date truncation based on period
    trunc_map = {"day": "day", "week": "week", "month": "month"}
    trunc = trunc_map[period]
    
    result = db.execute(
        text(f"""
            SELECT date_trunc(:trunc, created_at) as period_start, COUNT(*) as count
            FROM cases
            WHERE organization_id = :org_id
              AND is_archived = false
              AND created_at >= :start
              AND created_at < :end
            GROUP BY period_start
            ORDER BY period_start
        """),
        {"org_id": org_id, "start": start, "end": end, "trunc": trunc}
    )
    
    return [
        TrendPoint(date=row[0].strftime("%Y-%m-%d") if row[0] else "", count=row[1])
        for row in result
    ]


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
    start, end = parse_date_range(from_date, to_date)
    org_id = session.org_id
    
    # Get pipeline stages
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    
    # Get qualified and converted stage IDs
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    converted_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "application_submitted")
    
    # Build stage ID lists
    qualified_or_later_ids = []
    converted_or_later_ids = []
    
    if qualified_stage:
        qualified_or_later_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]
    if converted_stage:
        converted_or_later_ids = [
            s.id for s in stages if s.order >= converted_stage.order and s.is_active
        ]
    
    # Total leads received
    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)
    leads_received = db.query(MetaLead).filter(
        MetaLead.organization_id == org_id,
        lead_time >= start,
        lead_time < end,
    ).count()
    
    # Leads qualified = case reached "Qualified" stage or later
    leads_qualified = 0
    if qualified_or_later_ids:
        leads_qualified = db.execute(
            text("""
                SELECT COUNT(*) 
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
            {"org_id": org_id, "start": start, "end": end, "stage_ids": qualified_or_later_ids}
        ).scalar() or 0
    
    # Leads converted = case reached "Application Submitted" stage or later
    leads_converted = 0
    if converted_or_later_ids:
        leads_converted = db.execute(
            text("""
                SELECT COUNT(*) 
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
            {"org_id": org_id, "start": start, "end": end, "stage_ids": converted_or_later_ids}
        ).scalar() or 0
    
    qualification_rate = (leads_qualified / leads_received * 100) if leads_received > 0 else 0.0
    conversion_rate = (leads_converted / leads_received * 100) if leads_received > 0 else 0.0
    
    # Avg time to convert (in hours) - from lead created to case reaching application_submitted
    result = None
    if converted_stage:
        result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - COALESCE(ml.meta_created_time, ml.received_at))) / 3600) as avg_hours
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                JOIN case_status_history csh ON c.id = csh.case_id AND csh.to_stage_id = :converted_stage_id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
            """),
            {"org_id": org_id, "start": start, "end": end, "converted_stage_id": converted_stage.id}
        )
    row = result.fetchone() if result else None
    avg_hours = round(row[0], 1) if row and row[0] else None
    
    return MetaPerformance(
        leads_received=leads_received,
        leads_qualified=leads_qualified,
        leads_converted=leads_converted,
        qualification_rate=round(qualification_rate, 1),
        conversion_rate=round(conversion_rate, 1),
        avg_time_to_convert_hours=avg_hours,
    )


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
    import logging
    from app.core.config import settings
    from app.services import meta_api
    
    logger = logging.getLogger(__name__)
    
    start, end = parse_date_range(from_date, to_date)
    
    # Format dates for Meta API
    date_start = start.strftime("%Y-%m-%d")
    date_end = end.strftime("%Y-%m-%d")
    
    # Get ad account ID and token from settings
    ad_account_id = settings.META_AD_ACCOUNT_ID
    access_token = settings.META_SYSTEM_TOKEN
    
    # Check if properly configured (unless test mode)
    if not settings.META_TEST_MODE and (not ad_account_id or not access_token):
        logger.warning("Meta Ads spend: META_AD_ACCOUNT_ID or META_SYSTEM_TOKEN not configured")
        return MetaSpendSummary(
            total_spend=0.0,
            total_impressions=0,
            total_leads=0,
            cost_per_lead=None,
            campaigns=[],
        )
    
    breakdown_list = [item.strip() for item in breakdowns.split(",")] if breakdowns else []
    breakdown_list = [item for item in breakdown_list if item]
    
    # Fetch insights from Meta API
    insights, error = await meta_api.fetch_ad_account_insights(
        ad_account_id=ad_account_id or "act_mock",
        access_token=access_token or "mock_token",
        date_start=date_start,
        date_end=date_end,
        level="campaign",
        time_increment=time_increment,
        breakdowns=breakdown_list or None,
    )
    
    if error:
        logger.error(f"Meta Ads spend API error: {error}")
        return MetaSpendSummary(
            total_spend=0.0,
            total_impressions=0,
            total_leads=0,
            cost_per_lead=None,
            campaigns=[],
        )
    
    # Helper to safely parse numeric values (Meta often returns strings or empty)
    def safe_float(val, default=0.0) -> float:
        if val is None or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
    
    def safe_int(val, default=0) -> int:
        if val is None or val == "":
            return default
        try:
            return int(float(val))  # int(float()) handles "42.0"
        except (ValueError, TypeError):
            return default
    
    # Lead action types to check (Meta uses different names in different contexts)
    LEAD_ACTION_TYPES = {"lead", "leadgen", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"}
    
    # Process insights data
    campaigns_by_id: dict[str, dict[str, float | int | str]] = {}
    total_spend = 0.0
    total_impressions = 0
    total_leads = 0
    time_series: dict[tuple[str, str], dict[str, float | int]] = {}
    breakdown_totals: dict[tuple[str, ...], dict[str, float | int | dict[str, str]]] = {}
    
    for insight in insights:
        spend = safe_float(insight.get("spend"))
        impressions = safe_int(insight.get("impressions"))
        reach = safe_int(insight.get("reach"))
        clicks = safe_int(insight.get("clicks"))
        
        # Extract leads from actions array - check multiple action types
        leads = 0
        actions = insight.get("actions") or []
        for action in actions:
            action_type = action.get("action_type", "")
            if action_type in LEAD_ACTION_TYPES:
                leads += safe_int(action.get("value"))
        
        campaign_id = insight.get("campaign_id", "") or "unknown"
        campaign_name = insight.get("campaign_name", "Unknown")
        campaign_totals = campaigns_by_id.get(campaign_id)
        if not campaign_totals:
            campaign_totals = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "spend": 0.0,
                "impressions": 0,
                "reach": 0,
                "clicks": 0,
                "leads": 0,
            }
            campaigns_by_id[campaign_id] = campaign_totals
        campaign_totals["spend"] = float(campaign_totals["spend"]) + spend
        campaign_totals["impressions"] = int(campaign_totals["impressions"]) + impressions
        campaign_totals["reach"] = int(campaign_totals["reach"]) + reach
        campaign_totals["clicks"] = int(campaign_totals["clicks"]) + clicks
        campaign_totals["leads"] = int(campaign_totals["leads"]) + leads
        
        total_spend += spend
        total_impressions += impressions
        total_leads += leads
        
        if time_increment:
            date_start_value = insight.get("date_start") or date_start
            date_stop_value = insight.get("date_stop") or date_end
            time_key = (str(date_start_value), str(date_stop_value))
            point = time_series.get(time_key)
            if not point:
                point = {
                    "spend": 0.0,
                    "impressions": 0,
                    "reach": 0,
                    "clicks": 0,
                    "leads": 0,
                }
                time_series[time_key] = point
            point["spend"] = float(point["spend"]) + spend
            point["impressions"] = int(point["impressions"]) + impressions
            point["reach"] = int(point["reach"]) + reach
            point["clicks"] = int(point["clicks"]) + clicks
            point["leads"] = int(point["leads"]) + leads
        
        if breakdown_list:
            breakdown_values = {key: str(insight.get(key, "unknown")) for key in breakdown_list}
            breakdown_key = tuple(breakdown_values.get(key, "unknown") for key in breakdown_list)
            breakdown = breakdown_totals.get(breakdown_key)
            if not breakdown:
                breakdown = {
                    "breakdown_values": breakdown_values,
                    "spend": 0.0,
                    "impressions": 0,
                    "reach": 0,
                    "clicks": 0,
                    "leads": 0,
                }
                breakdown_totals[breakdown_key] = breakdown
            breakdown["spend"] = float(breakdown["spend"]) + spend
            breakdown["impressions"] = int(breakdown["impressions"]) + impressions
            breakdown["reach"] = int(breakdown["reach"]) + reach
            breakdown["clicks"] = int(breakdown["clicks"]) + clicks
            breakdown["leads"] = int(breakdown["leads"]) + leads
    
    overall_cpl = round(total_spend / total_leads, 2) if total_leads > 0 else None
    
    campaigns = []
    for campaign_totals in campaigns_by_id.values():
        campaign_spend = float(campaign_totals["spend"])
        campaign_leads = int(campaign_totals["leads"])
        cpl = round(campaign_spend / campaign_leads, 2) if campaign_leads > 0 else None
        campaigns.append(CampaignSpend(
            campaign_id=str(campaign_totals["campaign_id"]),
            campaign_name=str(campaign_totals["campaign_name"]),
            spend=campaign_spend,
            impressions=int(campaign_totals["impressions"]),
            reach=int(campaign_totals["reach"]),
            clicks=int(campaign_totals["clicks"]),
            leads=campaign_leads,
            cost_per_lead=cpl,
        ))
    
    time_series_points = []
    if time_increment:
        for (start_key, stop_key), totals in sorted(time_series.items()):
            point_spend = float(totals["spend"])
            point_leads = int(totals["leads"])
            point_cpl = round(point_spend / point_leads, 2) if point_leads > 0 else None
            time_series_points.append(MetaSpendTimePoint(
                date_start=start_key,
                date_stop=stop_key,
                spend=point_spend,
                impressions=int(totals["impressions"]),
                reach=int(totals["reach"]),
                clicks=int(totals["clicks"]),
                leads=point_leads,
                cost_per_lead=point_cpl,
            ))
    
    breakdown_points = []
    if breakdown_list:
        for breakdown in breakdown_totals.values():
            breakdown_spend = float(breakdown["spend"])
            breakdown_leads = int(breakdown["leads"])
            breakdown_cpl = round(breakdown_spend / breakdown_leads, 2) if breakdown_leads > 0 else None
            breakdown_points.append(MetaSpendBreakdown(
                breakdown_values=breakdown["breakdown_values"],
                spend=breakdown_spend,
                impressions=int(breakdown["impressions"]),
                reach=int(breakdown["reach"]),
                clicks=int(breakdown["clicks"]),
                leads=breakdown_leads,
                cost_per_lead=breakdown_cpl,
            ))
    
    breakdown_points.sort(key=lambda item: item.spend, reverse=True)
    
    return MetaSpendSummary(
        total_spend=round(total_spend, 2),
        total_impressions=total_impressions,
        total_leads=total_leads,
        cost_per_lead=overall_cpl,
        campaigns=campaigns,
        time_series=time_series_points,
        breakdowns=breakdown_points,
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    start, end = parse_date_range(from_date, to_date)
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
    
    # Cases by status
    status_query = db.query(
        PipelineStage.label.label('status'),
        func.count(Case.id).label('count')
    ).join(
        Case, Case.stage_id == PipelineStage.id
    ).filter(
        Case.organization_id == org_id,
        Case.is_archived == False
    ).group_by(PipelineStage.label, PipelineStage.order).order_by(PipelineStage.order)
    
    cases_by_status = [{"status": row.status, "count": row.count} for row in status_query.all()]
    
    # Cases by assignee
    from app.db.models import User
    assignee_query = db.query(
        User.display_name.label('display_name'),
        func.count(Case.id).label('count')
    ).outerjoin(
        User, (Case.owner_type == 'user') & (Case.owner_id == User.id)
    ).filter(
        Case.organization_id == org_id,
        Case.is_archived == False
    ).group_by(User.display_name).order_by(func.count(Case.id).desc())
    
    cases_by_assignee = [{"display_name": row.display_name or "Unassigned", "count": row.count} for row in assignee_query.all()]
    
    # Trend data (last 30 days)
    trend_start = datetime.now(timezone.utc) - timedelta(days=30)
    trend_query = db.query(
        func.date(Case.created_at).label('date'),
        func.count(Case.id).label('count')
    ).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.created_at >= trend_start
    ).group_by(func.date(Case.created_at)).order_by(func.date(Case.created_at))
    
    trend_data = [{"date": str(row.date), "count": row.count} for row in trend_query.all()]
    
    # Meta performance
    meta_performance = None
    leads_received = db.query(func.count(MetaLead.id)).filter(
        MetaLead.organization_id == org_id
    ).scalar() or 0
    
    if leads_received > 0:
        leads_converted = db.query(func.count(MetaLead.id)).filter(
            MetaLead.organization_id == org_id,
            MetaLead.is_converted == True
        ).scalar() or 0
        
        leads_qualified = leads_converted  # Simplified - could add stage check
        
        meta_performance = {
            "leads_received": leads_received,
            "leads_qualified": leads_qualified,
            "leads_converted": leads_converted,
            "qualification_rate": (leads_qualified / leads_received) * 100 if leads_received > 0 else 0,
            "conversion_rate": (leads_converted / leads_received) * 100 if leads_received > 0 else 0,
            "avg_time_to_convert_hours": None,
        }
    
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
