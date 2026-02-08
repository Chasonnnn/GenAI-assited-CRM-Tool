"""Security utilities for JWT session tokens and OAuth state management."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import settings


# =============================================================================
# Constant-Time Secret Verification
# =============================================================================


def verify_secret(provided: str | None, expected: str | None) -> bool:
    """
    Verify shared secrets using constant-time comparison.

    Returns False if either value is missing/empty.
    """
    if not provided or not expected:
        return False
    return secrets.compare_digest(str(provided), str(expected))


# =============================================================================
# Session Token (JWT in cookie)
# =============================================================================


def create_session_token(
    user_id: UUID,
    org_id: UUID,
    role: str,
    token_version: int,
    mfa_verified: bool = False,
    mfa_required: bool = True,
) -> str:
    """
    Create signed session JWT.

    Always signs with current secret (JWT_SECRET).
    Token contains user identity, org context, MFA status, and revocation version.
    """
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "token_version": token_version,
        "mfa_verified": mfa_verified,
        "mfa_required": mfa_required,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_support_session_token(
    user_id: UUID,
    org_id: UUID,
    role: str,
    token_version: int,
    support_session_id: UUID,
    mode: str,
    ttl_minutes: int,
    mfa_verified: bool = False,
    mfa_required: bool = True,
) -> str:
    """
    Create signed session JWT for support session role override.

    Adds support flags for downstream auth checks.
    """
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "token_version": token_version,
        "mfa_verified": mfa_verified,
        "mfa_required": mfa_required,
        "support": True,
        "support_session_id": str(support_session_id),
        "support_mode": mode,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    """
    Decode and verify session JWT.

    Tries current secret first, then previous (for rotation support).
    This allows zero-downtime secret rotation.

    Raises:
        jwt.InvalidTokenError: If token invalid with all secrets
    """
    last_error = None
    for secret in settings.jwt_secrets:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            last_error = e
            continue
    raise last_error  # type: ignore


# =============================================================================
# Export Token (short-lived, read-only)
# =============================================================================


def create_export_token(
    org_id: UUID,
    surrogate_id: UUID,
    ttl_minutes: int = 5,
    variant: str | None = None,
) -> str:
    """
    Create a short-lived export token for Journey PDF rendering.

    Purpose-bound and scoped to org + surrogate.
    """
    payload = {
        "org_id": str(org_id),
        "surrogate_id": str(surrogate_id),
        "purpose": "journey_export",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    if variant:
        payload["variant"] = variant
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_export_token(token: str) -> dict:
    """
    Decode and verify export token.

    Uses the same secret rotation strategy as session tokens.
    """
    last_error = None
    for secret in settings.jwt_secrets:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            last_error = e
            continue
    raise last_error  # type: ignore


# =============================================================================
# OAuth State/Nonce with User-Agent Binding
# =============================================================================


def generate_oauth_state() -> str:
    """Generate cryptographically random state (32 bytes, URL-safe base64)."""
    return secrets.token_urlsafe(32)


def generate_oauth_nonce() -> str:
    """Generate cryptographically random nonce (32 bytes, URL-safe base64)."""
    return secrets.token_urlsafe(32)


def hash_user_agent(user_agent: str) -> str:
    """
    Create a hash of user-agent for binding to OAuth state.

    This provides lightweight replay protection - an attacker would
    need to use the same browser to replay a stolen state cookie.
    """
    return hashlib.sha256(user_agent.encode()).hexdigest()[:16]


def create_oauth_state_payload(
    state: str, nonce: str, user_agent: str, return_to: str | None = None
) -> str:
    """
    Create JSON payload for OAuth state cookie.

    Includes:
    - state: CSRF protection
    - nonce: Replay protection (verified in ID token)
    - ua_hash: User-agent binding
    - return_to: Target app after auth ("app" or "ops")
    """
    payload = {
        "state": state,
        "nonce": nonce,
        "ua_hash": hash_user_agent(user_agent),
    }
    if return_to:
        payload["return_to"] = return_to
    return json.dumps(payload)


def parse_oauth_state_payload(cookie_value: str) -> dict:
    """Parse OAuth state cookie payload."""
    return json.loads(cookie_value)


def verify_oauth_state(
    stored_payload: dict, received_state: str, user_agent: str
) -> tuple[bool, str]:
    """
    Verify OAuth callback state matches stored state.

    Checks:
    1. State parameter matches (CSRF protection)
    2. User-agent hash matches (replay protection)

    Returns:
        (success, error_message)
    """
    stored_state = stored_payload.get("state")
    if not verify_secret(received_state, stored_state if isinstance(stored_state, str) else None):
        return False, "State mismatch - possible CSRF attack"

    expected_ua_hash = hash_user_agent(user_agent)
    stored_ua_hash = stored_payload.get("ua_hash")
    if not verify_secret(
        expected_ua_hash, stored_ua_hash if isinstance(stored_ua_hash, str) else None
    ):
        return False, "User-agent mismatch - possible session hijack"

    return True, ""
