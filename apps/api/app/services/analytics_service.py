"""Analytics service for Reports dashboard.

Provides query functions for case trends, status distributions, and geographic data.
Works without AI - purely script-generated aggregations.
"""
import uuid
from datetime import datetime, timedelta, date
from typing import Any

from sqlalchemy import func, case as sql_case, and_, extract
from sqlalchemy.orm import Session

from app.db.models import Case, CaseStatusHistory, PipelineStage
from app.db.enums import CaseSource, OwnerType


# ============================================================================
# Cases Trend (Time Series)
# ============================================================================

FUNNEL_SLUGS = [
    "new_unread",
    "contacted",
    "qualified",
    "pending_match",
    "matched",
    "meds_started",
]


def _get_default_pipeline_stages(db: Session, organization_id: uuid.UUID) -> list[PipelineStage]:
    """Get active stages for the default pipeline."""
    from app.services import pipeline_service
    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    return pipeline_service.get_stages(db, pipeline.id, include_inactive=True)

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
        Case.status_label,
        func.count(Case.id).label("count"),
    ).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if source:
        query = query.filter(Case.source == source)
    
    results = query.group_by(Case.status_label).all()
    
    return {r.status_label: r.count for r in results}


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
        func.coalesce(CaseStatusHistory.to_label_snapshot, "unknown").label("status_label"),
        func.count(CaseStatusHistory.id).label("count"),
    ).filter(
        CaseStatusHistory.organization_id == organization_id,
        CaseStatusHistory.changed_at >= start_date,
        CaseStatusHistory.changed_at <= end_date,
    ).group_by(
        func.date(CaseStatusHistory.changed_at),
        func.coalesce(CaseStatusHistory.to_label_snapshot, "unknown"),
    ).order_by(func.date(CaseStatusHistory.changed_at)).all()
    
    # Transform to chart format
    data_by_date: dict[str, dict[str, int]] = {}
    for r in results:
        date_str = r.date.isoformat()
        if date_str not in data_by_date:
            data_by_date[date_str] = {}
        data_by_date[date_str][r.status_label] = r.count
    
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
    stages = _get_default_pipeline_stages(db, organization_id)
    stage_by_slug = {s.slug: s for s in stages if s.is_active}
    funnel_stages = [stage_by_slug[slug] for slug in FUNNEL_SLUGS if slug in stage_by_slug]
    if not funnel_stages:
        funnel_stages = sorted(
            [s for s in stages if s.is_active],
            key=lambda s: s.order
        )[:5]
    
    query = db.query(Case).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
    )
    
    if start_date:
        query = query.filter(func.date(Case.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(Case.created_at) <= end_date)
    
    active_stages = [s for s in stages if s.is_active]
    total = query.count()
    
    funnel_data = []
    for stage in funnel_stages:
        eligible_stage_ids = [s.id for s in active_stages if s.order >= stage.order]
        count = query.filter(Case.stage_id.in_(eligible_stage_ids)).count()
        funnel_data.append({
            "stage": stage.slug,
            "label": stage.label,
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
    stages = _get_default_pipeline_stages(db, organization_id)
    stage_by_slug = {s.slug: s for s in stages if s.is_active}
    attention_stage_ids = [
        s.id for s in [
            stage_by_slug.get("new_unread"),
            stage_by_slug.get("contacted"),
        ] if s
    ]
    if not attention_stage_ids and stages:
        attention_stage_ids = [s.id for s in sorted(stages, key=lambda s: s.order)[:2]]

    needs_attention = db.query(func.count(Case.id)).filter(
        Case.organization_id == organization_id,
        Case.is_archived == False,
        Case.stage_id.in_(attention_stage_ids),
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
    stages = _get_default_pipeline_stages(db, organization_id)
    stage_by_slug = {s.slug: s for s in stages if s.is_active}
    funnel_stages = [stage_by_slug[slug] for slug in FUNNEL_SLUGS if slug in stage_by_slug]
    if not funnel_stages:
        funnel_stages = sorted(
            [s for s in stages if s.is_active],
            key=lambda s: s.order
        )[:5]
    
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
    
    active_stages = [s for s in stages if s.is_active]
    total = query.count()
    
    funnel_data = []
    for stage in funnel_stages:
        eligible_stage_ids = [s.id for s in active_stages if s.order >= stage.order]
        count = query.filter(Case.stage_id.in_(eligible_stage_ids)).count()
        funnel_data.append({
            "stage": stage.slug,
            "label": stage.label,
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
