"""Surrogate analytics service (trends, status, funnel, performance)."""

from __future__ import annotations

from collections import defaultdict
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, text, and_, case
from sqlalchemy.orm import Session

from app.db.enums import OwnerType
from app.db.models import (
    Membership,
    PipelineStage,
    Surrogate,
    SurrogateStatusHistory,
    User,
)
from app.services.analytics_shared import (
    _apply_date_range_filters,
    _get_default_pipeline_stages,
    _get_or_compute_snapshot,
    get_analytics_stage_configuration,
    get_funnel_stage_keys,
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
    analytics_config = get_analytics_stage_configuration(db, organization_id)
    snapshot = analytics_config["snapshot"]
    qualification_stage_key = analytics_config["qualification_stage_key"]
    qualification_stage = (
        analytics_config["stage_by_key"].get(qualification_stage_key)
        if qualification_stage_key
        else None
    )
    qualified_stage_ids = [
        stage.id
        for stage in snapshot.stages
        if stage.is_active
        and qualification_stage is not None
        and stage.order >= qualification_stage.order
    ]

    # Combine counts into a single aggregation query to reduce DB round trips.
    metrics = (
        db.query(
            func.count(Surrogate.id).label("total_surrogates"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(Surrogate.created_at >= start, Surrogate.created_at < end),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("new_this_period"),
            func.coalesce(
                func.sum(
                    case(
                        (Surrogate.stage_id.in_(qualified_stage_ids), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("pre_qualified_count"),
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.is_archived.is_(False),
        )
        .one()
    )

    total_surrogates = int(metrics.total_surrogates or 0)
    new_this_period = int(metrics.new_this_period or 0)
    qualified_count = int(metrics.pre_qualified_count or 0)

    qualification_rate = (
        (qualified_count / total_surrogates * 100) if total_surrogates > 0 else 0.0
    )

    avg_time_to_qualification_hours = None
    if qualification_stage:
        result = db.execute(
            text(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - c.created_at)) / 3600) as avg_hours
                FROM surrogates c
                JOIN surrogate_status_history csh ON c.id = csh.surrogate_id
                WHERE c.organization_id = :org_id
                  AND c.is_archived = false
                  AND csh.to_stage_id = :qualification_stage_id
                  AND csh.changed_at >= :start
                  AND csh.changed_at < :end
            """
            ),
            {
                "org_id": organization_id,
                "start": start,
                "end": end,
                "qualification_stage_id": qualification_stage.id,
            },
        )
        row = result.fetchone()
        avg_time_to_qualification_hours = float(round(row[0], 1)) if row and row[0] else None

    return {
        "total_surrogates": total_surrogates,
        "new_this_period": new_this_period,
        "qualification_rate": round(qualification_rate, 1),
        "qualification_stage_key": qualification_stage_key,
        "avg_time_to_qualification_hours": avg_time_to_qualification_hours,
    }


def get_surrogates_trend(
    db: Session,
    organization_id: uuid.UUID,
    start: datetime | None = None,
    end: datetime | None = None,
    source: str | None = None,
    owner_id: uuid.UUID | None = None,
    pipeline_id: uuid.UUID | None = None,
    timezone_name: str | None = None,
    group_by: str = "day",  # day, week, month
) -> list[dict[str, Any]]:
    """Get new surrogates created over time."""
    if not end:
        end = datetime.now(timezone.utc)
    if not start:
        start = end - timedelta(days=30)

    normalized_timezone_name: str | None = None
    if timezone_name:
        try:
            normalized_timezone_name = ZoneInfo(timezone_name).key
        except ZoneInfoNotFoundError:
            normalized_timezone_name = None

    timestamp_column = (
        func.timezone(normalized_timezone_name, Surrogate.created_at)
        if normalized_timezone_name
        else Surrogate.created_at
    )

    # Group by time period
    if group_by == "week":
        date_trunc = func.date_trunc("week", timestamp_column)
    elif group_by == "month":
        date_trunc = func.date_trunc("month", timestamp_column)
    else:
        date_trunc = func.date(timestamp_column)

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
    timezone_name: str | None = None,
) -> list[dict[str, Any]]:
    normalized_timezone_name: str | None = None
    if timezone_name:
        try:
            normalized_timezone_name = ZoneInfo(timezone_name).key
        except ZoneInfoNotFoundError:
            normalized_timezone_name = None

    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "group_by": group_by,
        "pipeline_id": str(pipeline_id) if pipeline_id else None,
        "owner_id": str(owner_id) if owner_id else None,
        "timezone_name": normalized_timezone_name,
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
            timezone_name=normalized_timezone_name,
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
    stage_by_key = {s.stage_key: s for s in stages if s.is_active}
    funnel_stage_keys = get_funnel_stage_keys(db, organization_id)
    funnel_stages = [stage_by_key[stage_key] for stage_key in funnel_stage_keys if stage_key in stage_by_key]
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


PERFORMANCE_STAGE_SLUGS: list[str] = []


def get_performance_stage_ids(
    db: Session,
    pipeline_id: uuid.UUID,
) -> dict[str, uuid.UUID | None]:
    """Resolve performance stage keys to IDs for a pipeline."""
    from app.services import pipeline_semantics_service

    snapshot = pipeline_semantics_service.get_pipeline_semantics_snapshot(db, pipeline_id)
    performance_stage_keys = snapshot.feature_config.analytics.performance_stage_keys or [
        stage.stage_key for stage in snapshot.stages if stage.is_active
    ]
    stage_ids: dict[str, uuid.UUID | None] = {}
    for stage_key in performance_stage_keys:
        stage = snapshot.stage_by_key.get(stage_key)
        stage_ids[stage_key] = stage.id if stage and stage.is_active else None
    return stage_ids


def _load_active_users(
    db: Session,
    organization_id: uuid.UUID,
) -> list[tuple[uuid.UUID, str]]:
    return (
        db.query(User.id, User.display_name)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == organization_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .all()
    )


def _build_performance_columns(analytics_config: dict[str, Any]) -> list[dict[str, Any]]:
    stage_by_key = analytics_config["stage_by_key"]
    columns: list[dict[str, Any]] = []
    for stage_key in analytics_config["performance_stage_keys"]:
        stage = stage_by_key.get(stage_key)
        if not stage:
            continue
        columns.append(
            {
                "stage_key": stage.stage_key,
                "label": stage.label,
                "color": stage.color,
                "order": stage.order,
            }
        )
    return columns


def _empty_stage_counts(stage_keys: list[str]) -> dict[str, int]:
    return {stage_key: 0 for stage_key in stage_keys}


def _empty_performance_bucket(stage_keys: list[str]) -> dict[str, Any]:
    return {
        "total_surrogates": 0,
        "archived_count": 0,
        "stage_counts": _empty_stage_counts(stage_keys),
        "conversion_rate": 0.0,
        "avg_days_to_match": None,
        "avg_days_to_conversion": None,
    }


def _load_history_stage_sets(
    db: Session,
    *,
    organization_id: uuid.UUID,
    surrogate_ids: set[uuid.UUID],
    stage_id_to_key: dict[uuid.UUID, str],
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> tuple[dict[uuid.UUID, set[str]], dict[uuid.UUID, dict[str, datetime]]]:
    reached: dict[uuid.UUID, set[str]] = defaultdict(set)
    first_changed_at: dict[uuid.UUID, dict[str, datetime]] = defaultdict(dict)
    if not surrogate_ids or not stage_id_to_key:
        return reached, first_changed_at

    query = db.query(
        SurrogateStatusHistory.surrogate_id,
        SurrogateStatusHistory.to_stage_id,
        SurrogateStatusHistory.changed_at,
    ).filter(
        SurrogateStatusHistory.organization_id == organization_id,
        SurrogateStatusHistory.surrogate_id.in_(list(surrogate_ids)),
        SurrogateStatusHistory.to_stage_id.in_(list(stage_id_to_key.keys())),
    )
    if start_dt is not None:
        query = query.filter(SurrogateStatusHistory.changed_at >= start_dt)
    if end_dt is not None:
        query = query.filter(SurrogateStatusHistory.changed_at <= end_dt)

    for surrogate_id, stage_id, changed_at in query.all():
        stage_key = stage_id_to_key.get(stage_id)
        if not stage_key:
            continue
        reached[surrogate_id].add(stage_key)
        existing = first_changed_at[surrogate_id].get(stage_key)
        if existing is None or changed_at < existing:
            first_changed_at[surrogate_id][stage_key] = changed_at

    return reached, first_changed_at


def _finalize_performance_rows(
    *,
    user_rows: list[tuple[uuid.UUID, str]],
    user_buckets: dict[str, dict[str, Any]],
    unassigned_bucket: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for user_id, display_name in user_rows:
        bucket = user_buckets.get(str(user_id))
        if bucket is None:
            data.append(
                {
                    "user_id": str(user_id),
                    "user_name": display_name or "Unknown",
                    **_empty_performance_bucket(list(unassigned_bucket["stage_counts"].keys())),
                }
            )
            continue
        data.append(
            {
                "user_id": str(user_id),
                "user_name": display_name or "Unknown",
                **bucket,
            }
        )

    data.sort(key=lambda item: item["total_surrogates"], reverse=True)
    return data, unassigned_bucket


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
    analytics_config = get_analytics_stage_configuration(db, organization_id, pipeline.id)
    columns = _build_performance_columns(analytics_config)

    now = datetime.now(timezone.utc)

    if mode == "cohort":
        user_data, unassigned = _get_cohort_performance(
            db, organization_id, start_dt, end_dt, analytics_config
        )
    else:
        user_data, unassigned = _get_activity_performance(
            db, organization_id, start_dt, end_dt, analytics_config
        )

    if mode == "cohort":
        _add_time_metrics(
            db,
            organization_id,
            start_dt,
            end_dt,
            analytics_config,
            user_data,
        )

    return {
        "from_date": start_date.isoformat(),
        "to_date": end_date.isoformat(),
        "mode": mode,
        "as_of": now.isoformat(),
        "pipeline_id": str(pipeline.id),
        "columns": columns,
        "match_stage_key": analytics_config["match_stage_key"],
        "conversion_stage_key": analytics_config["conversion_stage_key"],
        "data": user_data,
        "unassigned": unassigned,
    }


def _get_cohort_performance(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    analytics_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cohort mode: Cases created within date range, grouped by current owner."""
    stage_keys = list(analytics_config["performance_stage_keys"])
    stage_key_to_stage = analytics_config["stage_by_key"]
    stage_id_to_key = {
        stage.id: stage_key
        for stage_key, stage in stage_key_to_stage.items()
        if stage_key in stage_keys
    }
    users_query = _load_active_users(db, organization_id)
    user_buckets: dict[str, dict[str, Any]] = {}
    unassigned_bucket = _empty_performance_bucket(stage_keys)

    surrogates = (
        db.query(
            Surrogate.id,
            Surrogate.owner_id,
            Surrogate.owner_type,
            Surrogate.is_archived,
            Surrogate.stage_id,
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.created_at >= start_dt,
            Surrogate.created_at <= end_dt,
        )
        .all()
    )
    surrogate_ids = {row.id for row in surrogates}
    reached_by_surrogate, _ = _load_history_stage_sets(
        db,
        organization_id=organization_id,
        surrogate_ids=surrogate_ids,
        stage_id_to_key=stage_id_to_key,
    )
    conversion_stage_key = analytics_config["conversion_stage_key"]

    for row in surrogates:
        bucket = (
            user_buckets.setdefault(str(row.owner_id), _empty_performance_bucket(stage_keys))
            if row.owner_type == OwnerType.USER.value and row.owner_id
            else unassigned_bucket
        )
        bucket["total_surrogates"] += 1
        if row.is_archived:
            bucket["archived_count"] += 1

        reached_keys = set(reached_by_surrogate.get(row.id, set()))
        current_stage_key = stage_id_to_key.get(row.stage_id)
        if current_stage_key:
            reached_keys.add(current_stage_key)

        for stage_key in stage_keys:
            if stage_key == "lost":
                if "lost" in reached_keys and (
                    not conversion_stage_key or conversion_stage_key not in reached_keys
                ):
                    bucket["stage_counts"]["lost"] += 1
                continue
            if stage_key in reached_keys:
                bucket["stage_counts"][stage_key] += 1

    for bucket in [*user_buckets.values(), unassigned_bucket]:
        total = bucket["total_surrogates"]
        converted = bucket["stage_counts"].get(conversion_stage_key or "", 0)
        bucket["conversion_rate"] = round((converted / total * 100), 1) if total > 0 else 0.0

    return _finalize_performance_rows(
        user_rows=users_query,
        user_buckets=user_buckets,
        unassigned_bucket=unassigned_bucket,
    )


def _get_activity_performance(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    analytics_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Activity mode: Cases with status transitions within date range."""
    stage_keys = list(analytics_config["performance_stage_keys"])
    stage_key_to_stage = analytics_config["stage_by_key"]
    stage_id_to_key = {
        stage.id: stage_key
        for stage_key, stage in stage_key_to_stage.items()
        if stage_key in stage_keys
    }
    users_query = _load_active_users(db, organization_id)
    user_buckets: dict[str, dict[str, Any]] = {}
    unassigned_bucket = _empty_performance_bucket(stage_keys)

    activity_history_rows = (
        db.query(SurrogateStatusHistory.surrogate_id)
        .filter(
            SurrogateStatusHistory.organization_id == organization_id,
            SurrogateStatusHistory.changed_at >= start_dt,
            SurrogateStatusHistory.changed_at <= end_dt,
        )
        .distinct()
        .all()
    )
    touched_surrogate_ids = {row.surrogate_id for row in activity_history_rows}
    if not touched_surrogate_ids:
        return _finalize_performance_rows(
            user_rows=users_query,
            user_buckets=user_buckets,
            unassigned_bucket=unassigned_bucket,
        )

    surrogates = (
        db.query(
            Surrogate.id,
            Surrogate.owner_id,
            Surrogate.owner_type,
            Surrogate.is_archived,
        )
        .filter(
            Surrogate.organization_id == organization_id,
            Surrogate.id.in_(list(touched_surrogate_ids)),
        )
        .all()
    )
    activity_stage_sets, _ = _load_history_stage_sets(
        db,
        organization_id=organization_id,
        surrogate_ids=touched_surrogate_ids,
        stage_id_to_key=stage_id_to_key,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    conversion_stage_key = analytics_config["conversion_stage_key"]
    conversion_stage = (
        stage_key_to_stage.get(conversion_stage_key)
        if conversion_stage_key
        else None
    )
    conversion_ever, _ = _load_history_stage_sets(
        db,
        organization_id=organization_id,
        surrogate_ids=touched_surrogate_ids,
        stage_id_to_key=(
            {conversion_stage.id: conversion_stage_key}
            if conversion_stage and conversion_stage_key
            else {}
        ),
    )

    for row in surrogates:
        bucket = (
            user_buckets.setdefault(str(row.owner_id), _empty_performance_bucket(stage_keys))
            if row.owner_type == OwnerType.USER.value and row.owner_id
            else unassigned_bucket
        )
        bucket["total_surrogates"] += 1
        if row.is_archived:
            bucket["archived_count"] += 1

        activity_stage_keys = set(activity_stage_sets.get(row.id, set()))
        converted_ever = conversion_stage_key in conversion_ever.get(row.id, set())
        for stage_key in stage_keys:
            if stage_key == "lost":
                if "lost" in activity_stage_keys and not converted_ever:
                    bucket["stage_counts"]["lost"] += 1
                continue
            if stage_key in activity_stage_keys:
                bucket["stage_counts"][stage_key] += 1

    for bucket in [*user_buckets.values(), unassigned_bucket]:
        total = bucket["total_surrogates"]
        converted = bucket["stage_counts"].get(conversion_stage_key or "", 0)
        bucket["conversion_rate"] = round((converted / total * 100), 1) if total > 0 else 0.0

    return _finalize_performance_rows(
        user_rows=users_query,
        user_buckets=user_buckets,
        unassigned_bucket=unassigned_bucket,
    )


def _add_time_metrics(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    analytics_config: dict[str, Any],
    user_data: list[dict[str, Any]],
) -> None:
    """Add avg_days_to_match and avg_days_to_conversion to user data."""
    stage_by_key = analytics_config["stage_by_key"]
    match_stage_key = analytics_config["match_stage_key"]
    conversion_stage_key = analytics_config["conversion_stage_key"]
    matched_sid = stage_by_key[match_stage_key].id if match_stage_key in stage_by_key else None
    conversion_sid = (
        stage_by_key[conversion_stage_key].id if conversion_stage_key in stage_by_key else None
    )

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
    conversion_avgs = _avg_days_by_user(conversion_sid)

    for user in user_data:
        user_id = user["user_id"]
        user["avg_days_to_match"] = match_avgs.get(user_id)
        user["avg_days_to_conversion"] = conversion_avgs.get(user_id)


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
