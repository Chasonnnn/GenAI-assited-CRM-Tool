"""Encryption utilities for sensitive data storage."""

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.utils.normalization import normalize_email, normalize_phone


_fernet: Fernet | None = None
_data_fernet: Fernet | None = None
_ENCRYPTED_PREFIX = "enc:"


def get_fernet() -> Fernet:
    """Get or create Fernet instance for encryption/decryption."""
    global _fernet
    if _fernet is None:
        if not settings.META_ENCRYPTION_KEY:
            raise RuntimeError(
                "META_ENCRYPTION_KEY not configured. "
                'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        _fernet = Fernet(settings.META_ENCRYPTION_KEY.encode())
    return _fernet


def get_data_fernet() -> Fernet:
    """Get Fernet instance for field-level PII encryption."""
    global _data_fernet
    if _data_fernet is None:
        if not settings.DATA_ENCRYPTION_KEY:
            raise RuntimeError(
                "DATA_ENCRYPTION_KEY not configured. "
                'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        _data_fernet = Fernet(settings.DATA_ENCRYPTION_KEY.encode())
    return _data_fernet


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    if not token:
        return ""
    return get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token."""
    if not encrypted:
        return ""
    try:
        return get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid or corrupted encrypted token")


def encrypt_value(value: str) -> str:
    """Encrypt a string value for PII at rest."""
    if value is None:
        return value
    if value == "":
        return ""
    if value.startswith(_ENCRYPTED_PREFIX):
        return value
    encrypted = get_data_fernet().encrypt(value.encode()).decode()
    return f"{_ENCRYPTED_PREFIX}{encrypted}"


def decrypt_value(value: str) -> str:
    """Decrypt a stored PII value."""
    if value is None:
        return value
    if value == "":
        return ""
    if not value.startswith(_ENCRYPTED_PREFIX):
        raise ValueError("Encrypted data is missing prefix")
    token = value[len(_ENCRYPTED_PREFIX) :]
    try:
        return get_data_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid or corrupted encrypted data")


def hash_pii(value: str, purpose: str = "pii") -> str:
    """Hash PII deterministically for lookups and uniqueness."""
    if not settings.PII_HASH_KEY:
        raise RuntimeError("PII_HASH_KEY not configured.")
    if value is None:
        return ""
    data = f"{purpose}:{value}".encode()
    return hmac.new(settings.PII_HASH_KEY.encode(), data, hashlib.sha256).hexdigest()


def hash_email(email: str) -> str:
    """Normalize and hash an email address."""
    normalized = normalize_email(email) or ""
    return hash_pii(normalized, purpose="email")


def hash_phone(phone: str | None) -> str:
    """Normalize and hash a phone number."""
    if not phone:
        return ""
    try:
        normalized = normalize_phone(phone) or ""
    except ValueError:
        normalized = phone.strip()
    return hash_pii(normalized, purpose="phone")


def is_encryption_configured() -> bool:
    """Check if encryption is properly configured."""
    return bool(settings.META_ENCRYPTION_KEY)


def is_pii_encryption_configured() -> bool:
    """Check if PII encryption is properly configured."""
    return bool(settings.DATA_ENCRYPTION_KEY and settings.PII_HASH_KEY)
