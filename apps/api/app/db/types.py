"""Custom SQLAlchemy types for encrypted fields."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.types import TypeDecorator, Text

from app.core.encryption import decrypt_value, encrypt_value


class EncryptedString(TypeDecorator):
    """Encrypt/decrypt string values transparently."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        if value == "":
            return ""
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return value
        return decrypt_value(value)


class EncryptedText(EncryptedString):
    """Alias for encrypted text fields."""


class EncryptedDate(TypeDecorator):
    """Encrypt/decrypt date values as ISO strings."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            value = value.isoformat()
        if not isinstance(value, str):
            value = str(value)
        if value == "":
            return ""
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return None
        decrypted = decrypt_value(value)
        if not decrypted:
            return None
        try:
            return date.fromisoformat(decrypted)
        except ValueError:
            return None
