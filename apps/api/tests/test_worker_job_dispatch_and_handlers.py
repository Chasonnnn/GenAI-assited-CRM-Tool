from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.db.enums import JobStatus, JobType
from app.db.models import Job, Organization
from app import worker


class _CtxSession:
    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
def worker_db(db_engine):
    connection = db_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


def _job(
    *,
    job_type: str,
    status: str = JobStatus.PENDING.value,
    attempts: int = 1,
    max_attempts: int = 3,
    payload: dict | None = None,
    claim_token=None,
):
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        job_type=job_type,
        status=status,
        attempts=attempts,
        max_attempts=max_attempts,
        payload=payload or {},
        run_at=datetime.now(timezone.utc),
        claim_token=claim_token,
    )


def test_worker_env_flags_and_backoff(monkeypatch):
    assert worker._env_flag_enabled(None, default=True) is True
    assert worker._env_flag_enabled(" false ", default=True) is False
    assert worker._env_flag_enabled("1", default=False) is True
    assert worker.parse_worker_job_types("send_email, nope, campaign_send") == [
        JobType.SEND_EMAIL.value,
        JobType.CAMPAIGN_SEND.value,
    ]
    assert worker.parse_worker_job_types("") is None

    monkeypatch.setattr(worker.secrets, "randbelow", lambda n: 7)
    assert worker._rate_limit_backoff_seconds(1) == 67
    assert worker._rate_limit_backoff_seconds(10) <= 3630


def test_worker_claimed_job_types_exclude_remote_scan_jobs(monkeypatch):
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(
        worker.scan_dispatch_service,
        "remote_scan_dispatch_configured",
        lambda: True,
    )

    claimed = worker._claimed_job_types()

    assert claimed is not None
    assert JobType.ATTACHMENT_SCAN.value not in claimed
    assert JobType.FORM_SUBMISSION_FILE_SCAN.value not in claimed
    assert JobType.SEND_EMAIL.value in claimed


@pytest.mark.asyncio
async def test_cutover_hold_starts_neither_heartbeat_nor_reaper(monkeypatch):
    stop_event = asyncio.Event()

    monkeypatch.setattr(worker, "WORKER_CUTOVER_HOLD", True)
    monkeypatch.setattr(
        worker,
        "SessionLocal",
        lambda: pytest.fail("held worker must not open a database session"),
    )
    monkeypatch.setattr(
        worker,
        "_claimed_job_types",
        lambda: pytest.fail("held worker must not resolve claimable job types"),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *_args, **_kwargs: pytest.fail("held worker must not run schedulers"),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *_args, **_kwargs: pytest.fail("held worker must not run schedulers"),
    )
    monkeypatch.setattr(
        worker.job_service,
        "claim_pending_jobs",
        lambda *_args, **_kwargs: pytest.fail("held worker must not claim jobs"),
    )
    monkeypatch.setattr(
        worker.job_service,
        "recover_stale_worker_claims",
        lambda *_args, **_kwargs: pytest.fail("held worker must not reap claims"),
    )
    monkeypatch.setattr(
        worker.scan_claim_recovery_service,
        "recover_stale_remote_scan_claims",
        lambda *_args, **_kwargs: pytest.fail("held worker must not reap scan claims"),
    )
    monkeypatch.setattr(
        worker,
        "_start_claim_heartbeat",
        lambda *_args, **_kwargs: pytest.fail("held worker must not start heartbeats"),
    )

    task = asyncio.create_task(worker.worker_loop(stop_event))
    await asyncio.sleep(0)

    assert task.done() is False
    stop_event.set()
    await asyncio.wait_for(task, timeout=1)

    assert task.done() is True


