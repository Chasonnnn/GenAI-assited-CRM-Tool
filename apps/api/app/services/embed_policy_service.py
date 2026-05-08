"""Origin and session policy helpers for public intake embeds."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import EmbedSession, FormIntakeLink


EMBED_SESSION_TTL_MINUTES = 60
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class EmbedSessionToken:
    token: str
    session: EmbedSession


def stable_hash(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def stable_json_hash(value: object) -> str:
    import json

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def normalize_origin(value: str, *, allow_localhost: bool | None = None) -> str:
    """Return canonical scheme://host[:port] for an allowed embed origin."""
    allow_localhost = settings.is_dev if allow_localhost is None else allow_localhost
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Origin is required")
    if "*" in raw:
        raise ValueError("Wildcard origins are not allowed")
    if raw.startswith(("javascript:", "data:")):
        raise ValueError("Origin scheme is not allowed")

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Origin must include scheme and host")

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower().strip(".")
    if not hostname:
        raise ValueError("Origin host is required")
    if hostname.startswith(".") or ".." in hostname:
        raise ValueError("Origin host is invalid")

    is_localhost = hostname in _LOCAL_HOSTS or hostname.endswith(".localhost")
    if scheme != "https" and not (allow_localhost and is_localhost and scheme == "http"):
        raise ValueError("Only HTTPS origins are allowed")

    port = parsed.port
    default_port = (scheme == "https" and port == 443) or (scheme == "http" and port == 80)
    port_suffix = "" if not port or default_port else f":{port}"
    return f"{scheme}://{hostname}{port_suffix}"


def normalize_allowed_origins(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        origin = normalize_origin(value)
        if origin in seen:
            continue
        seen.add(origin)
        normalized.append(origin)
    return normalized


def is_origin_allowed(link: FormIntakeLink, origin: str) -> bool:
    try:
        normalized = normalize_origin(origin)
    except ValueError:
        return False
    allowed = link.allowed_embed_origins or []
    return normalized in allowed


def build_frame_ancestors_header(link: FormIntakeLink) -> str:
    origins = ["'self'", *(link.allowed_embed_origins or [])]
    return f"frame-ancestors {' '.join(origins)}"


def create_embed_session(
    db: Session,
    *,
    link: FormIntakeLink,
    parent_origin: str,
    attribution_snapshot: dict | None,
    client_ip: str | None,
    user_agent: str | None,
) -> EmbedSessionToken:
    normalized_origin = normalize_origin(parent_origin)
    if normalized_origin not in (link.allowed_embed_origins or []):
        raise PermissionError("Origin is not allowed")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session = EmbedSession(
        organization_id=link.organization_id,
        intake_link_id=link.id,
        public_session_token_hash=stable_hash(token),
        parent_origin=normalized_origin,
        attribution_snapshot_json=attribution_snapshot or None,
        ip_hash=stable_hash(client_ip),
        user_agent_hash=stable_hash(user_agent),
        expires_at=now + timedelta(minutes=EMBED_SESSION_TTL_MINUTES),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return EmbedSessionToken(token=token, session=session)


def validate_embed_session(
    db: Session,
    *,
    link: FormIntakeLink,
    token: str,
) -> EmbedSession:
    token_hash = stable_hash(token)
    if not token_hash:
        raise PermissionError("Embed session is required")
    session = (
        db.query(EmbedSession)
        .filter(
            EmbedSession.organization_id == link.organization_id,
            EmbedSession.intake_link_id == link.id,
            EmbedSession.public_session_token_hash == token_hash,
        )
        .first()
    )
    if not session:
        raise PermissionError("Embed session is invalid")
    now = datetime.now(timezone.utc)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise PermissionError("Embed session expired")
    if session.consumed_at is not None:
        raise PermissionError("Embed session already used")
    return session
