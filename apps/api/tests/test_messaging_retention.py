"""Seven-year messaging retention defaults and legal-hold-aware queries."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.services import compliance_service


def test_default_retention_policies_include_all_messaging_records(db, test_org):
    compliance_service.seed_default_retention_policies(db, test_org.id)

    policies = {
        policy.entity_type: policy.retention_days
        for policy in compliance_service.list_retention_policies(db, test_org.id)
    }
    assert policies["messaging_messages"] == 2557
    assert policies["messaging_consent_evidence"] == 2557
    assert policies["messaging_webhook_events"] == 2557
    assert policies["messaging_media_assets"] == 2557


def test_messaging_retention_query_preserves_entity_legal_hold(db, test_org, test_user):
    from app.core.encryption import hash_phone
    from app.db.models import MessagingContact, MessagingConversation, MessagingMessage
    from app.services import twilio_settings_service

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    route = next(item for item in settings.routes if item.purpose == "operational")
    contact = MessagingContact(
        organization_id=test_org.id,
        phone_e164="+14155550110",
        phone_hash=hash_phone("+14155550110"),
        phone_last4="0110",
    )
    db.add(contact)
    db.flush()
    conversation = MessagingConversation(
        organization_id=test_org.id,
        contact_id=contact.id,
        route_id=route.id,
    )
    db.add(conversation)
    db.flush()
    message = MessagingMessage(
        organization_id=test_org.id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        direction="inbound",
        body="Retained message",
        from_phone_hash=contact.phone_hash,
        from_phone_last4=contact.phone_last4,
        to_phone_hash=hash_phone("+14155550199"),
        to_phone_last4="0199",
        created_at=datetime.now(UTC) - timedelta(days=2600),
    )
    db.add(message)
    db.commit()
    compliance_service.create_legal_hold(
        db,
        test_org.id,
        test_user.id,
        entity_type="messaging_message",
        entity_id=message.id,
        reason="Preserve messaging history",
    )
    cutoff = datetime.now(UTC) - timedelta(days=2557)
    query = compliance_service._build_retention_query(
        db,
        test_org.id,
        "messaging_messages",
        cutoff,
        set(),
        {"messaging_message": {message.id}},
    )

    assert query.count() == 0


def test_messaging_retention_preserves_evidence_backing_active_consent_state(
    db,
    test_org,
):
    from app.db.models import MessagingConsentEvidence
    from app.services import messaging_consent_service

    result = messaging_consent_service.record_opt_in(
        db,
        organization_id=test_org.id,
        phone="+14155550110",
        purpose="operational",
        affirmative=True,
        disclosure_text="Operational consent disclosure",
        source="website_intake",
        source_reference="retention-active-consent",
        occurred_at=datetime.now(UTC) - timedelta(days=2600),
        idempotency_key="retention-active-consent",
        evidence_metadata={"affirmative_action": "checked"},
    )
    db.execute(
        update(MessagingConsentEvidence)
        .where(MessagingConsentEvidence.id == result.evidence_id)
        .values(created_at=datetime.now(UTC) - timedelta(days=2600))
    )
    db.commit()
    cutoff = datetime.now(UTC) - timedelta(days=2557)

    query = compliance_service._build_retention_query(
        db,
        test_org.id,
        "messaging_consent_evidence",
        cutoff,
        set(),
        {},
    )

    assert query.count() == 0


def test_messaging_media_purge_schedules_durable_application_storage_removal(
    db,
    test_org,
    test_user,
):
    from app.db.enums import JobType
    from app.db.models import Job, MessageMediaAsset

    storage_key = f"messaging/{test_org.id}/expired-image.png"
    asset = MessageMediaAsset(
        organization_id=test_org.id,
        storage_key=storage_key,
        original_filename="expired-image.png",
        content_type="image/png",
        byte_size=8,
        checksum_sha256="f" * 64,
        scan_status="clean",
        content_classification="no_phi",
        created_at=datetime.now(UTC) - timedelta(days=2600),
    )
    db.add(asset)
    db.commit()
    asset_id = asset.id
    compliance_service.seed_default_retention_policies(db, test_org.id)

    results = compliance_service.execute_purge(db, test_org.id, test_user.id)

    assert next(item.count for item in results if item.entity_type == "messaging_media_assets") == 1
    assert db.get(MessageMediaAsset, asset_id) is None
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.STORAGE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.payload == {"storage_keys": [storage_key]}