@pytest.mark.asyncio
async def test_worker_periodically_recovers_stale_claims_before_claiming(monkeypatch, db):
    stop_event = asyncio.Event()
    recovered: list[dict] = []
    scan_recovered: list[dict] = []

    monkeypatch.setattr(worker, "WORKER_CUTOVER_HOLD", False)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "_claimed_job_types", lambda: [JobType.NOTIFICATION.value])
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _recover(_session, **kwargs):
        recovered.append(kwargs)
        return {"requeued": 0, "quarantined": 0}

    def _claim(*_args, **_kwargs):
        stop_event.set()
        return []

    monkeypatch.setattr(worker.job_service, "recover_stale_worker_claims", _recover)
    monkeypatch.setattr(
        worker.scan_claim_recovery_service,
        "recover_stale_remote_scan_claims",
        lambda _session, **kwargs: (
            scan_recovered.append(kwargs)
            or SimpleNamespace(total=0, completed=0, requeued=0, quarantined=0)
        ),
    )
    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    await worker.worker_loop(stop_event)

    assert len(recovered) == 1
    assert recovered[0]["retry_safe_job_types"] == {JobType.WORKFLOW_APPROVAL_EXPIRY.value}
    assert recovered[0]["limit"] == worker.WORKER_STALE_CLAIM_REAPER_BATCH_SIZE
    assert scan_recovered == [
        {
            "now": recovered[0]["recovered_at"],
            "limit": worker.WORKER_STALE_CLAIM_REAPER_BATCH_SIZE,
        }
    ]
    stale_before = recovered[0]["stale_before"]
    recovered_at = recovered[0]["recovered_at"]
    assert recovered_at - stale_before == timedelta(seconds=worker.WORKER_CLAIM_LEASE_SECONDS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_type,payload",
    [
        (JobType.SEND_EMAIL.value, {"email_log_id": str(uuid4())}),
        (JobType.ORG_DELETE.value, {"organization_id": str(uuid4())}),
    ],
    ids=["email", "organization-delete"],
)
async def test_stale_side_effect_claim_is_quarantined_without_handler_call(
    monkeypatch,
    db,
    test_org,
    job_type,
    payload,
):
    now = datetime.now(timezone.utc)
    job = Job(
        organization_id=test_org.id,
        job_type=job_type,
        payload=payload,
        run_at=now - timedelta(hours=1),
        status=JobStatus.RUNNING.value,
        attempts=1,
        claim_token=uuid4(),
        claimed_at=now - timedelta(seconds=worker.WORKER_CLAIM_LEASE_SECONDS + 1),
    )
    db.add(job)
    db.commit()
    job_id = job.id
    stop_event = asyncio.Event()
    claim_pending_jobs = worker.job_service.claim_pending_jobs

    monkeypatch.setattr(worker, "WORKER_CUTOVER_HOLD", False)
    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "_claimed_job_types", lambda: [job_type])
    monkeypatch.setattr(worker, "SESSION_CLEANUP_INTERVAL_SECONDS", 10**12)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "process_job",
        lambda *_args, **_kwargs: pytest.fail(
            "quarantined stale side-effect jobs must not invoke their handler"
        ),
    )

    def _claim(session, *, limit, job_types):
        stop_event.set()
        return claim_pending_jobs(session, limit=limit, job_types=job_types)

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    await worker.worker_loop(stop_event)

    db.expire_all()
    quarantined = db.query(Job).filter(Job.id == job_id).one()
    assert quarantined.status == JobStatus.FAILED.value
    assert quarantined.claim_token is None
    assert quarantined.claimed_at is None
    assert quarantined.payload["_claim_recovery"]["non_replayable"] is True
    assert quarantined.payload["_claim_recovery"]["reason_code"] == ("stale_claim_outcome_unknown")


def test_worker_logs_retryable_job_failures_at_warning(caplog):
    job = _job(
        job_type=JobType.TICKET_OUTBOUND_SEND.value,
        status=JobStatus.PENDING.value,
        attempts=1,
        max_attempts=3,
    )

    with caplog.at_level(logging.WARNING):
        worker._log_job_failure(job, RuntimeError("boom"))

    assert "will retry" in caplog.text
    assert "type=ticket_outbound_send" in caplog.text
    assert "job_status=pending" in caplog.text
    assert "final=false" in caplog.text
    assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_worker_logs_final_job_failures_at_error(caplog):
    job = _job(
        job_type=JobType.TICKET_OUTBOUND_SEND.value,
        status=JobStatus.FAILED.value,
        attempts=3,
        max_attempts=3,
    )

    with caplog.at_level(logging.WARNING):
        worker._log_job_failure(job, RuntimeError("boom"))

    assert "failed permanently" in caplog.text
    assert "type=ticket_outbound_send" in caplog.text
    assert "job_status=failed" in caplog.text
    assert "final=true" in caplog.text
    assert any(record.levelno >= logging.ERROR for record in caplog.records)


