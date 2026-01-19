"""Analytics service for Reports dashboard.

Provides query functions for surrogate trends, status distributions, and geographic data.
Works without AI - purely script-generated aggregations.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Callable, Literal

from sqlalchemy import func, text, exists, and_, select, case, literal, or_
from sqlalchemy.orm import Session, aliased

from app.core.config import settings

from app.db.models import (
    AnalyticsSnapshot,
    Surrogate,
    SurrogateStatusHistory,
    MetaAdAccount,
    MetaCampaign,
    MetaDailySpend,
    MetaForm,
    MetaLead,
    Membership,
    PipelineStage,
    User,
)
from app.db.enums import OwnerType


# ============================================================================
# Surrogates Trend (Time Series)
# ============================================================================

FUNNEL_SLUGS = [
    "new_unread",
    "contacted",
    "qualified",
    "ready_to_match",
    "matched",
    "medical_clearance_passed",
]


def _build_snapshot_key(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_cached_snapshot(
    db: Session,
    org_id: uuid.UUID,
    snapshot_type: str,
    snapshot_key: str,
) -> Any | None:
    if settings.ANALYTICS_CACHE_TTL_SECONDS <= 0:
        return None
    now = datetime.now(timezone.utc)
    snapshot = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.organization_id == org_id,
            AnalyticsSnapshot.snapshot_type == snapshot_type,
            AnalyticsSnapshot.snapshot_key == snapshot_key,
        )
        .first()
    )
    if not snapshot:
        return None
    if snapshot.expires_at and snapshot.expires_at <= now:
        return None
    return snapshot.payload


def _store_snapshot(
    db: Session,
    org_id: uuid.UUID,
    snapshot_type: str,
    snapshot_key: str,
    payload: Any,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> None:
    if settings.ANALYTICS_CACHE_TTL_SECONDS <= 0:
        return
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.ANALYTICS_CACHE_TTL_SECONDS)
    snapshot = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.organization_id == org_id,
            AnalyticsSnapshot.snapshot_type == snapshot_type,
            AnalyticsSnapshot.snapshot_key == snapshot_key,
        )
        .first()
    )
    if snapshot:
        snapshot.payload = payload
        snapshot.range_start = range_start
        snapshot.range_end = range_end
        snapshot.expires_at = expires_at
        snapshot.created_at = now
    else:
        snapshot = AnalyticsSnapshot(
            organization_id=org_id,
            snapshot_type=snapshot_type,
            snapshot_key=snapshot_key,
            payload=payload,
            range_start=range_start,
            range_end=range_end,
            created_at=now,
            expires_at=expires_at,
        )
        db.add(snapshot)
    db.commit()


def _get_or_compute_snapshot(
    db: Session,
    org_id: uuid.UUID,
    snapshot_type: str,
    params: dict[str, Any],
    compute: Callable[[], Any],
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> Any:
    snapshot_key = _build_snapshot_key({"snapshot_type": snapshot_type, **params})
    cached = _get_cached_snapshot(db, org_id, snapshot_type, snapshot_key)
    if cached is not None:
        return cached
    payload = compute()
    _store_snapshot(
        db,
        org_id,
        snapshot_type,
        snapshot_key,
        payload,
        range_start=range_start,
        range_end=range_end,
    )
    return payload


async def _get_or_compute_snapshot_async(
    db: Session,
    org_id: uuid.UUID,
    snapshot_type: str,
    params: dict[str, Any],
    compute,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> Any:
    snapshot_key = _build_snapshot_key({"snapshot_type": snapshot_type, **params})
    cached = _get_cached_snapshot(db, org_id, snapshot_type, snapshot_key)
    if cached is not None:
        return cached
    payload = await compute()
    _store_snapshot(
        db,
        org_id,
        snapshot_type,
        snapshot_key,
        payload,
        range_start=range_start,
        range_end=range_end,
    )
    return payload


def _get_default_pipeline_stages(db: Session, organization_id: uuid.UUID) -> list[PipelineStage]:
    """Get active stages for the default pipeline."""
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    return pipeline_service.get_stages(db, pipeline.id, include_inactive=True)


def parse_date_range(
    from_date: str | None,
    to_date: str | None,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    """Parse ISO date strings to a datetime range with defaults."""
    if to_date:
        end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
    else:
        end = datetime.now(timezone.utc)

    if from_date:
        start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
    else:
        start = end - timedelta(days=default_days)

    return start, end


def _normalize_date_bounds(
    start_date: date | None,
    end_date: date | None,
) -> tuple[datetime | None, datetime | None]:
    if not start_date and not end_date:
        return None, None
    start_dt = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    end_dt = (
        datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        if end_date
        else None
    )
    return start_dt, end_dt


def _apply_date_range_filters(query, column, start_date: date | None, end_date: date | None):
    start_dt, end_dt = _normalize_date_bounds(start_date, end_date)
    if start_dt:
        query = query.filter(column >= start_dt)
    if end_dt:
        query = query.filter(column < end_dt)
    return query


def get_cached_analytics_summary(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "summary",
        params,
        lambda: get_analytics_summary(db, organization_id, start, end),
        range_start=start,
        range_end=end,
    )


def get_analytics_summary(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Get high-level analytics summary."""
    from app.services import pipeline_service

    total_surrogates = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
        .scalar()
        or 0
    )

    new_this_period = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
            Surrogate.created_at >= start,
            Surrogate.created_at < end,
        )
        .scalar()
        or 0
    )

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
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

    qualified_count = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
            Surrogate.stage_id.in_(qualified_stage_ids),
        )
        .scalar()
        or 0
    )

    qualified_rate = (qualified_count / total_surrogates * 100) if total_surrogates > 0 else 0.0

    avg_time_to_qualified_hours = None
    if qualified_stage:
        result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - c.created_at)) / 3600) as avg_hours
                FROM surrogates c
                JOIN surrogate_status_history csh ON c.id = csh.surrogate_id
                WHERE c.organization_id = :org_id
                  AND c.is_archived = false
                  AND csh.to_stage_id = :qualified_stage_id
                  AND csh.changed_at >= :start
                  AND csh.changed_at < :end
            """),
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "qualified_stage_id": qualified_stage.id,
            },
        )
        row = result.fetchone()
        avg_time_to_qualified_hours = float(round(row[0], 1)) if row and row[0] else None

    return {
        "total_surrogates": total_surrogates,
        "new_this_period": new_this_period,
        "qualified_rate": round(qualified_rate, 1),
        "avg_time_to_qualified_hours": avg_time_to_qualified_hours,
    }


def get_surrogates_trend(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    source: str | None = None,
    owner_id: uuid.UUID | None = None,
    pipeline_id: uuid.UUID | None = None,
    group_by: str = "day",  # day, week, month
) -> list[dict[str, Any]]:
    """Get new surrogates created over time."""
    if not end:
        end = datetime.now(timezone.utc)
    if not start:
        start = end - timedelta(days=30)

    # Group by time period
    if group_by == "week":
        date_trunc = func.date_trunc("week", Surrogate.created_at)
    elif group_by == "month":
        date_trunc = func.date_trunc("month", Surrogate.created_at)
    else:
        date_trunc = func.date(Surrogate.created_at)

    results = db.query(
        date_trunc.label("period"),
        func.count(Surrogate.id).label("count"),
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
        Surrogate.created_at >= start,
        Surrogate.created_at < end,
    )

    if source:
        results = results.filter(Surrogate.source == source)
    if owner_id:
        results = results.filter(
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == owner_id,
        )
    if pipeline_id:
        results = results.join(PipelineStage, Surrogate.stage_id == PipelineStage.id).filter(
            PipelineStage.pipeline_id == pipeline_id
        )

    results = results.group_by(date_trunc).order_by(date_trunc).all()

    trend = []
    for row in results:
        if isinstance(row.period, datetime):
            period_str = row.period.strftime("%Y-%m-%d")
        elif isinstance(row.period, date):
            period_str = row.period.isoformat()
        else:
            period_str = str(row.period)
        trend.append({"date": period_str, "count": row.count})

    return trend


def get_cached_surrogates_trend(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
    group_by: str = "day",
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "group_by": group_by,
        "pipeline_id": str(pipeline_id) if pipeline_id else None,
        "owner_id": str(owner_id) if owner_id else None,
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_trend",
        params,
        lambda: get_surrogates_trend(
            db,
            organization_id,
            start=start,
            end=end,
            group_by=group_by,
            pipeline_id=pipeline_id,
            owner_id=owner_id,
        ),
        range_start=start,
        range_end=end,
    )


# ============================================================================
# Cases by Status
# ============================================================================


def get_surrogates_by_status(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Get current case count by status with stage metadata."""
    # Join with PipelineStage to get stage_id and order
    query = db.query(
        PipelineStage.label.label("status"),
        PipelineStage.id.label("stage_id"),
        PipelineStage.order.label("stage_order"),
        func.count(Surrogate.id).label("count"),
    ).join(
        Surrogate, Surrogate.stage_id == PipelineStage.id
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if source:
        query = query.filter(Surrogate.source == source)
    if pipeline_id:
        query = query.filter(PipelineStage.pipeline_id == pipeline_id)
    if owner_id:
        query = query.filter(
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.owner_id == owner_id,
        )

    results = (
        query.group_by(PipelineStage.id, PipelineStage.label, PipelineStage.order)
        .order_by(PipelineStage.order)
        .all()
    )

    return [
        {
            "status": r.status,
            "stage_id": str(r.stage_id),
            "count": r.count,
            "order": r.stage_order,
        }
        for r in results
    ]


def get_cached_surrogates_by_status(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
    pipeline_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "source": source,
        "pipeline_id": str(pipeline_id) if pipeline_id else None,
        "owner_id": str(owner_id) if owner_id else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_status",
        params,
        lambda: get_surrogates_by_status(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            source=source,
            pipeline_id=pipeline_id,
            owner_id=owner_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


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
    query = db.query(
        func.date(SurrogateStatusHistory.changed_at).label("date"),
        func.coalesce(SurrogateStatusHistory.to_label_snapshot, "unknown").label("status_label"),
        func.count(SurrogateStatusHistory.id).label("count"),
    ).filter(SurrogateStatusHistory.organization_id == organization_id)
    query = _apply_date_range_filters(query, SurrogateStatusHistory.changed_at, start_date, end_date)
    results = (
        query.group_by(
            func.date(SurrogateStatusHistory.changed_at),
            func.coalesce(SurrogateStatusHistory.to_label_snapshot, "unknown"),
        )
        .order_by(func.date(SurrogateStatusHistory.changed_at))
        .all()
    )

    # Transform to chart format
    data_by_date: dict[str, dict[str, int]] = {}
    for r in results:
        date_str = r.date.isoformat()
        if date_str not in data_by_date:
            data_by_date[date_str] = {}
        data_by_date[date_str][r.status_label] = r.count

    return [{"date": d, **statuses} for d, statuses in sorted(data_by_date.items())]


# ============================================================================
# Cases by State (Geographic)
# ============================================================================


def get_surrogates_by_state(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Get case count by US state."""
    query = db.query(
        Surrogate.state,
        func.count(Surrogate.id).label("count"),
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
        Surrogate.state.isnot(None),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if source:
        query = query.filter(Surrogate.source == source)

    results = query.group_by(Surrogate.state).order_by(func.count(Surrogate.id).desc()).all()

    return [{"state": r.state, "count": r.count} for r in results]


def get_cached_surrogates_by_state(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "source": source,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_state",
        params,
        lambda: get_surrogates_by_state(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            source=source,
        ),
        range_start=range_start,
        range_end=range_end,
    )


# ============================================================================
# Cases by Source
# ============================================================================


def get_surrogates_by_source(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get case count by lead source."""
    query = db.query(
        Surrogate.source,
        func.count(Surrogate.id).label("count"),
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)

    results = query.group_by(Surrogate.source).order_by(func.count(Surrogate.id).desc()).all()

    return [{"source": r.source, "count": r.count} for r in results]


def get_cached_surrogates_by_source(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_source",
        params,
        lambda: get_surrogates_by_source(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
        ),
        range_start=range_start,
        range_end=range_end,
    )


# ============================================================================
# Cases by User (Owner)
# ============================================================================


def get_surrogates_by_user(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get surrogate count by owner (user-owned surrogates only)."""
    from app.db.models import User

    query = (
        db.query(
            Surrogate.owner_id,
            User.full_name,
            func.count(Surrogate.id).label("count"),
        )
        .outerjoin(User, Surrogate.owner_id == User.id)
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.is_archived.is_(False),
        )
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)

    results = (
        query.group_by(Surrogate.owner_id, User.full_name)
        .order_by(func.count(Surrogate.id).desc())
        .all()
    )

    return [
        {
            "user_id": str(r.owner_id) if r.owner_id else None,
            "user_name": r.full_name or "Unassigned",
            "count": r.count,
        }
        for r in results
    ]


def get_surrogates_by_assignee(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    label: str = "email",
) -> list[dict[str, Any]]:
    """Get surrogate count by assignee (user-owned surrogates only)."""
    from app.db.models import User

    label_column = User.email if label == "email" else User.display_name
    label_key = "user_email" if label == "email" else "display_name"

    query = (
        db.query(
            Surrogate.owner_id,
            label_column.label("label"),
            func.count(Surrogate.id).label("count"),
        )
        .outerjoin(User, Surrogate.owner_id == User.id)
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.owner_type == OwnerType.USER.value,
            Surrogate.is_archived.is_(False),
        )
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)

    results = (
        query.group_by(Surrogate.owner_id, label_column)
        .order_by(func.count(Surrogate.id).desc())
        .all()
    )

    payload = []
    for row in results:
        label_value = row.label
        if label == "display_name" and not label_value:
            label_value = "Unassigned"
        payload.append(
            {
                "user_id": str(row.owner_id) if row.owner_id else None,
                label_key: label_value,
                "count": row.count,
            }
        )

    return payload


def get_cached_surrogates_by_assignee(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    label: str = "email",
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "label": label,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_assignee",
        params,
        lambda: get_surrogates_by_assignee(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            label=label,
        ),
        range_start=range_start,
        range_end=range_end,
    )


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
        funnel_stages = sorted([s for s in stages if s.is_active], key=lambda s: s.order)[:5]

    query = db.query(Surrogate).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)

    active_stages = [s for s in stages if s.is_active]
    counts_by_stage = dict(
        query.with_entities(Surrogate.stage_id, func.count(Surrogate.id))
        .group_by(Surrogate.stage_id)
        .all()
    )
    total = sum(counts_by_stage.values())

    funnel_data = []
    for stage in funnel_stages:
        eligible_stage_ids = [s.id for s in active_stages if s.order >= stage.order]
        count = sum(counts_by_stage.get(stage_id, 0) for stage_id in eligible_stage_ids)
        funnel_data.append(
            {
                "stage": stage.slug,
                "label": stage.label,
                "count": count,
                "percentage": round((count / total * 100) if total > 0 else 0, 1),
            }
        )

    return funnel_data


def get_cached_conversion_funnel(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "conversion_funnel",
        params,
        lambda: get_conversion_funnel(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
        ),
        range_start=range_start,
        range_end=range_end,
    )


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
    current_query = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
    )
    current_query = _apply_date_range_filters(
        current_query,
        Surrogate.created_at,
        start_date,
        end_date,
    )
    current = current_query.scalar() or 0

    # Previous period
    previous_query = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
    )
    previous_query = _apply_date_range_filters(
        previous_query,
        Surrogate.created_at,
        prev_start,
        prev_end,
    )
    previous = previous_query.scalar() or 0

    # Calculate change
    if previous > 0:
        change_pct = round((current - previous) / previous * 100, 1)
    else:
        change_pct = 100 if current > 0 else 0

    # Total active surrogates
    total_active = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
        .scalar()
        or 0
    )

    # Cases needing attention (not contacted in 7+ days)
    stale_date = datetime.now(timezone.utc) - timedelta(days=7)
    stages = _get_default_pipeline_stages(db, organization_id)
    stage_by_slug = {s.slug: s for s in stages if s.is_active}
    attention_stage_ids = [
        s.id
        for s in [
            stage_by_slug.get("new_unread"),
            stage_by_slug.get("contacted"),
        ]
        if s
    ]
    if not attention_stage_ids and stages:
        attention_stage_ids = [s.id for s in sorted(stages, key=lambda s: s.order)[:2]]

    needs_attention = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
            Surrogate.stage_id.in_(attention_stage_ids),
            (Surrogate.last_contacted_at.is_(None)) | (Surrogate.last_contacted_at < stale_date),
        )
        .scalar()
        or 0
    )

    return {
        "new_surrogates": current,
        "new_surrogates_change_pct": change_pct,
        "total_active": total_active,
        "needs_attention": needs_attention,
        "period_days": period_days,
    }


def get_cached_summary_kpis(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "summary_kpis",
        params,
        lambda: get_summary_kpis(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_meta_performance(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Get Meta Lead Ads performance metrics."""
    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    converted_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "application_submitted")

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

    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)
    leads_received = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == organization_id,
            lead_time >= start,
            lead_time < end,
        )
        .count()
    )

    leads_qualified = 0
    if qualified_or_later_ids:
        leads_qualified = (
            db.execute(
                text("""
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
                {
                    "org_id": organization_id,
                    "start": start,
                    "end": end,
                    "stage_ids": qualified_or_later_ids,
                },
            ).scalar()
            or 0
        )

    leads_converted = 0
    if converted_or_later_ids:
        leads_converted = (
            db.execute(
                text("""
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
                {
                    "org_id": organization_id,
                    "start": start,
                    "end": end,
                    "stage_ids": converted_or_later_ids,
                },
            ).scalar()
            or 0
        )

    qualification_rate = (leads_qualified / leads_received * 100) if leads_received > 0 else 0.0
    conversion_rate = (leads_converted / leads_received * 100) if leads_received > 0 else 0.0

    avg_hours = None
    if converted_stage:
        result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - COALESCE(ml.meta_created_time, ml.received_at))) / 3600) as avg_hours
                FROM meta_leads ml
                JOIN surrogates c ON ml.converted_surrogate_id = c.id
                JOIN surrogate_status_history csh ON c.id = csh.surrogate_id AND csh.to_stage_id = :converted_stage_id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
            """),
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "converted_stage_id": converted_stage.id,
            },
        )
        row = result.fetchone()
        avg_hours = float(round(row[0], 1)) if row and row[0] else None

    return {
        "leads_received": leads_received,
        "leads_qualified": leads_qualified,
        "leads_converted": leads_converted,
        "qualification_rate": round(qualification_rate, 1),
        "conversion_rate": round(conversion_rate, 1),
        "avg_time_to_convert_hours": avg_hours,
    }


def get_cached_meta_performance(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "meta_performance",
        params,
        lambda: get_meta_performance(db, organization_id, start, end),
        range_start=start,
        range_end=end,
    )


# ============================================================================
# Campaign Filter
# ============================================================================


def get_campaigns(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Get unique meta_ad_external_id values for campaign filter dropdown."""
    # Get from surrogates table where meta_ad_external_id is set
    results = (
        db.query(
            Surrogate.meta_ad_external_id,
            func.count(Surrogate.id).label("surrogate_count"),
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.meta_ad_external_id.isnot(None),
            Surrogate.is_archived.is_(False),
        )
        .group_by(Surrogate.meta_ad_external_id)
        .order_by(func.count(Surrogate.id).desc())
        .all()
    )

    return [
        {
            "ad_id": r.meta_ad_external_id,
            "ad_name": f"Campaign {r.meta_ad_external_id[:8]}..."
            if len(r.meta_ad_external_id) > 8
            else r.meta_ad_external_id,
            "lead_count": r.surrogate_count,
        }
        for r in results
    ]


