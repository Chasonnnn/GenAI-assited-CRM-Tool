from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from threading import Barrier, Thread
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
async def test_legacy_send_email_handler_cannot_load_another_organizations_log(
    monkeypatch,
    db,
    test_org,
):
    from app.db.models import EmailLog
    from app.jobs.handlers import email as email_job_handler

    email_log = EmailLog(
        organization_id=test_org.id,
        recipient_email="tenant-boundary@example.com",
        subject="Tenant boundary",
        body="<p>Do not send</p>",
        status="pending",
    )
    db.add(email_log)
    db.commit()

    job = _job(
        job_type=JobType.SEND_EMAIL.value,
        payload={"email_log_id": str(email_log.id)},
    )
    assert job.organization_id != test_org.id

    send_calls: list = []

    async def _unexpected_send(*args, **kwargs):
        send_calls.append((args, kwargs))
        return "queued"

    monkeypatch.setattr(email_job_handler, "send_email_async", _unexpected_send)

    with pytest.raises(Exception, match=f"EmailLog {email_log.id} not found"):
        await email_job_handler.process_send_email(db, job)

    assert send_calls == []


def test_worker_email_failure_projection_cannot_mutate_another_organizations_log(
    monkeypatch,
    db,
    test_org,
):
    from app.db.models import EmailLog

    email_log = EmailLog(
        organization_id=test_org.id,
        recipient_email="tenant-failure-boundary@example.com",
        subject="Tenant failure boundary",
        body="<p>Do not mutate</p>",
        status="pending",
    )
    db.add(email_log)
    db.commit()

    job = _job(
        job_type=JobType.SEND_EMAIL.value,
        payload={"email_log_id": str(email_log.id)},
    )
    assert job.organization_id != test_org.id

    failed_logs: list = []
    monkeypatch.setattr(
        worker.email_service,
        "mark_email_failed",
        lambda _db, log, _error: failed_logs.append(log.id),
    )

    worker._mark_send_email_failed(db, job, "provider failure")

    assert failed_logs == []
    db.refresh(email_log)
    assert email_log.status == "pending"


@pytest.mark.asyncio
async def test_worker_reconciles_accepted_resend_event(db, test_org):
    """The worker links an accepted orphan event once its EmailLog is committed."""
    from app.db.models import EmailLog, ResendWebhookEvent

    email_log = EmailLog(
        organization_id=test_org.id,
        recipient_email="reconcile@example.com",
        subject="Reconcile event",
        body="<p>Body</p>",
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        status="sent",
        external_id="resend_reconcile_message",
    )
    event = ResendWebhookEvent(
        organization_id=test_org.id,
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        provider_event_id="svix_reconcile_event",
        event_type="email.delivered",
        event_created_at=datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc),
        payload={
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {"email_id": "resend_reconcile_message"},
        },
    )
    db.add_all([email_log, event])
    db.commit()

    job = _job(
        job_type=JobType.RESEND_EVENT_RECONCILE.value,
        status=JobStatus.RUNNING.value,
        payload={"event_id": str(event.id)},
    )
    job.organization_id = test_org.id

    completed = await worker.process_job(db, job)

    assert completed is True
    db.refresh(event)
    db.refresh(email_log)
    assert event.email_log_id == email_log.id
    assert event.processed_at is not None
    assert email_log.resend_status == "delivered"
    assert email_log.delivered_at.isoformat() == "2026-07-21T14:03:00+00:00"


