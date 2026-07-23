"""Tests for the organization-scoped Email Operations read API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.db.enums import EmailStatus
from app.db.models import (
    EmailDelivery,
    EmailDeliveryAttempt,
    EmailLog,
    Organization,
    ResendSettings,
    ResendWebhookEvent,
)


def _email_log(
    *,
    organization_id: UUID,
    created_at: datetime,
    message_id: UUID | None = None,
    status: str = EmailStatus.SENT.value,
    provider: str | None = "resend",
    provider_scope: str | None = "organization",
    provider_account_id: str | None = "stored-account",
    external_id: str | None = None,
) -> EmailLog:
    return EmailLog(
        id=message_id or uuid4(),
        organization_id=organization_id,
        recipient_email="recipient@example.com",
        subject="Operational message",
        body="<p>Private body</p>",
        text_body="Private body",
        headers={"X-Private": "secret"},
        provider=provider,
        provider_scope=provider_scope,
        provider_account_id=provider_account_id,
        external_id=external_id,
        status=status,
        created_at=created_at,
    )


def _delivery(
    *,
    email_log: EmailLog,
    created_at: datetime,
    provider_account_id: str = "delivery-account",
) -> EmailDelivery:
    return EmailDelivery(
        id=uuid4(),
        organization_id=email_log.organization_id,
        email_log_id=email_log.id,
        provider="resend",
        provider_scope="platform",
        provider_account_id=provider_account_id,
        idempotency_key=f"email-operations/{email_log.id}",
        request_fingerprint="f" * 64,
        status="sent",
        run_at=created_at,
        attempt_count=2,
        max_attempts=5,
        first_attempt_at=created_at,
        last_attempt_at=created_at + timedelta(minutes=1),
        completed_at=created_at + timedelta(minutes=1),
        provider_message_id="delivery-provider-message",
        created_at=created_at,
        updated_at=created_at + timedelta(minutes=1),
    )


def _assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "body",
        "text_body",
        "headers",
        "payload",
        "url",
        "webhook_url",
        "ip",
        "user_agent",
        "user-agent",
        "lease_token",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_no_forbidden_projection_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_forbidden_projection_keys(nested)


@pytest.mark.asyncio
async def test_message_list_is_org_scoped_and_uses_stable_created_at_id_cursor(
    authed_client,
    db,
    test_org,
):
    created_at = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    messages = [
        _email_log(
            organization_id=test_org.id,
            created_at=created_at,
            message_id=UUID(int=index),
            provider_scope="platform" if index == 3 else "organization",
            provider_account_id=f"stored-account-{index}",
        )
        for index in (1, 2, 3)
    ]
    other_org = Organization(
        id=uuid4(),
        name="Other Email Operations Org",
        slug=f"other-email-operations-{uuid4().hex[:8]}",
    )
    other_message = _email_log(
        organization_id=other_org.id,
        created_at=created_at + timedelta(days=1),
        provider_account_id="other-org-account",
    )
    db.add(other_org)
    db.add_all([*messages, other_message])
    db.flush()

    # Deliberately disagree with the log's immutable route fields. The message
    # projection must not infer or substitute route identity from the delivery.
    db.add(_delivery(email_log=messages[2], created_at=created_at))
    db.commit()

    first_page = await authed_client.get("/email-operations/messages?limit=2")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert [item["id"] for item in first_payload["items"]] == [
        str(UUID(int=3)),
        str(UUID(int=2)),
    ]
    assert first_payload["items"][0]["provider"] == "resend"
    assert first_payload["items"][0]["provider_scope"] == "platform"
    assert first_payload["items"][0]["provider_account_id"] == "stored-account-3"
    assert first_payload["items"][0]["open_tracking"] == "estimated"
    assert first_payload["next_cursor"]
    _assert_no_forbidden_projection_keys(first_payload)

    second_page = await authed_client.get(
        "/email-operations/messages",
        params={"limit": 2, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert [item["id"] for item in second_payload["items"]] == [str(UUID(int=1))]
    assert second_payload["next_cursor"] is None

    invalid_cursor = await authed_client.get(
        "/email-operations/messages",
        params={"cursor": "not-a-valid-cursor"},
    )
    assert invalid_cursor.status_code == 400


@pytest.mark.asyncio
async def test_message_detail_is_sanitized_and_orders_attempts_and_provider_events(
    authed_client,
    db,
    test_org,
):
    created_at = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    email_log = _email_log(
        organization_id=test_org.id,
        created_at=created_at,
        external_id="email-log-provider-message",
    )
    email_log.opened_at = created_at + timedelta(minutes=4)
    email_log.open_count = 2
    email_log.clicked_at = created_at + timedelta(minutes=5)
    email_log.click_count = 1
    db.add(email_log)
    db.flush()

    delivery = _delivery(email_log=email_log, created_at=created_at)
    db.add(delivery)
    db.flush()
    db.add_all(
        [
            EmailDeliveryAttempt(
                id=uuid4(),
                organization_id=test_org.id,
                delivery_id=delivery.id,
                attempt_number=2,
                lease_token=uuid4(),
                started_at=created_at + timedelta(minutes=1),
                completed_at=created_at + timedelta(minutes=2),
                outcome="succeeded",
                provider_http_status=200,
                provider_message_id="attempt-provider-message",
            ),
            EmailDeliveryAttempt(
                id=uuid4(),
                organization_id=test_org.id,
                delivery_id=delivery.id,
                attempt_number=1,
                lease_token=uuid4(),
                started_at=created_at,
                completed_at=created_at + timedelta(seconds=30),
                outcome="retryable_error",
                provider_http_status=429,
                error_type="rate_limited",
                error_message="Private URL https://example.test/token and recipient@example.com",
                retry_after_seconds=30,
            ),
        ]
    )
    later_event_id = UUID(int=12)
    earlier_event_id = UUID(int=11)
    db.add_all(
        [
            ResendWebhookEvent(
                id=later_event_id,
                organization_id=test_org.id,
                email_log_id=email_log.id,
                provider_event_id="event-delivered",
                event_type="email.delivered",
                event_created_at=created_at + timedelta(minutes=3),
                received_at=created_at + timedelta(minutes=4),
                processed_at=created_at + timedelta(minutes=4),
                payload={
                    "data": {
                        "click": {"link": "https://private.test/token"},
                        "ip": "192.0.2.10",
                        "user_agent": "private-agent",
                    }
                },
            ),
            ResendWebhookEvent(
                id=earlier_event_id,
                organization_id=test_org.id,
                email_log_id=email_log.id,
                provider_event_id="event-sent",
                event_type="email.sent",
                event_created_at=created_at + timedelta(minutes=1),
                received_at=created_at + timedelta(minutes=2),
                processed_at=created_at + timedelta(minutes=2),
                payload={"private": "secret"},
            ),
        ]
    )
    other_org = Organization(
        id=uuid4(),
        name="Other Event Projection Org",
        slug=f"other-event-projection-{uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    # The webhook model's email-log FK is not composite. Even a malformed
    # cross-org correlation must not leak into this organization's timeline.
    db.add(
        ResendWebhookEvent(
            id=uuid4(),
            organization_id=other_org.id,
            email_log_id=email_log.id,
            provider_event_id="cross-org-event",
            event_type="email.complained",
            event_created_at=created_at + timedelta(minutes=6),
            received_at=created_at + timedelta(minutes=6),
            processed_at=created_at + timedelta(minutes=6),
            payload={"private": "cross-org"},
        )
    )
    db.commit()

    response = await authed_client.get(f"/email-operations/messages/{email_log.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "resend"
    assert payload["provider_scope"] == "organization"
    assert payload["provider_account_id"] == "stored-account"
    assert payload["provider_message_id"] == "email-log-provider-message"
    assert payload["open_tracking"] == "estimated"
    assert payload["estimated_open_count"] == 2
    assert [attempt["attempt_number"] for attempt in payload["attempts"]] == [1, 2]
    assert [event["event_type"] for event in payload["provider_events"]] == [
        "email.sent",
        "email.delivered",
    ]
    _assert_no_forbidden_projection_keys(payload)


@pytest.mark.asyncio
async def test_message_detail_returns_404_for_another_organization(
    authed_client,
    db,
):
    other_org = Organization(
        id=uuid4(),
        name="Other Detail Org",
        slug=f"other-detail-org-{uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()
    other_message = _email_log(
        organization_id=other_org.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(other_message)
    db.commit()

    response = await authed_client.get(f"/email-operations/messages/{other_message.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_readiness_is_not_configured_without_persisted_provider(
    authed_client,
):
    response = await authed_client.get("/email-operations/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall"] == "not_configured"
    assert payload["provider"] is None
    assert payload["provider_scope"] is None
    assert payload["provider_account_id"] is None
    assert payload["can_send"] is False
    assert payload["can_track"] is False
    assert payload["recent_webhook_activity"] == "unknown"
    assert payload["last_webhook_received_at"] is None
    assert {check["key"] for check in payload["checks"]} >= {
        "provider_selected",
        "api_key_configured",
        "api_key_validated",
        "sender_configured",
        "domain_verified",
        "webhook_signing_secret_configured",
        "recent_webhook_activity",
    }
    assert payload["summary_24h"]["messages"] == 0


@pytest.mark.asyncio
async def test_readiness_keeps_send_and_tracking_independent_and_new_activity_unknown(
    authed_client,
    db,
    test_org,
):
    now = datetime.now(timezone.utc)
    settings = ResendSettings(
        id=uuid4(),
        organization_id=test_org.id,
        email_provider="resend",
        api_key_encrypted="persisted-ciphertext",
        from_email="operations@example.com",
        verified_domain="example.com",
        last_key_validated_at=now,
        webhook_id=str(uuid4()),
        webhook_secret_encrypted="persisted-webhook-ciphertext",
        created_at=now,
        updated_at=now,
    )
    db.add(settings)
    db.commit()

    ready = await authed_client.get("/email-operations/readiness")
    assert ready.status_code == 200
    payload = ready.json()
    checks = {check["key"]: check for check in payload["checks"]}
    assert payload["overall"] == "ready"
    assert payload["can_send"] is True
    assert payload["can_track"] is True
    assert payload["recent_webhook_activity"] == "unknown"
    assert payload["last_webhook_received_at"] is None
    assert checks["recent_webhook_activity"]["status"] == "unknown"

    # A tracking-capable integration remains independently unable to send if
    # persisted key validation and sender configuration are removed.
    settings.api_key_encrypted = None
    settings.last_key_validated_at = None
    settings.from_email = None
    db.commit()
    needs_attention = await authed_client.get("/email-operations/readiness")
    assert needs_attention.status_code == 200
    attention_payload = needs_attention.json()
    assert attention_payload["overall"] == "needs_attention"
    assert attention_payload["can_send"] is False
    assert attention_payload["can_track"] is True


@pytest.mark.asyncio
async def test_readiness_uses_org_scoped_webhook_evidence_and_24h_summary(
    authed_client,
    db,
    test_org,
):
    now = datetime.now(timezone.utc)
    db.add(
        ResendSettings(
            id=uuid4(),
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted="persisted-ciphertext",
            from_email="operations@example.com",
            verified_domain="example.com",
            last_key_validated_at=now,
            webhook_id=str(uuid4()),
            webhook_secret_encrypted="persisted-webhook-ciphertext",
            created_at=now,
            updated_at=now,
        )
    )
    recent_message = _email_log(
        organization_id=test_org.id,
        created_at=now - timedelta(hours=1),
        external_id="recent-provider-message",
    )
    recent_message.delivered_at = now - timedelta(minutes=30)
    recent_message.open_count = 3
    recent_message.click_count = 2
    old_message = _email_log(
        organization_id=test_org.id,
        created_at=now - timedelta(hours=25),
        external_id="old-provider-message",
    )
    other_org = Organization(
        id=uuid4(),
        name="Other Readiness Org",
        slug=f"other-readiness-org-{uuid4().hex[:8]}",
    )
    other_message = _email_log(
        organization_id=other_org.id,
        created_at=now - timedelta(minutes=5),
        status=EmailStatus.FAILED.value,
        external_id="other-provider-message",
    )
    db.add(other_org)
    db.add_all([recent_message, old_message, other_message])
    db.flush()
    db.add_all(
        [
            ResendWebhookEvent(
                id=uuid4(),
                organization_id=test_org.id,
                email_log_id=recent_message.id,
                provider_event_id="recent-event",
                event_type="email.delivered",
                event_created_at=now - timedelta(minutes=31),
                received_at=now - timedelta(minutes=30),
                processed_at=now - timedelta(minutes=30),
                payload={"private": "secret"},
            ),
            ResendWebhookEvent(
                id=uuid4(),
                organization_id=other_org.id,
                email_log_id=other_message.id,
                provider_event_id="other-event",
                event_type="email.failed",
                event_created_at=now - timedelta(minutes=4),
                received_at=now - timedelta(minutes=4),
                processed_at=now - timedelta(minutes=4),
                payload={"private": "secret"},
            ),
        ]
    )
    db.commit()

    response = await authed_client.get("/email-operations/readiness")
    assert response.status_code == 200
    payload = response.json()
    checks = {check["key"]: check for check in payload["checks"]}
    assert payload["overall"] == "ready"
    assert payload["recent_webhook_activity"] == "pass"
    assert payload["last_webhook_received_at"] is not None
    assert checks["recent_webhook_activity"]["status"] == "pass"
    assert payload["provider"] == "resend"
    assert payload["provider_scope"] == "organization"
    assert payload["provider_account_id"] == "stored-account"
    assert payload["summary_24h"] == {
        "messages": 1,
        "pending": 0,
        "sent": 1,
        "failed": 0,
        "delivered": 1,
        "bounced": 0,
        "complained": 0,
        "estimated_opens": 3,
        "clicks": 2,
        "delivery_attempts": 0,
        "webhook_events": 1,
    }
    _assert_no_forbidden_projection_keys(payload)
