"""Unsubscribe token and URL helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional
from uuid import UUID

from app.core.config import settings
from app.utils.normalization import normalize_email


TOKEN_VERSION = 1


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _get_signing_secrets() -> list[str]:
    return [s for s in settings.jwt_secrets if s]


def generate_unsubscribe_token(*, org_id: UUID, email: str) -> str:
    """Generate a signed unsubscribe token."""
    email_norm = normalize_email(email) or ""
    now = int(time.time())
    exp = now + settings.UNSUBSCRIBE_TOKEN_TTL_DAYS * 86400

    payload = {
        "v": TOKEN_VERSION,
        "org_id": str(org_id),
        "email": email_norm,
        "iat": now,
        "exp": exp,
    }
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    secrets = _get_signing_secrets()
    if not secrets:
        raise ValueError("JWT_SECRET must be set to generate unsubscribe tokens")

    signature = _sign(payload_b64, secrets[0])
    return f"{payload_b64}.{signature}"


def parse_unsubscribe_token(token: str) -> Optional[tuple[UUID, str]]:
    """Parse and verify an unsubscribe token. Returns (org_id, email) or None."""
    if not token:
        return None

    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    secrets = _get_signing_secrets()
    if not secrets:
        return None

    valid = False
    for secret in secrets:
        expected = _sign(payload_b64, secret)
        if hmac.compare_digest(expected, signature):
            valid = True
            break
    if not valid:
        return None

    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None

    if payload.get("v") != TOKEN_VERSION:
        return None

    exp = payload.get("exp")
    if isinstance(exp, int) and exp > 0 and int(time.time()) > exp:
        return None

    try:
        org_id = UUID(str(payload.get("org_id")))
    except Exception:
        return None

    email = normalize_email(payload.get("email")) or ""
    if not email:
        return None

    return org_id, email


def build_unsubscribe_url(*, org_id: UUID, email: str, base_url: str | None = None) -> str:
    """Build a full unsubscribe URL for use in email bodies.

    `base_url` is typically the organization's portal base URL
    (e.g., https://ewi.surrogacyforce.com).
    """
    token = generate_unsubscribe_token(org_id=org_id, email=email)
    base = (base_url or settings.FRONTEND_URL or settings.API_BASE_URL or "").strip()
    if not base:
        return f"/email/unsubscribe/{token}"
    return f"{base.rstrip('/')}/email/unsubscribe/{token}"


def build_list_unsubscribe_url(*, org_id: UUID, email: str, base_url: str | None = None) -> str:
    """Build the List-Unsubscribe URL used for one-click unsubscribe."""
    url = build_unsubscribe_url(org_id=org_id, email=email, base_url=base_url)
    return f"{url.rstrip('/')}/one-click"


def build_list_unsubscribe_headers(
    *, org_id: UUID, email: str, base_url: str | None = None
) -> dict[str, str]:
    """Build List-Unsubscribe headers for one-click unsubscribe."""
    url = build_list_unsubscribe_url(org_id=org_id, email=email, base_url=base_url)
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
