"""Fenced Twilio dispatch behavior at the provider boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

ACCOUNT_SID = "AC" + ("1" * 32)
API_KEY_SID = "SK" + ("2" * 32)
API_SECRET = "restricted-secret"
SERVICE_SID = "MG" + ("3" * 32)
MESSAGE_SID = "SM" + ("4" * 32)
SENDER = "+14155550199"
CONTACT = "+14155550110"


def _ready_claim(
    db,
    test_org,
    monkeypatch,
    *,
    media_asset_ids=None,
    phi_enabled=False,
    fully_ready=True,
    toll_free=False,
    purpose="operational",
):
    from app.core.encryption import hash_phone
    from app.services import (
        messaging_consent_service,
        messaging_delivery_service,
        twilio_readiness_service,
        twilio_settings_service,
    )

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.enabled = True
    settings.phi_enabled = phi_enabled
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential(ACCOUNT_SID)
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential(API_KEY_SID)
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential(API_SECRET)
    settings.auth_token_encrypted = twilio_settings_service.encrypt_credential("auth-token")
    route = next(item for item in settings.routes if item.purpose == purpose)
    route.enabled = True
    route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(SERVICE_SID)
    route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(SENDER)
    route.sender_phone_hash = hash_phone(SENDER)
    route.sender_phone_last4 = SENDER[-4:]
    route.a2p_status = "approved"
    route.advanced_opt_out_status = "verified"
    settings.legal_messaging_brand = "EWI Surrogacy"
    settings.operational_disclosure = "Operational SMS disclosure"
    settings.promotional_disclosure = "Promotional SMS disclosure"
    settings.sms_terms_url = "https://example.org/sms-terms"
    settings.privacy_policy_url = "https://example.org/privacy"
    settings.support_contact = "support@example.org"
    settings.expected_frequency = "Message frequency varies"
    settings.counsel_approved_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    if phi_enabled:
        settings.twilio_edition = "hipaa_eligible"
        settings.baa_verified_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
        settings.compliance_approved_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    route.consent_management_status = "available"
    route.capability_evidence = {
        "provider": {
            "account_active": True,
            "service_verified": True,
            "sender_in_pool": True,
            "sms": True,
            "mms": True,
            "a2p_status": "VERIFIED",
            "inbound_webhook_matches": True,
            "status_callback_matches": True,
            "checked_at": datetime.now(UTC).isoformat(),
            "settings_version": settings.current_version,
        },
    }
    if toll_free:
        sender = "+18005550199"
        route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(sender)
        route.sender_phone_hash = hash_phone(sender)
        route.sender_phone_last4 = sender[-4:]
        route.a2p_status = "unconfigured"
        route.consent_management_status = "unavailable"
        route.capability_evidence["provider"].update(
            sender_type="toll_free",
            a2p_status=None,
            toll_free_verification_status="TWILIO_APPROVED",
        )
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")
    if media_asset_ids:
        monkeypatch.setattr(
            twilio_readiness_service.app_settings,
            "ATTACHMENT_SCAN_ENABLED",
            True,
        )
    db.commit()
    consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=CONTACT,
        purpose=purpose,
        affirmative=True,
        disclosure_text=f"{purpose.title()} SMS disclosure",
        source="website",
        source_reference="dispatch-lead-1",
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        idempotency_key="dispatch-lead-1",
        evidence_metadata={},
    )
    delivery = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose=purpose,
        body="EWI operational enrollment. Frequency varies. Msg & data rates apply. HELP. STOP.",
        idempotency_key="dispatch-occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=media_asset_ids or [],
        is_enrollment_confirmation=True,
    )
    claimed = messaging_delivery_service.claim_due_deliveries(
        db,
        worker_id="test-worker",
        limit=1,
    )
    assert [item.id for item in claimed] == [delivery.id]
    if not fully_ready:
        settings.legal_messaging_brand = None
        db.commit()
    return claimed[0]


def _allow_sending_hours(monkeypatch):
    from app.services import messaging_dispatch_service
    from app.services.messaging_sending_hours import (
        RecipientTimezone,
        SendingWindowDecision,
    )

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


@pytest.mark.parametrize("revoked", [False, True])
def test_toll_free_materializes_and_dispatch_rechecks_verification(
    db, test_org, monkeypatch, revoked
):
    from app.services import messaging_dispatch_service, twilio_settings_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch, toll_free=True)
    _allow_sending_hours(monkeypatch)
    if revoked:
        settings = twilio_settings_service.get_settings(db, test_org.id)
        route = next(item for item in settings.routes if item.id == delivery.route_id)
        route.capability_evidence = {
            "provider": {
                **route.capability_evidence["provider"],
                "toll_free_verification_status": "TWILIO_REJECTED",
            }
        }
        db.commit()
    calls = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return twilio_transport.TwilioSendResult(
            success=True, message_sid=MESSAGE_SID, initial_status="accepted"
        )

    monkeypatch.setattr(twilio_transport, "send_message", fake_send)
    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )
    assert result == ("deferred_route_not_ready" if revoked else "submitted")
    assert len(calls) == (0 if revoked else 1)
    if calls:
        assert calls[0]["from_"] == "+18005550199"
        assert calls[0]["messaging_service_sid"] == SERVICE_SID


def test_dispatch_refuses_route_that_readiness_reports_blocked(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.services import messaging_dispatch_service

    delivery = _ready_claim(db, test_org, monkeypatch, fully_ready=False)
    _allow_sending_hours(monkeypatch)
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("A readiness-blocked route must not reach Twilio")
        ),
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 19, 0, tzinfo=UTC),
    )

    assert result == "deferred_route_not_ready"


def test_dispatch_defers_when_inbound_replies_miss_this_app(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.db.models import TwilioRoute
    from app.services import messaging_dispatch_service

    delivery = _ready_claim(db, test_org, monkeypatch)
    route = db.query(TwilioRoute).filter(TwilioRoute.id == delivery.route_id).one()
    route.capability_evidence = {
        **route.capability_evidence,
        "provider": {
            **route.capability_evidence["provider"],
            "inbound_webhook_matches": False,
        },
    }
    db.commit()
    _allow_sending_hours(monkeypatch)
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("A route whose opt-out replies miss this app must not send")
        ),
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 19, 0, tzinfo=UTC),
    )

    assert result == "deferred_route_not_ready"


def test_successful_dispatch_uses_exact_route_and_completes_fenced_attempt(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.services import messaging_dispatch_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch)
    _allow_sending_hours(monkeypatch)
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return twilio_transport.TwilioSendResult(
            success=True,
            message_sid=MESSAGE_SID,
            initial_status="accepted",
        )

    monkeypatch.setattr(messaging_dispatch_service.twilio_transport, "send_message", fake_send)

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "submitted"
    assert len(calls) == 1
    assert calls[0]["to"] == CONTACT
    assert calls[0]["from_"] == SENDER
    assert calls[0]["messaging_service_sid"] == SERVICE_SID
    assert calls[0]["credentials"].api_secret == API_SECRET
    db.refresh(delivery)
    assert delivery.status == "submitted"
    assert delivery.provider_message_sid == MESSAGE_SID
    assert delivery.lease_token is None
    assert delivery.attempts[0].outcome == "succeeded"


def test_mms_dispatch_uses_existing_short_lived_signed_media_contract(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.db.models import MessageMediaAsset
    from app.services import (
        message_content_service,
        messaging_dispatch_service,
        twilio_transport,
    )

    asset = MessageMediaAsset(
        organization_id=test_org.id,
        storage_key=f"messaging/{test_org.id}/{uuid4().hex}.png",
        original_filename="dispatch.png",
        content_type="image/png",
        byte_size=8,
        checksum_sha256=uuid4().hex * 2,
        scan_status="clean",
        content_classification="no_phi",
    )
    db.add(asset)
    db.commit()
    delivery = _ready_claim(db, test_org, monkeypatch, media_asset_ids=[asset.id])
    _allow_sending_hours(monkeypatch)
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return twilio_transport.TwilioSendResult(
            success=True,
            message_sid=MESSAGE_SID,
            initial_status="accepted",
        )

    monkeypatch.setattr(messaging_dispatch_service.twilio_transport, "send_message", fake_send)

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "submitted"
    assert len(calls) == 1
    assert len(calls[0]["media_urls"]) == 1
    media_url = urlparse(calls[0]["media_urls"][0])
    assert f"/messaging/media/{asset.id}/content" == media_url.path
    query = parse_qs(media_url.query)
    message_content_service.validate_media_access(
        asset_id=asset.id,
        expires_at=int(query["expires"][0]),
        signature=query["signature"][0],
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )


def test_dispatch_rechecks_phi_gate_immediately_before_provider_io(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.db.models import MessageMediaAsset
    from app.services import messaging_dispatch_service, twilio_settings_service

    asset = MessageMediaAsset(
        organization_id=test_org.id,
        storage_key=f"messaging/{test_org.id}/{uuid4().hex}.png",
        original_filename="phi.png",
        content_type="image/png",
        byte_size=8,
        checksum_sha256=uuid4().hex * 2,
        scan_status="clean",
        content_classification="phi",
    )
    db.add(asset)
    db.commit()
    delivery = _ready_claim(
        db,
        test_org,
        monkeypatch,
        media_asset_ids=[asset.id],
        phi_enabled=True,
    )
    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.phi_enabled = False
    db.commit()
    _allow_sending_hours(monkeypatch)
    called = False

    def should_not_send(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider I/O is forbidden after PHI messaging is disabled")

    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        should_not_send,
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "failed"
    assert called is False
    db.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.last_error_type == "phi_messaging_disabled"


def test_ambiguous_provider_outcome_requires_reconciliation_and_never_retries(
    db,
    test_org,
    monkeypatch,
) -> None:
    from app.db.models.messaging_delivery import MessageReconciliationCase
    from app.services import messaging_dispatch_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch)
    _allow_sending_hours(monkeypatch)
    calls = 0

    def ambiguous(**_kwargs):
        nonlocal calls
        calls += 1
        return twilio_transport.TwilioSendResult(
            success=False,
            failure_reason=twilio_transport.TwilioFailureReason.AMBIGUOUS_TRANSPORT,
            ambiguous=True,
        )

    monkeypatch.setattr(messaging_dispatch_service.twilio_transport, "send_message", ambiguous)
    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "reconciliation_required"
    assert calls == 1
    db.refresh(delivery)
    assert delivery.status == "reconciliation_required"
    assert db.query(MessageReconciliationCase).filter_by(delivery_id=delivery.id).count() == 1


def test_stop_after_claim_cancels_before_provider_io(db, test_org, monkeypatch) -> None:
    from app.services import (
        messaging_consent_service,
        messaging_dispatch_service,
        twilio_transport,
    )

    delivery = _ready_claim(db, test_org, monkeypatch)
    _allow_sending_hours(monkeypatch)
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone=CONTACT,
        instruction_text="STOP",
        source="twilio_inbound",
        source_reference="SM-race-stop",
        occurred_at=datetime(2026, 7, 31, 12, 5, tzinfo=UTC),
        idempotency_key="SM-race-stop",
        evidence_metadata={},
    )
    called = False

    def should_not_send(**_kwargs):
        nonlocal called
        called = True
        return twilio_transport.TwilioSendResult(success=True)

    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        should_not_send,
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "cancelled"
    assert called is False


def test_21610_adds_local_global_suppression(db, test_org, monkeypatch) -> None:
    from app.db.models import MessagingGlobalSuppression
    from app.services import messaging_dispatch_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch)
    _allow_sending_hours(monkeypatch)
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: twilio_transport.TwilioSendResult(
            success=False,
            failure_reason=twilio_transport.TwilioFailureReason.PROVIDER_OPT_OUT,
            provider_error_code=21610,
            provider_opt_out=True,
        ),
    )

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "failed"
    suppression = (
        db.query(MessagingGlobalSuppression)
        .filter(MessagingGlobalSuppression.contact_id == delivery.contact_id)
        .one()
    )
    assert suppression.active is True
    assert suppression.reason == "global_opt_out"


def test_promotional_with_unknown_timezone_waits_for_hours_open_everywhere(
    db, test_org, monkeypatch
) -> None:
    from app.services import messaging_dispatch_service
    from app.services.messaging_sending_hours import RecipientTimezone

    delivery = _ready_claim(db, test_org, monkeypatch, purpose="promotional")
    monkeypatch.setattr(
        messaging_dispatch_service.messaging_sending_hours,
        "resolve_recipient_timezone",
        lambda **_kwargs: RecipientTimezone(None, "ambiguous"),
    )
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("provider I/O not allowed")),
    )

    # 22:00 EDT on Friday is closed on the East Coast.
    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 8, 1, 2, 0, tzinfo=UTC),
    )

    assert result == "deferred_sending_hours"
    db.refresh(delivery)
    assert delivery.status == "retry_scheduled"
    assert delivery.last_error_type == "outside_sending_hours"
    # Hours open in every US zone and every state: 09:00 HST.
    assert delivery.run_at == datetime(2026, 8, 1, 19, 0, tzinfo=UTC)


def test_operational_dispatch_ignores_quiet_hours(db, test_org, monkeypatch) -> None:
    from app.services import messaging_dispatch_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch)
    for name in (
        "resolve_recipient_timezone",
        "evaluate_sending_window",
        "evaluate_sending_window_in_every_us_timezone",
    ):
        monkeypatch.setattr(
            messaging_dispatch_service.messaging_sending_hours,
            name,
            lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("Transactional messages have no sending window")
            ),
        )
    sent = []
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **kwargs: (
            sent.append(kwargs)
            or twilio_transport.TwilioSendResult(
                success=True, message_sid="SM" + "1" * 32, initial_status="queued"
            )
        ),
    )

    # 03:00 EDT.
    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 8, 1, 7, 0, tzinfo=UTC),
    )

    assert result == "submitted"
    assert len(sent) == 1


def _record_prior_promotional_sends(db, test_org, contact_id, started_times) -> None:
    from app.db.models.messaging_delivery import MessageDeliveryAttempt
    from app.services import messaging_delivery_service

    for index, started_at in enumerate(started_times):
        prior = messaging_delivery_service.materialize_delivery(
            db,
            organization_id=test_org.id,
            contact_id=contact_id,
            purpose="promotional",
            body=f"EWI Surrogacy info session {index}. Reply STOP to opt out.",
            idempotency_key=f"florida-cap-{index}",
            source_type="workflow",
            source_id=None,
            template_version_id=None,
            media_asset_ids=[],
            is_enrollment_confirmation=False,
        )
        db.add(
            MessageDeliveryAttempt(
                organization_id=test_org.id,
                delivery_id=prior.id,
                attempt_number=1,
                lease_token=uuid4(),
                lease_generation=1,
                started_at=started_at,
                completed_at=started_at,
                outcome="succeeded",
            )
        )
    db.commit()


@pytest.mark.parametrize(("prior_sends", "deferred"), [(2, False), (3, True)])
def test_florida_allows_three_promotional_texts_on_one_subject_per_day(
    db, test_org, monkeypatch, prior_sends, deferred
) -> None:
    from app.services import messaging_dispatch_service, twilio_transport

    delivery = _ready_claim(db, test_org, monkeypatch, purpose="promotional")
    now = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)
    _record_prior_promotional_sends(
        db,
        test_org,
        delivery.contact_id,
        [now - timedelta(hours=hours) for hours in (23, 10, 1)][-prior_sends:],
    )
    _allow_sending_hours(monkeypatch)
    sent = []
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **kwargs: (
            sent.append(kwargs)
            or twilio_transport.TwilioSendResult(
                success=True, message_sid="SM" + "1" * 32, initial_status="queued"
            )
        ),
    )

    # The contact has no address, so Florida's rule applies.
    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=now,
    )

    if deferred:
        assert result == "deferred_florida_daily_limit"
        assert sent == []
        db.refresh(delivery)
        assert delivery.last_error_type == "florida_daily_limit"
        # The oldest of the three leaves the 24-hour window first.
        assert delivery.run_at == now + timedelta(hours=1)
    else:
        assert result == "submitted"
        assert len(sent) == 1
