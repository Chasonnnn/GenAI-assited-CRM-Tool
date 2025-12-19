"""Analytics service for Reports dashboard.

Provides query functions for case trends, status distributions, and geographic data.
Works without AI - purely script-generated aggregations.
"""
import uuid
from datetime import datetime, timedelta, date
from typing import Any

from sqlalchemy import func, case as sql_case, and_, extract
from sqlalchemy.orm import Session

from app.db.models import Case, CaseStatusHistory
from app.db.enums import CaseStatus, CaseSource, OwnerType


# ============================================================================
# Cases Trend (Time Series)
# ============================================================================

def get_cases_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    owner_id: uuid.UUID | None = None,
    group_by: str = "day",  # day, week, month
) -> list[dict[str, Any]]:
    """Get new cases created over time."""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Build base query
    query = db.query(Case).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        func.date(Case.created_at) >= start_date,
        func.date(Case.created_at) <= end_date,
    )
    
    if source:
        query = query.filter(Case.source == source)
    if owner_id:
        query = query.filter(
            Case.owner_type == OwnerType.USER.value,
            Case.owner_id == owner_id,
        )
    
    # Group by time period
    if group_by == "week":
        date_trunc = func.date_trunc("week", Case.created_at)
    elif group_by == "month":
        date_trunc = func.date_trunc("month", Case.created_at)
    else:
        date_trunc = func.date(Case.created_at)
    
    results = db.query(
        date_trunc.label("period"),
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        func.date(Case.created_at) >= start_date,
        func.date(Case.created_at) <= end_date,
    )
    
    if source:
        results = results.filter(Case.source == source)
    if owner_id:
        results = results.filter(
            Case.owner_type == OwnerType.USER.value,
            Case.owner_id == owner_id,
        )
    
    results = results.group_by(date_trunc).order_by(date_trunc).all()
    
    return [
        {
            "period": r.period.isoformat() if hasattr(r.period, 'isoformat') else str(r.period),
            "count": r.count,
        }
        for r in results
    ]


# ============================================================================
# Cases by Status
# ============================================================================

