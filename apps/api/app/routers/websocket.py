"""
WebSocket router for real-time notifications.

Provides a WebSocket endpoint that:
1. Authenticates users via JWT cookie
2. Maintains persistent connections
3. Sends real-time notifications when events occur
"""

import asyncio
import time
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.websocket import manager, send_ws_to_user, send_ws_to_org
from app.core.security import decode_session_token
from app.core.deps import COOKIE_NAME
from app.db.models import Membership
from app.db.session import SessionLocal
from app.services import session_service

router = APIRouter(prefix="/ws", tags=["WebSocket"])
# Periodic DB check to close revoked sessions if Redis pub/sub is unavailable.
SESSION_RECHECK_SECONDS = 60


def _normalize_origin(origin: str) -> str:
    return origin.rstrip("/")


def _allowed_origins() -> set[str]:
    """Get static list of allowed origins (for backwards compatibility)."""
    allowed = {_normalize_origin(origin) for origin in settings.cors_origins_list}
    if settings.FRONTEND_URL:
        allowed.add(_normalize_origin(settings.FRONTEND_URL))
    return {origin for origin in allowed if origin}


def validate_websocket_origin(origin: str | None, db: Session) -> bool:
    """
    Validate a WebSocket origin against known org domains or static origins.

    This is used by tests and can be reused by callers that already have a DB session.
    """
    if not origin:
        return False

    normalized = _normalize_origin(origin)
    if normalized in _allowed_origins():
        return True

    from urllib.parse import urlparse
    from app.services import org_service

    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()
    if not host:
        return False

    if settings.is_dev and (
        host in ("localhost", "127.0.0.1") or host.endswith(".localhost") or host.endswith(".test")
    ):
        return True

    return org_service.get_org_by_host(db, host) is not None


def _validate_websocket_origin(origin: str | None, *, is_dev: bool) -> bool:
    """
    Validate WebSocket origin dynamically.

    Allows:
    - Any origin in dev mode
    - Static CORS_ORIGINS list
    - Dynamic {slug}.{PLATFORM_BASE_DOMAIN} subdomains
    """
    if is_dev:
        return True
    if not origin:
        return False

    normalized = _normalize_origin(origin)

    # Check static list first
    if normalized in _allowed_origins():
        return True

    # Extract hostname from origin (https://ewi.surrogacyforce.com -> ewi.surrogacyforce.com)
    from urllib.parse import urlparse

    parsed = urlparse(normalized)
    host = (parsed.hostname or "").lower()

    if not host:
        return False

    # Allow any *.{PLATFORM_BASE_DOMAIN} subdomain (will be validated at session level)
    base_domain = settings.PLATFORM_BASE_DOMAIN
    if base_domain and host.endswith(f".{base_domain}"):
        slug = host.removesuffix(f".{base_domain}")
        # Basic slug format check (actual org validation happens during auth)
        if slug and slug.replace("-", "").isalnum():
            return True

    return False


def _origin_is_allowed(origin: str | None, *, allowed: set[str], is_dev: bool) -> bool:
    """Legacy function for backwards compatibility."""
    return _validate_websocket_origin(origin, is_dev=is_dev)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
):
    """
    WebSocket endpoint for real-time notifications.

    Authenticates via session cookie (browser clients only).
    Requires an allowed Origin header.

    Once connected, the server pushes:
    - notifications (type: 'notification')
    - unread counts (type: 'count_update')
    - dashboard stats (type: 'stats_update')
    """
    origin = websocket.headers.get("origin")
    if not origin and not settings.is_dev:
        await websocket.close(code=4003, reason="Origin required")
        return
    allowed = _allowed_origins()
    if origin and not _origin_is_allowed(origin, allowed=allowed, is_dev=settings.is_dev):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # Authenticate
    user_id = None
    org_id = None
    token_hash = None

    def _mfa_verified(payload: dict) -> bool:
        if payload.get("mfa_required", True) and not payload.get("mfa_verified", False):
            return False
        return True

    cookie = websocket.cookies.get(COOKIE_NAME)
    if not cookie:
        await websocket.close(code=4001, reason="Authentication required")
        return

    try:
        payload = decode_session_token(cookie)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    if not _mfa_verified(payload):
        await websocket.close(code=4003, reason="MFA required")
        return

    user_id = UUID(payload["sub"])
    if "org_id" in payload:
        org_id = UUID(payload["org_id"])
    token_hash = session_service.hash_token(cookie)

    # Enforce session revocation for WebSocket connections
    if not token_hash:
        await websocket.close(code=4001, reason="Authentication required")
        return
    with SessionLocal() as db:
        from app.db.models import Organization

        db_session = session_service.get_session_by_token_hash(db, token_hash)
        if not db_session:
            await websocket.close(code=4001, reason="Session revoked")
            return
        if not org_id:
            org_id = db_session.organization_id
        membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.organization_id == org_id,
                Membership.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            await websocket.close(code=4001, reason="Membership inactive")
            return

        # Validate origin matches org's subdomain (cross-tenant protection)
        if origin and not settings.is_dev:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if org:
                from urllib.parse import urlparse

                parsed = urlparse(origin)
                origin_host = (parsed.hostname or "").lower()
                expected_host = f"{org.slug}.{settings.PLATFORM_BASE_DOMAIN}"
                # Allow both exact match and static CORS origins
                if (
                    origin_host != expected_host
                    and _normalize_origin(origin) not in _allowed_origins()
                ):
                    await websocket.close(code=4003, reason="Origin invalid for organization")
                    return

    # Register connection with org tracking
    await manager.connect(websocket, user_id, org_id, token_hash=token_hash)

    last_recheck = time.monotonic()
    try:
        # Keep connection alive, handle incoming messages (heartbeat/pings)
        while True:
            timeout = max(1.0, SESSION_RECHECK_SECONDS - (time.monotonic() - last_recheck))
            try:
                # Wait for client messages (pings, close, etc.)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)

                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            if time.monotonic() - last_recheck >= SESSION_RECHECK_SECONDS:
                with SessionLocal() as db:
                    db_session = session_service.get_session_by_token_hash(db, token_hash)
                    if not db_session:
                        await websocket.close(code=4001, reason="Session revoked")
                        break
                last_recheck = time.monotonic()
    finally:
        await manager.disconnect(websocket, user_id)


# Helper function to push notifications (used by notification_service)
async def push_notification(user_id: UUID, notification: dict):
    """Push a notification to a connected user."""
    await send_ws_to_user(
        user_id,
        {
            "type": "notification",
            "data": notification,
        },
    )


async def push_notification_count(user_id: UUID, count: int):
    """Push updated unread count to a connected user."""
    await send_ws_to_user(
        user_id,
        {
            "type": "count_update",
            "data": {"count": count},
        },
    )


async def push_dashboard_stats(org_id: UUID, stats: dict):
    """Push updated dashboard stats to all connected users in an organization."""
    await send_ws_to_org(
        org_id,
        {
            "type": "stats_update",
            "data": stats,
        },
    )
