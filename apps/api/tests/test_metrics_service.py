"""Tests for request metrics rollups and AI conversation constraints."""

import logging
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import AIConversation, RequestMetricsRollup
from app.services import metrics_service


def test_request_metrics_use_isolated_session(monkeypatch):
    """Metrics must not consume the request pool or its active transaction."""
    from app import main as main_module

    request_db = object()
    metrics_db = SimpleNamespace(closed=False)
    metrics_db.close = lambda: setattr(metrics_db, "closed", True)
    request = SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/tests/metrics")},
        state=SimpleNamespace(request_db=request_db, user_session=None),
        url=SimpleNamespace(path="/tests/metrics"),
    )
    recorded = {}

    def _unexpected_session():
        raise AssertionError("metrics used the request database pool")

    def _metrics_session():
        return metrics_db

    def _record_request(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(main_module, "SessionLocal", _unexpected_session)
    monkeypatch.setattr(
        main_module, "MetricsSessionLocal", _metrics_session, raising=False
    )
    monkeypatch.setattr(main_module.metrics_service, "record_request", _record_request)

    main_module._record_metrics(request, status_code=200, duration_ms=12)

    assert recorded["db"] is metrics_db
    assert recorded["route"] == "/tests/metrics"
    assert recorded["status_code"] == 200
    assert metrics_db.closed is True


@pytest.mark.asyncio
async def test_metrics_middleware_offloads_database_write(monkeypatch):
    """A slow metrics write must not block the event loop."""
    from app import main as main_module

    request = SimpleNamespace(url=SimpleNamespace(path="/tests/metrics"))
    response = SimpleNamespace(status_code=200)
    calls = []

    async def _call_next(_request):
        return response

    def _record_metrics(*args):
        calls.append(("record", args))

    async def _run_in_threadpool(func, *args):
        calls.append(("offload", args))
        func(*args)

    monkeypatch.setattr(main_module, "_record_metrics", _record_metrics)
    monkeypatch.setattr(
        main_module, "run_in_threadpool", _run_in_threadpool, raising=False
    )

    result = await main_module.metrics_middleware(request, _call_next)

    assert result is response
    assert [call[0] for call in calls] == ["offload", "record"]


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
    assert warning_messages == ["Failed to record request metrics: boom"]