@pytest.mark.asyncio
async def test_worker_reconciles_platform_event_only_to_platform_route(db, test_org):
    """A platform send/commit race recovers without crossing into organization email."""
    from app.db.models import EmailLog, ResendWebhookEvent

    provider_message_id = "platform_reconcile_message"
    platform_email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="platform-reconcile@example.com",
        subject="Reconcile platform event",
        body="<p>Body</p>",
        provider="resend",
        provider_scope="platform",
        provider_account_id="platform:default",
        status="sent",
        external_id=provider_message_id,
    )
    event = ResendWebhookEvent(
        organization_id=test_org.id,
        provider_scope="platform",
        provider_account_id="platform:default",
        provider_event_id="svix_platform_reconcile_event",
        event_type="email.delivered",
        event_created_at=datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc),
        payload={
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": provider_message_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(platform_email_log.id),
                },
            },
        },
    )
    db.add_all([platform_email_log, event])
    db.commit()

    job = _job(
        job_type=JobType.RESEND_EVENT_RECONCILE.value,
        status=JobStatus.RUNNING.value,
        payload={"event_id": str(event.id)},
    )
    job.organization_id = test_org.id

    completed = await worker.process_job(db, job)

    assert completed is True
    db.refresh(event)
    db.refresh(platform_email_log)
    assert event.email_log_id == platform_email_log.id
    assert event.processed_at is not None
    assert platform_email_log.resend_status == "delivered"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "expected_resend_status", "expected_email_status", "milestone_field"),
    [
        ("email.delivered", "delivered", "sent", "delivered_at"),
        ("email.bounced", "bounced", "failed", "bounced_at"),
    ],
)
async def test_worker_reconciles_older_orphan_event_after_provider_acceptance(
    db,
    test_org,
    event_type,
    expected_resend_status,
    expected_email_status,
    milestone_field,
):
    """A higher-rank provider event wins even when acceptance was recorded later."""
    from app.db.models import ResendWebhookEvent
    from app.services.email_delivery_service import (
        DeliveryRoute,
        EmailSource,
        RenderedEmail,
        claim_due_deliveries,
        queue_rendered_email,
        record_delivery_success,
    )

    provider_created_at = datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc)
    accepted_at = provider_created_at + timedelta(minutes=2)
    provider_message_id = f"resend_race_{event_type.rsplit('.', 1)[-1]}"
    queued = queue_rendered_email(
        db,
        organization_id=test_org.id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{test_org.id}",
        rendered_email=RenderedEmail(
            recipient_email="race@example.com",
            subject="Chronology race",
            html="<p>Body</p>",
            text="Body",
            from_email="Surrogacy Force <care@example.com>",
        ),
        idempotency_key=f"chronology-race/{event_type}",
        source=EmailSource(source_type="test"),
        schedule_at=accepted_at - timedelta(seconds=1),
        commit=False,
    )
    event = ResendWebhookEvent(
        organization_id=test_org.id,
        provider_event_id=f"svix_race_{event_type}",
        event_type=event_type,
        event_created_at=provider_created_at,
        payload={
            "type": event_type,
            "created_at": provider_created_at.isoformat(),
            "data": {
                "email_id": provider_message_id,
                "bounce": {"type": "Permanent"},
            },
        },
    )
    db.add(event)
    db.commit()

    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=accepted_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    record_delivery_success(
        db,
        claim=claim,
        provider_message_id=provider_message_id,
        now=accepted_at,
    )

    job = _job(
        job_type=JobType.RESEND_EVENT_RECONCILE.value,
        status=JobStatus.RUNNING.value,
        payload={"event_id": str(event.id)},
    )
    job.organization_id = test_org.id
    completed = await worker.process_job(db, job)

    assert completed is True
    db.refresh(event)
    db.refresh(queued.email_log)
    assert event.email_log_id == queued.email_log.id
    assert event.processed_at is not None
    assert queued.email_log.resend_status == expected_resend_status
    assert queued.email_log.status == expected_email_status
    assert queued.email_log.resend_status_at == provider_created_at
    assert getattr(queued.email_log, milestone_field) == provider_created_at


def test_verified_resend_projection_rejects_a_cross_route_message(db, test_org):
    """Every projection caller must preserve the event's trusted delivery route."""
    from app.db.models import EmailLog, ResendWebhookEvent
    from app.services.webhooks.resend import _process_verified_payload

    provider_created_at = datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc)
    platform_email_log = EmailLog(
        organization_id=test_org.id,
        recipient_email="cross-route@example.com",
        subject="Cross-route projection",
        body="<p>Body</p>",
        provider="resend",
        provider_scope="platform",
        provider_account_id="platform:default",
        status="sent",
        external_id="resend_cross_route_projection",
    )
    payload = {
        "type": "email.delivered",
        "created_at": provider_created_at.isoformat(),
        "data": {"email_id": platform_email_log.external_id},
    }
    organization_event = ResendWebhookEvent(
        organization_id=test_org.id,
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        provider_event_id="svix_cross_route_projection",
        event_type="email.delivered",
        event_created_at=provider_created_at,
        payload=payload,
    )
    db.add_all([platform_email_log, organization_event])
    db.commit()

    with pytest.raises(RuntimeError, match="delivery route"):
        _process_verified_payload(
            db,
            event=organization_event,
            email_log=platform_email_log,
            payload=payload,
        )

    db.refresh(platform_email_log)
    db.refresh(organization_event)
    assert platform_email_log.resend_status is None
    assert organization_event.email_log_id is None
    assert organization_event.processed_at is None


