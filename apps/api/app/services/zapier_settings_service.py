"""Zapier webhook settings service."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ZapierWebhookSettings
from app.services import oauth_service

logger = logging.getLogger(__name__)

DEFAULT_EVENT_MAPPING = [
    {"stage_slug": "new_unread", "event_name": "Lead", "enabled": True},
    {"stage_slug": "qualified", "event_name": "QualifiedLead", "enabled": True},
    {"stage_slug": "matched", "event_name": "ConvertedLead", "enabled": True},
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_webhook_secret() -> str:
    """Generate a shared secret for Zapier webhooks."""
    return secrets.token_urlsafe(32)


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


def get_settings_by_webhook_id(db: Session, webhook_id: str) -> ZapierWebhookSettings | None:
    return (
        db.query(ZapierWebhookSettings)
        .filter(ZapierWebhookSettings.webhook_id == webhook_id)
        .first()
    )


def get_or_create_settings(
    db: Session,
    organization_id: uuid.UUID,
) -> ZapierWebhookSettings:
    settings_row = get_settings(db, organization_id)
    if settings_row:
        return settings_row

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
    return settings_row


def normalize_event_mapping(mapping: list[dict] | None) -> list[dict]:
    if not mapping:
        return DEFAULT_EVENT_MAPPING
    normalized: list[dict] = []
    for item in mapping:
        if not isinstance(item, dict):
            continue
        stage_slug = str(item.get("stage_slug") or "").strip()
        event_name = str(item.get("event_name") or "").strip()
        enabled = bool(item.get("enabled", True))
        if not stage_slug or not event_name:
            continue
        normalized.append(
            {
                "stage_slug": stage_slug,
                "event_name": event_name,
                "enabled": enabled,
            }
        )
    return normalized or DEFAULT_EVENT_MAPPING


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
        settings_row.outbound_webhook_url = outbound_webhook_url.strip() or None
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
    secret = _generate_webhook_secret()
    settings_row.webhook_secret_encrypted = encrypt_secret(secret)
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
