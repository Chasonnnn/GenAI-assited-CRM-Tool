from __future__ import annotations

import uuid

import pytest

from app.db.enums import AuditEventType
from app.db.models import AuditLog


@pytest.mark.asyncio
async def test_record_workflow_metric_event_creates_audit_entry(authed_client, db, test_auth):
    surrogate_id = uuid.uuid4()
    response = await authed_client.post(
        "/workflow-metrics/events",
        json={
            "event_type": "workflow_path_surrogate_viewed",
            "target_type": "surrogate",
            "target_id": str(surrogate_id),
            "details": {"from": "dashboard"},
        },
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"success": True}

    event = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_auth.org.id,
            AuditLog.event_type == AuditEventType.WORKFLOW_PATH_SURROGATE_VIEWED.value,
            AuditLog.actor_user_id == test_auth.user.id,
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert event is not None
    assert event.target_type == "surrogate"
    assert event.target_id == surrogate_id
    assert (event.details or {}).get("from") == "dashboard"


@pytest.mark.asyncio
async def test_record_workflow_metric_event_rejects_unknown_type(authed_client):
    response = await authed_client.post(
        "/workflow-metrics/events",
        json={"event_type": "not_a_real_metric_event"},
    )
    assert response.status_code == 422, response.text
