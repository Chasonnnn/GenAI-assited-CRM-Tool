import pytest


@pytest.mark.asyncio
async def test_websocket_pubsub_no_redis(monkeypatch):
    import app.core.websocket as websocket

    monkeypatch.setattr(websocket, "get_async_redis_client", lambda: None)

    # Should no-op without raising
    await websocket._publish_ws_event({"type": "noop"})
    await websocket.start_websocket_event_listener()
    await websocket.start_session_revocation_listener()


def test_session_revocation_publish_without_redis(monkeypatch):
    from app.services import session_service
    import app.core.websocket as websocket

    called = {"count": 0}

    def _notify(token_hash: str) -> None:
        called["count"] += 1

    monkeypatch.setattr(websocket.manager, "notify_revocation", _notify)
    monkeypatch.setattr(session_service, "get_sync_redis_client", lambda: None)

    session_service._publish_session_revoked("token")
    assert called["count"] == 1