def test_verified_resend_projection_locks_tenant_event_and_email_rows(db, test_org):
    """Projection serializes event dedupe and message state within the tenant."""
    from sqlalchemy import event as sqlalchemy_event

    from app.db.models import EmailLog, ResendWebhookEvent
    from app.services.webhooks.resend import _process_verified_payload

    provider_created_at = datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc)
    email_log = EmailLog(
        organization_id=test_org.id,
        recipient_email="locked@example.com",
        subject="Locked projection",
        body="<p>Body</p>",
        status="sent",
        external_id="resend_locked_projection",
        resend_status="sent",
        resend_status_at=provider_created_at - timedelta(seconds=1),
    )
    db.add(email_log)
    db.flush()
    payload = {
        "type": "email.delivered",
        "created_at": provider_created_at.isoformat(),
        "data": {"email_id": email_log.external_id},
    }
    webhook_event = ResendWebhookEvent(
        organization_id=test_org.id,
        email_log_id=email_log.id,
        provider_event_id="svix_locked_projection",
        event_type="email.delivered",
        event_created_at=provider_created_at,
        payload=payload,
    )
    db.add(webhook_event)
    db.commit()

    statements: list[str] = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        _process_verified_payload(
            db,
            event=webhook_event,
            email_log=email_log,
            payload=payload,
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)

    locking_selects = [statement for statement in statements if "for update" in statement]
    assert any(
        "from resend_webhook_events" in statement and "organization_id" in statement
        for statement in locking_selects
    )
    assert any(
        "from email_logs" in statement and "organization_id" in statement
        for statement in locking_selects
    )


