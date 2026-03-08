"""Settings service for direct Meta CRM dataset outbound delivery."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import MetaCrmDatasetSettings
from app.services import oauth_service, zapier_settings_service

logger = logging.getLogger(__name__)

DEFAULT_CRM_NAME = "Surrogacy Force CRM"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def encrypt_access_token(access_token: str) -> str:
    return oauth_service.encrypt_token(access_token)


def decrypt_access_token(encrypted: str | None) -> str:
    if not encrypted:
        return ""
    return oauth_service.decrypt_token(encrypted)


def encrypt_secret(access_token: str) -> str:
    """Compatibility alias for older callers/tests."""
    return encrypt_access_token(access_token)


def default_crm_name() -> str:
    return DEFAULT_CRM_NAME


def normalize_event_mapping(mapping: list[dict] | None) -> list[dict]:
    return zapier_settings_service.normalize_event_mapping(mapping)


def get_settings(db: Session, organization_id: uuid.UUID) -> MetaCrmDatasetSettings | None:
    return (
        db.query(MetaCrmDatasetSettings)
        .filter(MetaCrmDatasetSettings.organization_id == organization_id)
        .first()
    )


def get_settings_by_id(
    db: Session, settings_id: uuid.UUID | str
) -> MetaCrmDatasetSettings | None:
    try:
        parsed = settings_id if isinstance(settings_id, uuid.UUID) else uuid.UUID(str(settings_id))
    except (TypeError, ValueError):
        return None
    return db.query(MetaCrmDatasetSettings).filter(MetaCrmDatasetSettings.id == parsed).first()


def get_or_create_settings(db: Session, organization_id: uuid.UUID) -> MetaCrmDatasetSettings:
    settings_row = get_settings(db, organization_id)
    if settings_row:
        if not settings_row.crm_name:
            settings_row.crm_name = DEFAULT_CRM_NAME
        if not settings_row.event_mapping:
            settings_row.event_mapping = normalize_event_mapping(None)
        return settings_row

    settings_row = MetaCrmDatasetSettings(
        organization_id=organization_id,
        crm_name=DEFAULT_CRM_NAME,
        enabled=False,
        send_hashed_pii=False,
        event_mapping=normalize_event_mapping(None),
    )
    db.add(settings_row)
    db.commit()
    db.refresh(settings_row)
    return settings_row


def update_settings(
    db: Session,
    organization_id: uuid.UUID,
    *,
    dataset_id: str | None = None,
    access_token: str | None = None,
    enabled: bool | None = None,
    crm_name: str | None = None,
    send_hashed_pii: bool | None = None,
    event_mapping: list[dict] | None = None,
    test_event_code: str | None = None,
) -> MetaCrmDatasetSettings:
    settings_row = get_or_create_settings(db, organization_id)

    if dataset_id is not None:
        stripped = dataset_id.strip()
        settings_row.dataset_id = stripped or None
    if access_token is not None:
        stripped = access_token.strip()
        settings_row.access_token_encrypted = (
            encrypt_access_token(stripped) if stripped else None
        )
    if enabled is not None:
        settings_row.enabled = enabled
    if crm_name is not None:
        settings_row.crm_name = crm_name.strip() or DEFAULT_CRM_NAME
    if send_hashed_pii is not None:
        settings_row.send_hashed_pii = send_hashed_pii
    if event_mapping is not None:
        settings_row.event_mapping = normalize_event_mapping(event_mapping)
    if test_event_code is not None:
        stripped = test_event_code.strip()
        settings_row.test_event_code = stripped or None

    settings_row.updated_at = _now_utc()
    db.commit()
    db.refresh(settings_row)
    return settings_row
