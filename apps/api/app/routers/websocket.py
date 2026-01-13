"""
WebSocket router for real-time notifications.

Provides a WebSocket endpoint that:
1. Authenticates users via JWT cookie
2. Maintains persistent connections
3. Sends real-time notifications when events occur
"""

from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.config import settings
from app.core.websocket import manager
from app.core.security import decode_session_token
from app.core.deps import COOKIE_NAME
from app.services import session_service

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str | None = Query(None),
):
    """
    WebSocket endpoint for real-time notifications.

    Authenticates via:
    1. JWT token in query parameter (?token=...)
    2. Or session cookie (for browser clients)

    Once connected, the server pushes:
    - notifications (type: 'notification')
    - unread counts (type: 'count_update')
    - dashboard stats (type: 'stats_update')
    """
    # Try to authenticate
    user_id = None
    org_id = None
    token_hash = None

    def _mfa_verified(payload: dict) -> bool:
        if payload.get("mfa_required", True) and not payload.get("mfa_verified", False):
            return False
        return True

    # Try token from query param first
    if token:
        try:
            payload = decode_session_token(token)
            if not _mfa_verified(payload):
                await websocket.close(code=4003, reason="MFA required")
                return
            user_id = UUID(payload["sub"])
            if "org_id" in payload:
                org_id = UUID(payload["org_id"])
            token_hash = session_service.hash_token(token)
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return

    # Fall back to cookie if no token param
    if not user_id:
        cookie = websocket.cookies.get(COOKIE_NAME)
        if cookie:
            try:
                payload = decode_session_token(cookie)
                if not _mfa_verified(payload):
                    await websocket.close(code=4003, reason="MFA required")
                    return
                user_id = UUID(payload["sub"])
                if "org_id" in payload:
                    org_id = UUID(payload["org_id"])
                token_hash = session_service.hash_token(cookie)
            except Exception:
                pass

    if not user_id and settings.DEV_BYPASS_AUTH:
        # Align WebSocket auth with HTTP dev bypass to avoid 403 spam in local dev.
        from app.db.session import SessionLocal
        from app.db.models import Membership, User

        with SessionLocal() as db:
            dev_user = db.query(User).filter(User.email == "admin@test.com").first()
            if not dev_user:
                dev_user = db.query(User).filter(User.is_active.is_(True)).first()
            if dev_user:
                user_id = dev_user.id
                membership = (
                    db.query(Membership)
                    .filter(
                        Membership.user_id == dev_user.id,
                        Membership.is_active.is_(True),
                    )
                    .first()
                )
                if membership:
                    org_id = membership.organization_id

    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Enforce session revocation for WebSocket connections (non-dev)
    if not settings.DEV_BYPASS_AUTH:
        if not token_hash:
            await websocket.close(code=4001, reason="Authentication required")
            return
        with SessionLocal() as db:
            if not session_service.get_session_by_token_hash(db, token_hash):
                await websocket.close(code=4001, reason="Session revoked")
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
    await manager.send_to_user(
        user_id,
        {
            "type": "notification",
            "data": notification,
        },
    )


async def push_notification_count(user_id: UUID, count: int):
    """Push updated unread count to a connected user."""
    await manager.send_to_user(
        user_id,
        {
            "type": "count_update",
            "data": {"count": count},
        },
    )


async def push_dashboard_stats(org_id: UUID, stats: dict):
    """Push updated dashboard stats to all connected users in an organization."""
    await manager.send_to_org(
        org_id,
        {
            "type": "stats_update",
            "data": stats,
        },
    )
