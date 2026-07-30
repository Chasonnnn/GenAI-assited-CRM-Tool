"""Autonomous recovery for stale delegated malware-scan claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import JobStatus, JobType
from app.db.models import Attachment, FormSubmissionFile, Job
from app.services import scan_dispatch_service

_REMOTE_SCAN_JOB_TYPES = {
    JobType.ATTACHMENT_SCAN.value,
    JobType.FORM_SUBMISSION_FILE_SCAN.value,
}
_TERMINAL_SCAN_STATUSES = {"clean", "infected", "error"}


@dataclass(frozen=True)
class ScanClaimRecoveryReport:
    completed: int = 0
    requeued: int = 0
    quarantined: int = 0

    @property
    def total(self) -> int:
        return self.completed + self.requeued + self.quarantined


def _resource_status(db: Session, job: Job) -> str | None:
    payload = job.payload or {}
    if job.job_type == JobType.ATTACHMENT_SCAN.value:
        raw_resource_id = payload.get("attachment_id")
        model = Attachment
    else:
        raw_resource_id = payload.get("submission_file_id")
        model = FormSubmissionFile
    if not raw_resource_id:
        return None
    return db.execute(
        select(model.scan_status).where(
            model.id == raw_resource_id,
            model.organization_id == job.organization_id,
        )
    ).scalar_one_or_none()


def _quarantine(job: Job, *, now: datetime, reason: str) -> None:
    payload = dict(job.payload or {})
    payload["_claim_recovery"] = {
        "non_replayable": True,
        "reason": reason,
        "recovered_at": now.isoformat(),
    }
    job.payload = payload
    job.status = JobStatus.FAILED.value
    job.last_error = reason
    job.completed_at = now
    job.claim_token = None
    job.claimed_at = None


def recover_stale_remote_scan_claims(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 50,
) -> ScanClaimRecoveryReport:
    """Recover stale scan claims without invoking scanners or user request paths."""
    recovered_at = now or datetime.now(UTC)
    stale_before = recovered_at - timedelta(
        seconds=scan_dispatch_service.scan_stale_lease_seconds()
    )
    statement = (
        select(Job)
        .where(
            Job.status == JobStatus.RUNNING.value,
            Job.job_type.in_(_REMOTE_SCAN_JOB_TYPES),
            Job.claim_token.is_not(None),
            Job.claimed_at.is_not(None),
            Job.claimed_at <= stale_before,
        )
        .order_by(Job.claimed_at, Job.id)
        .limit(max(1, min(limit, 500)))
        .execution_options(populate_existing=True)
    )
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)

    jobs = list(db.execute(statement).scalars())
    completed = 0
    requeued = 0
    quarantined = 0
    for job in jobs:
        status = _resource_status(db, job)
        if status in _TERMINAL_SCAN_STATUSES:
            job.status = JobStatus.COMPLETED.value
            job.completed_at = recovered_at
            job.last_error = None
            job.claim_token = None
            job.claimed_at = None
            completed += 1
            continue

        if status == "pending" and job.attempts < job.max_attempts:
            job.status = JobStatus.PENDING.value
            job.run_at = recovered_at
            job.completed_at = None
            job.last_error = "Recovered stale remote scan claim after ambiguous dispatch"
            job.claim_token = None
            job.claimed_at = None
            requeued += 1
            continue

        reason = (
            "Remote scan claim exhausted its attempts"
            if status == "pending"
            else "Remote scan resource was not found in the job organization"
        )
        _quarantine(job, now=recovered_at, reason=reason)
        quarantined += 1

    db.commit()
    return ScanClaimRecoveryReport(
        completed=completed,
        requeued=requeued,
        quarantined=quarantined,
    )
