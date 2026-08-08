"""Authenticated inbound MMS persistence, scan, and provider deletion contracts."""

from datetime import UTC, datetime

import pytest

from app.db.enums import JobScope, JobType
from app.db.models import (
    Job,
    MessageMediaAsset,
    MessageMediaLink,
    MessageReconciliationCase,
)
from app.jobs.handlers import twilio as twilio_job_handler
from app.services import twilio_transport

GIF_1X1 = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01"
    b"\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _job_for_event(db, organization_id, event_id):
    job = Job(
        organization_id=organization_id,
        job_scope=JobScope.ORGANIZATION.value,
        job_type=JobType.TWILIO_INBOUND_MEDIA_FETCH.value,
        status="running",
        payload={
            "provider_scope": "organization",
            "webhook_event_id": str(event_id),
        },
        run_at=datetime.now(UTC),
    )
    db.add(job)
    db.commit()
    return job


def _persist_inbound_event(db, test_org, *, num_media="1", content_type="image/gif"):
    from app.core.encryption import hash_phone, hash_pii
    from app.db.models import (
        MessageWebhookEvent,
        MessagingContact,
        MessagingConversation,
        MessagingMessage,
    )
    from app.services import twilio_settings_service

    settings = twilio_settings_service.get_or_create_settings(db, test_org.id)
    settings.enabled = True
    settings.account_sid_encrypted = twilio_settings_service.encrypt_credential(
        "AC" + "1" * 32
    )
    settings.api_key_sid_encrypted = twilio_settings_service.encrypt_credential(
        "SK" + "2" * 32
    )
    settings.api_secret_encrypted = twilio_settings_service.encrypt_credential("restricted")
    route = next(item for item in settings.routes if item.purpose == "operational")
    route.enabled = True
    route.messaging_service_sid_encrypted = twilio_settings_service.encrypt_credential(
        "MG" + "3" * 32
    )
    route.sender_phone_encrypted = twilio_settings_service.encrypt_credential(
        "+14155550199"
    )
    route.sender_phone_hash = hash_phone("+14155550199")
    route.sender_phone_last4 = "0199"
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
    message_sid = "MM" + "4" * 32
    media_sid = "ME" + "5" * 32
    message = MessagingMessage(
        organization_id=test_org.id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        route_id=route.id,
        purpose="operational",
        direction="inbound",
        body="Photo",
        provider_message_sid=message_sid,
        from_phone_hash=contact.phone_hash,
        from_phone_last4=contact.phone_last4,
        to_phone_hash=route.sender_phone_hash,
        to_phone_last4=route.sender_phone_last4,
        provider_status="received",
        is_unread=True,
    )
    db.add(message)
    db.flush()
    fields = [
        ["AccountSid", "AC" + "1" * 32],
        ["MessageSid", message_sid],
        ["NumMedia", num_media],
    ]
    count = int(num_media)
    for index in range(min(count, 11)):
        sid = media_sid if index == 0 else "ME" + f"{index:032x}"
        fields.extend(
            [
                [
                    f"MediaUrl{index}",
                    f"https://api.twilio.com/2010-04-01/Accounts/{'AC' + '1' * 32}/"
                    f"Messages/{message_sid}/Media/{sid}",
                ],
                [f"MediaContentType{index}", content_type],
            ]
        )
    import json

    event = MessageWebhookEvent(
        organization_id=test_org.id,
        route_id=route.id,
        account_sid_hash=hash_pii("AC" + "1" * 32, purpose="twilio-account"),
        event_key=f"inbound:{message_sid}",
        event_type="inbound",
        provider_message_sid=message_sid,
        provider_status="received",
        raw_fields=json.dumps(fields),
        processed_at=datetime.now(UTC),
    )
    db.add(event)
    db.commit()
    return event, message, media_sid


@pytest.mark.asyncio
async def test_inbound_mms_downloads_with_restricted_key_persists_then_deletes_provider(
    db, test_org, monkeypatch
):
    event, message, media_sid = _persist_inbound_event(db, test_org)
    job = _job_for_event(db, test_org.id, event.id)
    calls: list[str] = []

    monkeypatch.setattr(
        twilio_transport,
        "download_inbound_media",
        lambda **kwargs: (
            calls.append("download")
            or twilio_transport.TwilioMediaDownloadResult(
                success=True,
                media_sid=media_sid,
                content_type="image/gif",
                content=GIF_1X1,
            )
        ),
    )
    monkeypatch.setattr(
        twilio_transport,
        "delete_inbound_media",
        lambda **kwargs: (
            calls.append("delete")
            or twilio_transport.TwilioMediaDeleteResult(success=True)
        ),
    )

    await twilio_job_handler.process_twilio_inbound_media_fetch(db, job)

    link = db.query(MessageMediaLink).filter_by(message_id=message.id).one()
    asset = db.get(MessageMediaAsset, link.media_asset_id)
    assert calls == ["download", "delete"]
    assert asset is not None
    assert asset.scan_status == "pending"
    assert asset.checksum_sha256
    assert link.provider_media_sid == media_sid
    assert link.provider_deleted_at is not None
    assert link.processing_status == "stored"


