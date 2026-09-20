"""Monitoring helpers for outbound Zapier conversion events."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobStatus
from app.db.models import ZapierOutboundEvent
from app.db.session import SessionLocal
from app.services import job_service
from app.utils.pagination import paginate_query_by_offset

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_HOURS = 24
MIN_EVENTS_FOR_RATE_WARNING = 5
FAILURE_RATE_WARNING_THRESHOLD = 0.2
SKIPPED_RATE_WARNING_THRESHOLD = 0.25
NON_ACTIONABLE_SKIP_REASONS = {
    "duplicate",
    "donor_config_changed",
    "donor_dispatch_disabled",
    "donor_mapping_changed",
    "donor_outbound_disabled",
    "donor_stage_inactive",
    "donor_stage_undo",
    "unmapped_donor_stage",
}


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _persist_isolated(create_fn) -> None:
    db = SessionLocal()
    try:
        create_fn(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist Zapier outbound monitoring event")
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
        logger.exception("Failed to persist Zapier outbound monitoring event")


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
    donor_id: UUID | None = None,
    donor_status_history_id: UUID | None = None,
    donor_type: str | None = None,
    pipeline_id: UUID | None = None,
    stage_id: UUID | None = None,
    attribution_source: str | None = None,
    first_party_submission_id: UUID | None = None,
    config_fingerprint: str | None = None,
    attempts: int = 0,
    last_error: str | None = None,
) -> ZapierOutboundEvent:
    now = _now_utc()
    event = ZapierOutboundEvent(
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
        donor_id=donor_id,
        donor_status_history_id=donor_status_history_id,
        donor_type=donor_type,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        attribution_source=attribution_source,
        first_party_submission_id=first_party_submission_id,
        config_fingerprint=config_fingerprint,
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


def create_donor_event(
    db: Session,
    *,
    org_id: UUID,
    source: str,
    status: str,
    reason: str | None,
    event_id: str,
    event_name: str | None,
    lead_id: str | None,
    stage_key: str,
    stage_slug: str | None,
    stage_label: str,
    donor_id: UUID,
    donor_status_history_id: UUID,
    donor_type: str,
    pipeline_id: UUID,
    stage_id: UUID,
    attribution_source: str | None = None,
    first_party_submission_id: UUID | None = None,
    config_fingerprint: str | None = None,
    job_id: UUID | None = None,
) -> ZapierOutboundEvent:
    """Create a donor delivery record inside the caller-owned transaction."""
    return _create_event_record(
        db,
        org_id=org_id,
        source=source,
        status=status,
        reason=reason,
        job_id=job_id,
        event_id=event_id,
        event_name=event_name,
        lead_id=lead_id,
        stage_key=stage_key,
        stage_slug=stage_slug,
        stage_label=stage_label,
        donor_id=donor_id,
        donor_status_history_id=donor_status_history_id,
        donor_type=donor_type,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        attribution_source=attribution_source,
        first_party_submission_id=first_party_submission_id,
        config_fingerprint=config_fingerprint,
    )


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
) -> None:
    _persist(
        lambda inner_db: _create_event_record(
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
        ),
        db=db,
    )


def mark_job_delivered(*, job_id: UUID, attempts: int, db: Session | None = None) -> bool:
    should_record_success = True

    def _update(inner_db: Session) -> None:
        nonlocal should_record_success
        event = (
            inner_db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job_id).first()
        )
        if not event:
            return
        if event.status == "skipped":
            should_record_success = False
            event.attempts = attempts
            event.updated_at = _now_utc()
            return
        now = _now_utc()
        event.status = "delivered"
        event.attempts = attempts
        event.last_error = None
        event.updated_at = now
        event.last_attempt_at = now
        event.delivered_at = now

    _persist(_update, db=db)
    return should_record_success


def mark_job_skipped(
    *,
    job_id: UUID,
    reason: str,
    db: Session | None = None,
) -> None:
    def _update(inner_db: Session) -> None:
        event = (
            inner_db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job_id).first()
        )
        if not event:
            return
        event.status = "skipped"
        event.reason = reason[:50]
        event.last_error = None
        event.updated_at = _now_utc()

    if db is None:
        _persist(_update)
        return
    _update(db)
    db.commit()


def mark_job_failed(
    *,
    job_id: UUID,
    job_status: str,
    attempts: int,
    error_message: str,
    db: Session | None = None,
) -> None:
    def _update(db: Session) -> None:
        event = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.job_id == job_id).first()
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
) -> tuple[list[ZapierOutboundEvent], int]:
    query = db.query(ZapierOutboundEvent).filter(ZapierOutboundEvent.organization_id == org_id)
    if status:
        query = query.filter(ZapierOutboundEvent.status == status)
    effective_offset = max(0, offset)
    effective_limit = max(1, min(limit, 200))
    items, total = paginate_query_by_offset(
        query.order_by(ZapierOutboundEvent.created_at.desc()),
        offset=effective_offset,
        limit=effective_limit,
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
        db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.organization_id == org_id,
            ZapierOutboundEvent.created_at >= cutoff,
            ZapierOutboundEvent.source != "test",
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
        warning_messages.append("Failure rate is elevated for Zapier outbound events.")
    if skipped_rate_alert:
        warning_messages.append("Skipped-event rate is elevated for Zapier outbound events.")

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
) -> ZapierOutboundEvent:
    event = (
        db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.id == event_id,
            ZapierOutboundEvent.organization_id == org_id,
        )
        .first()
    )
    if event is None:
        raise ValueError("Event not found")
    if event.status != "failed":
        raise ValueError("Only failed events can be retried")
    if event.job_id is None:
        raise ValueError("Failed event does not have a replayable job")

    job_service.replay_failed_job(
        db,
        org_id=org_id,
        job_id=event.job_id,
        reason=reason or "zapier_outbound_event_retry",
        commit=False,
    )

    event.status = "queued"
    event.last_error = None
    event.attempts = 0
    event.updated_at = _now_utc()
    db.commit()
    db.refresh(event)
    return event
