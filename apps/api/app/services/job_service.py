"""Job service - business logic for background job scheduling and processing."""

from collections.abc import Collection
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.enums import JobStatus, JobType


class JobClaimLost(RuntimeError):
    """A stale worker tried to finish a job claimed by a newer generation."""


DELEGATED_SCAN_JOB_TYPES = frozenset(
    {
        JobType.ATTACHMENT_SCAN.value,
        JobType.FORM_SUBMISSION_FILE_SCAN.value,
    }
)


def enqueue_job(
    db: Session,
    org_id: UUID,
    job_type: JobType,
    payload: dict,
    run_at: datetime | None = None,
    idempotency_key: str | None = None,
    commit: bool = True,
) -> Job:
    """
    Enqueue a new background job.

    If run_at is None, the job runs immediately.
    If idempotency_key is provided, duplicate jobs with same key will fail
    with IntegrityError (caller should catch and handle).
    """
    job = Job(
        organization_id=org_id,
        job_type=job_type.value,
        payload=payload,
        run_at=run_at or datetime.now(timezone.utc),
        status=JobStatus.PENDING.value,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def schedule_job(
    db: Session,
    org_id: UUID,
    job_type: JobType,
    payload: dict,
    run_at: datetime | None = None,
    idempotency_key: str | None = None,
) -> Job:
    """Schedule a new background job and commit it."""
    return enqueue_job(
        db=db,
        org_id=org_id,
        job_type=job_type,
        payload=payload,
        run_at=run_at,
        idempotency_key=idempotency_key,
        commit=True,
    )


def get_pending_jobs(db: Session, limit: int = 10) -> list[Job]:
    """
    Get pending jobs that are due to run.

    Returns jobs where status='pending' and run_at <= now, ordered by run_at.
    """
    now = datetime.now(timezone.utc)
    return (
        db.query(Job)
        .filter(
            Job.status == JobStatus.PENDING.value,
            Job.run_at <= now,
        )
        .order_by(Job.run_at)
        .limit(limit)
        .all()
    )


def claim_pending_jobs(
    db: Session,
    limit: int = 10,
    job_types: list[JobType] | list[str] | None = None,
) -> list[Job]:
    """
    Atomically claim pending jobs by marking them running.

    Uses row locking on Postgres to avoid duplicate claims across workers.
    """
    now = datetime.now(timezone.utc)
    type_values: list[str] | None = None
    if job_types is not None:
        type_values = [jt.value if isinstance(jt, JobType) else str(jt) for jt in job_types if jt]
        if not type_values:
            return []
    query = select(Job.id).where(
        Job.status == JobStatus.PENDING.value,
        Job.run_at <= now,
    )
    if type_values:
        query = query.where(Job.job_type.in_(type_values))
    query = query.order_by(Job.run_at, Job.id).limit(limit)
    if getattr(db.get_bind(), "dialect", None) and db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    claimed_ids = list(db.execute(query).scalars())
    if not claimed_ids:
        return []

    db.execute(
        update(Job)
        .where(Job.id.in_(claimed_ids))
        .values(
            status=JobStatus.RUNNING.value,
            attempts=Job.attempts + 1,
            claim_token=func.gen_random_uuid(),
            claimed_at=now,
        )
        .execution_options(synchronize_session=False)
    )

    db.commit()
    db.expire_all()

    claimed_jobs = db.query(Job).filter(Job.id.in_(claimed_ids)).all()
    claimed_by_id = {job.id: job for job in claimed_jobs}
    return [claimed_by_id[job_id] for job_id in claimed_ids if job_id in claimed_by_id]


def claim_job_for_dispatch(db: Session, job_id: UUID) -> Job | None:
    """Atomically transition a pending job to running for direct dispatch."""
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.PENDING.value,
            Job.run_at <= now,
        )
        .values(
            status=JobStatus.RUNNING.value,
            attempts=Job.attempts + 1,
            run_at=now,
            completed_at=None,
            last_error=None,
            claim_token=func.gen_random_uuid(),
            claimed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if (result.rowcount or 0) != 1:
        db.expire_all()
        return None

    db.commit()
    db.expire_all()
    return db.query(Job).filter(Job.id == job_id).first()


def heartbeat_job_claim(
    db: Session,
    *,
    job_id: UUID,
    claim_token: UUID,
    heartbeat_at: datetime | None = None,
) -> bool:
    """Extend only the still-current running claim lease."""
    result = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            Job.claim_token == claim_token,
        )
        .values(claimed_at=heartbeat_at or datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    refreshed = (result.rowcount or 0) == 1
    db.commit()
    db.expire_all()
    return refreshed


def recover_stale_worker_claims(
    db: Session,
    *,
    stale_before: datetime,
    recovered_at: datetime,
    retry_safe_job_types: Collection[str],
    limit: int,
) -> dict[str, int]:
    """Recover stale tokened worker claims without replaying uncertain side effects."""
    safe_job_types = set(retry_safe_job_types) - DELEGATED_SCAN_JOB_TYPES
    query = (
        select(Job)
        .where(
            Job.status == JobStatus.RUNNING.value,
            Job.claim_token.is_not(None),
            Job.claimed_at.is_not(None),
            Job.claimed_at <= stale_before,
            Job.job_type.notin_(DELEGATED_SCAN_JOB_TYPES),
        )
        .order_by(Job.claimed_at, Job.id)
        .limit(max(1, limit))
    )
    if getattr(db.get_bind(), "dialect", None) and db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    candidates = list(db.execute(query).scalars())
    result_counts = {"requeued": 0, "quarantined": 0}
    for job in candidates:
        claim_token = job.claim_token
        claimed_at = job.claimed_at
        if claim_token is None or claimed_at is None:
            continue

        retry_safe = job.job_type in safe_job_types and job.attempts < job.max_attempts
        action = "requeued" if retry_safe else "quarantined"
        payload = dict(job.payload or {})
        payload["_claim_recovery"] = {
            "schema_version": 1,
            "non_replayable": not retry_safe,
            "reason_code": (
                "stale_claim_retry_safe" if retry_safe else "stale_claim_outcome_unknown"
            ),
            "recovered_at": recovered_at.isoformat(),
            "previous_claimed_at": claimed_at.isoformat(),
            "job_type": job.job_type,
        }
        values = {
            "status": JobStatus.PENDING.value if retry_safe else JobStatus.FAILED.value,
            "payload": payload,
            "last_error": (
                "Stale worker claim recovered for audited retry"
                if retry_safe
                else "Stale worker claim quarantined because the side-effect outcome is unknown"
            ),
            "run_at": recovered_at if retry_safe else job.run_at,
            "completed_at": None if retry_safe else recovered_at,
            "claim_token": None,
            "claimed_at": None,
        }
        updated = db.execute(
            update(Job)
            .where(
                Job.id == job.id,
                Job.status == JobStatus.RUNNING.value,
                Job.claim_token == claim_token,
                Job.claimed_at == claimed_at,
                Job.claimed_at <= stale_before,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if (updated.rowcount or 0) == 1:
            result_counts[action] += 1

    db.commit()
    db.expire_all()
    return result_counts


def recover_stale_running_job(
    db: Session,
    *,
    job: Job,
    stale_before: datetime,
    recovered_at: datetime,
    error: str,
    commit: bool = False,
) -> bool:
    """Atomically requeue a stale job without overwriting a newer claim."""
    expected_claim_token = job.claim_token
    if expected_claim_token is None:
        claim_filter = Job.claim_token.is_(None)
        stale_filter = Job.run_at <= stale_before
    else:
        claim_filter = Job.claim_token == expected_claim_token
        stale_filter = Job.claimed_at <= stale_before

    result = db.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.status == JobStatus.RUNNING.value,
            claim_filter,
            stale_filter,
        )
        .values(
            status=JobStatus.PENDING.value,
            last_error=error,
            run_at=recovered_at,
            completed_at=None,
            claim_token=None,
            claimed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    recovered = (result.rowcount or 0) == 1
    if recovered:
        if commit:
            db.commit()
        else:
            db.flush()
    db.expire(job)
    return recovered


def get_job(db: Session, job_id: UUID, org_id: UUID | None = None) -> Job | None:
    """Get a job by ID, optionally scoped to org."""
    query = db.query(Job).filter(Job.id == job_id)
    if org_id:
        query = query.filter(Job.organization_id == org_id)
    return query.first()


def get_job_by_idempotency_key(db: Session, *, org_id: UUID, idempotency_key: str) -> Job | None:
    """Return a job by idempotency key within organization scope."""
    return (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.idempotency_key == idempotency_key,
        )
        .first()
    )


def list_jobs(
    db: Session,
    org_id: UUID,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 50,
) -> list[Job]:
    """List jobs for an organization with optional filters."""
    query = db.query(Job).filter(Job.organization_id == org_id)
    if status:
        query = query.filter(Job.status == status.value)
    if job_type:
        query = query.filter(Job.job_type == job_type.value)
    return query.order_by(Job.created_at.desc()).limit(limit).all()


def list_dead_letter_jobs(
    db: Session,
    *,
    org_id: UUID,
    job_type: JobType | None = None,
    limit: int = 100,
) -> list[Job]:
    """List failed (dead-letter) jobs for an organization."""
    query = db.query(Job).filter(
        Job.organization_id == org_id,
        Job.status == JobStatus.FAILED.value,
    )
    if job_type:
        query = query.filter(Job.job_type == job_type.value)
    return query.order_by(Job.created_at.desc()).limit(max(1, min(limit, 500))).all()


def mark_job_running(db: Session, job: Job) -> Job:
    """Mark a job as running (increment attempts)."""
    job.status = JobStatus.RUNNING.value
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(db: Session, job: Job) -> Job:
    """Mark a job as completed."""
    if job.claim_token is not None:
        return complete_claimed_job(
            db,
            job_id=job.id,
            claim_token=job.claim_token,
        )
    job.status = JobStatus.COMPLETED.value
    job.completed_at = datetime.now(timezone.utc)
    job.last_error = None
    job.claim_token = None
    job.claimed_at = None
    db.commit()
    db.refresh(job)
    return job


def complete_claimed_job(
    db: Session,
    *,
    job_id: UUID,
    claim_token: UUID | None,
) -> Job:
    """Complete only the still-current worker claim."""
    completed_at = datetime.now(timezone.utc)
    claim_filter = (
        Job.claim_token.is_(None) if claim_token is None else Job.claim_token == claim_token
    )
    result = db.execute(
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            claim_filter,
        )
        .values(
            status=JobStatus.COMPLETED.value,
            completed_at=completed_at,
            last_error=None,
            claim_token=None,
            claimed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    if (result.rowcount or 0) != 1:
        db.expire_all()
        raise JobClaimLost("job claim is no longer current")
    db.commit()
    db.expire_all()
    return db.query(Job).filter(Job.id == job_id).one()


def mark_job_failed(db: Session, job: Job, error: str) -> Job:
    """
    Mark a job as failed.

    If attempts < max_attempts, reset to pending for retry.
    """
    if job.claim_token is not None:
        return fail_claimed_job(
            db,
            job_id=job.id,
            claim_token=job.claim_token,
            error=error,
        )

    job.last_error = error
    if job.attempts < job.max_attempts:
        job.status = JobStatus.PENDING.value
    else:
        job.status = JobStatus.FAILED.value
    job.claim_token = None
    job.claimed_at = None
    db.commit()
    db.refresh(job)
    return job


def fail_claimed_job(
    db: Session,
    *,
    job_id: UUID,
    claim_token: UUID | None,
    error: str,
) -> Job:
    """Fail or requeue only the still-current worker claim."""
    claim_filter = (
        Job.claim_token.is_(None) if claim_token is None else Job.claim_token == claim_token
    )
    job = db.execute(
        select(Job)
        .where(
            Job.id == job_id,
            Job.status == JobStatus.RUNNING.value,
            claim_filter,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if job is None:
        db.expire_all()
        raise JobClaimLost("job claim is no longer current")

    job.last_error = error
    if job.attempts < job.max_attempts:
        job.status = JobStatus.PENDING.value
    else:
        job.status = JobStatus.FAILED.value
    job.claim_token = None
    job.claimed_at = None
    db.commit()
    db.refresh(job)
    return job


def replay_failed_job(
    db: Session,
    *,
    org_id: UUID,
    job_id: UUID,
    reason: str | None = None,
    commit: bool = True,
) -> Job:
    """Reset a failed job back to pending for replay."""
    job = (
        db.query(Job)
        .filter(
            Job.id == job_id,
            Job.organization_id == org_id,
        )
        .first()
    )
    if job is None:
        raise ValueError("Job not found")
    if job.status != JobStatus.FAILED.value:
        raise ValueError("Only failed jobs can be replayed")

    now = datetime.now(timezone.utc)
    payload = dict(job.payload or {})
    reconciliation_meta = payload.get("_reconciliation")
    if isinstance(reconciliation_meta, dict) and reconciliation_meta.get("non_replayable") is True:
        raise ValueError("Cannot replay job with non-replayable reconciliation")
    claim_recovery_meta = payload.get("_claim_recovery")
    if isinstance(claim_recovery_meta, dict) and claim_recovery_meta.get("non_replayable") is True:
        raise ValueError("Cannot replay job with non-replayable claim recovery")
    replay_meta = payload.get("_replay")
    if not isinstance(replay_meta, dict):
        replay_meta = {}
    replay_count = int(replay_meta.get("count", 0) or 0) + 1
    payload["_replay"] = {
        "count": replay_count,
        "reason": reason,
        "replayed_at": now.isoformat(),
    }
    job.payload = payload

    job.status = JobStatus.PENDING.value
    job.run_at = now
    job.attempts = 0
    job.completed_at = None
    job.last_error = None

    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def replay_failed_jobs(
    db: Session,
    *,
    org_id: UUID,
    job_type: JobType | None = None,
    limit: int = 100,
    reason: str | None = None,
) -> list[Job]:
    """Replay a batch of failed jobs."""
    jobs = list_dead_letter_jobs(
        db,
        org_id=org_id,
        job_type=job_type,
        limit=limit,
    )
    replayed: list[Job] = []
    for job in jobs:
        replayed.append(
            replay_failed_job(
                db,
                org_id=org_id,
                job_id=job.id,
                reason=reason,
                commit=False,
            )
        )
    db.commit()
    for job in replayed:
        db.refresh(job)
    return replayed
