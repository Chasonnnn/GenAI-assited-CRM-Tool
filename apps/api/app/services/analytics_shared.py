"""Shared helpers for analytics services."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AnalyticsSnapshot


FUNNEL_SLUGS = [
    "new_unread",
    "contacted",
    "pre_qualified",
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


def _get_default_pipeline_stages(db: Session, organization_id: uuid.UUID):
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
