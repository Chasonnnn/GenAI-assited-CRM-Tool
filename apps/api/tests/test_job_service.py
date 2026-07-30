import uuid
from datetime import UTC, datetime, timedelta

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
            run_at=datetime.now(UTC),
            status=JobStatus.PENDING.value,
        )
        job_2 = Job(
            organization_id=org.id,
            job_type=claim_test_job_type,
            payload={"message": "job-2"},
            run_at=datetime.now(UTC),
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
        assert claimed_job.claimed_at <= datetime.now(UTC)

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
            run_at=datetime.now(UTC),
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
        run_at=datetime.now(UTC),
    )
    job_service.schedule_job(
        db=db,
        org_id=test_org.id,
        job_type=JobType.CAMPAIGN_SEND,
        payload={"message": "job-2"},
        run_at=datetime.now(UTC),
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
        run_at=datetime.now(UTC),
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
        run_at=datetime.now(UTC),
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
        run_at=datetime.now(UTC),
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
        run_at=datetime.now(UTC),
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
            claimed_at=datetime.now(UTC),
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


def test_claim_heartbeat_extends_only_current_token(db, test_org):
    current_token = uuid.uuid4()
    stale_token = uuid.uuid4()
    original_claimed_at = datetime.now(UTC) - timedelta(minutes=5)
    heartbeat_at = datetime.now(UTC)
    job = Job(
        organization_id=test_org.id,
        job_type=JobType.NOTIFICATION.value,
        payload={},
        run_at=original_claimed_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=current_token,
        claimed_at=original_claimed_at,
    )
    db.add(job)
    db.commit()

    assert (
        job_service.heartbeat_job_claim(
            db,
            job_id=job.id,
            claim_token=stale_token,
            heartbeat_at=heartbeat_at,
        )
        is False
    )
    db.expire_all()
    unchanged = db.query(Job).filter(Job.id == job.id).one()
    assert unchanged.claim_token == current_token
    assert unchanged.claimed_at == original_claimed_at

    assert (
        job_service.heartbeat_job_claim(
            db,
            job_id=job.id,
            claim_token=current_token,
            heartbeat_at=heartbeat_at,
        )
        is True
    )
    db.expire_all()
    refreshed = db.query(Job).filter(Job.id == job.id).one()
    assert refreshed.claim_token == current_token
    assert refreshed.claimed_at == heartbeat_at


def test_stale_claim_reaper_requeues_only_explicitly_retry_safe_types(db, test_org):
    now = datetime.now(UTC)
    stale_at = now - timedelta(minutes=10)
    retry_safe = Job(
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_APPROVAL_EXPIRY.value,
        payload={"scope": "expired-approvals"},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    uncertain = Job(
        organization_id=test_org.id,
        job_type=JobType.SEND_EMAIL.value,
        payload={"email_log_id": str(uuid.uuid4())},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    unknown = Job(
        organization_id=test_org.id,
        job_type="future_unknown_side_effect",
        payload={},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    db.add_all([retry_safe, uncertain, unknown])
    db.commit()

    result = job_service.recover_stale_worker_claims(
        db,
        stale_before=now - timedelta(minutes=5),
        recovered_at=now,
        retry_safe_job_types={JobType.WORKFLOW_APPROVAL_EXPIRY.value},
        limit=10,
    )

    assert result == {"requeued": 1, "quarantined": 2}
    db.expire_all()
    recovered_safe = db.query(Job).filter(Job.id == retry_safe.id).one()
    quarantined_uncertain = db.query(Job).filter(Job.id == uncertain.id).one()
    quarantined_unknown = db.query(Job).filter(Job.id == unknown.id).one()
    assert recovered_safe.status == JobStatus.PENDING.value
    assert recovered_safe.claim_token is None
    assert recovered_safe.claimed_at is None
    assert recovered_safe.payload["_claim_recovery"]["non_replayable"] is False
    assert quarantined_uncertain.status == JobStatus.FAILED.value
    assert quarantined_uncertain.claim_token is None
    assert quarantined_uncertain.claimed_at is None
    assert quarantined_uncertain.payload["_claim_recovery"]["non_replayable"] is True
    assert quarantined_unknown.status == JobStatus.FAILED.value
    assert quarantined_unknown.payload["_claim_recovery"]["non_replayable"] is True


def test_stale_claim_reaper_cannot_touch_fresh_replaced_or_specialized_claims(db, test_org):
    now = datetime.now(UTC)
    stale_at = now - timedelta(minutes=10)
    fresh_token = uuid.uuid4()
    replaced_token = uuid.uuid4()
    fresh = Job(
        organization_id=test_org.id,
        job_type=JobType.NOTIFICATION.value,
        payload={},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=fresh_token,
        claimed_at=now,
    )
    replaced = Job(
        organization_id=test_org.id,
        job_type=JobType.SEND_EMAIL.value,
        payload={},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    delegated_scan = Job(
        organization_id=test_org.id,
        job_type=JobType.ATTACHMENT_SCAN.value,
        payload={"attachment_id": str(uuid.uuid4())},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    resend_reconciliation = Job(
        organization_id=test_org.id,
        job_type=JobType.RESEND_EVENT_RECONCILE.value,
        payload={"event_id": str(uuid.uuid4())},
        run_at=stale_at,
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid.uuid4(),
        claimed_at=stale_at,
    )
    db.add_all([fresh, replaced, delegated_scan, resend_reconciliation])
    db.commit()
    replaced_id = replaced.id
    db.execute(
        update(Job)
        .where(Job.id == replaced_id)
        .values(claim_token=replaced_token, claimed_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()

    result = job_service.recover_stale_worker_claims(
        db,
        stale_before=now - timedelta(minutes=5),
        recovered_at=now,
        retry_safe_job_types={JobType.WORKFLOW_APPROVAL_EXPIRY.value},
        limit=10,
    )

    assert result == {"requeued": 0, "quarantined": 0}
    db.expire_all()
    current_fresh = db.query(Job).filter(Job.id == fresh.id).one()
    current_replaced = db.query(Job).filter(Job.id == replaced_id).one()
    current_scan = db.query(Job).filter(Job.id == delegated_scan.id).one()
    current_reconciliation = db.query(Job).filter(Job.id == resend_reconciliation.id).one()
    assert current_fresh.status == JobStatus.RUNNING.value
    assert current_fresh.claim_token == fresh_token
    assert current_fresh.claimed_at == now
    assert current_replaced.status == JobStatus.RUNNING.value
    assert current_replaced.claim_token == replaced_token
    assert current_replaced.claimed_at == now
    assert current_scan.status == JobStatus.RUNNING.value
    assert current_scan.claim_token is not None
    assert current_reconciliation.status == JobStatus.RUNNING.value
    assert current_reconciliation.claim_token is not None
    assert current_reconciliation.payload.get("_claim_recovery") is None
    assert current_scan.claimed_at == stale_at


def test_stale_recovery_does_not_clear_a_newer_claim(db, test_org):
    old_token = uuid.uuid4()
    newer_token = uuid.uuid4()
    now = datetime.now(UTC)
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


def test_operator_quarantined_job_cannot_be_replayed(db, test_org):
    job = Job(
        organization_id=test_org.id,
        job_type=JobType.WORKFLOW_EMAIL.value,
        payload={
            "email_template_snapshot": {"subject": "Legacy", "body": "Do not resend"},
            "_reconciliation": {
                "schema_version": 1,
                "non_replayable": True,
                "reason_code": "workflow_email_outcome_unknown",
            },
        },
        run_at=datetime.now(UTC),
        status=JobStatus.FAILED.value,
        attempts=1,
    )
    db.add(job)
    db.commit()

    with pytest.raises(ValueError, match="non-replayable reconciliation"):
        job_service.replay_failed_job(
            db,
            org_id=test_org.id,
            job_id=job.id,
            reason="operator retry",
        )

    db.refresh(job)
    assert job.status == JobStatus.FAILED.value


def test_stale_claim_quarantine_cannot_be_replayed(db, test_org):
    job = Job(
        organization_id=test_org.id,
        job_type=JobType.SEND_EMAIL.value,
        payload={
            "email_log_id": str(uuid.uuid4()),
            "_claim_recovery": {
                "schema_version": 1,
                "non_replayable": True,
                "reason_code": "stale_claim_outcome_unknown",
            },
        },
        run_at=datetime.now(UTC),
        status=JobStatus.FAILED.value,
        attempts=1,
    )
    db.add(job)
    db.commit()

    with pytest.raises(ValueError, match="non-replayable claim recovery"):
        job_service.replay_failed_job(
            db,
            org_id=test_org.id,
            job_id=job.id,
            reason="operator retry",
        )

    db.refresh(job)
    assert job.status == JobStatus.FAILED.value
