from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_websocket_pubsub_no_redis(monkeypatch):
    import app.core.websocket as websocket

    monkeypatch.setattr(websocket, "get_async_redis_client", lambda: None)
    monkeypatch.setattr(websocket, "get_async_redis_pubsub_client", lambda: None)

    # Should no-op without raising
    await websocket._publish_ws_event({"type": "noop"})
    await websocket.start_websocket_event_listener()
    await websocket.start_session_revocation_listener()


@pytest.mark.asyncio
async def test_websocket_send_records_safe_redis_publish_failure(monkeypatch, caplog):
    import app.core.websocket as websocket

    class FailingRedis:
        async def publish(self, channel, payload):
            del channel, payload
            raise ConnectionError("redis endpoint details must not be logged")

    monkeypatch.setattr(websocket, "get_async_redis_client", lambda: FailingRedis())

    await websocket.send_ws_to_user(uuid4(), {"type": "task.updated", "secret": "hidden"})

    record = next(record for record in caplog.records if record.msg == "ws_event_publish_failed")
    assert record.event == "ws_event_publish_failed"
    assert record.channel == websocket.WEBSOCKET_EVENT_CHANNEL
    assert record.error_class == "ConnectionError"
    assert record.target == "user"
    assert record.message_type == "task.updated"
    assert record.user_id
    assert "redis endpoint details" not in record.getMessage()
    assert "hidden" not in record.getMessage()


def test_session_revocation_publish_without_redis(monkeypatch):
    import app.core.websocket as websocket
    from app.services import session_service

    called = {"count": 0}

    def _notify(token_hash: str) -> None:
        called["count"] += 1

    monkeypatch.setattr(websocket.manager, "notify_revocation", _notify)
    monkeypatch.setattr(session_service, "get_sync_redis_client", lambda: None)

    session_service._publish_session_revoked("token")
    assert called["count"] == 1
