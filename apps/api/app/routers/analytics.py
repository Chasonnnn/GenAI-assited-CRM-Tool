"""
Analytics endpoints for manager dashboards.

Provides case statistics, trends, and Meta performance metrics.
"""
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_roles
from app.db.enums import Role
from app.db.models import Case, MetaLead
from app.services import pipeline_service
from app.schemas.auth import UserSession


router = APIRouter(prefix="/analytics", tags=["analytics"])


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
    leads_converted: int
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


class MetaSpendSummary(BaseModel):
    total_spend: float
    total_impressions: int
    total_leads: int
    cost_per_lead: Optional[float]
    campaigns: list[CampaignSpend]


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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    
    # Qualified rate (qualified stage and later, fallback to post_approval/terminal)
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    if qualified_stage:
        qualified_stage_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]
    else:
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """Get Meta Lead Ads performance metrics."""
    start, end = parse_date_range(from_date, to_date)
    org_id = session.org_id
    
    # Total leads received
    leads_received = db.query(MetaLead).filter(
        MetaLead.organization_id == org_id,
        MetaLead.received_at >= start,
        MetaLead.received_at < end,
    ).count()
    
    # Leads converted to cases
    leads_converted = db.query(MetaLead).filter(
        MetaLead.organization_id == org_id,
        MetaLead.received_at >= start,
        MetaLead.received_at < end,
        MetaLead.is_converted == True,
    ).count()
    
    conversion_rate = (leads_converted / leads_received * 100) if leads_received > 0 else 0.0
    
    # Avg time to convert (in hours)
    result = db.execute(
        text("""
            SELECT AVG(EXTRACT(EPOCH FROM (converted_at - received_at)) / 3600) as avg_hours
            FROM meta_leads
            WHERE organization_id = :org_id
              AND received_at >= :start
              AND received_at < :end
              AND is_converted = true
              AND converted_at IS NOT NULL
        """),
        {"org_id": org_id, "start": start, "end": end}
    )
    row = result.fetchone()
    avg_hours = round(row[0], 1) if row and row[0] else None
    
    return MetaPerformance(
        leads_received=leads_received,
        leads_converted=leads_converted,
        conversion_rate=round(conversion_rate, 1),
        avg_time_to_convert_hours=avg_hours,
    )


@router.get("/meta/spend", response_model=MetaSpendSummary)
async def get_meta_spend(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """
    Get Meta Ads spend data from Marketing API.
    
    Returns total spend, impressions, leads and cost per lead,
    broken down by campaign.
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
    
    # Fetch insights from Meta API
    insights, error = await meta_api.fetch_ad_account_insights(
        ad_account_id=ad_account_id or "act_mock",
        access_token=access_token or "mock_token",
        date_start=date_start,
        date_end=date_end,
        level="campaign",
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
    campaigns = []
    total_spend = 0.0
    total_impressions = 0
    total_leads = 0
    
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
        
        cpl = round(spend / leads, 2) if leads > 0 else None
        
        campaigns.append(CampaignSpend(
            campaign_id=insight.get("campaign_id", ""),
            campaign_name=insight.get("campaign_name", "Unknown"),
            spend=spend,
            impressions=impressions,
            reach=reach,
            clicks=clicks,
            leads=leads,
            cost_per_lead=cpl,
        ))
        
        total_spend += spend
        total_impressions += impressions
        total_leads += leads
    
    overall_cpl = round(total_spend / total_leads, 2) if total_leads > 0 else None
    
    return MetaSpendSummary(
        total_spend=round(total_spend, 2),
        total_impressions=total_impressions,
        total_leads=total_leads,
        cost_per_lead=overall_cpl,
        campaigns=campaigns,
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
