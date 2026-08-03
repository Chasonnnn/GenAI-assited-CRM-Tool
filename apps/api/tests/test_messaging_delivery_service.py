"""Durable Twilio messaging outbox contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text


def _consented_contact(db, test_org):
    from app.services import messaging_consent_service

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
