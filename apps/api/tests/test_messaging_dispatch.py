"""Fenced Twilio dispatch behavior at the provider boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock, Thread
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

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
):
    from app.core.encryption import hash_phone
    from app.services import (
        messaging_consent_service,
        messaging_delivery_service,
        twilio_settings_service,
    )

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.enabled = True
    settings.phi_enabled = phi_enabled
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential(ACCOUNT_SID)
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential(API_KEY_SID)
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential(API_SECRET)
    settings.auth_token_encrypted = twilio_settings_service.encrypt_credential("auth-token")
    route = next(item for item in settings.routes if item.purpose == "operational")
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
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")
    db.commit()
    consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=CONTACT,
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational SMS disclosure",
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
        purpose="operational",
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


def test_dispatch_refuses_inactive_twilio_account(
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
            "account_active": False,
        },
    }
    db.commit()
    _allow_sending_hours(monkeypatch)
    monkeypatch.setattr(
        messaging_dispatch_service.twilio_transport,
        "send_message",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("An inactive Twilio account must not reach provider I/O")
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


def test_ambiguous_timezone_defers_without_provider_io(db, test_org, monkeypatch) -> None:
    from app.services import messaging_dispatch_service
    from app.services.messaging_sending_hours import RecipientTimezone

    delivery = _ready_claim(db, test_org, monkeypatch)
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

    result = messaging_dispatch_service.dispatch_claimed_delivery(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
        lease_token=delivery.lease_token,
        lease_generation=delivery.lease_generation,
        now=datetime(2026, 7, 31, 18, 0, tzinfo=UTC),
    )

    assert result == "deferred_location_ambiguous"
    db.refresh(delivery)
    assert delivery.status == "retry_scheduled"
    assert delivery.last_error_type == "recipient_location_ambiguous"


def test_concurrent_first_account_admission_initialization_is_atomic(
    db_engine,
) -> None:
    import pytest

    from app.core.encryption import hash_pii
    from app.db.models import MessagingProviderAdmission, TwilioRoute
    from app.db.session import SessionLocal
    from app.services import messaging_dispatch_service

    if db_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent messaging admission requires PostgreSQL")

    route = TwilioRoute(
        purpose="operational",
        capability_evidence={"messages_per_second": 10},
    )
    account_sid = f"AC{uuid4().hex}"
    fixed_now = datetime.now(UTC).replace(microsecond=0)
    barrier = Barrier(2)
    result_lock = Lock()
    results: list[datetime | None] = []
    errors: list[Exception] = []

    def reserve_once() -> None:
        session = SessionLocal(bind=db_engine)
        try:
            barrier.wait(timeout=10)
            reserved = messaging_dispatch_service._reserve_account_slot(
                session,
                account_sid=account_sid,
                route=route,
                now=fixed_now,
            )
            session.commit()
            with result_lock:
                results.append(reserved)
        except Exception as exc:
            session.rollback()
            with result_lock:
                errors.append(exc)
        finally:
            session.close()

    threads = [Thread(target=reserve_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert results.count(None) == 1
    assert [value for value in results if value is not None] == [
        fixed_now + timedelta(milliseconds=100)
    ]

    account_hash = hash_pii(account_sid, purpose="twilio-admission")
    cleanup = SessionLocal(bind=db_engine)
    try:
        cleanup.query(MessagingProviderAdmission).filter_by(account_sid_hash=account_hash).delete()
        cleanup.commit()
    finally:
        cleanup.close()