def test_worker_resolve_integration_keys(db):
    keys = worker._resolve_integration_keys(
        db,
        _job(
            job_type=JobType.TICKET_OUTBOUND_SEND.value,
            payload={"mailbox_id": "m1", "mode": "reply"},
        ),
        integration_type="worker",
    )
    assert "mailbox:m1" in keys
    assert "ticket_outbound_reply" in keys

    keys = worker._resolve_integration_keys(
        db,
        _job(
            job_type=JobType.META_FORM_SYNC.value,
            payload={"page_id": "p1", "page_ids": ["p1", "p2"]},
        ),
        integration_type="meta_forms",
    )
    assert keys == ["p1", "p2"]


def test_worker_record_success_and_failure(monkeypatch, db):
    success_calls: list[tuple[str, str | None]] = []
    error_calls: list[tuple[str, str | None]] = []
    alerts: list[dict] = []

    monkeypatch.setattr(
        "app.services.ops_service.record_success",
        lambda db, org_id, integration_type, integration_key=None: success_calls.append(
            (integration_type, integration_key)
        ),
    )
    monkeypatch.setattr(
        "app.services.ops_service.record_error",
        lambda db, org_id, integration_type, error_message, integration_key=None: (
            error_calls.append((integration_type, integration_key))
        ),
    )
    monkeypatch.setattr(
        "app.services.alert_service.record_alert_isolated",
        lambda **kwargs: alerts.append(kwargs),
    )

    meta_job = _job(
        job_type=JobType.META_FORM_SYNC.value,
        payload={"page_id": "page-1"},
    )
    worker._record_job_success(db, meta_job)
    assert success_calls

    failed_job = _job(
        job_type=JobType.META_FORM_SYNC.value,
        attempts=3,
        max_attempts=3,
        payload={"email_log_id": str(uuid4())},
    )
    worker._record_job_failure(db, failed_job, "boom", exception=RuntimeError("boom"))
    assert error_calls
    assert alerts


def test_worker_rate_limit_classification(monkeypatch):
    from app.services import meta_token_service

    monkeypatch.setattr(
        meta_token_service,
        "classify_meta_error",
        lambda exc: meta_token_service.ErrorCategory.RATE_LIMIT,
    )
    rate_limited = worker._is_meta_rate_limit_error(
        _job(job_type=JobType.META_SPEND_SYNC.value),
        "rate limited",
    )
    assert rate_limited is True

    not_meta = worker._is_meta_rate_limit_error(
        _job(job_type=JobType.SEND_EMAIL.value),
        "rate limited",
    )
    assert not_meta is False


@pytest.mark.asyncio
async def test_worker_process_job_dispatch(monkeypatch, db):
    called: list[str] = []

    async def _handler(session, job):
        called.append(job.job_type)

    monkeypatch.setattr(worker, "resolve_job_handler", lambda job_type: _handler)

    job = _job(job_type=JobType.CAMPAIGN_SEND.value)
    await worker.process_job(db, job)
    assert called == [JobType.CAMPAIGN_SEND.value]


