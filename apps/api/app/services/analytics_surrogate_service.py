"""Surrogate analytics service (trends, status, funnel, performance)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Literal

from sqlalchemy import func, text, exists, and_, select, case, literal, or_
from sqlalchemy.orm import Session, aliased

from app.db.enums import OwnerType
from app.db.models import (
    Membership,
    PipelineStage,
    Surrogate,
    SurrogateStatusHistory,
    User,
)
from app.services.analytics_shared import (
    FUNNEL_SLUGS,
    _apply_date_range_filters,
    _get_default_pipeline_stages,
    _get_or_compute_snapshot,
)


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

    result = (
        db.query(
            func.count(Surrogate.id).label("total"),
            func.sum(
                case(
                    (and_(Surrogate.created_at >= start, Surrogate.created_at < end), 1),
                    else_=0,
                )
            ).label("new_period"),
            func.sum(
                case(
                    (Surrogate.stage_id.in_(qualified_stage_ids), 1),
                    else_=0,
                )
            ).label("qualified"),
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
        .one()
    )

    total_surrogates = result.total or 0
    new_this_period = result.new_period or 0
    qualified_count = result.qualified or 0

    qualified_rate = (qualified_count / total_surrogates * 100) if total_surrogates > 0 else 0.0

    avg_time_to_qualified_hours = None
    if qualified_stage:
        result = db.execute(
            text(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - c.created_at)) / 3600) as avg_hours
                FROM surrogates c
                JOIN surrogate_status_history csh ON c.id = csh.surrogate_id
                WHERE c.organization_id = :org_id
                  AND c.is_archived = false
                  AND csh.to_stage_id = :qualified_stage_id
                  AND csh.changed_at >= :start
                  AND csh.changed_at < :end
            """
            ),
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
    query = (
        db.query(
            PipelineStage.label.label("status"),
            PipelineStage.id.label("stage_id"),
            PipelineStage.order.label("stage_order"),
            func.count(Surrogate.id).label("count"),
        )
        .join(Surrogate, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
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

    query = db.query(
        func.date(SurrogateStatusHistory.changed_at).label("date"),
        func.coalesce(SurrogateStatusHistory.to_label_snapshot, "unknown").label("status_label"),
        func.count(SurrogateStatusHistory.id).label("count"),
    ).filter(SurrogateStatusHistory.organization_id == organization_id)
    query = _apply_date_range_filters(
        query, SurrogateStatusHistory.changed_at, start_date, end_date
    )
    results = (
        query.group_by(
            func.date(SurrogateStatusHistory.changed_at),
            func.coalesce(SurrogateStatusHistory.to_label_snapshot, "unknown"),
        )
        .order_by(func.date(SurrogateStatusHistory.changed_at))
        .all()
    )

    data_by_date: dict[str, dict[str, int]] = {}
    for r in results:
        date_str = r.date.isoformat()
        if date_str not in data_by_date:
            data_by_date[date_str] = {}
        data_by_date[date_str][r.status_label] = r.count

    return [{"date": d, **statuses} for d, statuses in sorted(data_by_date.items())]


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


def get_surrogates_by_user(
    db: Session,
    organization_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """Get surrogate count by owner (user-owned surrogates only)."""
    query = (
        db.query(
            Surrogate.owner_id,
            User.display_name,
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
        query.group_by(Surrogate.owner_id, User.display_name)
        .order_by(func.count(Surrogate.id).desc())
        .all()
    )

    return [
        {
            "user_id": str(r.owner_id) if r.owner_id else None,
            "user_name": r.display_name or "Unassigned",
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

    period_days = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)

    current_query = db.query(func.count(Surrogate.id)).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )
    current_query = _apply_date_range_filters(
        current_query,
        Surrogate.created_at,
        start_date,
        end_date,
    )
    current = current_query.scalar() or 0

    previous_query = db.query(func.count(Surrogate.id)).filter(
        Surrogate.organization_id == organization_id,
        Surrogate.is_archived.is_(False),
    )
    previous_query = _apply_date_range_filters(
        previous_query,
        Surrogate.created_at,
        prev_start,
        prev_end,
    )
    previous = previous_query.scalar() or 0

    if previous > 0:
        change_pct = round((current - previous) / previous * 100, 1)
    else:
        change_pct = 100 if current > 0 else 0

    total_active = (
        db.query(func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
        .scalar()
        or 0
    )

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
    """Resolve performance stage slugs to IDs for a pipeline."""
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
    """Get individual performance metrics by user."""
    from app.services import pipeline_service

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

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
    """Cohort mode: Cases created within date range, grouped by current owner."""
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
            csh_application_submitted = aliased(SurrogateStatusHistory)
            lost_condition = and_(
                SurrogateStatusHistory.to_stage_id == lost_sid,
                ~exists(
                    select(csh_application_submitted.id).where(
                        csh_application_submitted.surrogate_id == Surrogate.id,
                        csh_application_submitted.to_stage_id == application_submitted_sid,
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

    user_data.sort(key=lambda x: x["total_surrogates"], reverse=True)

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
    """Activity mode: Cases with status transitions within date range."""
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
            csh_application_submitted = aliased(SurrogateStatusHistory)
            lost_condition = and_(
                SurrogateStatusHistory.to_stage_id == lost_sid,
                ~exists(
                    select(csh_application_submitted.id).where(
                        csh_application_submitted.surrogate_id == Surrogate.id,
                        csh_application_submitted.to_stage_id == application_submitted_sid,
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

    user_data.sort(key=lambda x: x["total_surrogates"], reverse=True)

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
    """Add avg_days_to_match and avg_days_to_application_submitted to user data."""
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
