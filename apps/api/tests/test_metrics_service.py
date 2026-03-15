"""Tests for request metrics rollups and AI conversation constraints."""

import logging
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db.models import AIConversation, RequestMetricsRollup
from app.services import metrics_service


def test_record_request_dedupes_null_org(db, monkeypatch):
    """Null org metrics should upsert into a single rollup row."""
    fixed_bucket = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
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
