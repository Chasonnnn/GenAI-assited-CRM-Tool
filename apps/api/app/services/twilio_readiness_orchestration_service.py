"""Durable, coalesced admission for no-send Twilio readiness probes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import JobScope, JobStatus, JobType
from app.db.models import Job
from app.services import job_service, twilio_readiness_service, twilio_settings_service


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


def queue_check(
    db: Session,
    *,
    organization_id: uuid.UUID,
) -> TwilioReadinessCheckView:
    """Queue at most one active readiness check for this organization."""
    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    _lock_route(db, organization_id)
    active = db.execute(
        _active_query(organization_id).order_by(Job.created_at, Job.id).limit(1)
    ).scalar_one_or_none()
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
    return TwilioReadinessCheckView(
        check_status=("running" if active.status == JobStatus.RUNNING.value else "queued"),
        queued_at=queued_at,
    )


def cached_readiness(db: Session, *, organization_id: uuid.UUID):
    return twilio_readiness_service.get_readiness(db, organization_id)
