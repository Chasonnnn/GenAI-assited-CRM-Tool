"""
WebSocket router for real-time notifications.

Provides a WebSocket endpoint that:
1. Authenticates users via JWT cookie
2. Maintains persistent connections
3. Sends real-time notifications when events occur
"""

from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.websocket import manager
from app.core.security import decode_session_token

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
    
    Once connected, the server pushes notifications in real-time.
    """
    # Try to authenticate
    user_id = None
    
    # Try token from query param first
    if token:
        try:
            payload = decode_session_token(token)
            user_id = UUID(payload["sub"])
        except Exception:
            await websocket.close(code=4001, reason="Invalid token")
            return
    
    # Fall back to cookie if no token param
    if not user_id:
        cookie = websocket.cookies.get("session")
        if cookie:
            try:
                payload = decode_session_token(cookie)
                user_id = UUID(payload["sub"])
            except Exception:
                pass
    
    if not user_id:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Register connection
    await manager.connect(websocket, user_id)
    
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
    await manager.send_to_user(user_id, {
        "type": "notification",
        "data": notification,
    })


async def push_notification_count(user_id: UUID, count: int):
    """Push updated unread count to a connected user."""
    await manager.send_to_user(user_id, {
        "type": "count_update",
        "data": {"count": count},
    })
