"""
WebSocket connection manager for real-time notifications.

Manages active WebSocket connections per user, allowing
server-sent messages to reach connected clients instantly.
"""

from typing import Dict, Set
from uuid import UUID
import asyncio
import json
import os

from fastapi import WebSocket


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

        if not connections:
            return

        data = json.dumps(message)
        closed = []

        for ws in connections:
            try:
                await ws.send_text(data)
            except Exception:
                # Connection closed or errored
                closed.append(ws)

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
            except Exception:
                pass

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


async def start_session_revocation_listener() -> None:
    """Listen for session revocation events and close matching sockets."""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url or redis_url == "memory://":
        return

    try:
        import redis.asyncio as redis
    except Exception:
        return

    client = redis.from_url(redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(SESSION_REVOKE_CHANNEL)

    async def _listen() -> None:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            token_hash = data.decode() if isinstance(data, bytes) else str(data)
            await manager.close_by_token_hash(token_hash)

    asyncio.create_task(_listen())


# Singleton instance
manager = ConnectionManager()
