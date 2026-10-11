"""Durable, coalesced admission for no-send Twilio readiness probes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import JobScope, JobStatus, JobType
from app.db.models import Job, Organization, TwilioRoute, TwilioSettings
from app.services import job_service, twilio_readiness_service, twilio_settings_service

# Keeps carrier registration status current; sends use the latest evidence at any age.
REFRESH_EVIDENCE_AFTER = timedelta(hours=12)
# A probe that failed is retried, but a broken tenant is never probed more often than this.
FAILED_PROBE_RETRY_AFTER = timedelta(hours=1)
# Probes run sequentially on the shared job queue; the rest wait for the next pass.
REFRESH_BATCH_LIMIT = 20


@dataclass(frozen=True, slots=True)
class TwilioReadinessCheckView:
    check_status: str
    queued_at: datetime


def _lock_route(db: Session, organization_id: uuid.UUID) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"twilio-readiness:{organization_id}"},
        )


def _active_query(organization_id: uuid.UUID):
    return select(Job).where(
        Job.organization_id == organization_id,
        Job.job_scope == JobScope.ORGANIZATION.value,
        Job.job_type == JobType.TWILIO_READINESS_CHECK.value,
        Job.status.in_((JobStatus.PENDING.value, JobStatus.RUNNING.value)),
    )


def _queue_check(
    db: Session,
    *,
    organization_id: uuid.UUID,
) -> tuple[TwilioReadinessCheckView, bool]:
    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    _lock_route(db, organization_id)
    active = db.execute(
        _active_query(organization_id).order_by(Job.created_at, Job.id).limit(1)
    ).scalar_one_or_none()
    created = active is None
    if active is None:
        active = job_service.enqueue_job(
            db,
            org_id=organization_id,
            job_type=JobType.TWILIO_READINESS_CHECK,
            payload={
                "provider_scope": JobScope.ORGANIZATION.value,
                "settings_version": settings.current_version,
            },
            commit=False,
        )
    db.commit()
    queued_at = active.created_at
    if queued_at.tzinfo is None:
        queued_at = queued_at.replace(tzinfo=UTC)
    view = TwilioReadinessCheckView(
        check_status=("running" if active.status == JobStatus.RUNNING.value else "queued"),
        queued_at=queued_at,
    )
    return view, created


def queue_check(
    db: Session,
    *,
    organization_id: uuid.UUID,
) -> TwilioReadinessCheckView:
    """Queue at most one active readiness check for this organization."""
    return _queue_check(db, organization_id=organization_id)[0]


def _route_sends(route: TwilioRoute) -> bool:
    return bool(
        route.enabled and route.messaging_service_sid_encrypted and route.sender_phone_encrypted
    )


def _parse_timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _evidence_sections(route: TwilioRoute) -> tuple[dict, dict]:
    evidence = route.capability_evidence or {}
    provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
    readiness = evidence.get("readiness") if isinstance(evidence.get("readiness"), dict) else {}
    return provider, readiness


def _last_attempt_at(route: TwilioRoute) -> datetime | None:
    return _parse_timestamp(_evidence_sections(route)[1].get("checked_at"))


def _provider_evidence_due(route: TwilioRoute, *, now: datetime, settings_version: int) -> bool:
    provider, readiness = _evidence_sections(route)
    # A failed probe for the current settings waits a bounded time before retry. This
    # runs first: a full failure leaves the provider section missing, and a part-way
    # failure stamps incomplete route facts with a fresh checked_at; neither may be
    # probed every pass, nor left blocking sends until the evidence ages.
    if readiness.get("error_code") and readiness.get("settings_version") == settings_version:
        attempted = _parse_timestamp(readiness.get("checked_at"))
        return attempted is None or now - attempted > FAILED_PROBE_RETRY_AFTER
    if provider.get("settings_version") != settings_version:
        return True
    checked = _parse_timestamp(provider.get("checked_at"))
    if checked is None:
        return True
    return now - checked > REFRESH_EVIDENCE_AFTER


def queue_due_refreshes(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = REFRESH_BATCH_LIMIT,
) -> int:
    """Queue a no-send check for each sending organization whose provider evidence is ageing.

    Returns the number of jobs created, at most ``limit`` per pass so one tick never
    puts a long run of sequential provider probes ahead of other queued work.
    Organizations that cannot send (soft-deleted, disabled, no credentials, no
    configured route) are skipped so a broken setup is not probed every pass.
    """
    now = now or datetime.now(UTC)
    organization_ids = (
        db.execute(
            select(TwilioSettings.organization_id)
            .join(Organization, Organization.id == TwilioSettings.organization_id)
            .where(TwilioSettings.enabled.is_(True), Organization.deleted_at.is_(None))
            .order_by(TwilioSettings.organization_id)
        )
        .scalars()
        .all()
    )
    never = datetime.min.replace(tzinfo=UTC)
    due: list[tuple[datetime, uuid.UUID]] = []
    for organization_id in organization_ids:
        settings = twilio_settings_service.get_settings(db, organization_id)
        if settings is None or not twilio_readiness_service.credentials_configured(settings):
            continue
        sending = [route for route in settings.routes if _route_sends(route)]
        if not any(
            _provider_evidence_due(route, now=now, settings_version=settings.current_version)
            for route in sending
        ):
            continue
        attempts = [attempt for route in sending if (attempt := _last_attempt_at(route))]
        due.append((max(attempts) if attempts else never, organization_id))
    # Least recently probed first, so a run of failing tenants cannot fill the
    # batch every pass and starve the rest.
    due.sort()
    created = 0
    for _, organization_id in due:
        if created >= limit:
            break
        if _queue_check(db, organization_id=organization_id)[1]:
            created += 1
    return created


def cached_readiness(db: Session, *, organization_id: uuid.UUID):
    return twilio_readiness_service.get_readiness(db, organization_id)
