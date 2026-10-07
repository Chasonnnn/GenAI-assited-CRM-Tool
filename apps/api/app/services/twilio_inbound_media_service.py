"""Durable authenticated ingestion for Twilio inbound MMS media."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    MessageMediaAsset,
    MessageMediaLink,
    MessageReconciliationCase,
    MessageWebhookEvent,
    MessagingMessage,
    TwilioRoute,
    TwilioSettings,
)
from app.services import (
    attachment_service,
    message_content_service,
    twilio_settings_service,
    twilio_transport,
)

MAX_INBOUND_MEDIA_COUNT = 10
MAX_INBOUND_MEDIA_TOTAL_BYTES = 5 * 1024 * 1024
SUPPORTED_INBOUND_MIME = frozenset({"image/gif", "image/jpeg", "image/png"})


def _reconciliation(
    db: Session,
    *,
    event: MessageWebhookEvent,
    reason_code: str,
) -> None:
    exists = db.execute(
        select(MessageReconciliationCase.id).where(
            MessageReconciliationCase.organization_id == event.organization_id,
            MessageReconciliationCase.webhook_event_id == event.id,
            MessageReconciliationCase.reason_code == reason_code,
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(
            MessageReconciliationCase(
                organization_id=event.organization_id,
                case_type="media_processing",
                status="action_required",
                reason_code=reason_code,
                webhook_event_id=event.id,
            )
        )


def _raw_fields(event: MessageWebhookEvent) -> dict[str, str]:
    try:
        pairs = json.loads(event.raw_fields)
        if not isinstance(pairs, list):
            raise ValueError
        result: dict[str, str] = {}
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError
            key, value = pair
            if not isinstance(key, str):
                raise ValueError
            result[key] = str(value)
        return result
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Encrypted inbound media fields are invalid") from exc


def _quarantined_asset(
    db: Session,
    *,
    organization_id: uuid.UUID,
    media_sid: str,
    content_type: str,
    content: bytes,
    reason: str,
) -> MessageMediaAsset:
    checksum = hashlib.sha256(content).hexdigest()
    existing = db.execute(
        select(MessageMediaAsset).where(
            MessageMediaAsset.organization_id == organization_id,
            MessageMediaAsset.checksum_sha256 == checksum,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    asset_id = uuid.uuid4()
    storage_key = f"messaging/{organization_id}/quarantine/{asset_id.hex}.bin"
    attachment_service.store_file(storage_key, BytesIO(content), "application/octet-stream")
    attachment_service.register_storage_cleanup_on_rollback(db, storage_key)
    asset = MessageMediaAsset(
        id=asset_id,
        organization_id=organization_id,
        storage_key=storage_key,
        original_filename=f"{media_sid}.bin",
        content_type=content_type[:255],
        byte_size=len(content),
        checksum_sha256=checksum,
        scan_status="quarantined",
        quarantine_reason=reason,
        content_classification="no_phi",
        provider_media_sid=media_sid,
    )
    db.add(asset)
    db.flush()
    return asset


def _persist_media(
    db: Session,
    *,
    message: MessagingMessage,
    position: int,
    media_sid: str,
    claimed_content_type: str,
    downloaded: twilio_transport.TwilioMediaDownloadResult,
) -> MessageMediaLink:
    existing_link = db.execute(
        select(MessageMediaLink).where(
            MessageMediaLink.message_id == message.id,
            MessageMediaLink.position == position,
        )
    ).scalar_one_or_none()
    if existing_link is not None:
        return existing_link

    actual_content_type = (
        (downloaded.content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    )
    content = downloaded.content or b""
    quarantine_reason: str | None = None
    if claimed_content_type not in SUPPORTED_INBOUND_MIME:
        quarantine_reason = "unsupported_mime"
    elif actual_content_type != claimed_content_type:
        quarantine_reason = "mime_mismatch"

    asset: MessageMediaAsset
    if quarantine_reason is None:
        extension = {
            "image/gif": "gif",
            "image/jpeg": "jpg",
            "image/png": "png",
        }[actual_content_type]
        try:
            asset = message_content_service.upload_media_assets(
                db,
                organization_id=message.organization_id,
                uploads=[
                    message_content_service.MediaUpload(
                        filename=f"{media_sid}.{extension}",
                        content_type=actual_content_type,
                        file=BytesIO(content),
                    )
                ],
                content_classification="no_phi",
            )[0]
        except message_content_service.MessagingMediaValidationError:
            quarantine_reason = "invalid_media_bytes"

    if quarantine_reason is not None:
        asset = _quarantined_asset(
            db,
            organization_id=message.organization_id,
            media_sid=media_sid,
            content_type=actual_content_type,
            content=content,
            reason=quarantine_reason,
        )

    link = MessageMediaLink(
        organization_id=message.organization_id,
        message_id=message.id,
        media_asset_id=asset.id,
        position=position,
        provider_media_sid=media_sid,
        processing_status=("quarantined" if quarantine_reason else "stored"),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def process_inbound_media_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    webhook_event_id: uuid.UUID,
) -> None:
    event = db.execute(
        select(MessageWebhookEvent).where(
            MessageWebhookEvent.id == webhook_event_id,
            MessageWebhookEvent.organization_id == organization_id,
            MessageWebhookEvent.event_type == "inbound",
        )
    ).scalar_one_or_none()
    if event is None:
        raise ValueError("Inbound media webhook event was not found")
    fields = _raw_fields(event)
    try:
        media_count = int(fields.get("NumMedia", "0"))
    except ValueError:
        media_count = -1
    if media_count < 1 or media_count > MAX_INBOUND_MEDIA_COUNT:
        _reconciliation(db, event=event, reason_code="inbound_media_count_invalid")
        db.commit()
        return

    message = db.execute(
        select(MessagingMessage).where(
            MessagingMessage.organization_id == organization_id,
            MessagingMessage.route_id == event.route_id,
            MessagingMessage.provider_message_sid == event.provider_message_sid,
            MessagingMessage.direction == "inbound",
        )
    ).scalar_one_or_none()
    route = db.execute(
        select(TwilioRoute).where(
            TwilioRoute.id == event.route_id,
            TwilioRoute.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    settings = db.execute(
        select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
    ).scalar_one_or_none()
    if (
        message is None
        or route is None
        or settings is None
        or not settings.account_sid_encrypted
        or not settings.api_key_sid_encrypted
        or not settings.api_secret_encrypted
    ):
        _reconciliation(db, event=event, reason_code="inbound_media_configuration_missing")
        db.commit()
        return

    credentials = twilio_transport.TwilioCredentials(
        account_sid=twilio_settings_service.decrypt_credential(settings.account_sid_encrypted),
        api_key_sid=twilio_settings_service.decrypt_credential(settings.api_key_sid_encrypted),
        api_secret=twilio_settings_service.decrypt_credential(settings.api_secret_encrypted),
    )
    remaining_bytes = MAX_INBOUND_MEDIA_TOTAL_BYTES
    for position in range(media_count):
        media_url = fields.get(f"MediaUrl{position}", "")
        claimed_content_type = (
            fields.get(f"MediaContentType{position}", "application/octet-stream")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        try:
            account_sid, message_sid, media_sid = twilio_transport.parse_inbound_media_url(
                media_url
            )
        except ValueError:
            _reconciliation(db, event=event, reason_code="inbound_media_url_invalid")
            db.commit()
            continue
        if account_sid != credentials.account_sid or message_sid != event.provider_message_sid:
            _reconciliation(db, event=event, reason_code="inbound_media_url_mismatch")
            db.commit()
            continue
        if remaining_bytes <= 0:
            _reconciliation(db, event=event, reason_code="inbound_media_size_exceeded")
            db.commit()
            continue
        link = db.execute(
            select(MessageMediaLink).where(
                MessageMediaLink.organization_id == organization_id,
                MessageMediaLink.message_id == message.id,
                MessageMediaLink.position == position,
            )
        ).scalar_one_or_none()
        if link is None:
            downloaded = twilio_transport.download_inbound_media(
                credentials=credentials,
                media_url=media_url,
                message_sid=message_sid,
                media_sid=media_sid,
                max_bytes=remaining_bytes,
            )
            if not downloaded.success or downloaded.content is None:
                if downloaded.retryable:
                    raise RuntimeError("Twilio inbound media download transient failure")
                _reconciliation(db, event=event, reason_code="inbound_media_download_failed")
                db.commit()
                continue
            remaining_bytes -= len(downloaded.content)
            link = _persist_media(
                db,
                message=message,
                position=position,
                media_sid=media_sid,
                claimed_content_type=claimed_content_type,
                downloaded=downloaded,
            )
        elif link.provider_deleted_at is not None:
            continue
        deleted = twilio_transport.delete_inbound_media(
            credentials=credentials,
            message_sid=message_sid,
            media_sid=media_sid,
        )
        if deleted.success:
            link.provider_deleted_at = datetime.now(UTC)
        elif deleted.retryable:
            raise RuntimeError("Twilio inbound media deletion transient failure")
        else:
            link.processing_status = "delete_failed"
            _reconciliation(db, event=event, reason_code="inbound_media_delete_failed")
        db.commit()
