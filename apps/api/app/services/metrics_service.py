"""
Request metrics service.

Records API request metrics using DB upserts for multi-replica safety.
"""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.models import RequestMetricsRollup

logger = logging.getLogger(__name__)


def get_minute_bucket(dt: datetime | None = None) -> datetime:
    """Get the start of the minute for a given datetime."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.replace(second=0, microsecond=0)


def record_request(
    db: Session,
    route: str,
    method: str,
    status_code: int,
    duration_ms: int,
    org_id: UUID | None = None,
) -> None:
    """
    Record a single API request metric.

    Uses ON CONFLICT DO UPDATE for multi-replica safety.
    Multiple workers can safely increment the same bucket.
    """
    now = datetime.now(timezone.utc)
    minute_bucket = get_minute_bucket(now)

    # Determine status bucket
    status_2xx = 1 if 200 <= status_code < 300 else 0
    status_4xx = 1 if 400 <= status_code < 500 else 0
    status_5xx = 1 if 500 <= status_code < 600 else 0

    # Upsert with increment
    stmt = insert(
        RequestMetricsRollup
    ).values(
        organization_id=org_id,
        period_start=minute_bucket,
        period_type="minute",
        route=route[:100],  # Truncate for safety
        method=method.upper()[:10],
        status_2xx=status_2xx,
        status_4xx=status_4xx,
        status_5xx=status_5xx,
        total_duration_ms=duration_ms,
        request_count=1,
    )

    conflict_target = {"constraint": "uq_request_metrics_rollup"}
    if org_id is None:
        conflict_target = {
            "index_elements": ["period_start", "route", "method"],
            "index_where": RequestMetricsRollup.organization_id.is_(None),
        }

    stmt = stmt.on_conflict_do_update(
        **conflict_target,
        set_={
            "status_2xx": RequestMetricsRollup.status_2xx + status_2xx,
            "status_4xx": RequestMetricsRollup.status_4xx + status_4xx,
            "status_5xx": RequestMetricsRollup.status_5xx + status_5xx,
            "total_duration_ms": RequestMetricsRollup.total_duration_ms + duration_ms,
            "request_count": RequestMetricsRollup.request_count + 1,
        },
    )

    try:
        db.execute(stmt)
        db.commit()
    except Exception as exc:
        # Best effort - don't fail requests on metrics errors
        db.rollback()
        logger.warning("Failed to record request metrics: %s", exc)


def get_request_metrics(
    db: Session,
    org_id: UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    group_by_route: bool = True,
) -> list[dict]:
    """
    Get aggregated request metrics.

    Returns metrics grouped by route/method within the time range.
    """
    from sqlalchemy import text

    if from_time is None:
        from_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if to_time is None:
        to_time = datetime.now(timezone.utc)

    if group_by_route:
        query = text("""
            SELECT 
                route,
                method,
                SUM(request_count) as total_requests,
                SUM(status_2xx) as success_count,
                SUM(status_4xx) as client_error_count,
                SUM(status_5xx) as server_error_count,
                SUM(total_duration_ms) / NULLIF(SUM(request_count), 0) as avg_duration_ms
            FROM request_metrics_rollup
            WHERE (:org_id IS NULL OR organization_id = :org_id)
              AND period_start >= :from_time
              AND period_start < :to_time
            GROUP BY route, method
            ORDER BY total_requests DESC
            LIMIT 50
        """)
    else:
        query = text("""
            SELECT 
                period_start,
                SUM(request_count) as total_requests,
                SUM(status_2xx) as success_count,
                SUM(status_4xx) as client_error_count,
                SUM(status_5xx) as server_error_count,
                SUM(total_duration_ms) / NULLIF(SUM(request_count), 0) as avg_duration_ms
            FROM request_metrics_rollup
            WHERE (:org_id IS NULL OR organization_id = :org_id)
              AND period_start >= :from_time
              AND period_start < :to_time
            GROUP BY period_start
            ORDER BY period_start
        """)

    result = db.execute(
        query,
        {
            "org_id": org_id,
            "from_time": from_time,
            "to_time": to_time,
        },
    )

    metrics = []
    for row in result:
        if group_by_route:
            metrics.append(
                {
                    "route": row[0],
                    "method": row[1],
                    "total_requests": row[2],
                    "success_count": row[3],
                    "client_error_count": row[4],
                    "server_error_count": row[5],
                    "avg_duration_ms": int(row[6]) if row[6] else 0,
                }
            )
        else:
            metrics.append(
                {
                    "period_start": row[0].isoformat() if row[0] else None,
                    "total_requests": row[1],
                    "success_count": row[2],
                    "client_error_count": row[3],
                    "server_error_count": row[4],
                    "avg_duration_ms": int(row[5]) if row[5] else 0,
                }
            )

    return metrics


def get_sli_rollup(
    db: Session,
    org_id: UUID,
    prefixes: list[str],
    window_minutes: int,
) -> dict[str, int | float]:
    """Aggregate SLI metrics for a set of route prefixes."""
    from_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    prefix_filters = [RequestMetricsRollup.route.like(f"{prefix}%") for prefix in prefixes]
    if not prefix_filters:
        return {
            "request_count": 0,
            "success_rate": 0.0,
            "error_rate": 0.0,
            "avg_latency_ms": 0,
        }

    totals = (
        db.query(
            func.coalesce(func.sum(RequestMetricsRollup.request_count), 0),
            func.coalesce(func.sum(RequestMetricsRollup.status_2xx), 0),
            func.coalesce(func.sum(RequestMetricsRollup.status_4xx), 0),
            func.coalesce(func.sum(RequestMetricsRollup.status_5xx), 0),
            func.coalesce(func.sum(RequestMetricsRollup.total_duration_ms), 0),
        )
        .filter(
            RequestMetricsRollup.organization_id == org_id,
            RequestMetricsRollup.period_start >= from_time,
            or_(*prefix_filters),
        )
        .first()
    )

    if not totals:
        return {
            "request_count": 0,
            "success_rate": 0.0,
            "error_rate": 0.0,
            "avg_latency_ms": 0,
        }

    request_count = int(totals[0] or 0)
    success_count = int(totals[1] or 0)
    error_count = int((totals[2] or 0) + (totals[3] or 0))
    total_duration = int(totals[4] or 0)
    avg_latency = int(total_duration / request_count) if request_count else 0
    success_rate = success_count / request_count if request_count else 0.0
    error_rate = error_count / request_count if request_count else 0.0

    return {
        "request_count": request_count,
        "success_rate": round(success_rate, 4),
        "error_rate": round(error_rate, 4),
        "avg_latency_ms": avg_latency,
    }
