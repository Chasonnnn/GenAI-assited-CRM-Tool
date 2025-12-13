"""Security utilities for JWT session tokens and OAuth state management."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import settings


# =============================================================================
# Session Token (JWT in cookie)
# =============================================================================

def create_session_token(
    user_id: UUID, 
    org_id: UUID, 
    role: str, 
    token_version: int
) -> str:
    """
    Create signed session JWT.
    
    Always signs with current secret (JWT_SECRET).
    Token contains user identity, org context, and revocation version.
    """
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "token_version": token_version,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRES_HOURS),
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


def create_oauth_state_payload(state: str, nonce: str, user_agent: str) -> str:
    """
    Create JSON payload for OAuth state cookie.
    
    Includes:
    - state: CSRF protection
    - nonce: Replay protection (verified in ID token)
    - ua_hash: User-agent binding
    """
    payload = {
        "state": state,
        "nonce": nonce,
        "ua_hash": hash_user_agent(user_agent),
    }
    return json.dumps(payload)


def parse_oauth_state_payload(cookie_value: str) -> dict:
    """Parse OAuth state cookie payload."""
    return json.loads(cookie_value)


def verify_oauth_state(
    stored_payload: dict, 
    received_state: str, 
    user_agent: str
) -> tuple[bool, str]:
    """
    Verify OAuth callback state matches stored state.
    
    Checks:
    1. State parameter matches (CSRF protection)
    2. User-agent hash matches (replay protection)
    
    Returns:
        (success, error_message)
    """
    if stored_payload.get("state") != received_state:
        return False, "State mismatch - possible CSRF attack"
    
    expected_ua_hash = hash_user_agent(user_agent)
    if stored_payload.get("ua_hash") != expected_ua_hash:
        return False, "User-agent mismatch - possible session hijack"
    
    return True, ""
