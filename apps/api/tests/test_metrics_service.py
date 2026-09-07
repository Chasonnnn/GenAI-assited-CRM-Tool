"""Tests for request metrics rollups and AI conversation constraints."""

import asyncio
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import AIConversation, RequestMetricsRollup
from app.services import metrics_service


@pytest.fixture
def metrics_runtime(monkeypatch):
    from app import main

    executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(main, "_metrics_executor", executor, raising=False)
    monkeypatch.setattr(main, "_metrics_capacity", threading.BoundedSemaphore(1), raising=False)
    yield main
    executor.shutdown(wait=True, cancel_futures=True)


def metrics_request(org_id=None):
    return SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/records/{record_id}")},
        state=SimpleNamespace(user_session=SimpleNamespace(org_id=org_id)),
        url=SimpleNamespace(path="/records/private-id"),
    )


@pytest.mark.asyncio
async def test_slow_metrics_do_not_delay_requests_or_queue_on_saturation(
    metrics_runtime, monkeypatch
):
    main = metrics_runtime
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    org_id = uuid.uuid4()
    request = metrics_request(org_id)
    db = SimpleNamespace(close=finished.set)
    monkeypatch.setattr(main, "SessionLocal", lambda: db)
    monkeypatch.setattr(main, "MetricsSessionLocal", lambda: db, raising=False)

    def blocked_record(**kwargs):
        calls.append(kwargs)
        started.set()
        release.wait(timeout=1)

    monkeypatch.setattr(main.metrics_service, "record_request", blocked_record)
    response = SimpleNamespace(status_code=200)

    async def next_response(_request):
        return response

    try:
        assert await main.metrics_middleware(request, next_response) is response
        await asyncio.sleep(0.01)
        assert started.is_set()
        assert not finished.is_set(), "metrics blocked the event loop and request response"
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="https://test"
        ) as client:
            liveness = await asyncio.wait_for(client.get("/health/live"), timeout=0.5)
            assert liveness.status_code == 200
        request.state.user_session.org_id = uuid.uuid4()
        for _ in range(40):
            assert main._record_metrics(request, 200, 12) is False
        assert len(calls) == 1
        assert calls[0]["org_id"] == org_id
        assert calls[0]["route"] == "/records/{record_id}"
    finally:
        release.set()


def test_metrics_writer_never_uses_request_pool(metrics_runtime, monkeypatch):
    main = metrics_runtime
    calls = []
    closed = threading.Event()
    db = SimpleNamespace(close=closed.set)

    def fail_request_pool():
        raise AssertionError("Request pool used for metrics")

    monkeypatch.setattr(main, "SessionLocal", fail_request_pool)
    monkeypatch.setattr(main, "MetricsSessionLocal", lambda: db, raising=False)
    monkeypatch.setattr(
        main.metrics_service, "record_request", lambda **kwargs: calls.append(kwargs)
    )
    assert main._record_metrics(metrics_request(), 201, 17) is True
    assert closed.wait(timeout=1)
    assert calls[0]["db"] is db
    assert calls[0]["org_id"] is None


@pytest.mark.parametrize("failure", ["factory", "write", "close"])
def test_metrics_writer_failures_are_safe(metrics_runtime, monkeypatch, caplog, failure):
    main = metrics_runtime

    def fail(*args, **kwargs):
        raise RuntimeError("secret-token-should-not-appear")

    db = SimpleNamespace(close=fail if failure == "close" else lambda: None)
    monkeypatch.setattr(
        main, "MetricsSessionLocal", fail if failure == "factory" else lambda: db, raising=False
    )
    monkeypatch.setattr(
        main.metrics_service,
        "record_request",
        fail if failure == "write" else lambda **kwargs: None,
    )
    main._write_metrics(route="/test", method="GET", status_code=200, duration_ms=1, org_id=None)
    assert "secret-token-should-not-appear" not in caplog.text


def test_failed_metrics_submission_releases_capacity(metrics_runtime, monkeypatch):
    main = metrics_runtime

    def fail(*args, **kwargs):
        raise RuntimeError("Executor unavailable")

    monkeypatch.setattr(main._metrics_executor, "submit", fail)
    assert main._record_metrics(metrics_request(), 200, 1) is False
    assert main._metrics_capacity.acquire(blocking=False)
    main._metrics_capacity.release()