def get_cached_campaigns(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "campaigns",
        {"scope": "all"},
        lambda: get_campaigns(db, organization_id),
    )


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
        funnel_stages = sorted([s for s in stages if s.is_active], key=lambda s: s.order)[:5]

    query = db.query(Surrogate).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if ad_id:
        query = query.filter(Surrogate.meta_ad_external_id == ad_id)

    active_stages = [s for s in stages if s.is_active]
    counts_by_stage = dict(
        query.with_entities(Surrogate.stage_id, func.count(Surrogate.id))
        .group_by(Surrogate.stage_id)
        .all()
    )
    total = sum(counts_by_stage.values())

    funnel_data = []
    for stage in funnel_stages:
        eligible_stage_ids = [s.id for s in active_stages if s.order >= stage.order]
        count = sum(counts_by_stage.get(stage_id, 0) for stage_id in eligible_stage_ids)
        funnel_data.append(
            {
                "stage": stage.slug,
                "label": stage.label,
                "count": count,
                "percentage": round((count / total * 100) if total > 0 else 0, 1),
            }
        )

    return funnel_data


def get_cached_funnel_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "ad_id": ad_id,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "funnel_compare",
        params,
        lambda: get_funnel_with_filter(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            ad_id=ad_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_surrogates_by_state_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get case count by US state with optional campaign filter."""
    query = db.query(
        Surrogate.state,
        func.count(Surrogate.id).label("count"),
    ).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
        Surrogate.state.isnot(None),
    )

    query = _apply_date_range_filters(query, Surrogate.created_at, start_date, end_date)
    if ad_id:
        query = query.filter(Surrogate.meta_ad_external_id == ad_id)

    results = query.group_by(Surrogate.state).order_by(func.count(Surrogate.id).desc()).all()

    return [{"state": r.state, "count": r.count} for r in results]


def get_cached_surrogates_by_state_with_filter(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    ad_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "ad_id": ad_id,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "surrogates_by_state_compare",
        params,
        lambda: get_surrogates_by_state_with_filter(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            ad_id=ad_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


async def get_meta_spend_summary(
    start: datetime,
    end: datetime,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> dict[str, Any]:
    from app.core.config import settings
    from app.services import meta_api

    ad_account_id = settings.META_AD_ACCOUNT_ID
    access_token = settings.META_SYSTEM_TOKEN

    if not settings.META_TEST_MODE and (not ad_account_id or not access_token):
        return {
            "total_spend": 0.0,
            "total_impressions": 0,
            "total_leads": 0,
            "cost_per_lead": None,
            "campaigns": [],
            "time_series": [],
            "breakdowns": [],
        }

    date_start = start.strftime("%Y-%m-%d")
    date_end = end.strftime("%Y-%m-%d")

    insights, error = await meta_api.fetch_ad_account_insights(
        ad_account_id=ad_account_id or "act_mock",
        access_token=access_token or "mock_token",
        date_start=date_start,
        date_end=date_end,
        level="campaign",
        time_increment=time_increment,
        breakdowns=breakdowns or None,
    )

    if error or not insights:
        return {
            "total_spend": 0.0,
            "total_impressions": 0,
            "total_leads": 0,
            "cost_per_lead": None,
            "campaigns": [],
            "time_series": [],
            "breakdowns": [],
        }

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
            return int(float(val))
        except (ValueError, TypeError):
            return default

    lead_action_types = {
        "lead",
        "leadgen",
        "onsite_conversion.lead_grouped",
        "offsite_conversion.fb_pixel_lead",
    }

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

        leads = 0
        actions = insight.get("actions") or []
        for action in actions:
            action_type = action.get("action_type", "")
            if action_type in lead_action_types:
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

        if breakdowns:
            breakdown_values = {key: str(insight.get(key, "unknown")) for key in breakdowns}
            breakdown_key = tuple(breakdown_values.get(key, "unknown") for key in breakdowns)
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
    for totals in campaigns_by_id.values():
        campaign_spend = float(totals["spend"])
        campaign_leads = int(totals["leads"])
        cpl = round(campaign_spend / campaign_leads, 2) if campaign_leads > 0 else None
        campaigns.append(
            {
                "campaign_id": str(totals["campaign_id"]),
                "campaign_name": str(totals["campaign_name"]),
                "spend": campaign_spend,
                "impressions": int(totals["impressions"]),
                "reach": int(totals["reach"]),
                "clicks": int(totals["clicks"]),
                "leads": campaign_leads,
                "cost_per_lead": cpl,
            }
        )

    time_series_points = []
    if time_increment:
        for (start_key, stop_key), totals in sorted(time_series.items()):
            point_spend = float(totals["spend"])
            point_leads = int(totals["leads"])
            point_cpl = round(point_spend / point_leads, 2) if point_leads > 0 else None
            time_series_points.append(
                {
                    "date_start": start_key,
                    "date_stop": stop_key,
                    "spend": point_spend,
                    "impressions": int(totals["impressions"]),
                    "reach": int(totals["reach"]),
                    "clicks": int(totals["clicks"]),
                    "leads": point_leads,
                    "cost_per_lead": point_cpl,
                }
            )

    breakdown_points = []
    if breakdowns:
        for breakdown in breakdown_totals.values():
            breakdown_spend = float(breakdown["spend"])
            breakdown_leads = int(breakdown["leads"])
            breakdown_cpl = (
                round(breakdown_spend / breakdown_leads, 2) if breakdown_leads > 0 else None
            )
            breakdown_points.append(
                {
                    "breakdown_values": breakdown["breakdown_values"],
                    "spend": breakdown_spend,
                    "impressions": int(breakdown["impressions"]),
                    "reach": int(breakdown["reach"]),
                    "clicks": int(breakdown["clicks"]),
                    "leads": breakdown_leads,
                    "cost_per_lead": breakdown_cpl,
                }
            )

    breakdown_points.sort(key=lambda item: item["spend"], reverse=True)

    return {
        "total_spend": round(total_spend, 2),
        "total_impressions": total_impressions,
        "total_leads": total_leads,
        "cost_per_lead": overall_cpl,
        "campaigns": campaigns,
        "time_series": time_series_points,
        "breakdowns": breakdown_points,
    }


async def get_cached_meta_spend_summary(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime,
    end: datetime,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> dict[str, Any]:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "time_increment": time_increment,
        "breakdowns": breakdowns or [],
    }
    return await _get_or_compute_snapshot_async(
        db,
        organization_id,
        "meta_spend",
        params,
        lambda: get_meta_spend_summary(
            start=start, end=end, time_increment=time_increment, breakdowns=breakdowns
        ),
        range_start=start,
        range_end=end,
    )


# =============================================================================
# Activity Feed
# =============================================================================


def get_activity_feed(
    db: Session,
    organization_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    activity_type: str | None = None,
    user_id: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Get org-wide activity feed entries."""
    from app.db.models import SurrogateActivityLog, User
    from sqlalchemy import desc

    query = (
        db.query(
            SurrogateActivityLog,
            Surrogate.surrogate_number,
            Surrogate.full_name.label("surrogate_name"),
            User.display_name.label("actor_name"),
        )
        .join(Surrogate, SurrogateActivityLog.surrogate_id == Surrogate.id)
        .outerjoin(User, SurrogateActivityLog.actor_user_id == User.id)
        .filter(SurrogateActivityLog.organization_id == organization_id)
    )

    if activity_type:
        query = query.filter(SurrogateActivityLog.activity_type == activity_type)

    if user_id:
        try:
            parsed_id = uuid.UUID(user_id)
            query = query.filter(SurrogateActivityLog.actor_user_id == parsed_id)
        except ValueError:
            pass

    query = query.order_by(desc(SurrogateActivityLog.created_at))
    query = query.offset(offset).limit(limit + 1)

    results = query.all()
    has_more = len(results) > limit
    items = results[:limit]

    return (
        [
            {
                "id": str(row.SurrogateActivityLog.id),
                "activity_type": row.SurrogateActivityLog.activity_type,
                "surrogate_id": str(row.SurrogateActivityLog.surrogate_id),
                "surrogate_number": row.surrogate_number,
                "surrogate_name": row.surrogate_name,
                "actor_name": row.actor_name,
                "details": row.SurrogateActivityLog.details,
                "created_at": row.SurrogateActivityLog.created_at.isoformat(),
            }
            for row in items
        ],
        has_more,
    )


# =============================================================================
# Analytics PDF Export
# =============================================================================


def get_pdf_export_data(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> dict[str, Any]:
    """Build analytics data used for PDF export."""
    from app.db.models import Task
    from app.db.enums import TaskType
    from app.services import pipeline_service, org_service

    date_filter = Surrogate.is_archived.is_(False)
    if start_dt:
        date_filter = date_filter & (Surrogate.created_at >= start_dt)
    if end_dt:
        date_filter = date_filter & (Surrogate.created_at <= end_dt)

    org = org_service.get_org_by_id(db, organization_id)
    org_name = org.name if org else "Organization"

    total_surrogates = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            date_filter,
        )
        .scalar()
        or 0
    )

    period_start = (end_dt or datetime.now(timezone.utc)) - timedelta(days=7)
    new_this_period = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
            Surrogate.created_at >= period_start,
        )
        .scalar()
        or 0
    )

    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")

    qualified_rate = 0.0
    if qualified_stage and total_surrogates > 0:
        qualified_stage_ids = db.query(PipelineStage.id).filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.order >= qualified_stage.order,
            PipelineStage.is_active.is_(True),
        )
        qualified_count = (
            db.query(func.count(Surrogate.id))
            .filter(
                Surrogate.organization_id == organization_id,
                Surrogate.is_archived.is_(False),
                Surrogate.stage_id.in_(qualified_stage_ids),
            )
            .scalar()
            or 0
        )
        qualified_rate = (qualified_count / total_surrogates) * 100

    pending_tasks = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == organization_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .scalar()
        or 0
    )

    overdue_tasks = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == organization_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
            Task.due_date < datetime.now(timezone.utc).date(),
        )
        .scalar()
        or 0
    )

    summary = {
        "total_surrogates": total_surrogates,
        "new_this_period": new_this_period,
        "qualified_rate": qualified_rate,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
    }

    surrogates_by_status = get_surrogates_by_status(db, organization_id)
    surrogates_by_assignee = get_surrogates_by_assignee(db, organization_id, label="display_name")

    trend_start = datetime.now(timezone.utc) - timedelta(days=30)
    trend_data = get_surrogates_trend(
        db,
        organization_id,
        start=trend_start,
        end=datetime.now(timezone.utc),
        group_by="day",
    )

    meta_start = start_dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
    meta_end = end_dt or datetime.now(timezone.utc)
    meta_performance = get_meta_performance(db, organization_id, meta_start, meta_end)

    # Get funnel data
    start_date = start_dt.date() if start_dt else None
    end_date = end_dt.date() if end_dt else None
    funnel_data = get_funnel_with_filter(
        db, organization_id, start_date=start_date, end_date=end_date
    )

    # Get state data for US map
    state_data = get_surrogates_by_state_with_filter(
        db, organization_id, start_date=start_date, end_date=end_date
    )

    # Get performance data
    performance_data = get_performance_by_user(
        db, organization_id, start_date=start_date, end_date=end_date
    )

    return {
        "summary": summary,
        "surrogates_by_status": surrogates_by_status,
        "surrogates_by_assignee": surrogates_by_assignee,
        "trend_data": trend_data,
        "meta_performance": meta_performance,
        "funnel_data": funnel_data,
        "state_data": state_data,
        "performance_data": performance_data,
        "org_name": org_name,
    }


