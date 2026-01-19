from datetime import datetime, timezone
import uuid

import pytest

from app.db.enums import JobStatus, JobType
from app.db.models import Job, Organization
from app.db.session import SessionLocal
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


def test_claim_pending_jobs_skip_locked(db_engine):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("SKIP LOCKED behavior requires PostgreSQL")

    conn1 = db_engine.connect()
    conn2 = db_engine.connect()
    session1 = SessionLocal(bind=conn1)
    session2 = SessionLocal(bind=conn2)
    cleanup_conn = db_engine.connect()
    cleanup_session = SessionLocal(bind=cleanup_conn)

    org_id = None
    job_id = None
    try:
        org = Organization(
            id=uuid.uuid4(),
            name="Job Queue Org",
            slug=f"job-queue-{uuid.uuid4().hex[:8]}",
        )
        session1.add(org)
        session1.commit()
        org_id = org.id

        job = Job(
            organization_id=org.id,
            job_type=JobType.NOTIFICATION.value,
            payload={"message": "locked-job"},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        )
        session1.add(job)
        session1.commit()
        job_id = job.id

        session1.query(Job).filter(Job.id == job_id).with_for_update().one()

        claimed = job_service.claim_pending_jobs(session2, limit=1)
        assert claimed == []
    finally:
        session1.rollback()
        session2.rollback()
        if job_id:
            cleanup_session.query(Job).filter(Job.id == job_id).delete()
        if org_id:
            cleanup_session.query(Organization).filter(Organization.id == org_id).delete()
        cleanup_session.commit()
        cleanup_session.close()
        cleanup_conn.close()
        session1.close()
        session2.close()
        conn1.close()
        conn2.close()


def test_claim_pending_jobs_filters_by_type(db, test_org):
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
        job_type=JobType.CAMPAIGN_SEND,
        payload={"message": "job-2"},
        run_at=datetime.now(timezone.utc),
    )

    claimed = job_service.claim_pending_jobs(db, limit=10, job_types=[JobType.NOTIFICATION])
    assert len(claimed) == 1
    assert claimed[0].job_type == JobType.NOTIFICATION.value
