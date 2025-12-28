"""Encryption utilities for sensitive data storage."""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


_fernet: Fernet | None = None


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


def is_encryption_configured() -> bool:
    """Check if encryption is properly configured."""
    return bool(settings.META_ENCRYPTION_KEY)
