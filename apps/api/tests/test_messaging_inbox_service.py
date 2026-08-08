from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.encryption import hash_email, hash_phone
from app.db.models import (
    MessageDelivery,
    MessageDeliveryAttempt,
    MessageMediaAsset,
    MessageMediaLink,
    MessageReconciliationCase,
    MessageWebhookEvent,
    MessagingContact,
    MessagingConversation,
    MessagingMessage,
    Organization,
    Surrogate,
    TwilioRoute,
    TwilioSettings,
)
from app.services import messaging_consent_service, messaging_inbox_service


def _seed_conversation(
    db,
    *,
    organization_id,
    phone: str = "+14155550110",
    phone_last4: str = "0110",
    purpose: str = "operational",
    unread: bool = True,
):
    settings = TwilioSettings(organization_id=organization_id)
    db.add(settings)
    db.flush()
    route = TwilioRoute(
        settings_id=settings.id,
        organization_id=organization_id,
        purpose=purpose,
        sender_phone_hash="sender-hash",
        sender_phone_last4="9000",
    )
    contact = MessagingContact(
        organization_id=organization_id,
        phone_e164=phone,
        phone_hash=hash_phone(phone),
        phone_last4=phone_last4,
    )
    db.add_all([route, contact])
    db.flush()
    conversation = MessagingConversation(
        organization_id=organization_id,
        contact_id=contact.id,
        route_id=route.id,
        unread_count=1 if unread else 0,
        last_message_at=datetime(2026, 7, 31, 16, 0, tzinfo=UTC),
    )
    db.add(conversation)
    db.flush()
    message = MessagingMessage(
        organization_id=organization_id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose=purpose,
        direction="inbound",
        body="Please send the appointment details.",
        provider_message_sid=f"SM{uuid.uuid4().hex}",
        from_phone_hash=contact.phone_hash,
        from_phone_last4=contact.phone_last4,
        to_phone_hash=route.sender_phone_hash,
        to_phone_last4=route.sender_phone_last4,
        provider_status="received",
        is_unread=unread,
        created_at=datetime(2026, 7, 31, 16, 0, tzinfo=UTC),
    )
    db.add(message)
    db.flush()
    return settings, route, contact, conversation, message


def test_list_conversations_is_org_scoped_masked_and_filterable(db, test_org):
    _settings, _route, _contact, conversation, _message = _seed_conversation(
        db, organization_id=test_org.id
    )
    other_org = Organization(name="Other Inbox Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()
    _seed_conversation(
        db,
        organization_id=other_org.id,
        phone="+12125550199",
        phone_last4="0199",
    )
    db.commit()

    result = messaging_inbox_service.list_conversations(
        db,
        organization_id=test_org.id,
        unread=True,
        unlinked=True,
        purpose=None,
        limit=50,
        offset=0,
    )

    assert result.total == 1
    assert result.items[0].id == conversation.id
    assert result.items[0].masked_phone == "••• ••• 0110"
    assert result.items[0].route_label == "Operational route"
    assert result.items[0].unlinked is True
    assert result.items[0].last_message_preview == "Please send the appointment details."
    assert "+14155550110" not in str(result)


def test_detail_projects_body_media_consent_delivery_and_reconciliation(db, test_org):
    _settings, route, contact, conversation, message = _seed_conversation(
        db, organization_id=test_org.id
    )
    consent = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone=contact.phone_e164,
        purpose="operational",
        affirmative=True,
        disclosure_text="I agree to receive application texts. Reply STOP to opt out.",
        source="website_intake",
        source_reference="form-submission:1",
        occurred_at=datetime(2026, 7, 31, 15, 0, tzinfo=UTC),
        idempotency_key=f"inbox-consent-{contact.id}",
        evidence_metadata={"affirmative_action": "checkbox"},
    )
    asset = MessageMediaAsset(
        organization_id=test_org.id,
        storage_key="messaging/asset-1",
        original_filename="appointment.png",
        content_type="image/png",
        byte_size=1200,
        checksum_sha256="a" * 64,
        scan_status="clean",
    )
    db.add(asset)
    db.flush()
    db.add(
        MessageMediaLink(
            organization_id=test_org.id,
            message_id=message.id,
            media_asset_id=asset.id,
            position=0,
        )
    )
    delivery = MessageDelivery(
        organization_id=test_org.id,
        message_id=message.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        consent_evidence_id=consent.evidence_id,
        source_type="workflow",
        idempotency_key=f"delivery-{message.id}",
        payload_fingerprint="b" * 64,
        status="reconciliation_required",
        provider_message_sid=message.provider_message_sid,
    )
    db.add(delivery)
    db.flush()
    attempt = MessageDeliveryAttempt(
        organization_id=test_org.id,
        delivery_id=delivery.id,
        attempt_number=1,
        lease_token=uuid.uuid4(),
        lease_generation=1,
        started_at=datetime(2026, 7, 31, 16, 1, tzinfo=UTC),
        completed_at=datetime(2026, 7, 31, 16, 1, 5, tzinfo=UTC),
        outcome="ambiguous",
        error_type="provider_timeout",
        error_message="Provider acceptance was not confirmed",
    )
    webhook = MessageWebhookEvent(
        organization_id=test_org.id,
        route_id=route.id,
        account_sid_hash="account-hash",
        event_key=f"status:{message.provider_message_sid}:delivered",
        event_type="status",
        provider_message_sid=message.provider_message_sid,
        provider_status="delivered",
        raw_fields="{}",
        received_at=datetime(2026, 7, 31, 16, 2, tzinfo=UTC),
    )
    db.add_all([attempt, webhook])
    db.flush()
    reconciliation = MessageReconciliationCase(
        organization_id=test_org.id,
        case_type="ambiguous_delivery",
        status="action_required",
        reason_code="provider_timeout",
        delivery_id=delivery.id,
        version=2,
    )
    db.add(reconciliation)
    db.commit()

    detail = messaging_inbox_service.get_conversation(
        db, organization_id=test_org.id, conversation_id=conversation.id
    )

    assert detail.masked_phone == "••• ••• 0110"
    assert detail.messages[0].body == "Please send the appointment details."
    assert detail.messages[0].media[0].filename == "appointment.png"
    assert detail.messages[0].media[0].scan_status == "clean"
    assert detail.messages[0].delivery.status == "reconciliation_required"
    assert detail.messages[0].delivery.attempts[0].outcome == "ambiguous"
    assert detail.messages[0].delivery.status_events[0].status == "delivered"
    assert detail.consent_timeline[0].action == "opt_in"
    assert detail.consent_states["operational"] == "opted_in"
    assert detail.reconciliation_cases[0].id == reconciliation.id
    assert detail.reconciliation_cases[0].version == 2


