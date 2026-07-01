import logging

import pytest


class FakeWebSocket:
    def __init__(self):
        self.closed = None

    async def close(self, *, code, reason):
        self.closed = {"code": code, "reason": reason}


def test_validate_websocket_origin_allows_org_domain(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.routers import websocket as websocket_router

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    assert websocket_router.validate_websocket_origin("https://ewi.surrogacyforce.com", db) is True


def test_validate_websocket_origin_rejects_unknown_domain(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.routers import websocket as websocket_router

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    assert websocket_router.validate_websocket_origin("https://evil.com", db) is False


def test_validate_websocket_origin_rejects_missing_host(db):
    from app.routers import websocket as websocket_router

    assert websocket_router.validate_websocket_origin("not-a-url", db) is False


@pytest.mark.asyncio
async def test_reject_websocket_logs_safe_close_reason(caplog):
    from app.routers import websocket as websocket_router

    websocket = FakeWebSocket()

    with caplog.at_level(logging.INFO, logger="app.ops"):
        await websocket_router._reject_websocket(
            websocket,
            code=4001,
            reason="Authentication required",
            origin="https://ewi.surrogacyforce.com",
        )

    assert websocket.closed == {"code": 4001, "reason": "Authentication required"}

    records = [
        record
        for record in caplog.records
        if record.name == "app.ops" and record.message == "websocket_connection_rejected"
    ]
    assert records
    record = records[-1]
    assert record.status == 403
    assert record.error_code == "websocket_authentication_required"
    assert record.websocket_close_code == 4001
    assert record.websocket_close_reason == "Authentication required"
    assert record.origin_host == "ewi.surrogacyforce.com"
    assert "cookie" not in str(record.__dict__).lower()
