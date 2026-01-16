"""Session service - manages user session tracking for revocation support."""

import hashlib
import ipaddress
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

try:
    from user_agents import parse as parse_user_agent
except Exception:  # pragma: no cover - optional dependency in some envs
    parse_user_agent = None

from app.core.config import settings
from app.db.models import UserSession

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    """Create SHA256 hash of JWT token for storage and lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def parse_device_info(user_agent_str: str | None) -> str:
    """Parse user agent string into human-readable device info."""
    if not user_agent_str:
        return "Unknown Device"

    if parse_user_agent is None:
        return "Unknown Device"

    try:
        ua = parse_user_agent(user_agent_str)
        browser = ua.browser.family
        browser_version = ua.browser.version_string
        os = ua.os.family
        os_version = ua.os.version_string

        # Format: "Chrome 120 on Windows 11"
        device_parts = []
        if browser:
            device_parts.append(f"{browser} {browser_version}".strip())
        if os:
            device_parts.append(f"on {os} {os_version}".strip())

        return " ".join(device_parts) if device_parts else "Unknown Device"
    except Exception:
        return "Unknown Device"


def mask_ip(ip_address: str | None) -> str | None:
    """Mask IP for logs to avoid storing raw PII."""
    if not ip_address:
        return None
    try:
        ip_obj = ipaddress.ip_address(ip_address)
    except ValueError:
        return None
    if isinstance(ip_obj, ipaddress.IPv4Address):
        network = ipaddress.ip_network(f"{ip_address}/24", strict=False)
        return f"{network.network_address}/24"
    network = ipaddress.ip_network(f"{ip_address}/64", strict=False)
    return f"{network.network_address}/64"


def get_client_ip(request: Request | None) -> str | None:
    """Extract client IP from request, handling proxies."""
    if not request:
        return None

    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return None


def create_session(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    token: str,
    request: Request | None = None,
) -> UserSession:
    """
    Create a new session record when a user logs in.

    Args:
        db: Database session
        user_id: The user's ID
        org_id: The user's organization ID
        token: The JWT token (will be hashed for storage)
        request: Optional request for extracting device info

    Returns:
        The created UserSession record
    """
    token_hash = hash_token(token)
    user_agent = request.headers.get("User-Agent") if request else None
    ip_address = get_client_ip(request)
    device_info = parse_device_info(user_agent)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRES_HOURS)

    session_record = UserSession(
        user_id=user_id,
        organization_id=org_id,
        session_token_hash=token_hash,
        device_info=device_info,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,  # Truncate if needed
        expires_at=expires_at,
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)

    masked_ip = mask_ip(ip_address)
    logger.info(
        "Created session for user %s (device: %s, ip: %s)",
        user_id,
        device_info,
        masked_ip,
    )

    return session_record


def get_session_by_token_hash(
    db: Session,
    token_hash: str,
) -> UserSession | None:
    """
    Find an active session by token hash.

    Used by auth middleware to validate session exists.
    Returns None if session doesn't exist or is expired.
    """
    stmt = select(UserSession).where(
        UserSession.session_token_hash == token_hash,
        UserSession.expires_at > datetime.now(timezone.utc),
    )
    return db.scalars(stmt).first()


def list_user_sessions(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    current_token_hash: str | None = None,
) -> list[dict]:
    """
    List all active sessions for a user.

    Args:
        db: Database session
        user_id: The user's ID
        org_id: The user's organization ID
        current_token_hash: Hash of the current request's token (to mark as "current")

    Returns:
        List of session data dicts with is_current flag
    """
    # Clean up expired sessions while we're here (lazy cleanup)
    cleanup_expired_for_user(db, user_id)

    stmt = (
        select(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.organization_id == org_id,
            UserSession.expires_at > datetime.now(timezone.utc),
        )
        .order_by(UserSession.last_active_at.desc())
    )

    sessions = db.scalars(stmt).all()

    return [
        {
            "id": str(s.id),
            "device_info": s.device_info,
            "ip_address": s.ip_address,
            "created_at": s.created_at.isoformat(),
            "last_active_at": s.last_active_at.isoformat(),
            "expires_at": s.expires_at.isoformat(),
            "is_current": s.session_token_hash == current_token_hash,
        }
        for s in sessions
    ]


def revoke_session(
    db: Session,
    session_id: UUID,
    user_id: UUID,
    org_id: UUID,
) -> bool:
    """
    Revoke (delete) a specific session.

    Args:
        db: Database session
        session_id: The session ID to revoke
        user_id: The user's ID (for authorization)
        org_id: The organization ID (for authorization)

    Returns:
        True if session was found and deleted, False otherwise
    """
    token_stmt = select(UserSession.session_token_hash).where(
        UserSession.id == session_id,
        UserSession.user_id == user_id,
        UserSession.organization_id == org_id,
    )
    token_hash = db.scalars(token_stmt).first()
    if not token_hash:
        return False

    stmt = delete(UserSession).where(UserSession.id == session_id)
    result = db.execute(stmt)
    db.commit()

    deleted = result.rowcount > 0
    if deleted:
        logger.info("Revoked session %s for user %s", session_id, user_id)
        _publish_session_revoked(token_hash)
    else:
        logger.warning(
            "Failed to revoke session %s for user %s - not found or unauthorized",
            session_id,
            user_id,
        )

    return deleted


def delete_session_by_token(db: Session, token: str) -> bool:
    """
    Delete a session by its token (used during logout).

    Args:
        db: Database session
        token: The JWT token

    Returns:
        True if session was found and deleted, False otherwise
    """
    token_hash = hash_token(token)
    stmt = delete(UserSession).where(UserSession.session_token_hash == token_hash)
    result = db.execute(stmt)
    db.commit()
    deleted = result.rowcount > 0
    if deleted:
        _publish_session_revoked(token_hash)
    return deleted


def cleanup_expired_for_user(db: Session, user_id: UUID) -> int:
    """
    Delete expired sessions for a specific user (lazy cleanup).

    Called during list_user_sessions to keep the table clean.

    Returns:
        Number of sessions deleted
    """
    stmt = delete(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.expires_at <= datetime.now(timezone.utc),
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def cleanup_all_expired_sessions(db: Session) -> int:
    """
    Delete all expired sessions (scheduled job).

    Should be called periodically (e.g., hourly) to purge old sessions.

    Returns:
        Number of sessions deleted
    """
    stmt = delete(UserSession).where(
        UserSession.expires_at <= datetime.now(timezone.utc),
    )
    result = db.execute(stmt)
    db.commit()

    count = result.rowcount
    if count > 0:
        logger.info("Cleaned up %d expired sessions", count)
    return count


def update_last_active(
    db: Session,
    session_record: UserSession,
    throttle_minutes: int = 5,
) -> None:
    """
    Update last_active_at for a session (throttled).

    Only updates if more than throttle_minutes have passed since last update,
    to reduce database writes.

    Args:
        db: Database session
        session_record: The session to update
        throttle_minutes: Minimum minutes between updates
    """
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=throttle_minutes)

    if session_record.last_active_at < threshold:
        session_record.last_active_at = now
        db.commit()


def revoke_all_user_sessions(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    except_token_hash: str | None = None,
) -> int:
    """
    Revoke all sessions for a user (e.g., after password change or logout all).

    Args:
        db: Database session
        user_id: The user's ID
        org_id: The organization ID
        except_token_hash: Optional token hash to keep (current session)

    Returns:
        Number of sessions revoked
    """
    conditions = [
        UserSession.user_id == user_id,
        UserSession.organization_id == org_id,
    ]

    if except_token_hash:
        conditions.append(UserSession.session_token_hash != except_token_hash)

    token_stmt = select(UserSession.session_token_hash).where(*conditions)
    token_hashes = [row for row in db.scalars(token_stmt).all()]

    stmt = delete(UserSession).where(*conditions)
    result = db.execute(stmt)
    db.commit()

    count = result.rowcount
    logger.info("Revoked %d sessions for user %s", count, user_id)
    for token_hash in token_hashes:
        _publish_session_revoked(token_hash)
    return count


def _publish_session_revoked(token_hash: str) -> None:
    """Notify websocket workers to close connections for a revoked session."""
    if not token_hash:
        return

    try:
        from app.core.websocket import manager, SESSION_REVOKE_CHANNEL

        manager.notify_revocation(token_hash)
    except Exception:
        logger.debug("Local WebSocket revocation notify failed", exc_info=True)

    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis_url == "memory://":
        return

    try:
        import redis

        client = redis.from_url(redis_url)
        client.publish(SESSION_REVOKE_CHANNEL, token_hash)
        client.close()
    except Exception:
        logger.warning("Failed to publish session revocation", exc_info=True)
