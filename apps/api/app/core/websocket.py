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
    """Manages WebSocket connections per user."""
    
    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[UUID, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Remove a WebSocket connection."""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
    
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
    
    def get_connected_count(self, user_id: UUID) -> int:
        """Get the number of active connections for a user."""
        return len(self._connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections across all users."""
        return sum(len(conns) for conns in self._connections.values())


# Singleton instance
manager = ConnectionManager()