def test_mark_read_and_link_preserve_org_scope(db, test_org, test_user, default_stage):
    _settings, _route, contact, conversation, message = _seed_conversation(
        db, organization_id=test_org.id
    )
    surrogate = Surrogate(
        organization_id=test_org.id,
        surrogate_number="S99001",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Inbox Candidate",
        email="inbox-candidate@example.com",
        email_hash=hash_email("inbox-candidate@example.com"),
    )
    other_org = Organization(name="Other Link Org", slug=f"link-{uuid.uuid4().hex[:8]}")
    db.add_all([surrogate, other_org])
    db.flush()
    other_surrogate = Surrogate(
        organization_id=other_org.id,
        surrogate_number="S99002",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Other Candidate",
        email="other-candidate@example.com",
        email_hash=hash_email("other-candidate@example.com"),
    )
    db.add(other_surrogate)
    db.commit()

    messaging_inbox_service.mark_conversation_read(
        db, organization_id=test_org.id, conversation_id=conversation.id
    )
    assert conversation.unread_count == 0
    assert message.is_unread is False

    linked = messaging_inbox_service.link_conversation(
        db,
        organization_id=test_org.id,
        conversation_id=conversation.id,
        entity_type="surrogate",
        entity_id=surrogate.id,
    )
    assert contact.surrogate_id == surrogate.id
    assert linked.linked_entities[0].label == "S99001 · Inbox Candidate"

    with pytest.raises(messaging_inbox_service.MessagingInboxEntityNotFound):
        messaging_inbox_service.link_conversation(
            db,
            organization_id=test_org.id,
            conversation_id=conversation.id,
            entity_type="surrogate",
            entity_id=other_surrogate.id,
        )


def test_reconciliation_resolution_uses_optimistic_version(db, test_org):
    _settings, route, contact, _conversation, message = _seed_conversation(
        db, organization_id=test_org.id
    )
    delivery = MessageDelivery(
        organization_id=test_org.id,
        message_id=message.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        source_type="workflow",
        idempotency_key=f"reconcile-{message.id}",
        payload_fingerprint="c" * 64,
        status="reconciliation_required",
    )
    db.add(delivery)
    db.flush()
    case = MessageReconciliationCase(
        organization_id=test_org.id,
        case_type="ambiguous_delivery",
        status="action_required",
        reason_code="ambiguous_timeout",
        delivery_id=delivery.id,
        version=3,
    )
    db.add(case)
    db.commit()

    resolved = messaging_inbox_service.update_reconciliation_case(
        db,
        organization_id=test_org.id,
        case_id=case.id,
        expected_version=3,
        action="resolve",
        resolution_code="provider_delivery_confirmed",
    )
    assert resolved.status == "resolved"
    assert resolved.version == 4

    with pytest.raises(messaging_inbox_service.MessagingInboxVersionConflict):
        messaging_inbox_service.update_reconciliation_case(
            db,
            organization_id=test_org.id,
            case_id=case.id,
            expected_version=3,
            action="dismiss",
            resolution_code="duplicate_case",
        )
