"""Settings credentials must be SecretStr so they never leak in plaintext.

Plain ``str`` secret fields surface in ``repr(settings)``, ``model_dump()`` and
``model_dump_json()`` — which means they can land in tracebacks, structured logs
and Sentry events. Typing them as ``pydantic.SecretStr`` masks the value at the
type level while keeping it retrievable via ``.get_secret_value()``.
"""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings

# Every credential/secret that must be masked. Pure identifiers (client ids,
# integration keys, access-key ids) are intentionally excluded — they are not
# secrets.
SECRET_FIELDS = [
    "VERSION_ENCRYPTION_KEY",
    "JWT_SECRET",
    "JWT_SECRET_PREVIOUS",
    "GOOGLE_CLIENT_SECRET",
    "PLATFORM_RESEND_API_KEY",
    "PLATFORM_RESEND_WEBHOOK_SECRET",
    "PLATFORM_RESEND_ADMISSION_GROUP_TOKEN",
    "AUDIT_HMAC_SECRET",
    "DEV_SECRET",
    "META_VERIFY_TOKEN",
    "META_APP_SECRET",
    "META_ENCRYPTION_KEY",
    "INTERNAL_SECRET",
    "ZOOM_CLIENT_SECRET",
    "ZOOM_WEBHOOK_SECRET",
    "FERNET_KEY",
    "DATA_ENCRYPTION_KEY",
    "PII_HASH_KEY",
    "GMAIL_PUSH_WEBHOOK_TOKEN",
    "WIF_OIDC_PRIVATE_KEY",
    "SENTRY_DSN",
    "FORMS_SHARED_CHALLENGE_SECRET",
    "AWS_SECRET_ACCESS_KEY",
    "DUO_CLIENT_SECRET",
    "DUO_ADMIN_SECRET_KEY",
]

_SENTINEL = "sup3r-secret-sentinel-DO-NOT-LEAK-9f8e7d6c"


# The DB URL embeds a password, so it must be masked too. The sentinel is placed
# in the password slot so the repr/model_dump leak tests below also cover it.
_DB_URL_WITH_SECRET = f"postgresql+psycopg://u:{_SENTINEL}@localhost:5432/db"


def _settings_with_sentinels() -> Settings:
    return Settings(
        ENV="test",
        DATABASE_URL=_DB_URL_WITH_SECRET,
        **{field: _SENTINEL for field in SECRET_FIELDS},
    )


def test_database_url_is_masked_secretstr():
    """DATABASE_URL carries the DB password; it must be a SecretStr and never
    surface in repr()/model_dump()."""
    s = _settings_with_sentinels()
    assert isinstance(s.DATABASE_URL, SecretStr)
    assert s.DATABASE_URL.get_secret_value() == _DB_URL_WITH_SECRET
    assert _SENTINEL not in repr(s)
    assert _SENTINEL not in str(s.model_dump())
    assert _SENTINEL not in s.model_dump_json()


def test_secret_fields_are_secretstr():
    s = _settings_with_sentinels()
    for field in SECRET_FIELDS:
        assert isinstance(getattr(s, field), SecretStr), f"{field} must be typed as SecretStr"


def test_secret_values_still_retrievable():
    s = _settings_with_sentinels()
    for field in SECRET_FIELDS:
        assert getattr(s, field).get_secret_value() == _SENTINEL, field


def test_repr_does_not_leak_secrets():
    s = _settings_with_sentinels()
    assert _SENTINEL not in repr(s)


def test_model_dump_does_not_leak_secrets():
    s = _settings_with_sentinels()
    assert _SENTINEL not in str(s.model_dump())
    assert _SENTINEL not in s.model_dump_json()


def test_jwt_secrets_property_returns_plaintext():
    """jwt_secrets feeds the JWT decoder, so it must yield plaintext strings."""
    s = Settings(
        ENV="test",
        DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/db",
        JWT_SECRET=_SENTINEL,
        JWT_SECRET_PREVIOUS="previous-secret-value",
    )
    secrets = s.jwt_secrets
    assert all(isinstance(item, str) for item in secrets)
    assert secrets[0] == _SENTINEL
    assert "previous-secret-value" in secrets


@pytest.mark.parametrize(
    "token",
    ["x" * 31, "x" * 257],
    ids=["too-short", "too-long"],
)
def test_platform_resend_admission_group_token_requires_32_to_256_characters(token):
    with pytest.raises(ValidationError, match=r"32.*256"):
        Settings(
            _env_file=None,
            ENV="test",
            DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/db",
            PLATFORM_RESEND_ADMISSION_GROUP_TOKEN=token,
        )