@pytest.mark.asyncio
async def test_unsupported_inbound_mime_is_quarantined_before_provider_delete(
    db, test_org, monkeypatch
):
    event, message, media_sid = _persist_inbound_event(
        db, test_org, content_type="application/x-msdownload"
    )
    job = _job_for_event(db, test_org.id, event.id)
    monkeypatch.setattr(
        twilio_transport,
        "download_inbound_media",
        lambda **_kwargs: twilio_transport.TwilioMediaDownloadResult(
            success=True,
            media_sid=media_sid,
            content_type="application/x-msdownload",
            content=b"MZ executable",
        ),
    )
    monkeypatch.setattr(
        twilio_transport,
        "delete_inbound_media",
        lambda **_kwargs: twilio_transport.TwilioMediaDeleteResult(success=True),
    )

    await twilio_job_handler.process_twilio_inbound_media_fetch(db, job)

    link = db.query(MessageMediaLink).filter_by(message_id=message.id).one()
    asset = db.get(MessageMediaAsset, link.media_asset_id)
    assert asset.scan_status == "quarantined"
    assert asset.quarantine_reason == "unsupported_mime"
    assert link.processing_status == "quarantined"
    assert link.provider_deleted_at is not None


@pytest.mark.asyncio
async def test_transient_inbound_media_download_failure_retries_job(
    db,
    test_org,
    monkeypatch,
):
    event, message, media_sid = _persist_inbound_event(db, test_org)
    job = _job_for_event(db, test_org.id, event.id)
    monkeypatch.setattr(
        twilio_transport,
        "download_inbound_media",
        lambda **_kwargs: twilio_transport.TwilioMediaDownloadResult(
            success=False,
            media_sid=media_sid,
            failure_reason=twilio_transport.TwilioFailureReason.RATE_LIMITED,
            provider_status_code=429,
            retryable=True,
        ),
    )

    with pytest.raises(RuntimeError, match="transient"):
        await twilio_job_handler.process_twilio_inbound_media_fetch(db, job)

    assert db.query(MessageMediaLink).filter_by(message_id=message.id).count() == 0
    assert db.query(MessageReconciliationCase).filter_by(webhook_event_id=event.id).count() == 0


@pytest.mark.asyncio
async def test_transient_inbound_media_delete_failure_retries_job(
    db,
    test_org,
    monkeypatch,
):
    event, message, media_sid = _persist_inbound_event(db, test_org)
    job = _job_for_event(db, test_org.id, event.id)
    monkeypatch.setattr(
        twilio_transport,
        "download_inbound_media",
        lambda **_kwargs: twilio_transport.TwilioMediaDownloadResult(
            success=True,
            media_sid=media_sid,
            content_type="image/gif",
            content=GIF_1X1,
        ),
    )
    monkeypatch.setattr(
        twilio_transport,
        "delete_inbound_media",
        lambda **_kwargs: twilio_transport.TwilioMediaDeleteResult(
            success=False,
            failure_reason=twilio_transport.TwilioFailureReason.RATE_LIMITED,
            provider_status_code=429,
            retryable=True,
        ),
    )

    with pytest.raises(RuntimeError, match="transient"):
        await twilio_job_handler.process_twilio_inbound_media_fetch(db, job)

    link = db.query(MessageMediaLink).filter_by(message_id=message.id).one()
    assert link.provider_deleted_at is None
    assert link.processing_status == "stored"
    assert db.query(MessageReconciliationCase).filter_by(webhook_event_id=event.id).count() == 0


@pytest.mark.asyncio
async def test_excessive_inbound_media_count_creates_actionable_case_without_download(
    db, test_org, monkeypatch
):
    event, _message, _media_sid = _persist_inbound_event(db, test_org, num_media="11")
    job = _job_for_event(db, test_org.id, event.id)
    monkeypatch.setattr(
        twilio_transport,
        "download_inbound_media",
        lambda **_kwargs: pytest.fail("invalid media count must fail before provider I/O"),
    )

    await twilio_job_handler.process_twilio_inbound_media_fetch(db, job)

    case = db.query(MessageReconciliationCase).filter_by(webhook_event_id=event.id).one()
    assert case.case_type == "media_processing"
    assert case.status == "action_required"
    assert case.reason_code == "inbound_media_count_invalid"
