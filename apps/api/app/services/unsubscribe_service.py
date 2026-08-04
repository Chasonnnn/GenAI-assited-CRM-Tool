"""Unsubscribe token and URL helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UnsubscribeToken
from app.utils.normalization import normalize_email

LEGACY_TOKEN_VERSION = 1
OPAQUE_TOKEN_PREFIX = "u2_"


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


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_unsubscribe_token(db: Session, *, org_id: UUID, email: str) -> str:
    """Generate and persist a high-entropy token without storing its raw value."""
    email_norm = normalize_email(email) or ""
    if not email_norm:
        raise ValueError("A valid recipient email is required")

    token = f"{OPAQUE_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    now = datetime.now(UTC)
    db.add(
        UnsubscribeToken(
            organization_id=org_id,
            email=email_norm,
            token_hash=_token_hash(token),
            expires_at=now + timedelta(days=settings.UNSUBSCRIBE_TOKEN_TTL_DAYS),
        )
    )
    db.flush()
    return token


def _parse_opaque_token(db: Session, token: str) -> tuple[UUID, str] | None:
    record = (
        db.query(UnsubscribeToken).filter(UnsubscribeToken.token_hash == _token_hash(token)).first()
    )
    if record is None:
        return None

    now = datetime.now(UTC)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < now:
        return None

    # Consumption is an audit marker, not a one-shot invalidation. Mail clients
    # and providers may repeat GET/POST requests, and suppression is idempotent.
    if record.consumed_at is None:
        record.consumed_at = now
        db.flush()

    return record.organization_id, normalize_email(record.email) or record.email


def _parse_legacy_token(token: str) -> tuple[UUID, str] | None:
    """Verify an unexpired v1 signed token already present in delivered mail."""
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None

    valid = any(
        hmac.compare_digest(_sign(payload_b64, secret), signature)
        for secret in _get_signing_secrets()
    )
    if not valid:
        return None

    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None

    if payload.get("v") != LEGACY_TOKEN_VERSION:
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


def parse_unsubscribe_token(db: Session, token: str) -> tuple[UUID, str] | None:
    """Resolve an opaque token or verify a still-valid legacy v1 token."""
    if not token:
        return None
    if token.startswith(OPAQUE_TOKEN_PREFIX):
        return _parse_opaque_token(db, token)
    return _parse_legacy_token(token)


def build_unsubscribe_url(
    db: Session,
    *,
    org_id: UUID,
    email: str,
    base_url: str | None = None,
) -> str:
    """Build a full unsubscribe URL for use in email bodies."""
    token = generate_unsubscribe_token(db, org_id=org_id, email=email)
    base = (base_url or settings.FRONTEND_URL or settings.API_BASE_URL or "").strip()
    if not base:
        return f"/email/unsubscribe/{token}"
    return f"{base.rstrip('/')}/email/unsubscribe/{token}"


def build_list_unsubscribe_url(
    db: Session,
    *,
    org_id: UUID,
    email: str,
    base_url: str | None = None,
) -> str:
    """Build the List-Unsubscribe URL used for one-click unsubscribe."""
    url = build_unsubscribe_url(db, org_id=org_id, email=email, base_url=base_url)
    return f"{url.rstrip('/')}/one-click"


def build_list_unsubscribe_headers(
    db: Session,
    *,
    org_id: UUID,
    email: str,
    base_url: str | None = None,
) -> dict[str, str]:
    """Build List-Unsubscribe headers for one-click unsubscribe."""
    url = build_list_unsubscribe_url(db, org_id=org_id, email=email, base_url=base_url)
    return {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
