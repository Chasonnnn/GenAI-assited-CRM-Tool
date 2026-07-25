from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import update

from app.db.enums import JobStatus, JobType
from app.db.models import Job, Organization
from app.db.session import SessionLocal
from app.services import job_service


def test_claim_pending_jobs_marks_running(db_engine):
    conn = db_engine.connect()
    session = SessionLocal(bind=conn)
    verification_conn = db_engine.connect()
    verification_session = SessionLocal(bind=verification_conn)
    cleanup_conn = db_engine.connect()
    cleanup_session = SessionLocal(bind=cleanup_conn)

    org_id = None
    job_ids: list[uuid.UUID] = []
    try:
        org = Organization(
            id=uuid.uuid4(),
            name="Claim Jobs Org",
            slug=f"claim-jobs-{uuid.uuid4().hex[:8]}",
        )
        session.add(org)
        session.commit()
        org_id = org.id

        claim_test_job_type = f"job_claim_test_{uuid.uuid4().hex[:12]}"
        job_1 = Job(
            organization_id=org.id,
            job_type=claim_test_job_type,
            payload={"message": "job-1"},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        )
        job_2 = Job(
            organization_id=org.id,
            job_type=claim_test_job_type,
            payload={"message": "job-2"},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        )
        session.add_all([job_1, job_2])
        session.commit()
        job_ids = [job_1.id, job_2.id]

        claimed = job_service.claim_pending_jobs(
            session,
            limit=1,
            job_types=[claim_test_job_type],
        )
        assert len(claimed) == 1
        claimed_job = claimed[0]
        assert claimed_job.status == JobStatus.RUNNING.value
        assert claimed_job.attempts == 1
        assert claimed_job.claim_token is not None
        assert claimed_job.claimed_at is not None
        assert claimed_job.claimed_at <= datetime.now(timezone.utc)

        pending = (
            verification_session.query(Job)
            .filter(
                Job.id.in_(job_ids),
                Job.status == JobStatus.PENDING.value,
            )
            .all()
        )
        assert len(pending) == 1
        assert pending[0].id != claimed_job.id
        assert pending[0].status == JobStatus.PENDING.value
        assert pending[0].claim_token is None
        assert pending[0].claimed_at is None
    finally:
        session.rollback()
        verification_session.rollback()
        if job_ids:
            cleanup_session.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if org_id:
            cleanup_session.query(Organization).filter(Organization.id == org_id).delete(
                synchronize_session=False
            )
        cleanup_session.commit()
        cleanup_session.close()
        cleanup_conn.close()
        verification_session.close()
        verification_conn.close()
        session.close()
        conn.close()


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

        lock_test_job_type = f"job_lock_test_{uuid.uuid4().hex[:12]}"
        job = Job(
            organization_id=org.id,
            job_type=lock_test_job_type,
            payload={"message": "locked-job"},
            run_at=datetime.now(timezone.utc),
            status=JobStatus.PENDING.value,
        )
        session1.add(job)
        session1.commit()
        job_id = job.id

        session1.query(Job).filter(Job.id == job_id).with_for_update().one()

        claimed = job_service.claim_pending_jobs(
            session2,
            limit=1,
            job_types=[lock_test_job_type],
        )
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


def test_claim_job_for_dispatch_writes_claim_identity(db, test_org):
    job = job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN,
        payload={"attachment_id": str(uuid.uuid4())},
        run_at=datetime.now(timezone.utc),
    )

    claimed = job_service.claim_job_for_dispatch(db, job.id)

    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.attempts == 1
    assert claimed.claim_token is not None
    assert claimed.claimed_at is not None


def test_mark_job_completed_clears_current_claim_identity(db, test_org):
    claim_test_job_type = f"job_complete_test_{uuid.uuid4().hex[:12]}"
    job = Job(
        organization_id=test_org.id,
        job_type=claim_test_job_type,
        payload={},
        run_at=datetime.now(timezone.utc),
        status=JobStatus.PENDING.value,
    )
    db.add(job)
    db.commit()
    claimed = job_service.claim_pending_jobs(
        db,
        limit=1,
        job_types=[claim_test_job_type],
    )[0]

    completed = job_service.mark_job_completed(db, claimed)

    assert completed.status == JobStatus.COMPLETED.value
    assert completed.claim_token is None
    assert completed.claimed_at is None


def test_mark_job_failed_clears_current_claim_before_retry(db, test_org):
    claim_test_job_type = f"job_failure_test_{uuid.uuid4().hex[:12]}"
    job = Job(
        organization_id=test_org.id,
        job_type=claim_test_job_type,
        payload={},
        run_at=datetime.now(timezone.utc),
        status=JobStatus.PENDING.value,
        max_attempts=3,
    )
    db.add(job)
    db.commit()
    claimed = job_service.claim_pending_jobs(
        db,
        limit=1,
        job_types=[claim_test_job_type],
    )[0]

    retried = job_service.mark_job_failed(db, claimed, "retryable failure")

    assert retried.status == JobStatus.PENDING.value
    assert retried.last_error == "retryable failure"
    assert retried.claim_token is None
    assert retried.claimed_at is None


def test_stale_claim_token_cannot_complete_a_newer_claim(db, test_org):
    claim_test_job_type = f"job_stale_claim_test_{uuid.uuid4().hex[:12]}"
    job = Job(
        organization_id=test_org.id,
        job_type=claim_test_job_type,
        payload={},
        run_at=datetime.now(timezone.utc),
        status=JobStatus.PENDING.value,
    )
    db.add(job)
    db.commit()
    claimed = job_service.claim_pending_jobs(
        db,
        limit=1,
        job_types=[claim_test_job_type],
    )[0]
    stale_token = claimed.claim_token
    assert stale_token is not None
    newer_token = uuid.uuid4()
    db.execute(
        update(Job)
        .where(Job.id == claimed.id)
        .values(
            claim_token=newer_token,
            claimed_at=datetime.now(timezone.utc),
        )
        .execution_options(synchronize_session=False)
    )
    db.commit()

    with pytest.raises(job_service.JobClaimLost, match="no longer current"):
        job_service.complete_claimed_job(
            db,
            job_id=claimed.id,
            claim_token=stale_token,
        )

    db.expire_all()
    current = db.query(Job).filter(Job.id == claimed.id).one()
    assert current.status == JobStatus.RUNNING.value
    assert current.claim_token == newer_token
    assert current.completed_at is None


def test_stale_recovery_does_not_clear_a_newer_claim(db, test_org):
    old_token = uuid.uuid4()
    newer_token = uuid.uuid4()
    now = datetime.now(timezone.utc)
    job = Job(
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        payload={"attachment_id": str(uuid.uuid4())},
        run_at=now - timedelta(minutes=10),
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=old_token,
        claimed_at=now - timedelta(minutes=10),
    )
    db.add(job)
    db.commit()
    assert job.claim_token == old_token

    db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            claim_token=newer_token,
            claimed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    db.flush()

    recovered = job_service.recover_stale_running_job(
        db,
        job=job,
        stale_before=now - timedelta(minutes=5),
        recovered_at=now,
        error="stale scan lease",
    )

    assert recovered is False
    current = db.query(Job).filter(Job.id == job.id).one()
    assert current.status == JobStatus.RUNNING.value
    assert current.claim_token == newer_token
    assert current.claimed_at == now
