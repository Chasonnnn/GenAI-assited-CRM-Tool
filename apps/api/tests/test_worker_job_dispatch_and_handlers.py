from __future__ import annotations

from datetime import datetime, timezone
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import JobStatus, JobType
from app import worker


class _CtxSession:
    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc, tb):
        return False


def _job(
    *,
    job_type: str,
    status: str = JobStatus.PENDING.value,
    attempts: int = 1,
    max_attempts: int = 3,
    payload: dict | None = None,
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


def test_worker_global_resend_warning_is_specific(monkeypatch, caplog):
    monkeypatch.setattr(worker, "RESEND_API_KEY", "")

    with caplog.at_level(logging.WARNING):
        worker._log_global_email_sender_status()

    assert (
        "Global RESEND_API_KEY not set; legacy non-campaign SEND_EMAIL jobs will be "
        "logged but not sent." in caplog.text
    )
    assert (
        "Org workflow Resend and platform/system email use separate configuration." in caplog.text
    )


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
        lambda session, limit, job_types: jobs,
    )

    def _mark_completed(session, job):
        job.status = JobStatus.COMPLETED.value

    def _mark_failed(session, job, error_msg):
        job.status = JobStatus.FAILED.value
        job.attempts += 1

    monkeypatch.setattr(worker.job_service, "mark_job_completed", _mark_completed)
    monkeypatch.setattr(worker.job_service, "mark_job_failed", _mark_failed)
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
