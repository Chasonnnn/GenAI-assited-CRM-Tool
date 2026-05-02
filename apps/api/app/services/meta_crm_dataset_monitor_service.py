"""Monitoring helpers for direct Meta CRM dataset outbound events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobStatus
from app.db.models import MetaCrmDatasetEvent
from app.db.session import SessionLocal
from app.services import job_service
from app.utils.pagination import paginate_query_by_offset

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_HOURS = 24
MIN_EVENTS_FOR_RATE_WARNING = 5
FAILURE_RATE_WARNING_THRESHOLD = 0.2
SKIPPED_RATE_WARNING_THRESHOLD = 0.25
NON_ACTIONABLE_SKIP_REASONS = {"duplicate"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _persist_isolated(create_fn) -> None:
    db = SessionLocal()
    try:
        create_fn(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist Meta CRM dataset monitoring event")
    finally:
        db.close()


def _persist(create_fn, *, db: Session | None = None) -> None:
    if db is None:
        _persist_isolated(create_fn)
        return
    try:
        create_fn(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist Meta CRM dataset monitoring event")


def _create_event_record(
    db: Session,
    *,
    org_id: UUID,
    source: str,
    status: str,
    reason: str | None = None,
    job_id: UUID | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
    lead_id: str | None = None,
    stage_key: str | None = None,
    stage_slug: str | None = None,
    stage_label: str | None = None,
    surrogate_id: UUID | None = None,
    attempts: int = 0,
    last_error: str | None = None,
) -> MetaCrmDatasetEvent:
    now = _now_utc()
    event = MetaCrmDatasetEvent(
        organization_id=org_id,
        job_id=job_id,
        source=source,
        status=status,
        reason=reason,
        event_id=event_id,
        event_name=event_name,
        lead_id=lead_id,
        stage_key=stage_key,
        stage_slug=stage_slug,
        stage_label=stage_label,
        surrogate_id=surrogate_id,
        attempts=attempts,
        last_error=last_error,
        created_at=now,
        updated_at=now,
        last_attempt_at=now if status in {"failed", "delivered"} else None,
        delivered_at=now if status == "delivered" else None,
    )
    db.add(event)
    db.flush()
    return event


def record_skipped_event(
    *,
    org_id: UUID,
    source: str,
    reason: str,
    event_id: str | None = None,
    event_name: str | None = None,
    lead_id: str | None = None,
    stage_key: str | None = None,
    stage_slug: str | None = None,
    stage_label: str | None = None,
    surrogate_id: UUID | None = None,
    db: Session | None = None,
) -> None:
    _persist(
        lambda inner_db: _create_event_record(
            inner_db,
            org_id=org_id,
            source=source,
            status="skipped",
            reason=reason,
            event_id=event_id,
            event_name=event_name,
            lead_id=lead_id,
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            surrogate_id=surrogate_id,
        ),
        db=db,
    )


def record_queued_event(
    *,
    org_id: UUID,
    job_id: UUID,
    source: str,
    event_id: str | None = None,
    event_name: str | None = None,
    lead_id: str | None = None,
    stage_key: str | None = None,
    stage_slug: str | None = None,
    stage_label: str | None = None,
    surrogate_id: UUID | None = None,
    db: Session | None = None,
) -> MetaCrmDatasetEvent | None:
    event_holder: dict[str, MetaCrmDatasetEvent] = {}

    def _create(inner_db: Session) -> None:
        event_holder["event"] = _create_event_record(
            inner_db,
            org_id=org_id,
            job_id=job_id,
            source=source,
            status="queued",
            event_id=event_id,
            event_name=event_name,
            lead_id=lead_id,
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            surrogate_id=surrogate_id,
        )

    _persist(_create, db=db)
    return event_holder.get("event")


def mark_job_delivered(*, job_id: UUID, attempts: int, db: Session | None = None) -> None:
    def _update(inner_db: Session) -> None:
        event = (
            inner_db.query(MetaCrmDatasetEvent).filter(MetaCrmDatasetEvent.job_id == job_id).first()
        )
        if not event:
            return
        now = _now_utc()
        event.status = "delivered"
        event.attempts = attempts
        event.last_error = None
        event.updated_at = now
        event.last_attempt_at = now
        event.delivered_at = now

    _persist(_update, db=db)


def mark_job_failed(
    *,
    job_id: UUID,
    job_status: str,
    attempts: int,
    error_message: str,
    db: Session | None = None,
) -> None:
    def _update(inner_db: Session) -> None:
        event = (
            inner_db.query(MetaCrmDatasetEvent).filter(MetaCrmDatasetEvent.job_id == job_id).first()
        )
        if not event:
            return
        now = _now_utc()
        event.status = "failed" if job_status == JobStatus.FAILED.value else "queued"
        event.attempts = attempts
        event.last_error = error_message[:1000]
        event.updated_at = now
        event.last_attempt_at = now

    _persist(_update, db=db)


def list_events(
    db: Session,
    *,
    org_id: UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MetaCrmDatasetEvent], int]:
    query = db.query(MetaCrmDatasetEvent).filter(MetaCrmDatasetEvent.organization_id == org_id)
    if status:
        query = query.filter(MetaCrmDatasetEvent.status == status)
    normalized_offset = max(0, offset)
    normalized_limit = max(1, min(limit, 200))
    items, total = paginate_query_by_offset(
        query.order_by(MetaCrmDatasetEvent.created_at.desc()),
        offset=normalized_offset,
        limit=normalized_limit,
        count_query=query,
    )
    return items, total


def get_summary(
    db: Session,
    *,
    org_id: UUID,
    window_hours: int = DEFAULT_WINDOW_HOURS,
) -> dict[str, Any]:
    window_hours = max(1, min(window_hours, 24 * 30))
    cutoff = _now_utc() - timedelta(hours=window_hours)
    items = (
        db.query(MetaCrmDatasetEvent)
        .filter(
            MetaCrmDatasetEvent.organization_id == org_id,
            MetaCrmDatasetEvent.created_at >= cutoff,
            MetaCrmDatasetEvent.source != "test",
        )
        .all()
    )

    counts = {"queued": 0, "delivered": 0, "failed": 0, "skipped": 0}
    actionable_skipped = 0
    for item in items:
        if item.status in counts:
            counts[item.status] += 1
        if item.status == "skipped" and item.reason not in NON_ACTIONABLE_SKIP_REASONS:
            actionable_skipped += 1

    total_count = len(items)
    delivery_base = counts["delivered"] + counts["failed"]
    failure_rate = counts["failed"] / delivery_base if delivery_base else 0.0
    skipped_rate = actionable_skipped / total_count if total_count else 0.0

    failure_rate_alert = (
        total_count >= MIN_EVENTS_FOR_RATE_WARNING
        and delivery_base > 0
        and failure_rate >= FAILURE_RATE_WARNING_THRESHOLD
    )
    skipped_rate_alert = (
        total_count >= MIN_EVENTS_FOR_RATE_WARNING
        and actionable_skipped > 0
        and skipped_rate >= SKIPPED_RATE_WARNING_THRESHOLD
    )
    warning_messages: list[str] = []
    if failure_rate_alert:
        warning_messages.append("Failure rate is elevated for direct Meta CRM dataset events.")
    if skipped_rate_alert:
        warning_messages.append(
            "Skipped-event rate is elevated for direct Meta CRM dataset events."
        )

    return {
        "window_hours": window_hours,
        "total_count": total_count,
        "queued_count": counts["queued"],
        "delivered_count": counts["delivered"],
        "failed_count": counts["failed"],
        "skipped_count": counts["skipped"],
        "actionable_skipped_count": actionable_skipped,
        "failure_rate": failure_rate,
        "skipped_rate": skipped_rate,
        "failure_rate_alert": failure_rate_alert,
        "skipped_rate_alert": skipped_rate_alert,
        "warning_messages": warning_messages,
    }


def retry_failed_event(
    db: Session,
    *,
    org_id: UUID,
    event_id: UUID,
    reason: str | None = None,
) -> MetaCrmDatasetEvent:
    event = (
        db.query(MetaCrmDatasetEvent)
        .filter(
            MetaCrmDatasetEvent.id == event_id,
            MetaCrmDatasetEvent.organization_id == org_id,
        )
        .first()
    )
    if event is None:
        raise ValueError("Event not found")
    if event.status != "failed":
        raise ValueError("Only failed events can be retried")
    if event.job_id is None:
        raise ValueError("Failed event does not have a replayable job")

    replay_job = job_service.get_job(db, org_id=org_id, job_id=event.job_id)
    if replay_job is None:
        raise ValueError("Replayable job not found")
    if replay_job.status != JobStatus.FAILED.value:
        replay_job.status = JobStatus.FAILED.value
        replay_job.last_error = replay_job.last_error or event.last_error

    job_service.replay_failed_job(
        db,
        org_id=org_id,
        job_id=event.job_id,
        reason=reason or "meta_crm_dataset_event_retry",
        commit=False,
    )

    event.status = "queued"
    event.last_error = None
    event.attempts = 0
    event.updated_at = _now_utc()
    db.commit()
    db.refresh(event)
    return event
