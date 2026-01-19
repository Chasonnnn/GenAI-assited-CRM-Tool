"""Job service - business logic for background job scheduling and processing."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Job
from app.db.enums import JobStatus, JobType


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
        type_values = [
            jt.value if isinstance(jt, JobType) else str(jt)
            for jt in job_types
            if jt
        ]
        if not type_values:
            return []
    query = db.query(Job).filter(
        Job.status == JobStatus.PENDING.value,
        Job.run_at <= now,
    )
    if type_values:
        query = query.filter(Job.job_type.in_(type_values))
    query = query.order_by(Job.run_at).limit(limit)
    if getattr(db.get_bind(), "dialect", None) and db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    jobs = query.all()
    if not jobs:
        return []

    for job in jobs:
        job.status = JobStatus.RUNNING.value
        job.attempts += 1

    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


def get_job(db: Session, job_id: UUID, org_id: UUID | None = None) -> Job | None:
    """Get a job by ID, optionally scoped to org."""
    query = db.query(Job).filter(Job.id == job_id)
    if org_id:
        query = query.filter(Job.organization_id == org_id)
    return query.first()


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


def mark_job_running(db: Session, job: Job) -> Job:
    """Mark a job as running (increment attempts)."""
    job.status = JobStatus.RUNNING.value
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(db: Session, job: Job) -> Job:
    """Mark a job as completed."""
    job.status = JobStatus.COMPLETED.value
    job.completed_at = datetime.now(timezone.utc)
    job.last_error = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(db: Session, job: Job, error: str) -> Job:
    """
    Mark a job as failed.

    If attempts < max_attempts, reset to pending for retry.
    """
    job.last_error = error
    if job.attempts < job.max_attempts:
        job.status = JobStatus.PENDING.value
    else:
        job.status = JobStatus.FAILED.value
    db.commit()
    db.refresh(job)
    return job
