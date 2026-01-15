"""Tests for request metrics rollups and AI conversation constraints."""

import uuid
from datetime import datetime, timezone

import pytest
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


def test_ai_conversation_unique_constraint(db, test_org, test_user):
    """Duplicate conversations for the same user/entity should be rejected."""
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

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
