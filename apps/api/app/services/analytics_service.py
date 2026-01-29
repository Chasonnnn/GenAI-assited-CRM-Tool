"""Analytics service facade for Reports dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import TaskType
from app.db.models import PipelineStage, Surrogate, Task
from app.services import analytics_meta_service as _meta
from app.services import analytics_shared as _shared
from app.services import analytics_surrogate_service as _surrogate
from app.services import analytics_usage_service as _usage


def get_pdf_export_data(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> dict[str, Any]:
    """Build analytics data used for PDF export."""
    from app.services import org_service

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

    from app.services import pipeline_service

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

    surrogates_by_status = _surrogate.get_surrogates_by_status(db, organization_id)
    surrogates_by_assignee = _surrogate.get_surrogates_by_assignee(
        db, organization_id, label="display_name"
    )

    trend_start = datetime.now(timezone.utc) - timedelta(days=30)
    trend_data = _surrogate.get_surrogates_trend(
        db,
        organization_id,
        start=trend_start,
        end=datetime.now(timezone.utc),
        group_by="day",
    )

    meta_start = start_dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
    meta_end = end_dt or datetime.now(timezone.utc)
    meta_performance = _meta.get_meta_performance(db, organization_id, meta_start, meta_end)

    start_date = start_dt.date() if start_dt else None
    end_date = end_dt.date() if end_dt else None
    funnel_data = _meta.get_funnel_with_filter(
        db, organization_id, start_date=start_date, end_date=end_date
    )

    state_data = _meta.get_surrogates_by_state_with_filter(
        db, organization_id, start_date=start_date, end_date=end_date
    )

    performance_data = _surrogate.get_performance_by_user(
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


_SHARED_EXPORTS = {
    "FUNNEL_SLUGS",
    "_normalize_date_bounds",
    "parse_date_range",
}
_SURROGATE_EXPORTS = {
    "PERFORMANCE_STAGE_SLUGS",
    "get_cached_analytics_summary",
    "get_cached_conversion_funnel",
    "get_cached_performance_by_user",
    "get_cached_summary_kpis",
    "get_cached_surrogates_by_assignee",
    "get_cached_surrogates_by_source",
    "get_cached_surrogates_by_state",
    "get_cached_surrogates_by_status",
    "get_cached_surrogates_trend",
    "get_analytics_summary",
    "get_conversion_funnel",
    "get_performance_by_user",
    "get_performance_stage_ids",
    "get_status_trend",
    "get_summary_kpis",
    "get_surrogates_by_assignee",
    "get_surrogates_by_source",
    "get_surrogates_by_state",
    "get_surrogates_by_status",
    "get_surrogates_by_user",
    "get_surrogates_trend",
}
_META_EXPORTS = {
    "get_cached_leads_by_ad",
    "get_cached_campaigns",
    "get_cached_funnel_with_filter",
    "get_cached_leads_by_form",
    "get_cached_meta_performance",
    "get_cached_meta_platform_breakdown",
    "get_cached_meta_spend_summary",
    "get_cached_spend_by_breakdown",
    "get_cached_spend_by_campaign",
    "get_cached_spend_trend",
    "get_cached_surrogates_by_state_with_filter",
    "get_campaigns",
    "get_funnel_with_filter",
    "get_leads_by_form",
    "get_leads_by_ad",
    "get_meta_ad_accounts",
    "get_meta_campaign_list",
    "get_meta_performance",
    "get_meta_platform_breakdown",
    "get_meta_spend_summary",
    "get_spend_by_breakdown",
    "get_spend_by_campaign",
    "get_spend_sync_status",
    "get_spend_totals",
    "get_spend_trend",
    "get_surrogates_by_state_with_filter",
}
_USAGE_EXPORTS = {"get_activity_feed"}


def __getattr__(name: str):
    if name in _SHARED_EXPORTS:
        return getattr(_shared, name)
    if name in _SURROGATE_EXPORTS:
        return getattr(_surrogate, name)
    if name in _META_EXPORTS:
        return getattr(_meta, name)
    if name in _USAGE_EXPORTS:
        return getattr(_usage, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_SHARED_EXPORTS | _SURROGATE_EXPORTS | _META_EXPORTS | _USAGE_EXPORTS) + [
    "get_pdf_export_data"
]
