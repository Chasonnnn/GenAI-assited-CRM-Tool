"""Durable orchestration around live Resend readiness probes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.enums import JobScope, JobStatus, JobType
from app.db.models import Job
from app.services import job_service, resend_readiness_service
from app.services.resend_readiness_snapshot_service import ReadinessSnapshotView

ReadinessCheckStatus = Literal["idle", "queued", "running", "stalled"]

READINESS_QUEUE_STALL_AFTER = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class ReadinessEnvelopeView:
    """Safe projection for a durable check and its cached provider result."""

    check_status: ReadinessCheckStatus
    queued_at: datetime | None
    last_snapshot: ReadinessSnapshotView


def _lock_route(db: Session, *, route_key: str) -> None:
    """Serialize check admission even when no active job row exists yet."""
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:route_key, 0))"),
        {"route_key": route_key},
    )


def _active_job_query(
    *,
    job_scope: JobScope,
    organization_id: UUID | None,
):
    query = select(Job).where(
        Job.job_type == JobType.RESEND_READINESS_CHECK.value,
        Job.job_scope == job_scope.value,
        Job.status.in_((JobStatus.PENDING.value, JobStatus.RUNNING.value)),
    )
    if job_scope is JobScope.ORGANIZATION:
        return query.where(Job.organization_id == organization_id)
    return query.where(Job.organization_id.is_(None))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _active_check_state(
    db: Session,
    *,
    job_scope: JobScope,
    organization_id: UUID | None,
) -> tuple[ReadinessCheckStatus, datetime | None]:
    active_jobs = tuple(
        db.execute(
            _active_job_query(
                job_scope=job_scope,
                organization_id=organization_id,
            ).order_by(Job.created_at, Job.id)
        ).scalars()
    )
    running_job = next(
        (job for job in active_jobs if job.status == JobStatus.RUNNING.value),
        None,
    )
    if running_job is not None:
        return "running", _as_utc(running_job.created_at)

    pending_job = next(
        (job for job in active_jobs if job.status == JobStatus.PENDING.value),
        None,
    )
    if pending_job is None:
        return "idle", None

    queued_at = _as_utc(pending_job.created_at)
    if queued_at <= datetime.now(timezone.utc) - READINESS_QUEUE_STALL_AFTER:
        return "stalled", queued_at
    return "queued", queued_at


def get_organization_envelope(
    db: Session,
    *,
    organization_id: UUID,
) -> ReadinessEnvelopeView:
    """Read organization readiness from local state only."""
    check_status, queued_at = _active_check_state(
        db,
        job_scope=JobScope.ORGANIZATION,
        organization_id=organization_id,
    )
    return ReadinessEnvelopeView(
        check_status=check_status,
        queued_at=queued_at,
        last_snapshot=resend_readiness_service.get_cached_organization_readiness(
            db,
            organization_id=organization_id,
        ),
    )


def queue_organization_check(
    db: Session,
    *,
    organization_id: UUID,
) -> ReadinessEnvelopeView:
    """Coalesce and durably queue a read-only organization readiness probe."""
    _lock_route(db, route_key=f"resend-readiness:organization:{organization_id}")
    active_job = db.execute(
        _active_job_query(
            job_scope=JobScope.ORGANIZATION,
            organization_id=organization_id,
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
    ).scalar_one_or_none()
    if active_job is None:
        job_service.enqueue_job(
            db,
            org_id=organization_id,
            job_type=JobType.RESEND_READINESS_CHECK,
            payload={"provider_scope": JobScope.ORGANIZATION.value},
            commit=False,
        )
    db.commit()
    return get_organization_envelope(db, organization_id=organization_id)


def get_platform_envelope(db: Session) -> ReadinessEnvelopeView:
    """Read platform readiness from local state only."""
    check_status, queued_at = _active_check_state(
        db,
        job_scope=JobScope.PLATFORM,
        organization_id=None,
    )
    return ReadinessEnvelopeView(
        check_status=check_status,
        queued_at=queued_at,
        last_snapshot=resend_readiness_service.get_cached_platform_readiness(db),
    )


def queue_platform_check(db: Session) -> ReadinessEnvelopeView:
    """Coalesce and durably queue a read-only platform readiness probe."""
    _lock_route(db, route_key="resend-readiness:platform")
    active_job = db.execute(
        _active_job_query(
            job_scope=JobScope.PLATFORM,
            organization_id=None,
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
    ).scalar_one_or_none()
    if active_job is None:
        job_service.enqueue_platform_job(
            db,
            job_type=JobType.RESEND_READINESS_CHECK,
            payload={"provider_scope": JobScope.PLATFORM.value},
            commit=False,
        )
    db.commit()
    return get_platform_envelope(db)
