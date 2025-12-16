"""AI Settings service.

Manages org-level AI configuration with BYOK key storage.
"""
import uuid
from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AISettings
from app.services.ai_provider import AIProvider, get_provider


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


def get_ai_settings(db: Session, organization_id: uuid.UUID) -> AISettings | None:
    """Get AI settings for an organization."""
    return db.query(AISettings).filter(
        AISettings.organization_id == organization_id
    ).first()


def get_or_create_ai_settings(db: Session, organization_id: uuid.UUID) -> AISettings:
    """Get or create AI settings for an organization."""
    ai_settings = get_ai_settings(db, organization_id)
    if ai_settings:
        return ai_settings
    
    # Create default settings
    ai_settings = AISettings(
        organization_id=organization_id,
        is_enabled=False,
        provider="openai",
        model="gpt-4o-mini",
    )
    db.add(ai_settings)
    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def update_ai_settings(
    db: Session,
    organization_id: uuid.UUID,
    *,
    is_enabled: bool | None = None,
    provider: str | None = None,
    api_key: str | None = None,  # Plain text, will be encrypted
    model: str | None = None,
    context_notes_limit: int | None = None,
    conversation_history_limit: int | None = None,
    anonymize_pii: bool | None = None,
) -> AISettings:
    """Update AI settings for an organization."""
    ai_settings = get_or_create_ai_settings(db, organization_id)
    
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
    
    ai_settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def accept_consent(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AISettings:
    """Record that a user accepted the AI data processing consent."""
    ai_settings = get_or_create_ai_settings(db, organization_id)
    ai_settings.consent_accepted_at = datetime.utcnow()
    ai_settings.consent_accepted_by = user_id
    ai_settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ai_settings)
    return ai_settings


def is_consent_required(ai_settings: AISettings) -> bool:
    """Check if consent is required (AI enabled but no consent recorded)."""
    return ai_settings.is_enabled and ai_settings.consent_accepted_at is None


def get_ai_provider_for_org(db: Session, organization_id: uuid.UUID) -> AIProvider | None:
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