# =============================================================================
# Individual Performance Analytics
# =============================================================================

# Stage slugs for performance metrics
PERFORMANCE_STAGE_SLUGS = [
    "contacted",
    "qualified",
    "ready_to_match",
    "matched",
    "application_submitted",
    "lost",
]


def get_performance_stage_ids(
    db: Session,
    pipeline_id: uuid.UUID,
) -> dict[str, uuid.UUID | None]:
    """
    Resolve performance stage slugs to IDs for a pipeline.

    Returns a dict mapping slug -> stage_id (None if stage not found).
    This is centralized to avoid slug drift issues.
    """
    from app.services import pipeline_service

    stage_ids: dict[str, uuid.UUID | None] = {}
    for slug in PERFORMANCE_STAGE_SLUGS:
        stage = pipeline_service.get_stage_by_slug(db, pipeline_id, slug)
        stage_ids[slug] = stage.id if stage else None

    return stage_ids


def get_performance_by_user(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    mode: Literal["cohort", "activity"] = "cohort",
) -> dict[str, Any]:
    """
    Get individual performance metrics by user.

    Args:
        db: Database session
        organization_id: Organization to query
        start_date: Start of date range (defaults to 30 days ago)
        end_date: End of date range (defaults to today)
        mode: 'cohort' (surrogates created in range) or 'activity' (status changes in range)

    Returns:
        Dict with user performance data, unassigned bucket, and metadata
    """
    from app.services import pipeline_service

    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Convert to datetime for comparisons
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    # Get pipeline and stage IDs
    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    stage_ids = get_performance_stage_ids(db, pipeline.id)

    now = datetime.now(timezone.utc)

    if mode == "cohort":
        user_data, unassigned = _get_cohort_performance(
            db, organization_id, start_dt, end_dt, stage_ids
        )
    else:
        user_data, unassigned = _get_activity_performance(
            db, organization_id, start_dt, end_dt, stage_ids
        )

    # Calculate time metrics (avg days to match/apply) for cohort mode
    if mode == "cohort":
        _add_time_metrics(db, organization_id, start_dt, end_dt, stage_ids, user_data)

    return {
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "mode": mode,
        "as_of": now.isoformat(),
        "pipeline_id": str(pipeline.id),
        "data": user_data,
        "unassigned": unassigned,
    }


