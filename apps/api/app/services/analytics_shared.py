"""Shared helpers for analytics services."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, date, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AnalyticsSnapshot
from app.services import pipeline_semantics_service, pipeline_service
from app.schemas.pipeline_semantics import (
    DEFAULT_ANALYTICS_CONVERSION_STAGE_KEY,
    DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS,
    DEFAULT_ANALYTICS_QUALIFICATION_STAGE_KEY,
)


DEFAULT_FUNNEL_STAGE_KEYS = [
    "new_unread",
    "contacted",
    "pre_qualified",
    "ready_to_match",
    "matched",
    "medical_clearance_passed",
]


def get_analytics_stage_configuration(
    db: Session,
    organization_id: uuid.UUID,
    pipeline_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    if pipeline_id is None:
        pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    else:
        pipeline = pipeline_service.get_pipeline(db, organization_id, pipeline_id)
        if pipeline is None:
            pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)

    snapshot = pipeline_semantics_service.get_pipeline_semantics_snapshot(db, pipeline)
    stage_by_key = {
        stage.stage_key: stage
        for stage in snapshot.stages
        if stage.is_active and stage.stage_key
    }

    analytics = snapshot.feature_config.analytics
    performance_stage_keys = [
        stage_key
        for stage_key in analytics.performance_stage_keys or DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS
        if stage_key in stage_by_key
    ]
    if not performance_stage_keys:
        performance_stage_keys = [
            stage.stage_key for stage in snapshot.stages if stage.is_active
        ]

    qualification_stage_key = analytics.qualification_stage_key
    if qualification_stage_key not in stage_by_key:
        qualification_stage_key = next(
            (stage_key for stage_key in DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS if stage_key in stage_by_key),
            DEFAULT_ANALYTICS_QUALIFICATION_STAGE_KEY,
        )
        if qualification_stage_key not in stage_by_key:
            qualification_stage_key = performance_stage_keys[0] if performance_stage_keys else None

    conversion_stage_key = analytics.conversion_stage_key
    if conversion_stage_key not in stage_by_key:
        conversion_stage_key = next(
            (stage_key for stage_key in DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS if stage_key in stage_by_key),
            DEFAULT_ANALYTICS_CONVERSION_STAGE_KEY,
        )
        if conversion_stage_key not in stage_by_key:
            conversion_stage_key = performance_stage_keys[-1] if performance_stage_keys else None

    match_stage = pipeline_semantics_service.get_first_active_stage_with_capability(
        snapshot,
        "locks_match_state",
    )

    return {
        "pipeline": pipeline,
        "snapshot": snapshot,
        "stage_by_key": stage_by_key,
        "performance_stage_keys": performance_stage_keys,
        "qualification_stage_key": qualification_stage_key,
        "conversion_stage_key": conversion_stage_key,
        "match_stage_key": match_stage.stage_key if match_stage else None,
    }


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
    pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    return pipeline_service.get_stages(db, pipeline.id, include_inactive=True)


def get_funnel_stage_keys(
    db: Session,
    organization_id: uuid.UUID,
    pipeline_id: uuid.UUID | None = None,
) -> list[str]:
    if pipeline_id is None:
        pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    else:
        pipeline = pipeline_service.get_pipeline(db, organization_id, pipeline_id)
        if pipeline is None:
            pipeline = pipeline_service.get_or_create_default_pipeline(db, organization_id)
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline)
    return list(feature_config.analytics.funnel_stage_keys or DEFAULT_FUNNEL_STAGE_KEYS)


def parse_date_range(
    from_date: str | None,
    to_date: str | None,
    default_days: int = 30,
    inclusive_date_end: bool = False,
    timezone_name: str | None = None,
) -> tuple[datetime, datetime]:
    """Parse ISO date strings to a datetime range with defaults."""
    requested_tz = timezone.utc
    if timezone_name:
        try:
            requested_tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            requested_tz = timezone.utc

    def _parse_bound(value: str, *, is_end: bool) -> datetime:
        raw = value.strip().replace("Z", "+00:00")
        is_date_only = "T" not in raw and " " not in raw

        if is_date_only:
            parsed_local = datetime.combine(
                date.fromisoformat(raw),
                datetime.min.time(),
                tzinfo=requested_tz,
            )
            if is_end and inclusive_date_end:
                parsed_local += timedelta(days=1)
            return parsed_local.astimezone(timezone.utc)

        parsed = datetime.fromisoformat(raw)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=requested_tz)
        return parsed.astimezone(timezone.utc)

    if to_date:
        end = _parse_bound(to_date, is_end=True)
    else:
        end = datetime.now(timezone.utc)

    if from_date:
        start = _parse_bound(from_date, is_end=False)
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
