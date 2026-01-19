"""
WebSocket router for real-time notifications.

Provides a WebSocket endpoint that:
1. Authenticates users via JWT cookie
2. Maintains persistent connections
3. Sends real-time notifications when events occur
"""

from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.websocket import manager, send_ws_to_user, send_ws_to_org
from app.core.security import decode_session_token
from app.core.deps import COOKIE_NAME
from app.db.models import Membership
from app.db.session import SessionLocal
from app.services import session_service

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _normalize_origin(origin: str) -> str:
    return origin.rstrip("/")


def _allowed_origins() -> set[str]:
    allowed = {_normalize_origin(origin) for origin in settings.cors_origins_list}
    if settings.FRONTEND_URL:
        allowed.add(_normalize_origin(settings.FRONTEND_URL))
    return {origin for origin in allowed if origin}


def _origin_is_allowed(origin: str | None, *, allowed: set[str], is_dev: bool) -> bool:
    if is_dev:
        return True
    if not origin:
        return False
    if not allowed:
        return False
    return _normalize_origin(origin) in allowed


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

    # Register connection with org tracking
    await manager.connect(websocket, user_id, org_id, token_hash=token_hash)

    try:
        # Keep connection alive, handle incoming messages (heartbeat/pings)
        while True:
            try:
                # Wait for client messages (pings, close, etc.)
                data = await websocket.receive_text()

                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
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