def test_concurrent_resend_open_events_do_not_lose_counts(db_engine):
    """Distinct provider events serialize their updates to one EmailLog."""
    from app.db.models import EmailLog, Organization, ResendWebhookEvent
    from app.db.session import SessionLocal
    from app.services.webhooks.resend import _process_verified_payload

    organization_id = uuid4()
    email_log_id = uuid4()
    provider_created_at = datetime(2026, 7, 21, 14, 3, tzinfo=timezone.utc)
    event_ids: list = []
    setup = SessionLocal(bind=db_engine)
    try:
        setup.add(
            Organization(
                id=organization_id,
                name="Webhook Concurrency Test",
                slug=f"webhook-concurrency-{uuid4().hex[:10]}",
            )
        )
        setup.add(
            EmailLog(
                id=email_log_id,
                organization_id=organization_id,
                recipient_email="concurrent@example.com",
                subject="Concurrent projection",
                body="<p>Body</p>",
                status="sent",
                external_id="resend_concurrent_projection",
                resend_status="sent",
                resend_status_at=provider_created_at - timedelta(seconds=1),
            )
        )
        for sequence in (1, 2):
            payload = {
                "type": "email.opened",
                "created_at": (provider_created_at + timedelta(seconds=sequence)).isoformat(),
                "data": {"email_id": "resend_concurrent_projection"},
            }
            webhook_event = ResendWebhookEvent(
                organization_id=organization_id,
                email_log_id=email_log_id,
                provider_event_id=f"svix_concurrent_open_{sequence}",
                event_type="email.opened",
                event_created_at=provider_created_at + timedelta(seconds=sequence),
                payload=payload,
            )
            setup.add(webhook_event)
            setup.flush()
            event_ids.append(webhook_event.id)
        setup.commit()
    finally:
        setup.close()

    ready = Barrier(2)
    errors: list[BaseException] = []

    def project(event_id):
        session = SessionLocal(bind=db_engine)
        try:
            webhook_event = session.get(ResendWebhookEvent, event_id)
            email_log = session.get(EmailLog, email_log_id)
            assert webhook_event is not None
            assert email_log is not None
            ready.wait(timeout=5)
            _process_verified_payload(
                session,
                event=webhook_event,
                email_log=email_log,
                payload=webhook_event.payload,
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            session.close()

    threads = [Thread(target=project, args=(event_id,)) for event_id in event_ids]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert all(not thread.is_alive() for thread in threads)
        assert errors == []

        verify = SessionLocal(bind=db_engine)
        try:
            email_log = verify.get(EmailLog, email_log_id)
            assert email_log is not None
            assert email_log.open_count == 2
            assert (
                verify.query(ResendWebhookEvent)
                .filter(
                    ResendWebhookEvent.organization_id == organization_id,
                    ResendWebhookEvent.processed_at.isnot(None),
                )
                .count()
                == 2
            )
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal(bind=db_engine)
        try:
            cleanup.query(Organization).filter(Organization.id == organization_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


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
    stale_recovery_calls = {"count": 0}

    def _recover_stale_jobs(*_args, **_kwargs):
        stale_recovery_calls["count"] += 1
        return SimpleNamespace(inspected=0, requeued=0, failed=0, resolved=0)

    monkeypatch.setattr(
        worker.job_service,
        "recover_stale_resend_reconciliation_jobs",
        _recover_stale_jobs,
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
    assert stale_recovery_calls["count"] == 1
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


@pytest.mark.asyncio
async def test_worker_loop_dispatches_one_bounded_email_delivery_batch(monkeypatch, db):
    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(worker, "EMAIL_DELIVERY_DISPATCH_ENABLED", True)
    monkeypatch.setattr(worker, "EMAIL_DELIVERY_BATCH_SIZE", 4)
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
        "claim_pending_jobs",
        lambda *_args, **_kwargs: [],
    )
    dispatch_calls: list[dict[str, object]] = []

    async def fake_dispatch_due_delivery_batch(**kwargs):
        dispatch_calls.append(kwargs)
        return SimpleNamespace(
            claimed=2,
            sent=1,
            retry_scheduled=1,
            failed=0,
            cancelled=0,
            lease_lost=0,
            unexpected_errors=0,
        )

    monkeypatch.setattr(
        worker.email_delivery_dispatch,
        "dispatch_due_delivery_batch",
        fake_dispatch_due_delivery_batch,
    )

    async def stop_after_iteration(_seconds):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(worker.asyncio, "sleep", stop_after_iteration)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await worker.worker_loop()

    assert len(dispatch_calls) == 1
    assert dispatch_calls[0]["session_factory"] is worker.SessionLocal
    assert dispatch_calls[0]["limit"] == 4
    assert dispatch_calls[0]["worker_id"]


@pytest.mark.asyncio
async def test_worker_loop_drains_full_email_batches_before_poll_sleep(monkeypatch, db):
    monkeypatch.setattr(worker, "SessionLocal", lambda: _CtxSession(db))
    monkeypatch.setattr(worker, "WORKER_JOB_TYPES", None)
    monkeypatch.setattr(worker, "POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(worker, "EMAIL_DELIVERY_DISPATCH_ENABLED", True)
    monkeypatch.setattr(worker, "EMAIL_DELIVERY_BATCH_SIZE", 3)
    monkeypatch.setattr(worker, "EMAIL_DELIVERY_MAX_BATCHES_PER_TICK", 4)
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
        "claim_pending_jobs",
        lambda *_args, **_kwargs: [],
    )
    claimed_counts = iter((3, 2))
    dispatch_calls: list[dict[str, object]] = []

    async def fake_dispatch_due_delivery_batch(**kwargs):
        dispatch_calls.append(kwargs)
        claimed = next(claimed_counts)
        return SimpleNamespace(
            claimed=claimed,
            sent=claimed,
            retry_scheduled=0,
            failed=0,
            cancelled=0,
            lease_lost=0,
            unexpected_errors=0,
        )

    monkeypatch.setattr(
        worker.email_delivery_dispatch,
        "dispatch_due_delivery_batch",
        fake_dispatch_due_delivery_batch,
    )

    async def stop_after_iteration(_seconds):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(worker.asyncio, "sleep", stop_after_iteration)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await worker.worker_loop()

    assert len(dispatch_calls) == 2
    assert all(call["limit"] == 3 for call in dispatch_calls)


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