def test_failed_metrics_write_releases_capacity(metrics_runtime, monkeypatch):
    main = metrics_runtime

    def fail():
        raise RuntimeError("Metrics unavailable")

    monkeypatch.setattr(main, "MetricsSessionLocal", fail)
    assert main._record_metrics(metrics_request(), 200, 1) is True
    assert main._metrics_capacity.acquire(timeout=1)
    main._metrics_capacity.release()


@pytest.mark.asyncio
async def test_metrics_shutdown_does_not_wait_for_blocked_write(metrics_runtime, monkeypatch):
    from app.core import websocket

    main = metrics_runtime
    started, release = threading.Event(), threading.Event()

    async def no_listener():
        pass

    def blocked_write(**kwargs):
        started.set()
        release.wait(timeout=1)

    monkeypatch.setattr(main.settings, "DB_MIGRATION_CHECK", False)
    monkeypatch.setattr(main.settings, "DB_AUTO_MIGRATE", False)
    monkeypatch.setattr(websocket, "start_session_revocation_listener", no_listener)
    monkeypatch.setattr(websocket, "start_websocket_event_listener", no_listener)
    monkeypatch.setattr(websocket.manager, "set_event_loop", lambda loop: None)
    monkeypatch.setattr(main.metrics_engine, "dispose", lambda: None)
    monkeypatch.setattr(main, "_write_metrics", blocked_write)
    try:
        async with main.lifespan(main.app):
            assert main._record_metrics(metrics_request(), 200, 1) is True
            await asyncio.sleep(0.01)
            assert started.is_set()
            started_at = asyncio.get_running_loop().time()
        assert asyncio.get_running_loop().time() - started_at < 0.5
    finally:
        release.set()
        main._metrics_executor.shutdown(wait=True, cancel_futures=True)


def test_record_request_dedupes_null_org(db, monkeypatch):
    """Null org metrics should upsert into a single rollup row."""
    fixed_bucket = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(metrics_service, "get_minute_bucket", lambda _=None: fixed_bucket)

    route = "/tests/metrics"

    metrics_service.record_request(
        db=db,
        route=route,
        method="get",
        status_code=200,
        duration_ms=100,
        org_id=None,
    )
    metrics_service.record_request(
        db=db,
        route=route,
        method="get",
        status_code=500,
        duration_ms=50,
        org_id=None,
    )

    rows = (
        db.query(RequestMetricsRollup)
        .filter(
            RequestMetricsRollup.organization_id.is_(None),
            RequestMetricsRollup.route == route,
            RequestMetricsRollup.method == "GET",
            RequestMetricsRollup.period_start == fixed_bucket,
        )
        .all()
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.request_count == 2
    assert row.status_2xx == 1
    assert row.status_5xx == 1
    assert row.total_duration_ms == 150


def test_ai_conversation_constraint_behavior(db, test_org, test_user):
    """Duplicate conversations follow the active DB schema constraint behavior."""
    entity_id = uuid.uuid4()
    conversation = AIConversation(
        organization_id=test_org.id,
        user_id=test_user.id,
        entity_type="case",
        entity_id=entity_id,
    )
    db.add(conversation)
    db.commit()

    duplicate = AIConversation(
        organization_id=test_org.id,
        user_id=test_user.id,
        entity_type="case",
        entity_id=entity_id,
    )
    db.add(duplicate)

    has_unique_conversation_per_entity = any(
        constraint.get("name") == "uq_ai_conversations_user_entity"
        for constraint in inspect(db.bind).get_unique_constraints("ai_conversations")
    )

    if has_unique_conversation_per_entity:
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        return

    db.commit()
    rows = (
        db.query(AIConversation)
        .filter(
            AIConversation.organization_id == test_org.id,
            AIConversation.user_id == test_user.id,
            AIConversation.entity_type == "case",
            AIConversation.entity_id == entity_id,
        )
        .all()
    )
    assert len(rows) == 2


def test_record_request_logs_warning_on_persist_failure(db, caplog, monkeypatch):
    """Metrics persistence failures should be logged for observability."""

    def _fail_execute(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "execute", _fail_execute)
    caplog.set_level(logging.WARNING)

    metrics_service.record_request(
        db=db,
        route="/tests/metrics-failure",
        method="GET",
        status_code=200,
        duration_ms=12,
        org_id=None,
    )

    warning_messages = [
        record.message
        for record in caplog.records
        if "Failed to record request metrics" in record.message
    ]
    assert warning_messages == ["Failed to record request metrics"]
