"""
WebSocket connection manager for real-time notifications.

Manages active WebSocket connections per user, allowing
server-sent messages to reach connected clients instantly.
"""

from typing import Dict, Set
from uuid import UUID
import asyncio
import json

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections per user and organization."""

    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[UUID, Set[WebSocket]] = {}
        # user_id -> org_id (for org-based broadcasts)
        self._user_orgs: Dict[UUID, UUID] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: UUID, org_id: UUID | None = None
    ):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
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


# Singleton instance
manager = ConnectionManager()
