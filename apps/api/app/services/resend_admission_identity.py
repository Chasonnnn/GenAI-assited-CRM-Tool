"""Secret-safe admission identities for Resend provider accounts."""

from __future__ import annotations

import hashlib
import re


_ADMISSION_GROUP_NAMESPACE = b"resend-rate-limit-group:v1\0"
_GROUP_TOKEN_MIN_LENGTH = 32
_GROUP_TOKEN_MAX_LENGTH = 256
_CANONICAL_SHA256 = re.compile(r"[0-9a-f]{64}")


def credential_fingerprint(api_key: str) -> str:
    """Return the stable fingerprint used to admit one exact credential."""
    if not api_key or api_key != api_key.strip():
        raise ValueError("api_key must be a non-empty, trimmed value")
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def admission_group_fingerprint(group_token: str) -> str:
    """Return a domain-separated fingerprint for a write-only team token."""
    if group_token != group_token.strip():
        raise ValueError("group_token must be trimmed")
    if not _GROUP_TOKEN_MIN_LENGTH <= len(group_token) <= _GROUP_TOKEN_MAX_LENGTH:
        raise ValueError("group_token must be between 32 and 256 characters")
    return hashlib.sha256(_ADMISSION_GROUP_NAMESPACE + group_token.encode("utf-8")).hexdigest()


def resolve_resend_admission_identity(
    *,
    api_key: str,
    group_fingerprint: str | None,
) -> str:
    """Resolve the shared-team identity, falling back to the exact credential."""
    exact_credential = credential_fingerprint(api_key)
    if group_fingerprint is None:
        return f"credential:{exact_credential}"
    if _CANONICAL_SHA256.fullmatch(group_fingerprint) is None:
        raise ValueError("group_fingerprint must be a canonical SHA-256 digest")
    return f"team:{group_fingerprint}"