@pytest.mark.asyncio
async def test_worker_loop_single_iteration_success_and_failure(monkeypatch, db):
    jobs = [
        _job(job_type=JobType.CAMPAIGN_SEND.value),
        _job(
            job_type=JobType.SEND_EMAIL.value,
            payload={"email_log_id": str(uuid4())},
        ),
    ]
    pending_jobs = jobs.copy()

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker, "maybe_schedule_gmail_sync_jobs", lambda *args, **kwargs: datetime.now(timezone.utc)
    )

    def _claim(session, limit, job_types):
        claimed = pending_jobs[:limit]
        del pending_jobs[:limit]
        return claimed

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    def _complete_claimed_job(session, *, job_id, claim_token):
        job = next(item for item in jobs if item.id == job_id)
        job.status = JobStatus.COMPLETED.value
        return job

    def _fail_claimed_job(session, *, job_id, claim_token, error):
        job = next(item for item in jobs if item.id == job_id)
        job.status = JobStatus.FAILED.value
        job.attempts += 1
        return job

    monkeypatch.setattr(worker.job_service, "complete_claimed_job", _complete_claimed_job)
    monkeypatch.setattr(worker.job_service, "fail_claimed_job", _fail_claimed_job)
    monkeypatch.setattr(worker, "_record_job_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_record_job_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker.email_service, "mark_email_failed", lambda *args, **kwargs: None)

    async def _process(session, job):
        if job.job_type == JobType.SEND_EMAIL.value:
            raise RuntimeError("send failed")
        return True

    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(worker, "_is_meta_rate_limit_error", lambda *args, **kwargs: False)

    slept = {"count": 0}

    async def _sleep(seconds):
        slept["count"] += 1
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(worker.asyncio, "sleep", _sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await worker.worker_loop()

    assert slept["count"] == 1
    assert jobs[0].status == JobStatus.COMPLETED.value
    assert jobs[1].status == JobStatus.FAILED.value


@pytest.mark.asyncio
async def test_worker_claims_one_job_at_a_time_within_each_batch(monkeypatch, db):
    pending_jobs = [
        _job(job_type=JobType.CAMPAIGN_SEND.value),
        _job(job_type=JobType.NOTIFICATION.value),
    ]
    all_jobs = pending_jobs.copy()
    processed: list[str] = []
    claim_limits: list[int] = []

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 2)
    monkeypatch.setattr(worker, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _claim(session, *, limit, job_types):
        claim_limits.append(limit)
        claimed = pending_jobs[:limit]
        del pending_jobs[:limit]
        return claimed

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    async def _process(session, job):
        processed.append(job.job_type)
        return True

    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(
        worker.job_service,
        "complete_claimed_job",
        lambda _session, *, job_id, claim_token: next(
            item for item in all_jobs if item.id == job_id
        ),
    )
    monkeypatch.setattr(worker, "_record_job_success", lambda *args, **kwargs: None)

    async def _sleep(seconds):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(worker.asyncio, "sleep", _sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await worker.worker_loop()

    assert claim_limits == [1, 1]
    assert processed == [JobType.CAMPAIGN_SEND.value, JobType.NOTIFICATION.value]


@pytest.mark.asyncio
async def test_worker_heartbeats_current_token_while_handler_runs(monkeypatch, db):
    claim_token = uuid4()
    job = _job(
        job_type=JobType.NOTIFICATION.value,
        status=JobStatus.RUNNING.value,
        claim_token=claim_token,
    )
    stop_event = asyncio.Event()
    claimed = False
    heartbeats: list[tuple] = []
    stopped: list[bool] = []

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 1)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker.job_service,
        "recover_stale_worker_claims",
        lambda *_args, **_kwargs: {"requeued": 0, "quarantined": 0},
    )
    monkeypatch.setattr(
        worker.scan_claim_recovery_service,
        "recover_stale_remote_scan_claims",
        lambda *_args, **_kwargs: SimpleNamespace(
            total=0,
            completed=0,
            requeued=0,
            quarantined=0,
        ),
    )

    def _claim(*_args, **_kwargs):
        nonlocal claimed
        if claimed:
            return []
        claimed = True
        return [job]

    def _start_heartbeat(*, job_id, claim_token):
        heartbeats.append((job_id, claim_token))
        return SimpleNamespace(stop=lambda: stopped.append(True))

    async def _process(_session, _job):
        stop_event.set()
        return True

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)
    monkeypatch.setattr(worker, "_start_claim_heartbeat", _start_heartbeat)
    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(
        worker.job_service,
        "complete_claimed_job",
        lambda *_args, **_kwargs: job,
    )
    monkeypatch.setattr(worker, "_record_job_success", lambda *_args, **_kwargs: None)

    await worker.worker_loop(stop_event)

    assert heartbeats == [(job.id, claim_token)]
    assert stopped == [True]


