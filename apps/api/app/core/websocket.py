"""
WebSocket connection manager for real-time notifications.

Manages active WebSocket connections per user, allowing
server-sent messages to reach connected clients instantly.
"""

from typing import Dict, Set
from uuid import UUID, uuid4
import asyncio
import json
import os
import logging

from fastapi import WebSocket

from app.core.redis_client import get_async_redis_client

logger = logging.getLogger(__name__)

WEBSOCKET_EVENT_CHANNEL = "websocket_events"
WEBSOCKET_INSTANCE_ID = os.getenv("WEBSOCKET_INSTANCE_ID") or os.getenv("HOSTNAME") or str(uuid4())


class ConnectionManager:
    """Manages WebSocket connections per user and organization."""

    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[UUID, Set[WebSocket]] = {}
        # user_id -> org_id (for org-based broadcasts)
        self._user_orgs: Dict[UUID, UUID] = {}
        # token_hash -> set of active WebSocket connections
        self._connections_by_token: Dict[str, Set[WebSocket]] = {}
        # websocket -> token_hash
        self._ws_tokens: Dict[WebSocket, str] = {}
        # websocket -> user_id
        self._ws_users: Dict[WebSocket, UUID] = {}
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the main event loop for cross-thread notifications."""
        self._loop = loop

    def notify_revocation(self, token_hash: str) -> None:
        """Schedule local WebSocket cleanup for a revoked session."""
        if not token_hash or not self._loop:
            return
        self._loop.call_soon_threadsafe(asyncio.create_task, self.close_by_token_hash(token_hash))

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        org_id: UUID | None = None,
        token_hash: str | None = None,
    ):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
            self._ws_users[websocket] = user_id
            if token_hash:
                if token_hash not in self._connections_by_token:
                    self._connections_by_token[token_hash] = set()
                self._connections_by_token[token_hash].add(websocket)
                self._ws_tokens[websocket] = token_hash
            if org_id:
                self._user_orgs[user_id] = org_id

    async def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Remove a WebSocket connection."""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
                    # Remove org mapping when no connections left
                    self._user_orgs.pop(user_id, None)
            token_hash = self._ws_tokens.pop(websocket, None)
            self._ws_users.pop(websocket, None)
            if token_hash and token_hash in self._connections_by_token:
                self._connections_by_token[token_hash].discard(websocket)
                if not self._connections_by_token[token_hash]:
                    del self._connections_by_token[token_hash]

    async def send_to_user(self, user_id: UUID, message: dict):
        """Send a message to all connections for a specific user."""
        async with self._lock:
            connections = self._connections.get(user_id, set()).copy()
            org_id = self._user_orgs.get(user_id)

        if not connections:
            return

        data = json.dumps(message)
        closed = []
        errors: list[Exception] = []

        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception as exc:
                # Connection closed or errored
                closed.append(ws)
                errors.append(exc)

        if errors:
            message_type = message.get("type")
            logger.warning(
                "ws_send_failed",
                extra={
                    "event": "ws_send_failed",
                    "user_id": str(user_id),
                    "org_id": str(org_id) if org_id else None,
                    "message_type": message_type,
                    "failed_count": len(errors),
                    "connection_count": len(connections),
                    "error_class": errors[0].__class__.__name__,
                },
            )

        # Clean up closed connections
        if closed:
            async with self._lock:
                if user_id in self._connections:
                    for ws in closed:
                        self._connections[user_id].discard(ws)
                        token_hash = self._ws_tokens.pop(ws, None)
                        self._ws_users.pop(ws, None)
                        if token_hash and token_hash in self._connections_by_token:
                            self._connections_by_token[token_hash].discard(ws)
                            if not self._connections_by_token[token_hash]:
                                del self._connections_by_token[token_hash]
                    if not self._connections[user_id]:
                        del self._connections[user_id]

    async def broadcast_to_org(self, org_id: UUID, user_ids: list[UUID], message: dict):
        """Broadcast a message to multiple users in an organization."""
        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    async def send_to_org(self, org_id: UUID, message: dict):
        """Send a message to all connected users in an organization."""
        async with self._lock:
            user_ids = [uid for uid, oid in self._user_orgs.items() if oid == org_id]

        for user_id in user_ids:
            await self.send_to_user(user_id, message)

    def get_connected_count(self, user_id: UUID) -> int:
        """Get the number of active connections for a user."""
        return len(self._connections.get(user_id, set()))

    def get_org_user_ids(self, org_id: UUID) -> list[UUID]:
        """Get all connected user IDs for an organization."""
        return [uid for uid, oid in self._user_orgs.items() if oid == org_id]

    def get_total_connections(self) -> int:
        """Get total number of active connections across all users."""
        return sum(len(conns) for conns in self._connections.values())

    async def close_by_token_hash(self, token_hash: str) -> None:
        """Close all connections associated with a revoked session token."""
        async with self._lock:
            connections = self._connections_by_token.get(token_hash, set()).copy()

        if not connections:
            return

        for ws in connections:
            try:
                await ws.close(code=4001, reason="Session revoked")
            except Exception as exc:
                logger.debug("ws_close_failed", exc_info=exc)

        async with self._lock:
            for ws in connections:
                user_id = self._ws_users.pop(ws, None)
                self._ws_tokens.pop(ws, None)
                if user_id and user_id in self._connections:
                    self._connections[user_id].discard(ws)
                    if not self._connections[user_id]:
                        del self._connections[user_id]
                        self._user_orgs.pop(user_id, None)
            self._connections_by_token.pop(token_hash, None)


