"""Zapier webhook settings service."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.stage_definitions import canonicalize_stage_key
from app.core.url_validation import validate_outbound_webhook_url
from app.db.models import ZapierInboundWebhook, ZapierWebhookSettings
from app.services import oauth_service

logger = logging.getLogger(__name__)

QUALIFIED_EVENT_NAME = "Qualified"
CONVERTED_EVENT_NAME = "Converted"
LOST_EVENT_NAME = "Lost"
NOT_QUALIFIED_EVENT_NAME = "Not Qualified"

QUALIFIED_BUCKET = "qualified"
CONVERTED_BUCKET = "converted"
LOST_BUCKET = "lost"
NOT_QUALIFIED_BUCKET = "not_qualified"

QUALIFIED_STAGE_KEYS = {
    "pre_qualified",
    "interview_scheduled",
    "application_submitted",
    "under_review",
    "approved",
}
CONVERTED_STAGE_KEYS = {
    "ready_to_match",
    "matched",
    "medical_clearance_passed",
    "legal_clearance_passed",
    "transfer_cycle",
    "second_hcg_confirmed",
    "heartbeat_confirmed",
    "ob_care_established",
    "anatomy_scanned",
    "delivered",
}
LOST_STAGE_KEYS = {"lost"}
NOT_QUALIFIED_STAGE_KEYS = {"disqualified"}

DEFAULT_BUCKET_BY_STAGE_KEY: dict[str, str] = {
    **{stage_key: QUALIFIED_BUCKET for stage_key in QUALIFIED_STAGE_KEYS},
    **{stage_key: CONVERTED_BUCKET for stage_key in CONVERTED_STAGE_KEYS},
    **{stage_key: LOST_BUCKET for stage_key in LOST_STAGE_KEYS},
    **{stage_key: NOT_QUALIFIED_BUCKET for stage_key in NOT_QUALIFIED_STAGE_KEYS},
}

EVENT_NAME_BY_BUCKET = {
    QUALIFIED_BUCKET: QUALIFIED_EVENT_NAME,
    CONVERTED_BUCKET: CONVERTED_EVENT_NAME,
    LOST_BUCKET: LOST_EVENT_NAME,
    NOT_QUALIFIED_BUCKET: NOT_QUALIFIED_EVENT_NAME,
}

DEFAULT_EVENT_MAPPING = [
    {"stage_key": "new_unread", "event_name": "Lead", "enabled": True, "bucket": None},
    {
        "stage_key": "pre_qualified",
        "event_name": QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": QUALIFIED_BUCKET,
    },
    {
        "stage_key": "interview_scheduled",
        "event_name": QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": QUALIFIED_BUCKET,
    },
    {
        "stage_key": "application_submitted",
        "event_name": QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": QUALIFIED_BUCKET,
    },
    {
        "stage_key": "under_review",
        "event_name": QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": QUALIFIED_BUCKET,
    },
    {
        "stage_key": "approved",
        "event_name": QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": QUALIFIED_BUCKET,
    },
    {
        "stage_key": "ready_to_match",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "matched",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "medical_clearance_passed",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "legal_clearance_passed",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "transfer_cycle",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "second_hcg_confirmed",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "heartbeat_confirmed",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "ob_care_established",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "anatomy_scanned",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {
        "stage_key": "delivered",
        "event_name": CONVERTED_EVENT_NAME,
        "enabled": True,
        "bucket": CONVERTED_BUCKET,
    },
    {"stage_key": "lost", "event_name": LOST_EVENT_NAME, "enabled": True, "bucket": LOST_BUCKET},
    {
        "stage_key": "disqualified",
        "event_name": NOT_QUALIFIED_EVENT_NAME,
        "enabled": True,
        "bucket": NOT_QUALIFIED_BUCKET,
    },
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_webhook_secret() -> str:
    """Generate a shared secret for Zapier webhooks."""
    return secrets.token_urlsafe(32)


def _event_name_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _normalize_bucket(value: str | None) -> str | None:
    if not value:
        return None
    key = _event_name_key(value)
    if key in {QUALIFIED_BUCKET, "qualifiedlead", "prequalifiedlead", "qualifiedconverted"}:
        return QUALIFIED_BUCKET
    if key in {CONVERTED_BUCKET, "convertedlead"}:
        return CONVERTED_BUCKET
    if key in {LOST_BUCKET, "lostlead"}:
        return LOST_BUCKET
    if key in {
        "notqualified",
        "notqualifiedlead",
        "notqualifiedlost",
        "disqualified",
        NOT_QUALIFIED_BUCKET,
    }:
        return NOT_QUALIFIED_BUCKET
    return None


def event_name_for_bucket(bucket: str | None) -> str | None:
    if not bucket:
        return None
    return EVENT_NAME_BY_BUCKET.get(bucket)


def _resolve_bucket_from_mapping_item(stage_key: str, item: dict) -> str | None:
    if not bool(item.get("enabled", True)):
        return None
    configured_bucket = _normalize_bucket(str(item.get("bucket") or "").strip())
    if configured_bucket:
        return configured_bucket
    event_name = str(item.get("event_name") or "").strip()
    event_bucket = _normalize_bucket(event_name)
    if event_bucket:
        return event_bucket
    return DEFAULT_BUCKET_BY_STAGE_KEY.get(stage_key)


def resolve_meta_stage_bucket(stage_key: str | None, mapping: list[dict] | None = None) -> str | None:
    """Return a canonical funnel bucket for Meta CAPI-style webhook events."""
    normalized = canonicalize_stage_key(stage_key)
    if not normalized:
        return None

    if mapping:
        for item in mapping:
            if not isinstance(item, dict):
                continue
            mapped_stage = canonicalize_stage_key(str(item.get("stage_key") or "").strip())
            if mapped_stage != normalized:
                continue
            return _resolve_bucket_from_mapping_item(normalized, item)

    return DEFAULT_BUCKET_BY_STAGE_KEY.get(normalized)


def _normalize_event_name(stage_key: str, event_name: str) -> str:
    key = _event_name_key(event_name)
    if stage_key in QUALIFIED_STAGE_KEYS and key in {
        "qualified",
        "qualifiedlead",
        "prequalifiedlead",
        "qualifiedconverted",
    }:
        return QUALIFIED_EVENT_NAME
    if stage_key in CONVERTED_STAGE_KEYS and key in {
        "converted",
        "convertedlead",
    }:
        return CONVERTED_EVENT_NAME
    if stage_key in LOST_STAGE_KEYS and key in {"lost", "lostlead"}:
        return LOST_EVENT_NAME
    if stage_key in NOT_QUALIFIED_STAGE_KEYS and key in {
        "notqualified",
        "notqualifiedlead",
        "notqualifiedlost",
        "disqualified",
    }:
        return NOT_QUALIFIED_EVENT_NAME
    return event_name


def encrypt_secret(secret: str) -> str:
    """Encrypt a secret for storage."""
    return oauth_service.encrypt_token(secret)


def decrypt_webhook_secret(encrypted: str | None) -> str:
    """Decrypt the stored webhook secret."""
    if not encrypted:
        return ""
    return oauth_service.decrypt_token(encrypted)


def get_settings(db: Session, organization_id: uuid.UUID) -> ZapierWebhookSettings | None:
    return (
        db.query(ZapierWebhookSettings)
        .filter(ZapierWebhookSettings.organization_id == organization_id)
        .first()
    )


def list_inbound_webhooks(db: Session, organization_id: uuid.UUID) -> list[ZapierInboundWebhook]:
    return list(
        db.query(ZapierInboundWebhook)
        .filter(ZapierInboundWebhook.organization_id == organization_id)
        .order_by(ZapierInboundWebhook.created_at.asc())
        .all()
    )


def get_inbound_webhook_by_id(db: Session, webhook_id: str) -> ZapierInboundWebhook | None:
    return (
        db.query(ZapierInboundWebhook).filter(ZapierInboundWebhook.webhook_id == webhook_id).first()
    )


def get_primary_inbound_webhook(
    db: Session, organization_id: uuid.UUID
) -> ZapierInboundWebhook | None:
    return (
        db.query(ZapierInboundWebhook)
        .filter(ZapierInboundWebhook.organization_id == organization_id)
        .order_by(ZapierInboundWebhook.created_at.asc())
        .first()
    )


def get_or_create_settings(
    db: Session,
    organization_id: uuid.UUID,
) -> ZapierWebhookSettings:
    settings_row = get_settings(db, organization_id)
    if not settings_row:
        webhook_id = str(uuid.uuid4())
        secret = _generate_webhook_secret()
        settings_row = ZapierWebhookSettings(
            organization_id=organization_id,
            webhook_id=webhook_id,
            webhook_secret_encrypted=encrypt_secret(secret),
            is_active=True,
            outbound_enabled=False,
            outbound_send_hashed_pii=False,
            outbound_event_mapping=DEFAULT_EVENT_MAPPING,
        )
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)

    _ensure_primary_inbound_webhook(db, settings_row)
    return settings_row


def _default_inbound_label(index: int) -> str:
    return f"Zapier Webhook {index}"


def _ensure_primary_inbound_webhook(
    db: Session, settings_row: ZapierWebhookSettings
) -> ZapierInboundWebhook:
    inbound = get_primary_inbound_webhook(db, settings_row.organization_id)
    if inbound:
        return inbound

    secret = decrypt_webhook_secret(settings_row.webhook_secret_encrypted)
    if not secret:
        secret = _generate_webhook_secret()
        settings_row.webhook_secret_encrypted = encrypt_secret(secret)

    if not settings_row.webhook_id:
        settings_row.webhook_id = str(uuid.uuid4())

    inbound = ZapierInboundWebhook(
        organization_id=settings_row.organization_id,
        webhook_id=settings_row.webhook_id,
        webhook_secret_encrypted=settings_row.webhook_secret_encrypted,
        is_active=settings_row.is_active,
        label="Primary",
    )
    settings_row.updated_at = _now_utc()
    db.add(inbound)
    db.commit()
    db.refresh(inbound)
    return inbound


def create_inbound_webhook(
    db: Session,
    organization_id: uuid.UUID,
    *,
    label: str | None = None,
) -> tuple[ZapierInboundWebhook, str]:
    count = (
        db.query(ZapierInboundWebhook)
        .filter(ZapierInboundWebhook.organization_id == organization_id)
        .count()
    )
    secret = _generate_webhook_secret()
    inbound = ZapierInboundWebhook(
        organization_id=organization_id,
        webhook_id=str(uuid.uuid4()),
        webhook_secret_encrypted=encrypt_secret(secret),
        is_active=True,
        label=label or _default_inbound_label(count + 1),
    )
    db.add(inbound)
    db.commit()
    db.refresh(inbound)
    return inbound, secret


def delete_inbound_webhook(db: Session, organization_id: uuid.UUID, webhook_id: str) -> None:
    inbound = get_inbound_webhook_by_id(db, webhook_id)
    if not inbound or inbound.organization_id != organization_id:
        raise LookupError("Webhook not found.")

    count = (
        db.query(ZapierInboundWebhook)
        .filter(ZapierInboundWebhook.organization_id == organization_id)
        .count()
    )
    if count <= 1:
        raise ValueError("At least one inbound webhook is required.")

    db.delete(inbound)
    db.commit()

    settings_row = get_settings(db, organization_id)
    if settings_row and settings_row.webhook_id == webhook_id:
        primary = get_primary_inbound_webhook(db, organization_id)
        if primary:
            settings_row.webhook_id = primary.webhook_id
            settings_row.webhook_secret_encrypted = primary.webhook_secret_encrypted
            settings_row.is_active = primary.is_active
            settings_row.updated_at = _now_utc()
            db.commit()


def rotate_inbound_webhook_secret(
    db: Session,
    organization_id: uuid.UUID,
    webhook_id: str,
) -> tuple[ZapierInboundWebhook, str]:
    inbound = (
        db.query(ZapierInboundWebhook)
        .filter(
            ZapierInboundWebhook.organization_id == organization_id,
            ZapierInboundWebhook.webhook_id == webhook_id,
        )
        .first()
    )
    if not inbound:
        raise ValueError("Webhook not found")
    secret = _generate_webhook_secret()
    inbound.webhook_secret_encrypted = encrypt_secret(secret)
    inbound.updated_at = _now_utc()
    db.commit()
    db.refresh(inbound)
    return inbound, secret


def update_inbound_webhook(
    db: Session,
    organization_id: uuid.UUID,
    webhook_id: str,
    *,
    label: str | None = None,
    is_active: bool | None = None,
) -> ZapierInboundWebhook:
    inbound = (
        db.query(ZapierInboundWebhook)
        .filter(
            ZapierInboundWebhook.organization_id == organization_id,
            ZapierInboundWebhook.webhook_id == webhook_id,
        )
        .first()
    )
    if not inbound:
        raise ValueError("Webhook not found")
    if label is not None:
        inbound.label = label.strip() or None
    if is_active is not None:
        inbound.is_active = is_active
    inbound.updated_at = _now_utc()
    db.commit()
    db.refresh(inbound)
    return inbound


def normalize_event_mapping(mapping: list[dict] | None) -> list[dict]:
    if not mapping:
        return [dict(item) for item in DEFAULT_EVENT_MAPPING]
    normalized: list[dict] = []
    index_by_stage_key: dict[str, int] = {}
    for item in mapping:
        if not isinstance(item, dict):
            continue
        stage_ref = str(item.get("stage_key") or item.get("stage_slug") or "").strip()
        stage_key = canonicalize_stage_key(stage_ref)
        event_name = str(item.get("event_name") or "").strip()
        bucket = _normalize_bucket(str(item.get("bucket") or "").strip())
        enabled = bool(item.get("enabled", True))
        if not stage_key:
            continue
        if not bucket:
            bucket = _normalize_bucket(event_name)
        if not bucket:
            bucket = DEFAULT_BUCKET_BY_STAGE_KEY.get(stage_key)

        normalized_event_name = event_name_for_bucket(bucket)
        if not normalized_event_name:
            normalized_event_name = _normalize_event_name(stage_key, event_name)
        if not normalized_event_name:
            continue

        normalized_item = {
            "stage_key": stage_key,
            "event_name": normalized_event_name,
            "enabled": enabled,
            "bucket": bucket,
        }
        existing_index = index_by_stage_key.get(stage_key)
        if existing_index is None:
            index_by_stage_key[stage_key] = len(normalized)
            normalized.append(normalized_item)
        else:
            normalized[existing_index] = normalized_item

    for default_item in DEFAULT_EVENT_MAPPING:
        stage_key = default_item["stage_key"]
        if stage_key in index_by_stage_key:
            continue
        index_by_stage_key[stage_key] = len(normalized)
        normalized.append(dict(default_item))

    return normalized or [dict(item) for item in DEFAULT_EVENT_MAPPING]


def update_outbound_settings(
    db: Session,
    organization_id: uuid.UUID,
    *,
    outbound_webhook_url: str | None = None,
    outbound_webhook_secret: str | None = None,
    outbound_enabled: bool | None = None,
    send_hashed_pii: bool | None = None,
    event_mapping: list[dict] | None = None,
) -> ZapierWebhookSettings:
    settings_row = get_or_create_settings(db, organization_id)

    if outbound_webhook_url is not None:
        stripped = outbound_webhook_url.strip()
        settings_row.outbound_webhook_url = (
            validate_outbound_webhook_url(stripped) if stripped else None
        )
    if outbound_webhook_secret is not None:
        settings_row.outbound_webhook_secret_encrypted = encrypt_secret(outbound_webhook_secret)
    if outbound_enabled is not None:
        settings_row.outbound_enabled = outbound_enabled
    if send_hashed_pii is not None:
        settings_row.outbound_send_hashed_pii = send_hashed_pii
    if event_mapping is not None:
        settings_row.outbound_event_mapping = normalize_event_mapping(event_mapping)

    settings_row.updated_at = _now_utc()
    db.commit()
    db.refresh(settings_row)
    return settings_row


def rotate_webhook_secret(
    db: Session,
    organization_id: uuid.UUID,
) -> tuple[ZapierWebhookSettings, str]:
    settings_row = get_or_create_settings(db, organization_id)
    inbound = get_primary_inbound_webhook(db, organization_id)
    if not inbound:
        inbound = _ensure_primary_inbound_webhook(db, settings_row)
    inbound, secret = rotate_inbound_webhook_secret(db, organization_id, inbound.webhook_id)

    # Keep legacy settings row in sync with primary inbound webhook.
    if (
        settings_row.webhook_id != inbound.webhook_id
        or settings_row.webhook_secret_encrypted != inbound.webhook_secret_encrypted
        or settings_row.is_active != inbound.is_active
    ):
        settings_row.webhook_id = inbound.webhook_id
        settings_row.webhook_secret_encrypted = inbound.webhook_secret_encrypted
        settings_row.is_active = inbound.is_active
        settings_row.updated_at = _now_utc()
        db.commit()
        db.refresh(settings_row)
    return settings_row, secret


def get_webhook_url(webhook_id: str) -> str:
    base_url = settings.API_BASE_URL or settings.FRONTEND_URL or ""
    if not base_url:
        logger.warning("API_BASE_URL not configured; webhook URL unavailable")
        return ""
    return f"{base_url.rstrip('/')}/webhooks/zapier/{webhook_id}"