@pytest.mark.asyncio
async def test_worker_finishes_active_job_without_claiming_another_after_stop(monkeypatch, db):
    pending_jobs = [
        _job(job_type=JobType.CAMPAIGN_SEND.value),
        _job(job_type=JobType.NOTIFICATION.value),
    ]
    all_jobs = pending_jobs.copy()
    processed: list[str] = []
    stop_event = worker.asyncio.Event()

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 2)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _claim(session, *, limit, job_types):
        claimed = pending_jobs[:limit]
        del pending_jobs[:limit]
        return claimed

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    async def _process(session, job):
        processed.append(job.job_type)
        stop_event.set()
        return True

    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(
        worker.job_service,
        "complete_claimed_job",
        lambda _session, *, job_id, claim_token: next(
            item for item in all_jobs if item.id == job_id
        ),
    )
    monkeypatch.setattr(worker, "_record_job_success", lambda *args, **kwargs: None)

    await worker.worker_loop(stop_event)

    assert processed == [JobType.CAMPAIGN_SEND.value]
    assert [job.job_type for job in pending_jobs] == [JobType.NOTIFICATION.value]


@pytest.mark.asyncio
async def test_worker_cannot_adopt_a_newer_claim_after_handler_expires_job(
    monkeypatch,
    worker_db,
):
    organization = Organization(
        id=uuid4(),
        name="Worker completion claim replacement test",
        slug=f"worker-completion-claim-replacement-{uuid4().hex}",
    )
    original_token = uuid4()
    newer_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=organization.id,
        job_type=JobType.NOTIFICATION.value,
        status=JobStatus.RUNNING.value,
        payload={},
        run_at=datetime.now(timezone.utc),
        attempts=1,
        max_attempts=3,
        claim_token=original_token,
        claimed_at=datetime.now(timezone.utc),
    )
    worker_db.add_all([organization, job])
    worker_db.commit()
    job_id = job.id
    stop_event = worker.asyncio.Event()
    claimed = False

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(worker_db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 1)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _claim(*_args, **_kwargs):
        nonlocal claimed
        if claimed:
            return []
        claimed = True
        return [job]

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)

    async def _process(session, claimed_job):
        assert claimed_job.id == job.id
        session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(
                claim_token=newer_token,
                claimed_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        stop_event.set()
        return True

    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(worker, "_record_job_success", lambda *args, **kwargs: None)

    await worker.worker_loop(stop_event)

    worker_db.expire_all()
    current = worker_db.query(Job).filter(Job.id == job_id).one()
    assert current.status == JobStatus.RUNNING.value
    assert current.claim_token == newer_token
    assert current.completed_at is None


@pytest.mark.asyncio
async def test_worker_rolls_back_aborted_session_before_failing_current_claim(
    monkeypatch,
    worker_db,
):
    organization = Organization(
        id=uuid4(),
        name="Worker rollback test",
        slug=f"worker-rollback-{uuid4().hex}",
    )
    claim_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=organization.id,
        job_type=JobType.NOTIFICATION.value,
        status=JobStatus.RUNNING.value,
        payload={},
        run_at=datetime.now(timezone.utc),
        attempts=1,
        max_attempts=1,
        claim_token=claim_token,
        claimed_at=datetime.now(timezone.utc),
    )
    worker_db.add_all([organization, job])
    worker_db.commit()
    job_id = job.id
    stop_event = worker.asyncio.Event()
    claimed = False

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(worker_db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 1)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _claim(*_args, **_kwargs):
        nonlocal claimed
        if claimed:
            return []
        claimed = True
        return [job]

    async def _process(session, _claimed_job):
        stop_event.set()
        session.execute(text("SELECT 1 / 0"))
        pytest.fail("division by zero must abort the database transaction")

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)
    monkeypatch.setattr(worker, "process_job", _process)
    monkeypatch.setattr(worker, "_record_job_failure", lambda *args, **kwargs: None)

    await worker.worker_loop(stop_event)

    worker_db.expire_all()
    current = worker_db.query(Job).filter(Job.id == job_id).one()
    assert current.status == JobStatus.FAILED.value
    assert current.claim_token is None
    assert current.claimed_at is None
    assert "division by zero" in current.last_error


