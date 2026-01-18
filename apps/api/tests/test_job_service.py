from datetime import datetime, timezone

from app.db.enums import JobStatus, JobType
from app.services import job_service


def test_claim_pending_jobs_marks_running(db, test_org):
    job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.NOTIFICATION,
        payload={"message": "job-1"},
        run_at=datetime.now(timezone.utc),
    )
    job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.NOTIFICATION,
        payload={"message": "job-2"},
        run_at=datetime.now(timezone.utc),
    )

    claimed = job_service.claim_pending_jobs(db, limit=1)
    assert len(claimed) == 1
    claimed_job = claimed[0]
    assert claimed_job.status == JobStatus.RUNNING.value
    assert claimed_job.attempts == 1

    pending = job_service.get_pending_jobs(db, limit=10)
    assert len(pending) == 1
    assert pending[0].id != claimed_job.id
    assert pending[0].status == JobStatus.PENDING.value
