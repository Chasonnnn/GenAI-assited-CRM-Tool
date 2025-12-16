"""
Analytics endpoints for manager dashboards.

Provides case statistics, trends, and Meta performance metrics.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_roles
from app.db.enums import Role, CaseStatus
from app.db.models import Case, MetaLead
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
    
    # Qualified rate (qualified + approved + later stages / total)
    qualified_statuses = [
        CaseStatus.QUALIFIED.value, CaseStatus.APPLIED.value,
        CaseStatus.APPROVED.value, CaseStatus.PENDING_HANDOFF.value,
        CaseStatus.PENDING_MATCH.value, CaseStatus.DELIVERED.value,
    ]
    qualified_count = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.status.in_(qualified_statuses),
    ).count()
    qualified_rate = (qualified_count / total_cases * 100) if total_cases > 0 else 0.0
    
    return AnalyticsSummary(
        total_cases=total_cases,
        new_this_period=new_this_period,
        qualified_rate=round(qualified_rate, 1),
        avg_time_to_qualified_hours=None,  # TODO: Compute from status history
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
            SELECT status, COUNT(*) as count
            FROM cases
            WHERE organization_id = :org_id
              AND is_archived = false
            GROUP BY status
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
    """Get case counts grouped by assigned user."""
    org_id = session.org_id
    
    result = db.execute(
        text("""
            SELECT c.assigned_to_user_id, u.email, COUNT(*) as count
            FROM cases c
            LEFT JOIN users u ON c.assigned_to_user_id = u.id
            WHERE c.organization_id = :org_id
              AND c.is_archived = false
            GROUP BY c.assigned_to_user_id, u.email
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
    period: str = Query("day", regex="^(day|week|month)$"),
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