def get_cases_by_status(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
) -> dict[str, int]:
    """Get current case count by status."""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    query = db.query(
        Case.status,
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if source:
        query = query.filter(Case.source == source)
    
    results = query.group_by(Case.status).all()
    
    return {r.status: r.count for r in results}


def get_status_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get status distribution over time (using status history)."""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Get status changes over time
    results = db.query(
        func.date(CaseStatusHistory.changed_at).label("date"),
        CaseStatusHistory.new_status,
        func.count(CaseStatusHistory.id).label("count"),
    ).filter(
        CaseStatusHistory.changed_at >= start_date,
        CaseStatusHistory.changed_at <= end_date,
    ).group_by(
        func.date(CaseStatusHistory.changed_at),
        CaseStatusHistory.new_status,
    ).order_by(func.date(CaseStatusHistory.changed_at)).all()
    
    # Transform to chart format
    data_by_date: dict[str, dict[str, int]] = {}
    for r in results:
        date_str = r.date.isoformat()
        if date_str not in data_by_date:
            data_by_date[date_str] = {}
        status_val = r.new_status if isinstance(r.new_status, str) else r.new_status.value
        data_by_date[date_str][status_val] = r.count
    
    return [
        {"date": d, **statuses}
        for d, statuses in sorted(data_by_date.items())
    ]


# ============================================================================
# Cases by State (Geographic)
# ============================================================================

def get_cases_by_state(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Get case count by US state."""
    query = db.query(
        Case.state,
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        Case.state.isnot(None),
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    if source:
        query = query.filter(Case.source == source)
    
    results = query.group_by(Case.state).order_by(func.count(Case.id).desc()).all()
    
    return [
        {"state": r.state, "count": r.count}
        for r in results
    ]


# ============================================================================
# Cases by Source
# ============================================================================

def get_cases_by_source(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get case count by lead source."""
    query = db.query(
        Case.source,
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    
    results = query.group_by(Case.source).order_by(func.count(Case.id).desc()).all()
    
    return [
        {"source": r.source, "count": r.count}
        for r in results
    ]


# ============================================================================
# Cases by User (Owner)
# ============================================================================

def get_cases_by_user(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get case count by owner (user-owned cases only)."""
    from app.db.models import User
    
    query = db.query(
        Case.owner_id,
        User.full_name,
        func.count(Case.id).label("count"),
    ).outerjoin(
        User, Case.owner_id == User.id
    ).filter(
        Case.organization_id == organization_id,
        Case.owner_type == OwnerType.USER.value,
        Case.is_archived == False,
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    
    results = query.group_by(
        Case.owner_id, User.full_name
    ).order_by(func.count(Case.id).desc()).all()
    
    return [
        {
            "user_id": str(r.owner_id) if r.owner_id else None,
            "user_name": r.full_name or "Unassigned",
            "count": r.count,
        }
        for r in results
    ]


# ============================================================================
# Conversion Funnel
# ============================================================================

def get_conversion_funnel(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get conversion funnel data."""
    # Define funnel stages in order (matching actual CaseStatus values)
    funnel_stages = [
        ("new_unread", "New Leads"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("pending_match", "Matched"),
        ("meds_started", "Active"),
    ]
    
    query = db.query(Case).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    
    # Count cases that reached each stage
    total = query.count()
    
    funnel_data = []
    for status_value, label in funnel_stages:
        # Count cases currently at or past this stage
        count = query.filter(Case.status == status_value).count()
        funnel_data.append({
            "stage": status_value,
            "label": label,
            "count": count,
            "percentage": round((count / total * 100) if total > 0 else 0, 1),
        })
    
    return funnel_data


# ============================================================================
# Summary KPIs
# ============================================================================

def get_summary_kpis(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Get summary KPIs for dashboard cards."""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Previous period for comparison
    period_days = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)
    
    # Current period
    current = db.query(func.count(Case.id)).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        func.date(Case.created_at) >= start_date,
        func.date(Case.created_at) <= end_date,
    ).scalar() or 0
    
    # Previous period
    previous = db.query(func.count(Case.id)).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        func.date(Case.created_at) >= prev_start,
        func.date(Case.created_at) <= prev_end,
    ).scalar() or 0
    
    # Calculate change
    if previous > 0:
        change_pct = round((current - previous) / previous * 100, 1)
    else:
        change_pct = 100 if current > 0 else 0
    
    # Total active cases
    total_active = db.query(func.count(Case.id)).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    ).scalar() or 0
    
    # Cases needing attention (not contacted in 7+ days)
    stale_date = datetime.utcnow() - timedelta(days=7)
    needs_attention = db.query(func.count(Case.id)).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        Case.status.in_(["new_unread", "contacted"]),
        (Case.last_contacted_at.is_(None)) | (Case.last_contacted_at < stale_date),
    ).scalar() or 0
    
    return {
        "new_cases": current,
        "new_cases_change_pct": change_pct,
        "total_active": total_active,
        "needs_attention": needs_attention,
        "period_days": period_days,
    }


# ============================================================================
# Campaign Filter
# ============================================================================

def get_campaigns(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Get unique meta_ad_id values for campaign filter dropdown."""
    # Get from cases table where meta_ad_id is set
    results = db.query(
        Case.meta_ad_id,
        func.count(Case.id).label("case_count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.meta_ad_id.isnot(None),
        Case.is_archived == False,
    ).group_by(
        Case.meta_ad_id
    ).order_by(func.count(Case.id).desc()).all()
    
    return [
        {
            "ad_id": r.meta_ad_id,
            "ad_name": f"Campaign {r.meta_ad_id[:8]}..." if len(r.meta_ad_id) > 8 else r.meta_ad_id,
            "lead_count": r.case_count,
        }
        for r in results
    ]


def get_funnel_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get conversion funnel data with optional campaign filter."""
    funnel_stages = [
        ("lead_new", "New Leads"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("matched", "Matched"),
        ("active", "Active"),
    ]
    
    query = db.query(Case).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    if ad_id:
        query = query.filter(Case.meta_ad_id == ad_id)
    
    total = query.count()
    
    funnel_data = []
    for status_value, label in funnel_stages:
        count = query.filter(Case.status == status_value).count()
        funnel_data.append({
            "stage": status_value,
            "label": label,
            "count": count,
            "percentage": round((count / total * 100) if total > 0 else 0, 1),
        })
    
    return funnel_data


def get_cases_by_state_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get case count by US state with optional campaign filter."""
    query = db.query(
        Case.state,
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        Case.state.isnot(None),
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    if ad_id:
        query = query.filter(Case.meta_ad_id == ad_id)
    
    results = query.group_by(Case.state).order_by(func.count(Case.id).desc()).all()
    
    return [
        {"state": r.state, "count": r.count}
        for r in results
    ]
