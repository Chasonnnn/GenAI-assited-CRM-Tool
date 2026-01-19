def test_should_deliver_ws_event_skips_same_instance():
    from app.core import websocket

    event = {"source_id": "instance-1", "target": "user", "user_id": "user-1"}

    assert websocket.should_deliver_ws_event(event, "instance-1") is False
    assert websocket.should_deliver_ws_event(event, "instance-2") is True