def _get_cohort_performance(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    stage_ids: dict[str, uuid.UUID | None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Cohort mode: Cases created within date range, grouped by current owner.

    Stage counts are "ever reached" (any history entry to that stage).
    """
    # Get all active org users via Membership
    users_query = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == organization_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )

    def _stage_condition(stage_id: uuid.UUID | None):
        return (
            literal(False) if stage_id is None else SurrogateStatusHistory.to_stage_id == stage_id
        )

    def _count_distinct(condition):
        return func.count(func.distinct(case((condition, Surrogate.id))))

    application_submitted_sid = stage_ids.get("application_submitted")
    lost_sid = stage_ids.get("lost")
    if lost_sid:
        if application_submitted_sid:
            CSH_application_submitted = aliased(SurrogateStatusHistory)
            lost_condition = and_(
                SurrogateStatusHistory.to_stage_id == lost_sid,
                ~exists(
                    select(CSH_application_submitted.id).where(
                        CSH_application_submitted.surrogate_id == Surrogate.id,
                        CSH_application_submitted.to_stage_id == application_submitted_sid,
                    )
                ),
            )
        else:
            lost_condition = SurrogateStatusHistory.to_stage_id == lost_sid
    else:
        lost_condition = literal(False)

    base_filters = [
        Surrogate.organization_id == organization_id,
        Surrogate.owner_type == OwnerType.USER.value,
        Surrogate.owner_id.isnot(None),
        Surrogate.created_at >= start_dt,
        Surrogate.created_at <= end_dt,
    ]

    metrics_rows = (
        db.query(
            Surrogate.owner_id.label("user_id"),
            func.count(func.distinct(Surrogate.id)).label("total_surrogates"),
            _count_distinct(Surrogate.is_archived.is_(True)).label("archived_count"),
            _count_distinct(_stage_condition(stage_ids.get("contacted"))).label("contacted"),
            _count_distinct(_stage_condition(stage_ids.get("qualified"))).label("qualified"),
            _count_distinct(_stage_condition(stage_ids.get("ready_to_match"))).label(
                "ready_to_match"
            ),
            _count_distinct(_stage_condition(stage_ids.get("matched"))).label("matched"),
            _count_distinct(_stage_condition(stage_ids.get("application_submitted"))).label(
                "application_submitted"
            ),
            _count_distinct(lost_condition).label("lost"),
        )
        .select_from(Surrogate)
        .outerjoin(SurrogateStatusHistory, SurrogateStatusHistory.surrogate_id == Surrogate.id)
        .filter(*base_filters)
        .group_by(Surrogate.owner_id)
        .all()
    )

    metrics_by_user = {row.user_id: row for row in metrics_rows}

    user_data = []
    for user_id, user_name in users_query:
        metrics = metrics_by_user.get(user_id)
        total = metrics.total_surrogates if metrics else 0
        conversion_rate = (
            round((metrics.application_submitted / total * 100), 1)
            if metrics and total > 0
            else 0.0
        )

        user_data.append(
            {
                "user_id": str(user_id),
                "user_name": user_name or "Unknown",
                "total_surrogates": total,
                "archived_count": metrics.archived_count if metrics else 0,
                "contacted": metrics.contacted if metrics else 0,
                "qualified": metrics.qualified if metrics else 0,
                "ready_to_match": metrics.ready_to_match if metrics else 0,
                "matched": metrics.matched if metrics else 0,
                "application_submitted": metrics.application_submitted if metrics else 0,
                "lost": metrics.lost if metrics else 0,
                "conversion_rate": conversion_rate,
                "avg_days_to_match": None,
                "avg_days_to_application_submitted": None,
            }
        )

    # Sort by total_surrogates descending
    user_data.sort(key=lambda x: x["total_surrogates"], reverse=True)

    # Unassigned bucket (queue-owned or no owner)
    unassigned_filters = [
        Surrogate.organization_id == organization_id,
        Surrogate.created_at >= start_dt,
        Surrogate.created_at <= end_dt,
        or_(Surrogate.owner_type != OwnerType.USER.value, Surrogate.owner_id.is_(None)),
    ]

    unassigned_row = (
        db.query(
            func.count(func.distinct(Surrogate.id)).label("total_surrogates"),
            _count_distinct(Surrogate.is_archived.is_(True)).label("archived_count"),
            _count_distinct(_stage_condition(stage_ids.get("contacted"))).label("contacted"),
            _count_distinct(_stage_condition(stage_ids.get("qualified"))).label("qualified"),
            _count_distinct(_stage_condition(stage_ids.get("ready_to_match"))).label(
                "ready_to_match"
            ),
            _count_distinct(_stage_condition(stage_ids.get("matched"))).label("matched"),
            _count_distinct(_stage_condition(stage_ids.get("application_submitted"))).label(
                "application_submitted"
            ),
            _count_distinct(lost_condition).label("lost"),
        )
        .select_from(Surrogate)
        .outerjoin(SurrogateStatusHistory, SurrogateStatusHistory.surrogate_id == Surrogate.id)
        .filter(*unassigned_filters)
        .first()
    )

    unassigned = {
        "total_surrogates": unassigned_row.total_surrogates if unassigned_row else 0,
        "archived_count": unassigned_row.archived_count if unassigned_row else 0,
        "contacted": unassigned_row.contacted if unassigned_row else 0,
        "qualified": unassigned_row.qualified if unassigned_row else 0,
        "ready_to_match": unassigned_row.ready_to_match if unassigned_row else 0,
        "matched": unassigned_row.matched if unassigned_row else 0,
        "application_submitted": unassigned_row.application_submitted if unassigned_row else 0,
        "lost": unassigned_row.lost if unassigned_row else 0,
    }

    return user_data, unassigned


def _get_activity_performance(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    stage_ids: dict[str, uuid.UUID | None],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Activity mode: Cases with status transitions within date range.

    total_surrogates = distinct surrogates with ANY transition in range.
    Stage counts = transitions to that stage within range.
    """
    # Get all active org users via Membership
    users_query = (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == organization_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )

    def _stage_condition(stage_id: uuid.UUID | None):
        return (
            literal(False) if stage_id is None else SurrogateStatusHistory.to_stage_id == stage_id
        )

    def _count_distinct(condition):
        return func.count(func.distinct(case((condition, Surrogate.id))))

    application_submitted_sid = stage_ids.get("application_submitted")
    lost_sid = stage_ids.get("lost")
    if lost_sid:
        if application_submitted_sid:
            CSH_application_submitted = aliased(SurrogateStatusHistory)
            lost_condition = and_(
                SurrogateStatusHistory.to_stage_id == lost_sid,
                ~exists(
                    select(CSH_application_submitted.id).where(
                        CSH_application_submitted.surrogate_id == Surrogate.id,
                        CSH_application_submitted.to_stage_id == application_submitted_sid,
                    )
                ),
            )
        else:
            lost_condition = SurrogateStatusHistory.to_stage_id == lost_sid
    else:
        lost_condition = literal(False)

    base_filters = [
        Surrogate.organization_id == organization_id,
        Surrogate.owner_type == OwnerType.USER.value,
        Surrogate.owner_id.isnot(None),
        SurrogateStatusHistory.changed_at >= start_dt,
        SurrogateStatusHistory.changed_at <= end_dt,
    ]

    metrics_rows = (
        db.query(
            Surrogate.owner_id.label("user_id"),
            func.count(func.distinct(Surrogate.id)).label("total_surrogates"),
            _count_distinct(Surrogate.is_archived.is_(True)).label("archived_count"),
            _count_distinct(_stage_condition(stage_ids.get("contacted"))).label("contacted"),
            _count_distinct(_stage_condition(stage_ids.get("qualified"))).label("qualified"),
            _count_distinct(_stage_condition(stage_ids.get("ready_to_match"))).label(
                "ready_to_match"
            ),
            _count_distinct(_stage_condition(stage_ids.get("matched"))).label("matched"),
            _count_distinct(_stage_condition(stage_ids.get("application_submitted"))).label(
                "application_submitted"
            ),
            _count_distinct(lost_condition).label("lost"),
        )
        .select_from(Surrogate)
        .join(SurrogateStatusHistory, SurrogateStatusHistory.surrogate_id == Surrogate.id)
        .filter(*base_filters)
        .group_by(Surrogate.owner_id)
        .all()
    )

    metrics_by_user = {row.user_id: row for row in metrics_rows}

    user_data = []
    for user_id, user_name in users_query:
        metrics = metrics_by_user.get(user_id)
        total = metrics.total_surrogates if metrics else 0
        conversion_rate = (
            round((metrics.application_submitted / total * 100), 1)
            if metrics and total > 0
            else 0.0
        )

        user_data.append(
            {
                "user_id": str(user_id),
                "user_name": user_name or "Unknown",
                "total_surrogates": total,
                "archived_count": metrics.archived_count if metrics else 0,
                "contacted": metrics.contacted if metrics else 0,
                "qualified": metrics.qualified if metrics else 0,
                "ready_to_match": metrics.ready_to_match if metrics else 0,
                "matched": metrics.matched if metrics else 0,
                "application_submitted": metrics.application_submitted if metrics else 0,
                "lost": metrics.lost if metrics else 0,
                "conversion_rate": conversion_rate,
                "avg_days_to_match": None,
                "avg_days_to_application_submitted": None,
            }
        )

    # Sort by total_surrogates descending
    user_data.sort(key=lambda x: x["total_surrogates"], reverse=True)

    # Unassigned bucket
    unassigned_filters = [
        Surrogate.organization_id == organization_id,
        or_(Surrogate.owner_type != OwnerType.USER.value, Surrogate.owner_id.is_(None)),
        SurrogateStatusHistory.changed_at >= start_dt,
        SurrogateStatusHistory.changed_at <= end_dt,
    ]

    unassigned_row = (
        db.query(
            func.count(func.distinct(Surrogate.id)).label("total_surrogates"),
            _count_distinct(Surrogate.is_archived.is_(True)).label("archived_count"),
            _count_distinct(_stage_condition(stage_ids.get("contacted"))).label("contacted"),
            _count_distinct(_stage_condition(stage_ids.get("qualified"))).label("qualified"),
            _count_distinct(_stage_condition(stage_ids.get("ready_to_match"))).label(
                "ready_to_match"
            ),
            _count_distinct(_stage_condition(stage_ids.get("matched"))).label("matched"),
            _count_distinct(_stage_condition(stage_ids.get("application_submitted"))).label(
                "application_submitted"
            ),
            _count_distinct(lost_condition).label("lost"),
        )
        .select_from(Surrogate)
        .join(SurrogateStatusHistory, SurrogateStatusHistory.surrogate_id == Surrogate.id)
        .filter(*unassigned_filters)
        .first()
    )

    unassigned = {
        "total_surrogates": unassigned_row.total_surrogates if unassigned_row else 0,
        "archived_count": unassigned_row.archived_count if unassigned_row else 0,
        "contacted": unassigned_row.contacted if unassigned_row else 0,
        "qualified": unassigned_row.qualified if unassigned_row else 0,
        "ready_to_match": unassigned_row.ready_to_match if unassigned_row else 0,
        "matched": unassigned_row.matched if unassigned_row else 0,
        "application_submitted": unassigned_row.application_submitted if unassigned_row else 0,
        "lost": unassigned_row.lost if unassigned_row else 0,
    }

    return user_data, unassigned


def _add_time_metrics(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    stage_ids: dict[str, uuid.UUID | None],
    user_data: list[dict[str, Any]],
) -> None:
    """
    Add avg_days_to_match and avg_days_to_application_submitted to user data.

    Uses first-reach (MIN changed_at) for each stage.
    """
    matched_sid = stage_ids.get("matched")
    application_submitted_sid = stage_ids.get("application_submitted")

    def _avg_days_by_user(stage_id: uuid.UUID | None) -> dict[str, float]:
        if not stage_id:
            return {}

        first_stage = (
            db.query(
                SurrogateStatusHistory.surrogate_id.label("surrogate_id"),
                func.min(SurrogateStatusHistory.changed_at).label("first_changed_at"),
            )
            .filter(
                SurrogateStatusHistory.organization_id == organization_id,
                SurrogateStatusHistory.to_stage_id == stage_id,
            )
            .group_by(SurrogateStatusHistory.surrogate_id)
            .subquery()
        )

        rows = (
            db.query(
                Surrogate.owner_id.label("user_id"),
                func.avg(
                    func.extract("epoch", first_stage.c.first_changed_at - Surrogate.created_at)
                    / 86400
                ).label("avg_days"),
            )
            .join(first_stage, first_stage.c.surrogate_id == Surrogate.id)
            .filter(
                Surrogate.organization_id == organization_id,
                Surrogate.owner_type == OwnerType.USER.value,
                Surrogate.owner_id.isnot(None),
                Surrogate.created_at >= start_dt,
                Surrogate.created_at <= end_dt,
            )
            .group_by(Surrogate.owner_id)
            .all()
        )

        return {
            str(row.user_id): round(float(row.avg_days), 1)
            for row in rows
            if row.avg_days is not None
        }

    match_avgs = _avg_days_by_user(matched_sid)
    apply_avgs = _avg_days_by_user(application_submitted_sid)

    for user in user_data:
        user_id = user["user_id"]
        user["avg_days_to_match"] = match_avgs.get(user_id)
        user["avg_days_to_application_submitted"] = apply_avgs.get(user_id)


def get_cached_performance_by_user(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    mode: Literal["cohort", "activity"] = "cohort",
) -> dict[str, Any]:
    """Cached version of get_performance_by_user."""
    from app.services import pipeline_service

    # Get pipeline ID for cache key
    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)

    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "mode": mode,
        "pipeline_id": str(pipeline.id),
        "pipeline_version": pipeline.current_version,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "performance_by_user",
        params,
        lambda: get_performance_by_user(
            db,
            organization_id,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
        ),
        range_start=range_start,
        range_end=range_end,
    )


