"""Durable Twilio messaging outbox contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _enable_messaging_dispatch(monkeypatch):
    monkeypatch.setenv("MESSAGING_DELIVERY_DISPATCH_ENABLED", "true")


def _consented_contact(db, test_org, *, ready=True):
    from app.core.encryption import hash_phone
    from app.services import messaging_consent_service, twilio_settings_service

    if ready:
        settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
        settings.enabled = True
        settings.account_sid_encrypted = twilio_settings_service.encrypt_credential("AC" + "1" * 32)
        settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential("SK" + "2" * 32)
        settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("secret")
        settings.auth_token_encrypted = twilio_settings_service.encrypt_credential("auth-token")
        settings.legal_messaging_brand = "EWI Surrogacy"
        settings.operational_disclosure = "Operational SMS disclosure"
        settings.promotional_disclosure = "Promotional SMS disclosure"
        settings.sms_terms_url = "https://example.org/sms-terms"
        settings.privacy_policy_url = "https://example.org/privacy"
        settings.support_contact = "support@example.org"
        settings.expected_frequency = "Message frequency varies"
        settings.counsel_approved_at = datetime.now(UTC)
        route = next(item for item in settings.routes if item.purpose == "operational")
        route.enabled = True
        route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(
            "MG" + "3" * 32
        )
        route.sender_phone_encrypted = twilio_settings_service.encrypt_credential("+14155550199")
        route.sender_phone_hash = hash_phone("+14155550199")
        route.sender_phone_last4 = "0199"
        route.a2p_status = "approved"
        route.advanced_opt_out_status = "verified"
        route.consent_management_status = "available"
        route.capability_evidence = {
            "meta_consent_mapping_verified": True,
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
        db.commit()

    return messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational SMS disclosure v1",
        source="website",
        source_reference="intake-1",
        occurred_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        idempotency_key="intake-1-operational",
        evidence_metadata={"affirmative_action": "checked"},
    )


def test_materialize_refuses_to_queue_when_dispatch_readiness_is_blocked(
    db,
    test_org,
) -> None:
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org, ready=False)

    with pytest.raises(messaging_delivery_service.MessagingRouteNotReady):
        messaging_delivery_service.materialize_delivery(
            db,
            organization_id=test_org.id,
            contact_id=consent.contact_id,
            purpose="operational",
            body="We received your application.",
            idempotency_key="workflow:blocked-route:occurrence-1",
            source_type="workflow",
            source_id=None,
            template_version_id=None,
            media_asset_ids=[],
            is_enrollment_confirmation=True,
        )


def test_materialize_encrypts_message_and_coalesces_identical_idempotency_key(
    db,
    test_org,
) -> None:
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)
    body = (
        "EWI Surrogacy operational updates: We received your application. "
        "Message frequency varies. Msg & data rates may apply. "
        "Reply HELP for help or STOP to opt out."
    )

    first = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body=body,
        idempotency_key="workflow:application-received:occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    duplicate = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body=body,
        idempotency_key="workflow:application-received:occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )

    assert duplicate.id == first.id
    assert first.status == "pending"
    stored_body = db.execute(
        text("SELECT body_encrypted FROM messages WHERE id = :id"),
        {"id": first.message_id},
    ).scalar_one()
    assert body not in stored_body
    assert "+14155550110" not in str(first.__dict__)


def test_same_idempotency_key_with_different_payload_is_rejected(db, test_org) -> None:
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)
    kwargs = {
        "organization_id": test_org.id,
        "contact_id": consent.contact_id,
        "purpose": "operational",
        "idempotency_key": "workflow:application-received:occurrence-2",
        "source_type": "workflow",
        "source_id": None,
        "template_version_id": None,
        "media_asset_ids": [],
        "is_enrollment_confirmation": True,
    }
    messaging_delivery_service.materialize_delivery(db, body="First payload", **kwargs)

    with pytest.raises(messaging_delivery_service.MessagingIdempotencyConflict):
        messaging_delivery_service.materialize_delivery(db, body="Changed payload", **kwargs)


def test_first_message_in_consent_epoch_requires_enrollment_confirmation(db, test_org) -> None:
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)

    with pytest.raises(
        messaging_delivery_service.MessagingEnrollmentRequired,
        match="enrollment confirmation",
    ):
        messaging_delivery_service.materialize_delivery(
            db,
            organization_id=test_org.id,
            contact_id=consent.contact_id,
            purpose="operational",
            body="We received your application.",
            idempotency_key="workflow:application-received:occurrence-3",
            source_type="workflow",
            source_id=None,
            template_version_id=None,
            media_asset_ids=[],
            is_enrollment_confirmation=False,
        )


def test_atomic_pre_send_recheck_blocks_delivery_after_stop(db, test_org) -> None:
    from app.services import messaging_consent_service, messaging_delivery_service

    consent = _consented_contact(db, test_org)
    delivery = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="EWI operational. Msg & data rates may apply. HELP. Reply STOP to opt out.",
        idempotency_key="workflow:application-received:occurrence-4",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    messaging_consent_service.record_global_stop(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        source="twilio_inbound",
        source_reference="SM-stop-1",
        occurred_at=datetime(2026, 7, 31, 12, 1, tzinfo=UTC),
        idempotency_key="SM-stop-1",
        instruction_text="STOP",
        evidence_metadata={},
    )

    result = messaging_delivery_service.recheck_before_provider_io(
        db,
        organization_id=test_org.id,
        delivery_id=delivery.id,
    )

    assert result.allowed is False
    assert result.reason == "globally_suppressed"
    db.refresh(delivery)
    assert delivery.status == "cancelled"


def test_expired_lease_is_quarantined_for_reconciliation_not_resent(db, test_org) -> None:
    from app.db.models.messaging_delivery import MessageReconciliationCase
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)
    delivery = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="EWI enrollment. Frequency varies. Msg & data rates apply. HELP. STOP.",
        idempotency_key="workflow:expired-lease:occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    claimed = messaging_delivery_service.claim_due_deliveries(
        db,
        worker_id="expired-worker",
        lease_for=timedelta(seconds=30),
        limit=1,
    )[0]
    recovered = messaging_delivery_service.recover_expired_delivery_leases(
        db,
        now=claimed.lease_expires_at + timedelta(seconds=1),
    )

    assert recovered == 1
    db.refresh(delivery)
    assert delivery.status == "reconciliation_required"
    assert delivery.attempts[0].outcome == "lease_expired"
    assert db.query(MessageReconciliationCase).filter_by(delivery_id=delivery.id).count() == 1


def test_expired_lease_recovery_bulk_loads_attempts_and_cases(db, test_org) -> None:
    from app.db.models.messaging_delivery import MessageReconciliationCase
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)
    bulk_token = uuid4().hex
    deliveries = [
        messaging_delivery_service.materialize_delivery(
            db,
            organization_id=test_org.id,
            contact_id=consent.contact_id,
            purpose="operational",
            body=f"Enrollment confirmation {index}",
            idempotency_key=f"workflow:expired-lease:{bulk_token}:{index}",
            source_type="workflow",
            source_id=None,
            template_version_id=None,
            media_asset_ids=[],
            is_enrollment_confirmation=(index == 0),
        )
        for index in range(2)
    ]
    claimed = messaging_delivery_service.claim_due_deliveries(
        db,
        worker_id="expired-bulk-worker",
        lease_for=timedelta(seconds=30),
        limit=2,
    )
    assert {delivery.id for delivery in claimed} == {delivery.id for delivery in deliveries}

    recovery_selects: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and any(
            table in normalized
            for table in (
                "from message_deliveries",
                "from message_delivery_attempts",
                "from message_reconciliation_cases",
            )
        ):
            recovery_selects.append(normalized)

    recovery_time = max(delivery.lease_expires_at for delivery in claimed) + timedelta(seconds=1)
    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        recovered = messaging_delivery_service.recover_expired_delivery_leases(
            db,
            now=recovery_time,
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_sql)

    assert recovered == 2
    assert len(recovery_selects) == 3
    for delivery in deliveries:
        db.refresh(delivery)
        assert delivery.status == "reconciliation_required"
        assert delivery.attempts[0].outcome == "lease_expired"
    assert (
        db.query(MessageReconciliationCase)
        .filter(MessageReconciliationCase.delivery_id.in_([delivery.id for delivery in deliveries]))
        .count()
        == 2
    )


def test_claim_terminalizes_exhausted_delivery_without_blocking_healthy_rows(
    db,
    test_org,
) -> None:
    from app.services import messaging_consent_service, messaging_delivery_service

    exhausted_consent = _consented_contact(db, test_org)
    exhausted = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=exhausted_consent.contact_id,
        purpose="operational",
        body="Exhausted enrollment",
        idempotency_key="workflow:exhausted:occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    exhausted.status = "retry_scheduled"
    exhausted.attempt_count = exhausted.max_attempts
    exhausted.run_at = datetime.now(UTC) - timedelta(minutes=1)

    healthy_consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone="+14155550111",
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational SMS disclosure v1",
        source="website",
        source_reference="intake-healthy",
        occurred_at=datetime(2026, 7, 31, 12, 1, tzinfo=UTC),
        idempotency_key="intake-healthy-operational",
        evidence_metadata={"affirmative_action": "checked"},
    )
    healthy = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=healthy_consent.contact_id,
        purpose="operational",
        body="Healthy enrollment",
        idempotency_key="workflow:healthy:occurrence-1",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    db.commit()

    claimed = messaging_delivery_service.claim_due_deliveries(
        db,
        worker_id="healthy-worker",
        limit=2,
    )

    assert [item.id for item in claimed] == [healthy.id]
    db.refresh(exhausted)
    assert exhausted.status == "failed"
    assert exhausted.attempt_count == exhausted.max_attempts
    assert exhausted.last_error_type == "max_attempts_exhausted"


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_terminal_enrollment_confirmation_can_be_replaced(
    db,
    test_org,
    terminal_status,
) -> None:
    from app.services import messaging_delivery_service

    consent = _consented_contact(db, test_org)
    failed = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="First enrollment",
        idempotency_key="workflow:enrollment:failed",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )
    failed.status = terminal_status
    failed.completed_at = datetime.now(UTC)
    db.commit()

    replacement = messaging_delivery_service.materialize_delivery(
        db,
        organization_id=test_org.id,
        contact_id=consent.contact_id,
        purpose="operational",
        body="Replacement enrollment",
        idempotency_key="workflow:enrollment:replacement",
        source_type="workflow",
        source_id=None,
        template_version_id=None,
        media_asset_ids=[],
        is_enrollment_confirmation=True,
    )

    assert replacement.id != failed.id
    assert replacement.status == "pending"
