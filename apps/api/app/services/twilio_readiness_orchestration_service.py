"""Durable, coalesced admission for no-send Twilio readiness probes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import JobScope, JobStatus, JobType
from app.db.models import Job, TwilioRoute, TwilioSettings
from app.services import job_service, twilio_readiness_service, twilio_settings_service

# Half the send gate: one missed hourly pass still leaves a full refresh window
# before dispatch starts deferring sends as `<purpose>_provider_evidence_stale`.
REFRESH_EVIDENCE_AFTER = twilio_readiness_service.PROVIDER_EVIDENCE_MAX_AGE / 2


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


def _provider_evidence_due(route: TwilioRoute, *, now: datetime, settings_version: int) -> bool:
    evidence = route.capability_evidence or {}
    provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
    if provider.get("settings_version") != settings_version:
        return True
    try:
        checked = datetime.fromisoformat(str(provider.get("checked_at") or ""))
    except ValueError:
        return True
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    return now - checked.astimezone(UTC) > REFRESH_EVIDENCE_AFTER


def queue_due_refreshes(db: Session, *, now: datetime | None = None) -> int:
    """Queue a no-send check for each sending organization whose provider evidence is ageing.

    Returns the number of jobs created. Organizations that cannot send (disabled,
    no credentials, no configured route) are skipped so a broken setup is not
    probed every pass.
    """
    now = now or datetime.now(UTC)
    organization_ids = (
        db.execute(
            select(TwilioSettings.organization_id)
            .where(TwilioSettings.enabled.is_(True))
            .order_by(TwilioSettings.organization_id)
        )
        .scalars()
        .all()
    )
    created = 0
    for organization_id in organization_ids:
        settings = twilio_settings_service.get_settings(db, organization_id)
        if settings is None or not twilio_readiness_service.credentials_configured(settings):
            continue
        if not any(
            _route_sends(route)
            and _provider_evidence_due(route, now=now, settings_version=settings.current_version)
            for route in settings.routes
        ):
            continue
        if _queue_check(db, organization_id=organization_id)[1]:
            created += 1
    return created


def cached_readiness(db: Session, *, organization_id: uuid.UUID):
    return twilio_readiness_service.get_readiness(db, organization_id)