# =============================================================================
# Meta Spend Analytics (Stored Data)
# =============================================================================


def get_meta_ad_accounts(
    db: Session,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Get list of ad accounts for the organization."""
    accounts = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.organization_id == organization_id,
            MetaAdAccount.is_active.is_(True),
        )
        .order_by(MetaAdAccount.ad_account_name)
        .all()
    )

    return [
        {
            "id": str(a.id),
            "ad_account_external_id": a.ad_account_external_id,
            "ad_account_name": a.ad_account_name or a.ad_account_external_id,
            "hierarchy_synced_at": a.hierarchy_synced_at.isoformat()
            if a.hierarchy_synced_at
            else None,
            "spend_synced_at": a.spend_synced_at.isoformat() if a.spend_synced_at else None,
        }
        for a in accounts
    ]


def get_spend_sync_status(
    db: Session,
    organization_id: uuid.UUID,
    ad_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Get sync status for spend data."""
    query = db.query(MetaAdAccount).filter(
        MetaAdAccount.organization_id == organization_id,
        MetaAdAccount.is_active.is_(True),
    )

    if ad_account_id:
        query = query.filter(MetaAdAccount.id == ad_account_id)

    accounts = query.all()

    if not accounts:
        return {
            "sync_status": "never",
            "last_synced_at": None,
            "ad_accounts_configured": 0,
        }

    # Find most recent sync
    last_synced = None
    for a in accounts:
        if a.spend_synced_at:
            if not last_synced or a.spend_synced_at > last_synced:
                last_synced = a.spend_synced_at

    if not last_synced:
        return {
            "sync_status": "pending",
            "last_synced_at": None,
            "ad_accounts_configured": len(accounts),
        }

    return {
        "sync_status": "synced",
        "last_synced_at": last_synced.isoformat(),
        "ad_accounts_configured": len(accounts),
    }


def get_spend_by_campaign(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """
    Aggregate spend by campaign from stored data.

    Filters to breakdown_type="_total" for aggregate metrics.
    Returns: [{campaign_external_id, campaign_name, spend, impressions, clicks, leads, cpl}]
    """
    query = (
        db.query(
            MetaDailySpend.campaign_external_id,
            MetaDailySpend.campaign_name,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == "_total",
        )
        .group_by(
            MetaDailySpend.campaign_external_id,
            MetaDailySpend.campaign_name,
        )
        .order_by(func.sum(MetaDailySpend.spend).desc())
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    results = query.all()

    campaigns = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = r.leads or 0
        cpl = round(spend / leads, 2) if leads > 0 else None

        campaigns.append(
            {
                "campaign_external_id": r.campaign_external_id,
                "campaign_name": r.campaign_name,
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return campaigns


def get_spend_by_breakdown(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    breakdown_type: str,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """
    Aggregate spend by breakdown dimension.

    Args:
        breakdown_type: "publisher_platform", "platform_position", "age", "region"

    Returns: [{breakdown_value, spend, impressions, clicks, leads, cpl}]
    """
    if breakdown_type not in (
        "publisher_platform",
        "platform_position",
        "age",
        "region",
    ):
        return []

    query = (
        db.query(
            MetaDailySpend.breakdown_value,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == breakdown_type,
        )
        .group_by(MetaDailySpend.breakdown_value)
        .order_by(func.sum(MetaDailySpend.spend).desc())
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    results = query.all()

    breakdowns = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = r.leads or 0
        cpl = round(spend / leads, 2) if leads > 0 else None

        breakdowns.append(
            {
                "breakdown_value": r.breakdown_value,
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return breakdowns


def get_spend_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
    campaign_external_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Daily spend time series from stored data.

    Returns: [{date, spend, impressions, clicks, leads, cpl}]
    """
    query = (
        db.query(
            MetaDailySpend.spend_date,
            func.sum(MetaDailySpend.spend).label("spend"),
            func.sum(MetaDailySpend.impressions).label("impressions"),
            func.sum(MetaDailySpend.clicks).label("clicks"),
            func.sum(MetaDailySpend.leads).label("leads"),
        )
        .filter(
            MetaDailySpend.organization_id == organization_id,
            MetaDailySpend.spend_date >= start_date,
            MetaDailySpend.spend_date <= end_date,
            MetaDailySpend.breakdown_type == "_total",
        )
        .group_by(MetaDailySpend.spend_date)
        .order_by(MetaDailySpend.spend_date)
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)
    if campaign_external_id:
        query = query.filter(MetaDailySpend.campaign_external_id == campaign_external_id)

    results = query.all()

    trend = []
    for r in results:
        spend = float(r.spend) if r.spend else 0.0
        leads = r.leads or 0
        cpl = round(spend / leads, 2) if leads > 0 else None

        trend.append(
            {
                "date": r.spend_date.isoformat(),
                "spend": round(spend, 2),
                "impressions": r.impressions or 0,
                "clicks": r.clicks or 0,
                "leads": leads,
                "cost_per_lead": cpl,
            }
        )

    return trend


def get_spend_totals(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """
    Get aggregate spend totals for the date range.

    Returns totals plus sync status.
    """
    query = db.query(
        func.sum(MetaDailySpend.spend).label("spend"),
        func.sum(MetaDailySpend.impressions).label("impressions"),
        func.sum(MetaDailySpend.clicks).label("clicks"),
        func.sum(MetaDailySpend.leads).label("leads"),
    ).filter(
        MetaDailySpend.organization_id == organization_id,
        MetaDailySpend.spend_date >= start_date,
        MetaDailySpend.spend_date <= end_date,
        MetaDailySpend.breakdown_type == "_total",
    )

    if ad_account_id:
        query = query.filter(MetaDailySpend.ad_account_id == ad_account_id)

    result = query.first()

    spend = float(result.spend) if result and result.spend else 0.0
    impressions = result.impressions if result else 0
    clicks = result.clicks if result else 0
    leads = int(result.leads) if result and result.leads else 0
    cpl = round(spend / leads, 2) if leads > 0 else None

    # Get sync status
    sync_status = get_spend_sync_status(db, organization_id, ad_account_id)

    return {
        "total_spend": round(spend, 2),
        "total_impressions": impressions or 0,
        "total_clicks": clicks or 0,
        "total_leads": leads or 0,
        "cost_per_lead": cpl,
        **sync_status,
    }


def get_cached_spend_by_campaign(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_by_campaign",
        params,
        lambda: get_spend_by_campaign(db, organization_id, start_date, end_date, ad_account_id),
        range_start=range_start,
        range_end=range_end,
    )


def get_cached_spend_by_breakdown(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    breakdown_type: str,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "breakdown_type": breakdown_type,
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_by_breakdown",
        params,
        lambda: get_spend_by_breakdown(
            db, organization_id, start_date, end_date, breakdown_type, ad_account_id
        ),
        range_start=range_start,
        range_end=range_end,
    )


def get_cached_spend_trend(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date,
    end_date: date,
    ad_account_id: uuid.UUID | None = None,
    campaign_external_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ad_account_id": str(ad_account_id) if ad_account_id else None,
        "campaign_external_id": campaign_external_id,
    }
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "spend_trend",
        params,
        lambda: get_spend_trend(
            db,
            organization_id,
            start_date,
            end_date,
            ad_account_id,
            campaign_external_id,
        ),
        range_start=range_start,
        range_end=range_end,
    )


# =============================================================================
# Meta Form Analytics
# =============================================================================


def get_leads_by_form(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Lead counts from meta_leads, conversion rates from joined Cases.

    Returns: [{
        form_external_id, form_name,
        lead_count,      # From meta_leads
        surrogate_count,      # From surrogates (converted leads)
        qualified_count, # From surrogates with qualified+ status
        qualified_rate,  # qualified_count / surrogate_count
        conversion_rate  # surrogate_count / lead_count (lead-to-case)
    }]
    """
    from app.services import pipeline_service

    # Build date filter
    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)

    # Get lead counts by form
    lead_counts_query = (
        db.query(
            MetaLead.meta_form_id.label("form_external_id"),
            func.count(MetaLead.id).label("lead_count"),
            func.count(MetaLead.converted_surrogate_id).label("surrogate_count"),
        )
        .filter(MetaLead.organization_id == organization_id)
        .filter(MetaLead.meta_form_id.isnot(None))
        .group_by(MetaLead.meta_form_id)
    )
    lead_counts_query = _apply_date_range_filters(
        lead_counts_query, lead_time, start_date, end_date
    )

    lead_counts = {r.form_external_id: r for r in lead_counts_query.all()}

    # Get qualified stage IDs
    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")

    qualified_stage_ids = []
    if qualified_stage:
        qualified_stage_ids = [
            s.id for s in stages if s.order >= qualified_stage.order and s.is_active
        ]

    # Get qualified counts by form
    qualified_counts: dict[str, int] = {}
    if qualified_stage_ids:
        qualified_query = (
            db.query(
                MetaLead.meta_form_id.label("form_external_id"),
                func.count(Surrogate.id).label("qualified_count"),
            )
            .join(Surrogate, MetaLead.converted_surrogate_id == Surrogate.id)
            .filter(
                MetaLead.organization_id == organization_id,
                MetaLead.meta_form_id.isnot(None),
                MetaLead.is_converted.is_(True),
                Surrogate.stage_id.in_(qualified_stage_ids),
            )
        )
        qualified_query = _apply_date_range_filters(
            qualified_query, lead_time, start_date, end_date
        )

        qualified_query = qualified_query.group_by(MetaLead.meta_form_id)

        for r in qualified_query.all():
            qualified_counts[r.form_external_id] = r.qualified_count

    # Get form names from MetaForm table
    form_names: dict[str, str] = {}
    forms = (
        db.query(MetaForm.form_external_id, MetaForm.form_name)
        .filter(MetaForm.organization_id == organization_id)
        .all()
    )
    for f in forms:
        form_names[f.form_external_id] = f.form_name

    # Build result
    result = []
    for form_external_id, counts in lead_counts.items():
        lead_count = counts.lead_count or 0
        surrogate_count = counts.surrogate_count or 0
        qualified_count = qualified_counts.get(form_external_id, 0)

        conversion_rate = round(surrogate_count / lead_count * 100, 1) if lead_count > 0 else 0.0
        qualified_rate = (
            round(qualified_count / surrogate_count * 100, 1) if surrogate_count > 0 else 0.0
        )

        result.append(
            {
                "form_external_id": form_external_id,
                "form_name": form_names.get(form_external_id, f"Form {form_external_id[:8]}..."),
                "lead_count": lead_count,
                "surrogate_count": surrogate_count,
                "qualified_count": qualified_count,
                "conversion_rate": conversion_rate,
                "qualified_rate": qualified_rate,
            }
        )

    # Sort by lead_count descending
    result.sort(key=lambda x: x["lead_count"], reverse=True)

    return result


def get_cached_leads_by_form(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    params = {
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    range_start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        if start_date
        else None
    )
    range_end = (
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) if end_date else None
    )
    return _get_or_compute_snapshot(
        db,
        organization_id,
        "leads_by_form",
        params,
        lambda: get_leads_by_form(db, organization_id, start_date, end_date),
        range_start=range_start,
        range_end=range_end,
    )


def get_meta_campaign_list(
    db: Session,
    organization_id: uuid.UUID,
    ad_account_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Get list of synced campaigns for filter dropdown."""
    query = db.query(MetaCampaign).filter(
        MetaCampaign.organization_id == organization_id,
    )

    if ad_account_id:
        query = query.filter(MetaCampaign.ad_account_id == ad_account_id)

    campaigns = query.order_by(MetaCampaign.campaign_name).all()

    return [
        {
            "campaign_external_id": c.campaign_external_id,
            "campaign_name": c.campaign_name,
            "status": c.status,
            "objective": c.objective,
        }
        for c in campaigns
    ]
