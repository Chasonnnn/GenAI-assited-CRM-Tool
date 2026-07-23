"""Contract tests for the organization email reconciliation workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db.models import (
    EmailReconciliationCase,
    Organization,
    ResendWebhookEvent,
)


def _assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "payload",
        "recipient_email",
        "subject",
        "body",
        "text_body",
        "headers",
        "raw_error",
        "last_error",
        "url",
        "ip",
        "user_agent",
        "user-agent",
        "lease_token",
        "lease_owner",
        "provider_account_id",
        "credential",
        "secret",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_no_forbidden_projection_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_forbidden_projection_keys(nested)


@pytest.mark.asyncio
async def test_reconciliation_queue_requires_authentication(client):
    response = await client.get("/email-operations/reconciliation-cases")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reconciliation_queue_starts_empty_for_an_organization(authed_client):
    response = await authed_client.get("/email-operations/reconciliation-cases")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "next_cursor": None,
        "counts": {
            "monitoring": 0,
            "action_required": 0,
            "resolved": 0,
        },
    }


@pytest.mark.asyncio
async def test_reconciliation_queue_is_org_scoped_and_never_projects_raw_event_data(
    authed_client,
    db,
    test_org,
):
    detected_at = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id="evt_operator_case",
        event_type="email.delivered",
        event_created_at=detected_at - timedelta(minutes=2),
        received_at=detected_at - timedelta(minutes=1),
        payload={
            "data": {
                "to": ["private@example.com"],
                "url": "https://example.com/private",
                "headers": {"authorization": "Bearer secret"},
            },
            "ip": "192.0.2.10",
            "user_agent": "private-agent",
            "webhook_secret": "must-never-project",
        },
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="correlation_exhausted",
        version=3,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at + timedelta(minutes=5),
    )

    other_org = Organization(
        id=uuid4(),
        name="Other Reconciliation Org",
        slug=f"other-reconciliation-{uuid4().hex[:8]}",
    )
    other_event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=other_org.id,
        provider_event_id="evt_other_org",
        event_type="email.bounced",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"secret": "cross-org"},
    )
    other_case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=other_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="correlation_exhausted",
        resend_webhook_event_id=other_event.id,
        detected_at=detected_at + timedelta(minutes=10),
        updated_at=detected_at + timedelta(minutes=10),
    )
    db.add_all([event, case, other_org, other_event, other_case])
    db.commit()

    response = await authed_client.get(
        "/email-operations/reconciliation-cases?status=action_required&limit=25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_cursor"] is None
    assert payload["counts"] == {
        "monitoring": 0,
        "action_required": 1,
        "resolved": 0,
    }
    assert payload["items"] == [
        {
            "id": str(case.id),
            "case_type": "orphan_webhook",
            "status": "action_required",
            "reason_code": "correlation_exhausted",
            "version": 3,
            "provider": "resend",
            "event_type": "email.delivered",
            "event_created_at": (detected_at - timedelta(minutes=2)).isoformat().replace(
                "+00:00", "Z"
            ),
            "received_at": (detected_at - timedelta(minutes=1)).isoformat().replace(
                "+00:00", "Z"
            ),
            "message_id": None,
            "delivery_id": None,
            "attempt_count": None,
            "max_attempts": None,
            "next_attempt_at": None,
            "available_actions": [
                "retry_correlation",
                "link_event",
                "dismiss",
            ],
            "detected_at": detected_at.isoformat().replace("+00:00", "Z"),
            "updated_at": (detected_at + timedelta(minutes=5))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    ]
    _assert_no_forbidden_projection_keys(payload)
