import asyncio
import uuid

import pytest

from app.core.websocket import ConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, _data: str) -> None:
        return None

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


def test_notify_revocation_ignores_a_closed_event_loop():
    manager = ConnectionManager()
    loop = asyncio.new_event_loop()
    manager.set_event_loop(loop)
    loop.close()

    manager.notify_revocation("revoked-token")


def test_notify_revocation_preserves_unrelated_scheduling_errors():
    class BrokenEventLoop:
        def call_soon_threadsafe(self, _callback):
            raise RuntimeError("scheduler failure")

        def is_closed(self):
            return False

    manager = ConnectionManager()
    manager.set_event_loop(BrokenEventLoop())

    with pytest.raises(RuntimeError, match="scheduler failure"):
        manager.notify_revocation("revoked-token")


@pytest.mark.asyncio
async def test_notify_revocation_schedules_cleanup_on_registered_loop():
    manager = ConnectionManager()
    user_id = uuid.uuid4()
    websocket = FakeWebSocket()
    await manager.connect(websocket, user_id, token_hash="revoked-token")
    manager.set_event_loop(asyncio.get_running_loop())

    manager.notify_revocation("revoked-token")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert websocket.closed is True


@pytest.mark.asyncio
async def test_close_by_token_hash_closes_matching_connections():
    manager = ConnectionManager()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await manager.connect(ws_a, user_a, token_hash="token-a")
    await manager.connect(ws_b, user_b, token_hash="token-b")

    await manager.close_by_token_hash("token-a")

    assert ws_a.closed is True
    assert ws_a.close_reason == "Session revoked"
    assert ws_b.closed is False
