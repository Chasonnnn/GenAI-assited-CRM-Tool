"""AI Settings service.

Manages org-level AI configuration with BYOK key storage.
v2: With version control (API keys are redacted in snapshots).
"""

import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AISettings
from app.services.ai_provider import AIProvider, get_provider
from app.services import version_service


ENTITY_TYPE = "ai_settings"


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    key = settings.FERNET_KEY
    if not key:
        raise ValueError("FERNET_KEY not configured")
    return Fernet(key.encode())


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    fernet = _get_fernet()
    return fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted_key.encode()).decode()


def _ai_settings_payload(ai_settings: AISettings) -> dict:
    """
    Extract versionable payload from AI settings.

    NOTE: API key is stored as [REDACTED] - never store secrets in versions.
    """
    return {
        "is_enabled": ai_settings.is_enabled,
        "provider": ai_settings.provider,
        "api_key": "[REDACTED]" if ai_settings.api_key_encrypted else None,
        "model": ai_settings.model,
        "context_notes_limit": ai_settings.context_notes_limit,
        "conversation_history_limit": ai_settings.conversation_history_limit,
        "anonymize_pii": ai_settings.anonymize_pii,
    }


def get_ai_settings(db: Session, organization_id: uuid.UUID) -> AISettings | None:
    """Get AI settings for an organization."""
    return (
        db.query(AISettings)
        .filter(AISettings.organization_id == organization_id)
        .first()
    )


def get_or_create_ai_settings(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> AISettings:
    """Get or create AI settings for an organization with initial version."""
    ai_settings = get_ai_settings(db, organization_id)
    if ai_settings:
        return ai_settings

    # Create default settings
    ai_settings = AISettings(
        organization_id=organization_id,
        is_enabled=False,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
    )
    db.add(ai_settings)
    db.flush()

    # Create initial version snapshot
    version_service.create_version(
        db=db,
        org_id=organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=ai_settings.id,
        payload=_ai_settings_payload(ai_settings),
        created_by_user_id=user_id or organization_id,  # Fallback for system
        comment="Initial version",
    )

    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def update_ai_settings(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    is_enabled: bool | None = None,
    provider: str | None = None,
    api_key: str | None = None,  # Plain text, will be encrypted
    model: str | None = None,
    context_notes_limit: int | None = None,
    conversation_history_limit: int | None = None,
    anonymize_pii: bool | None = None,
    expected_version: int | None = None,
    comment: str | None = None,
) -> AISettings:
    """Update AI settings with version control."""
    ai_settings = get_or_create_ai_settings(db, organization_id, user_id)

    # Optimistic locking
    if expected_version is not None:
        version_service.check_version(ai_settings.current_version, expected_version)

    if is_enabled is not None:
        ai_settings.is_enabled = is_enabled
    if provider is not None:
        ai_settings.provider = provider
    if api_key is not None:
        ai_settings.api_key_encrypted = encrypt_api_key(api_key)
    if model is not None:
        ai_settings.model = model
    if context_notes_limit is not None:
        ai_settings.context_notes_limit = context_notes_limit
    if conversation_history_limit is not None:
        ai_settings.conversation_history_limit = conversation_history_limit
    if anonymize_pii is not None:
        ai_settings.anonymize_pii = anonymize_pii

    ai_settings.current_version += 1
    ai_settings.updated_at = datetime.now(timezone.utc)

    # Create version snapshot
    version_service.create_version(
        db=db,
        org_id=organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=ai_settings.id,
        payload=_ai_settings_payload(ai_settings),
        created_by_user_id=user_id,
        comment=comment or "Updated",
    )

    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def accept_consent(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AISettings:
    """Record that a user accepted the AI data processing consent."""
    ai_settings = get_or_create_ai_settings(db, organization_id, user_id)
    ai_settings.consent_accepted_at = datetime.now(timezone.utc)
    ai_settings.consent_accepted_by = user_id
    ai_settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def is_consent_required(ai_settings: AISettings) -> bool:
    """Check if consent is required (AI enabled but no consent recorded)."""
    return ai_settings.is_enabled and ai_settings.consent_accepted_at is None


def get_ai_provider_for_org(
    db: Session, organization_id: uuid.UUID
) -> AIProvider | None:
    """Get a configured AI provider for an organization.

    Returns None if AI is not enabled or not configured.
    """
    ai_settings = get_ai_settings(db, organization_id)

    if not ai_settings:
        return None
    if not ai_settings.is_enabled:
        return None
    if not ai_settings.api_key_encrypted:
        return None

    api_key = decrypt_api_key(ai_settings.api_key_encrypted)
    return get_provider(ai_settings.provider, api_key, ai_settings.model)


async def test_api_key(provider: str, api_key: str) -> bool:
    """Test if an API key is valid."""
    try:
        ai_provider = get_provider(provider, api_key)
        return await ai_provider.validate_key()
    except Exception:
        return False


def mask_api_key(api_key_encrypted: str | None) -> str | None:
    """Return masked version of API key for display.

    Shows first 4 and last 4 characters: sk-ab...yz
    """
    if not api_key_encrypted:
        return None

    try:
        decrypted = decrypt_api_key(api_key_encrypted)
        if len(decrypted) <= 8:
            return "****"
        return f"{decrypted[:4]}...{decrypted[-4:]}"
    except Exception:
        return "****"


# =============================================================================
# Version Control
# =============================================================================


def get_ai_settings_versions(
    db: Session,
    org_id: uuid.UUID,
    settings_id: uuid.UUID,
    limit: int = 50,
) -> list:
    """Get version history for AI settings."""
    return version_service.get_version_history(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=settings_id,
        limit=limit,
    )


def rollback_ai_settings(
    db: Session,
    ai_settings: AISettings,
    target_version: int,
    user_id: uuid.UUID,
) -> tuple[AISettings | None, str | None]:
    """
    Rollback AI settings to a previous version.

    NOTE: API key is NOT rolled back (always [REDACTED] in snapshots).
    """
    new_version, error = version_service.rollback_to_version(
        db=db,
        org_id=ai_settings.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=ai_settings.id,
        target_version=target_version,
        user_id=user_id,
    )

    if error:
        return None, error

    # Apply rolled-back payload (except API key)
    payload = version_service.decrypt_payload(new_version.payload_encrypted)
    ai_settings.is_enabled = payload.get("is_enabled", ai_settings.is_enabled)
    ai_settings.provider = payload.get("provider", ai_settings.provider)
    ai_settings.model = payload.get("model", ai_settings.model)
    ai_settings.context_notes_limit = payload.get(
        "context_notes_limit", ai_settings.context_notes_limit
    )
    ai_settings.conversation_history_limit = payload.get(
        "conversation_history_limit", ai_settings.conversation_history_limit
    )
    ai_settings.anonymize_pii = payload.get("anonymize_pii", ai_settings.anonymize_pii)
    # NOTE: api_key is NOT rolled back - it's always [REDACTED] in versions

    ai_settings.current_version = new_version.version
    ai_settings.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ai_settings)
    return ai_settings, None
