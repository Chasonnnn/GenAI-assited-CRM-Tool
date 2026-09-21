"""WebSocket database waits must not prevent HTTP sessions from releasing slots."""

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from anyio import to_thread
from fastapi import WebSocketDisconnect
from sqlalchemy.pool import QueuePool

from app.core.deps import COOKIE_NAME
from app.routers import websocket as websocket_router
from app.services import membership_service, org_service, session_service


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["handshake", "revocation_check"])
@pytest.mark.parametrize("release_in_worker", [False, True])
async def test_database_wait_allows_other_requests_to_release_connections(
    monkeypatch, phase, release_in_worker
):
    pool = QueuePool(Mock, pool_size=2, max_overflow=0, timeout=0.2)
    held = []
    release_task = None
    user_id, org_id = uuid4(), uuid4()
    lookups = 0
    connected = False
    disconnected = False
    closed = None

    if release_in_worker:
        # Reproduce shared-worker saturation with one socket instead of forty.
        monkeypatch.setattr(to_thread.current_default_thread_limiter(), "total_tokens", 1)

    async def release_slot():
        await asyncio.sleep(0.01)
        if release_in_worker:
            await to_thread.run_sync(lambda: held.pop().close())
        else:
            held.pop().close()

    def occupy_pool():
        nonlocal release_task
        held.extend([pool.connect(), pool.connect()])
        release_task = asyncio.create_task(release_slot())

    class DatabaseSession:
        def __enter__(self):
            self.connection = None
            return self

        def __exit__(self, *_args):
            if self.connection is not None:
                self.connection.close()

    def get_session(db, _token_hash):
        nonlocal lookups
        db.connection = pool.connect()
        lookups += 1
        return SimpleNamespace(organization_id=org_id) if lookups == 1 else None

    class Socket:
        headers = {"origin": "https://tenant.surrogacyforce.com"}
        cookies = {COOKIE_NAME: "synthetic-token"}

        async def receive_text(self):
            if phase == "handshake":
                raise WebSocketDisconnect()
            return "ping"

        async def send_text(self, _text):
            pass

        async def close(self, *, code, reason):
            nonlocal closed
            closed = (code, reason)

    async def connect(_socket, actual_user_id, actual_org_id, **_kwargs):
        nonlocal connected
        assert (actual_user_id, actual_org_id) == (user_id, org_id)
        connected = True
        if phase == "revocation_check":
            occupy_pool()

    async def disconnect(*_args):
        nonlocal disconnected
        disconnected = True

    monkeypatch.setattr(websocket_router.settings, "ENV", "production")
    monkeypatch.setattr(websocket_router.settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com")
    monkeypatch.setattr(websocket_router, "SESSION_RECHECK_SECONDS", 0)
    monkeypatch.setattr(websocket_router, "SessionLocal", DatabaseSession)
    monkeypatch.setattr(
        websocket_router,
        "decode_session_token",
        lambda _cookie: {
            "sub": str(user_id),
            "org_id": str(org_id),
            "mfa_required": False,
        },
    )
    monkeypatch.setattr(session_service, "get_session_by_token_hash", get_session)
    monkeypatch.setattr(membership_service, "get_membership_for_org", lambda *_args: object())
    monkeypatch.setattr(
        org_service, "get_org_by_id", lambda *_args, **_kwargs: SimpleNamespace(slug="tenant")
    )
    monkeypatch.setattr(websocket_router.manager, "connect", connect)
    monkeypatch.setattr(websocket_router.manager, "disconnect", disconnect)

    try:
        if phase == "handshake":
            occupy_pool()
        await websocket_router.websocket_notifications(Socket())
        assert connected is True
        assert disconnected is True
        assert lookups == (1 if phase == "handshake" else 2)
        if phase == "revocation_check":
            assert closed == (4001, "Session revoked")
    finally:
        if release_task is not None:
            await release_task
        for connection in held:
            connection.close()
        assert pool.checkedout() == 0
        pool.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "code", "reason"),
    [
        ("revoked", 4001, "Session revoked"),
        ("membership", 4001, "Membership inactive"),
        ("cross_org_origin", 4003, "Origin invalid for organization"),
    ],
)
async def test_threaded_authorization_preserves_session_and_tenant_rejections(
    monkeypatch, failure, code, reason
):
    user_id, org_id = uuid4(), uuid4()
    db = object()
    socket = SimpleNamespace(
        headers={"origin": "https://other.surrogacyforce.com"},
        cookies={COOKIE_NAME: "synthetic-token"},
        close=AsyncMock(),
    )
    membership = Mock(return_value=None if failure == "membership" else object())
    connect = AsyncMock()
    monkeypatch.setattr(websocket_router.settings, "ENV", "production")
    monkeypatch.setattr(websocket_router.settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com")
    monkeypatch.setattr(websocket_router.settings, "CORS_ORIGINS", "")
    monkeypatch.setattr(websocket_router, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(
        websocket_router,
        "decode_session_token",
        lambda _cookie: {"sub": str(user_id), "org_id": str(org_id), "mfa_required": False},
    )
    monkeypatch.setattr(
        session_service,
        "get_session_by_token_hash",
        lambda *_args: None if failure == "revoked" else SimpleNamespace(organization_id=org_id),
    )
    monkeypatch.setattr(membership_service, "get_membership_for_org", membership)
    monkeypatch.setattr(
        org_service, "get_org_by_id", lambda *_args, **_kwargs: SimpleNamespace(slug="tenant")
    )
    monkeypatch.setattr(websocket_router.manager, "connect", connect)

    await websocket_router.websocket_notifications(socket)

    socket.close.assert_awaited_once_with(code=code, reason=reason)
    connect.assert_not_awaited()
    if failure != "revoked":
        membership.assert_called_once_with(db, org_id, user_id)
