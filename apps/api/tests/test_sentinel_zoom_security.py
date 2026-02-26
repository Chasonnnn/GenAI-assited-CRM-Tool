
import hmac
import hashlib
import json
import time
from unittest.mock import MagicMock
import pytest
from app.core.config import settings

def _sign_zoom(secret: str, timestamp: str, body: str) -> str:
    msg = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"v0={digest}"

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture
async def client(mock_db_session):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as c:
        yield c

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_zoom_webhook_rejects_replay_attack(client, monkeypatch):
    """Test that requests with old timestamps are rejected."""
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    payload = {"event": "meeting.started", "payload": {"object": {"id": 123}}}
    body = json.dumps(payload)

    # Generate a timestamp from 10 minutes ago
    old_timestamp = str(int(time.time()) - 600)
    signature = _sign_zoom(secret, old_timestamp, body)

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": old_timestamp,
            "x-zm-signature": signature,
        },
    )

    # Should fail (403 or 401)
    assert res.status_code == 403, "Should reject old timestamp"

@pytest.mark.asyncio
async def test_zoom_webhook_accepts_valid_timestamp(client, monkeypatch):
    """Test that requests with current timestamps are accepted."""
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    payload = {"event": "meeting.started", "payload": {"object": {"id": 123}}}
    body = json.dumps(payload)

    # Generate current timestamp
    timestamp = str(int(time.time()))
    signature = _sign_zoom(secret, timestamp, body)

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )

    # Should pass (200)
    assert res.status_code == 200, "Should accept valid timestamp"