@pytest.mark.asyncio
async def test_worker_failure_cas_cannot_overwrite_newer_claim_after_session_rollback(
    monkeypatch,
    worker_db,
):
    organization = Organization(
        id=uuid4(),
        name="Worker claim replacement test",
        slug=f"worker-claim-replacement-{uuid4().hex}",
    )
    original_token = uuid4()
    newer_token = uuid4()
    job = Job(
        id=uuid4(),
        organization_id=organization.id,
        job_type=JobType.NOTIFICATION.value,
        status=JobStatus.RUNNING.value,
        payload={},
        run_at=datetime.now(timezone.utc),
        attempts=1,
        max_attempts=1,
        claim_token=original_token,
        claimed_at=datetime.now(timezone.utc),
    )
    worker_db.add_all([organization, job])
    worker_db.commit()
    job_id = job.id
    stop_event = worker.asyncio.Event()
    claimed = False
    fail_claimed_job = worker.job_service.fail_claimed_job

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(worker_db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "BATCH_SIZE", 1)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker,
        "maybe_schedule_gmail_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )

    def _claim(*_args, **_kwargs):
        nonlocal claimed
        if claimed:
            return []
        claimed = True
        return [job]

    async def _process(session, _claimed_job):
        stop_event.set()
        session.execute(text("SELECT 1 / 0"))
        pytest.fail("division by zero must abort the database transaction")

    def _replace_claim_then_fail(session, *, job_id, claim_token, error):
        assert claim_token == original_token
        session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                claim_token=newer_token,
                claimed_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        session.commit()
        return fail_claimed_job(
            session,
            job_id=job_id,
            claim_token=claim_token,
            error=error,
        )

    monkeypatch.setattr(worker.job_service, "claim_pending_jobs", _claim)
    monkeypatch.setattr(worker.job_service, "fail_claimed_job", _replace_claim_then_fail)
    monkeypatch.setattr(worker, "process_job", _process)

    await worker.worker_loop(stop_event)

    worker_db.expire_all()
    current = worker_db.query(Job).filter(Job.id == job_id).one()
    assert current.status == JobStatus.RUNNING.value
    assert current.claim_token == newer_token
    assert current.completed_at is None
    assert current.last_error is None


@pytest.mark.asyncio
async def test_worker_loop_leaves_job_running_when_handler_defers_completion(monkeypatch, db):
    job = _job(
        job_type=JobType.ATTACHMENT_SCAN.value,
        status=JobStatus.RUNNING.value,
        payload={"attachment_id": str(uuid4())},
    )

    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(
        worker,
        "maybe_schedule_google_calendar_sync_jobs",
        lambda *args, **kwargs: datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        worker, "maybe_schedule_gmail_sync_jobs", lambda *args, **kwargs: datetime.now(timezone.utc)
    )
    monkeypatch.setattr(
        worker.job_service,
        "claim_pending_jobs",
        lambda session, limit, job_types: [job],
    )
    completed = {"count": 0}

    def _mark_completed(*_args, **_kwargs):
        completed["count"] += 1

    monkeypatch.setattr(worker.job_service, "mark_job_completed", _mark_completed)
    monkeypatch.setattr(worker.job_service, "mark_job_failed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "_record_job_success", lambda *args, **kwargs: None)
    monkeypatch.setattr(worker, "_record_job_failure", lambda *args, **kwargs: None)

    async def _process(session, claimed_job):
        assert claimed_job is job
        return False

    monkeypatch.setattr(worker, "process_job", _process)

    async def _sleep(seconds):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(worker.asyncio, "sleep", _sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await worker.worker_loop()

    assert job.status == JobStatus.RUNNING.value
    assert completed["count"] == 0


def test_worker_main_paths(monkeypatch):
    called = {"sync": 0, "scan": 0, "run": 0, "report": 0}

    monkeypatch.setattr(
        worker, "_sync_clamav_signatures", lambda: called.__setitem__("sync", called["sync"] + 1)
    )
    monkeypatch.setattr(
        worker,
        "_ensure_attachment_scanner_available",
        lambda: called.__setitem__("scan", called["scan"] + 1),
    )

    def _run_ok(coro):
        coro.close()
        called["run"] += 1

    monkeypatch.setattr(worker.asyncio, "run", _run_ok)

    worker.main()
    assert called["sync"] == 1
    assert called["scan"] == 1
    assert called["run"] == 1

    def _run_fail(coro):
        coro.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(worker.asyncio, "run", _run_fail)
    monkeypatch.setattr(
        worker,
        "report_exception",
        lambda *_args, **_kwargs: called.__setitem__("report", called["report"] + 1),
    )
    with pytest.raises(RuntimeError):
        worker.main()
    assert called["report"] == 1