# Session revocation pub/sub
SESSION_REVOKE_CHANNEL = "session_revoked"


def should_deliver_ws_event(event: dict, instance_id: str) -> bool:
    source_id = event.get("source_id")
    return not source_id or source_id != instance_id


async def _publish_ws_event(event: dict) -> None:
    client = get_async_redis_client()
    if client is None:
        return
    try:
        await client.publish(WEBSOCKET_EVENT_CHANNEL, json.dumps(event))
    except Exception:
        logger.warning(
            "ws_event_publish_failed",
            extra={"event": "ws_event_publish_failed", "channel": WEBSOCKET_EVENT_CHANNEL},
        )


async def send_ws_to_user(user_id: UUID, message: dict) -> None:
    await manager.send_to_user(user_id, message)
    await _publish_ws_event(
        {
            "source_id": WEBSOCKET_INSTANCE_ID,
            "target": "user",
            "user_id": str(user_id),
            "message": message,
        }
    )


async def send_ws_to_org(org_id: UUID, message: dict) -> None:
    await manager.send_to_org(org_id, message)
    await _publish_ws_event(
        {
            "source_id": WEBSOCKET_INSTANCE_ID,
            "target": "org",
            "org_id": str(org_id),
            "message": message,
        }
    )


async def start_session_revocation_listener() -> None:
    """Listen for session revocation events and close matching sockets."""
    if get_async_redis_client() is None:
        return

    async def _handle_message(message: dict) -> None:
        data = message.get("data")
        token_hash = data.decode() if isinstance(data, bytes) else str(data)
        await manager.close_by_token_hash(token_hash)

    asyncio.create_task(_listen_channel(SESSION_REVOKE_CHANNEL, _handle_message))


async def start_websocket_event_listener() -> None:
    """Listen for websocket events from other instances."""
    if get_async_redis_client() is None:
        return

    async def _handle_message(message: dict) -> None:
        data = message.get("data")
        raw = data.decode() if isinstance(data, bytes) else data
        try:
            event = json.loads(raw)
        except Exception:
            return
        if not should_deliver_ws_event(event, WEBSOCKET_INSTANCE_ID):
            return

        target = event.get("target")
        payload = event.get("message")
        if target == "user" and event.get("user_id"):
            await manager.send_to_user(UUID(event["user_id"]), payload)
        elif target == "org" and event.get("org_id"):
            await manager.send_to_org(UUID(event["org_id"]), payload)

    asyncio.create_task(_listen_channel(WEBSOCKET_EVENT_CHANNEL, _handle_message))


async def _listen_channel(channel: str, handler) -> None:
    client = get_async_redis_client()
    if client is None:
        return

    while True:
        pubsub = None
        try:
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                await handler(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "redis_pubsub_failed",
                extra={"event": "redis_pubsub_failed", "channel": channel},
            )
            await asyncio.sleep(2)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.close()
                except Exception as exc:
                    logger.debug("redis_pubsub_close_failed", exc_info=exc)


# Singleton instance
manager = ConnectionManager()
