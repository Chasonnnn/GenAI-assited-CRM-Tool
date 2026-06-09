"""Analytics service facade for Reports dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import TaskType
from app.db.models import Surrogate, Task
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

    from sqlalchemy import case, and_

    period_start = (end_dt or datetime.now(timezone.utc)) - timedelta(days=7)

    analytics_config = _shared.get_analytics_stage_configuration(db, organization_id)
    snapshot = analytics_config.get("snapshot")
    qualification_stage_key = analytics_config.get("qualification_stage_key")
    qualification_stage = (
        analytics_config.get("stage_by_key", {}).get(qualification_stage_key)
        if qualification_stage_key
        else None
    )

    qualified_stage_ids = []
    if snapshot and hasattr(snapshot, "stages"):
        qualified_stage_ids = [
            stage.id
            for stage in snapshot.stages
            if stage.is_active and qualification_stage and stage.order >= qualification_stage.order
        ]

    metrics = (
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (date_filter, 1),
                        else_=0,
                    )
                ),
                0,
            ).label("total_surrogates"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Surrogate.is_archived.is_(False),
                                Surrogate.created_at >= period_start,
                            ),
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
                        (
                            and_(
                                Surrogate.is_archived.is_(False),
                                Surrogate.stage_id.in_(qualified_stage_ids),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("qualified_count"),
        )
        .filter(Surrogate.organization_id == organization_id)
        .one()
    )

    total_surrogates = int(metrics.total_surrogates or 0)
    new_this_period = int(metrics.new_this_period or 0)
    qualified_count = int(metrics.qualified_count or 0)

    qualification_rate = 0.0
    if total_surrogates > 0:
        qualification_rate = (qualified_count / total_surrogates) * 100

    today = datetime.now(timezone.utc).date()
    task_counts = (
        db.query(
            func.count(Task.id).label("pending_tasks"),
            func.count(Task.id).filter(Task.due_date < today).label("overdue_tasks"),
        )
        .filter(
            Task.organization_id == organization_id,
            Task.is_completed.is_(False),
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .one()
    )
    pending_tasks = int(task_counts.pending_tasks or 0)
    overdue_tasks = int(task_counts.overdue_tasks or 0)

    summary = {
        "total_surrogates": total_surrogates,
        "new_this_period": new_this_period,
        "qualification_rate": qualification_rate,
        "qualification_stage_key": qualification_stage_key,
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
    "DEFAULT_FUNNEL_STAGE_KEYS",
    "_normalize_date_bounds",
    "get_analytics_stage_configuration",
    "get_funnel_stage_keys",
    "parse_date_range",
}
_SURROGATE_EXPORTS = {
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
