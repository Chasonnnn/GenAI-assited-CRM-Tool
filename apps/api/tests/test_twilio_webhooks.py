"""Signed, tenant-bound Twilio inbound and status webhook contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from twilio.request_validator import RequestValidator

ACCOUNT_SID = "AC" + ("1" * 32)
SERVICE_SID = "MG" + ("2" * 32)
AUTH_TOKEN = "primary-auth-token-for-webhooks"
SENDER = "+14155550199"
CONTACT = "+14155550110"


def _configure_route(db, test_org, purpose: str = "operational"):
    from app.services import twilio_settings_service

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.enabled = True
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential(ACCOUNT_SID)
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + ("8" * 32))
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential(
        "restricted-media-secret"
    )
    settings.auth_token_encrypted = twilio_settings_service.encrypt_credential(AUTH_TOKEN)
    route = next(item for item in settings.routes if item.purpose == purpose)
    route.enabled = True
    route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(SERVICE_SID)
    route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(SENDER)
    from app.core.encryption import hash_phone

    route.sender_phone_hash = hash_phone(SENDER)
    route.sender_phone_last4 = SENDER[-4:]
    db.commit()
    return route


def _signed_headers(url: str, data: dict[str, str]) -> dict[str, str]:
    return {
        "X-Twilio-Signature": RequestValidator(AUTH_TOKEN).compute_signature(url, data),
    }


async def test_inbound_stop_validates_exact_url_and_applies_suppression_before_persisting(
    client,
    db,
    test_org,
) -> None:
    from app.core.config import settings as app_settings
    from app.db.models import MessagingContact, MessagingGlobalSuppression
    from app.db.models.messaging_delivery import MessageWebhookEvent, MessagingMessage

    route = _configure_route(db, test_org)
    path = f"/webhooks/twilio/{route.webhook_id}/inbound"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"
    data = {
        "AccountSid": ACCOUNT_SID,
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": "SM" + ("3" * 32),
        "SmsSid": "SM" + ("3" * 32),
        "From": CONTACT,
        "To": SENDER,
        "Body": "STOP",
        "NumMedia": "0",
        "OptOutType": "STOP",
        "FutureTwilioField": "must-be-signed-too",
    }

    response = await client.post(path, data=data, headers=_signed_headers(url, data))

    assert response.status_code == 200
    assert response.text == "<Response></Response>"
    contact = (
        db.query(MessagingContact).filter(MessagingContact.organization_id == test_org.id).one()
    )
    suppression = (
        db.query(MessagingGlobalSuppression)
        .filter(MessagingGlobalSuppression.contact_id == contact.id)
        .one()
    )
    assert suppression.active is True
    assert db.query(MessagingMessage).filter_by(organization_id=test_org.id).count() == 1
    assert db.query(MessageWebhookEvent).filter_by(organization_id=test_org.id).count() == 1


async def test_inbound_replay_is_idempotent(client, db, test_org) -> None:
    from app.core.config import settings as app_settings
    from app.db.models import MessagingConsentEvidence
    from app.db.models.messaging_delivery import MessageWebhookEvent, MessagingMessage

    route = _configure_route(db, test_org)
    path = f"/webhooks/twilio/{route.webhook_id}/inbound"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"
    data = {
        "AccountSid": ACCOUNT_SID,
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": "SM" + ("4" * 32),
        "SmsSid": "SM" + ("4" * 32),
        "From": CONTACT,
        "To": SENDER,
        "Body": "Please stop texting me",
        "NumMedia": "0",
    }
    headers = _signed_headers(url, data)

    first = await client.post(path, data=data, headers=headers)
    replay = await client.post(path, data=data, headers=headers)

    assert first.status_code == replay.status_code == 200
    assert db.query(MessageWebhookEvent).filter_by(organization_id=test_org.id).count() == 1
    assert db.query(MessagingMessage).filter_by(organization_id=test_org.id).count() == 1
    assert (
        db.query(MessagingConsentEvidence)
        .filter(MessagingConsentEvidence.organization_id == test_org.id)
        .count()
        == 1
    )


async def test_webhook_rejects_invalid_signature_and_signed_tenant_spoof(
    client,
    db,
    test_org,
) -> None:
    from app.core.config import settings as app_settings
    from app.db.models.messaging_delivery import MessageWebhookEvent

    route = _configure_route(db, test_org)
    path = f"/webhooks/twilio/{route.webhook_id}/inbound"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"
    data = {
        "AccountSid": "AC" + ("9" * 32),
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": "SM" + ("5" * 32),
        "From": CONTACT,
        "To": SENDER,
        "Body": "STOP",
        "NumMedia": "0",
    }

    invalid = await client.post(path, data=data, headers={"X-Twilio-Signature": "invalid"})
    signed_spoof = await client.post(path, data=data, headers=_signed_headers(url, data))

    assert invalid.status_code == 403
    assert signed_spoof.status_code == 403
    assert db.query(MessageWebhookEvent).count() == 0


async def test_unordered_status_callbacks_preserve_monotonic_delivery_state(
    client,
    db,
    test_org,
) -> None:
    from app.core.config import settings as app_settings
    from app.db.models.messaging_delivery import MessageWebhookEvent
    from app.services import messaging_consent_service, messaging_delivery_service

    route = _configure_route(db, test_org)
    consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=CONTACT,
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational messaging disclosure",
        source="website",
        source_reference="lead-status-1",
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        idempotency_key="lead-status-1",
        evidence_metadata={},
    )
    delivery = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="EWI operational. Frequency varies. Msg & data rates apply. HELP. STOP.",
        idempotency_key="status-delivery-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    message_sid = "SM" + ("6" * 32)
    delivery.provider_message_sid = message_sid
    delivery.message.provider_message_sid = message_sid
    db.commit()
    path = f"/webhooks/twilio/{route.webhook_id}/status"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"

    delivered = {
        "AccountSid": ACCOUNT_SID,
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": message_sid,
        "MessageStatus": "delivered",
        "From": SENDER,
        "To": CONTACT,
    }
    sent = {**delivered, "MessageStatus": "sent"}
    first = await client.post(path, data=delivered, headers=_signed_headers(url, delivered))
    late = await client.post(path, data=sent, headers=_signed_headers(url, sent))

    assert first.status_code == late.status_code == 200
    db.refresh(delivery)
    db.refresh(delivery.message)
    assert delivery.status == "delivered"
    assert delivery.message.provider_status == "delivered"
    assert (
        db.query(MessageWebhookEvent)
        .filter(MessageWebhookEvent.provider_message_sid == message_sid)
        .count()
        == 2
    )


async def test_status_callback_arriving_before_send_commit_is_replayed_after_sid_link(
    client,
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.core.config import settings as app_settings
    from app.db.models import MessageReconciliationCase
    from app.db.models.messaging_delivery import MessageWebhookEvent
    from app.services import (
        messaging_consent_service,
        messaging_delivery_service,
        messaging_dispatch_service,
        twilio_transport,
    )
    from app.services.messaging_sending_hours import RecipientTimezone, SendingWindowDecision

    route = _configure_route(db, test_org)
    route.a2p_status = "approved"
    route.advanced_opt_out_status = "verified"
    db.commit()
    consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=CONTACT,
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational messaging disclosure",
        source="website",
        source_reference="lead-status-race",
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        idempotency_key="lead-status-race",
        evidence_metadata={},
    )
    delivery = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="EWI operational. Frequency varies. HELP. STOP.",
        idempotency_key="status-race-delivery",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    claimed = messaging_delivery_service.claim_due_deliveries(
        db,
        worker_id="status-race-worker",
        limit=1,
    )[0]
    message_sid = "SM" + ("9" * 32)
    path = f"/webhooks/twilio/{route.webhook_id}/status"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"
    callback = {
        "AccountSid": ACCOUNT_SID,
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": message_sid,
        "MessageStatus": "delivered",
        "From": SENDER,
        "To": CONTACT,
    }

    response = await client.post(path, data=callback, headers=_signed_headers(url, callback))

    assert response.status_code == 200
    event = db.query(MessageWebhookEvent).filter_by(provider_message_sid=message_sid).one()
    case = db.query(MessageReconciliationCase).filter_by(webhook_event_id=event.id).one()
    assert event.processed_at is None
    assert case.status == "action_required"
    monkeypatch.setattr(
        messaging_dispatch_service.messaging_sending_hours,
        "resolve_recipient_timezone",
        lambda **_kwargs: RecipientTimezone("America/Los_Angeles", "state"),
    )
    monkeypatch.setattr(
        messaging_dispatch_service.messaging_sending_hours,
        "evaluate_sending_window",
        lambda **_kwargs: SendingWindowDecision(True, None, None),
    )
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: twilio_transport.TwilioSendResult(
            success=True,
            message_sid=message_sid,
            initial_status="accepted",
        ),
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=claimed.lease_token,
        lease_generation=claimed.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "submitted"
    db.refresh(delivery)
    db.refresh(event)
    db.refresh(case)
    assert delivery.status == "delivered"
    assert event.processed_at is not None
    assert case.status == "resolved"
    assert case.delivery_id == delivery.id
    assert case.resolution_code == "status_callback_replayed"


async def test_inbound_mms_returns_promptly_and_queues_only_opaque_event_identity(
    client,
    db,
    test_org,
) -> None:
    from app.core.config import settings as app_settings
    from app.db.enums import JobType
    from app.db.models import Job
    from app.db.models.messaging_delivery import MessageWebhookEvent

    route = _configure_route(db, test_org)
    path = f"/webhooks/twilio/{route.webhook_id}/inbound"
    url = f"{app_settings.API_BASE_URL.rstrip('/')}{path}"
    message_sid = "MM" + ("7" * 32)
    media_sid = "ME" + ("8" * 32)
    data = {
        "AccountSid": ACCOUNT_SID,
        "MessagingServiceSid": SERVICE_SID,
        "MessageSid": message_sid,
        "From": CONTACT,
        "To": SENDER,
        "Body": "Photo attached",
        "NumMedia": "1",
        "MediaUrl0": (
            f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/"
            f"Messages/{message_sid}/Media/{media_sid}"
        ),
        "MediaContentType0": "image/gif",
    }

    response = await client.post(path, data=data, headers=_signed_headers(url, data))

    assert response.status_code == 200
    event = db.query(MessageWebhookEvent).filter_by(provider_message_sid=message_sid).one()
    job = db.query(Job).filter_by(job_type=JobType.TWILIO_INBOUND_MEDIA_FETCH.value).one()
    assert job.payload == {
        "provider_scope": "organization",
        "webhook_event_id": str(event.id),
    }
    assert CONTACT not in str(job.payload)
    assert data["MediaUrl0"] not in str(job.payload)
