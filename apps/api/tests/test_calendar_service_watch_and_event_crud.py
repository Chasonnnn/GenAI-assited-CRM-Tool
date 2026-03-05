from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import calendar_service


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._payload


class _AsyncClientFactory:
    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, params=None):
        return await self._handler(method="GET", url=url, headers=headers, params=params, json=None)

    async def post(self, url, headers=None, params=None, json=None):
        return await self._handler(
            method="POST", url=url, headers=headers, params=params, json=json
        )


@pytest.mark.asyncio
async def test_calendar_busy_slots_success_failure_and_exception(monkeypatch):
    async def _ok_handler(**kwargs):
        del kwargs
        return _FakeResponse(
            200,
            {
                "calendars": {
                    "primary": {
                        "busy": [
                            {"start": "2026-01-01T10:00:00Z", "end": "2026-01-01T11:00:00Z"},
                            {"start": "2026-01-01T12:00:00Z", "end": "2026-01-01T13:00:00Z"},
                        ]
                    }
                }
            },
        )

    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_ok_handler),
    )
    busy = await calendar_service.get_google_busy_slots(
        access_token="tok",
        calendar_id="primary",
        time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert len(busy) == 2

    async def _bad_handler(**kwargs):
        del kwargs
        return _FakeResponse(500, {})

    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_bad_handler),
    )
    busy = await calendar_service.get_google_busy_slots(
        access_token="tok",
        calendar_id="primary",
        time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert busy == []

    class _ExplodingClient:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        calendar_service.httpx, "AsyncClient", lambda *args, **kwargs: _ExplodingClient()
    )
    busy = await calendar_service.get_google_busy_slots(
        access_token="tok",
        calendar_id="primary",
        time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert busy == []


@pytest.mark.asyncio
async def test_calendar_get_events_and_calendar_ids_pagination(monkeypatch):
    state = {"event_calls": 0, "calendar_calls": 0}

    async def _handler(method, url, headers=None, params=None, json=None):
        del headers, json
        if method == "GET" and url.endswith("/events"):
            state["event_calls"] += 1
            if state["event_calls"] == 1:
                return _FakeResponse(
                    200,
                    {
                        "items": [
                            {
                                "id": "evt1",
                                "summary": "Timed Event",
                                "start": {"dateTime": "2026-01-01T10:00:00Z"},
                                "end": {"dateTime": "2026-01-01T11:00:00Z"},
                                "htmlLink": "https://calendar/evt1",
                            },
                            {
                                "id": "evt2",
                                "summary": "All Day",
                                "start": {"date": "2026-01-02"},
                                "end": {"date": "2026-01-03"},
                                "htmlLink": "https://calendar/evt2",
                            },
                            {
                                "id": "evt3",
                                "summary": "Bad",
                                "start": {"dateTime": "bad"},
                                "end": {"dateTime": "bad"},
                            },
                        ],
                        "nextPageToken": "next",
                    },
                )
            assert params and params.get("pageToken") == "next"
            return _FakeResponse(200, {"items": []})

        if method == "GET" and url.endswith("/users/me/calendarList"):
            state["calendar_calls"] += 1
            if state["calendar_calls"] == 1:
                return _FakeResponse(
                    200,
                    {"items": [{"id": "primary"}, {"id": "team"}], "nextPageToken": "next"},
                )
            return _FakeResponse(200, {"items": [{"id": "team"}, {"id": "shared"}]})

        return _FakeResponse(500, {})

    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_handler),
    )

    events = await calendar_service.get_google_events(
        access_token="tok",
        calendar_id="primary",
        time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
        time_max=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    assert {event["id"] for event in events} == {"evt1", "evt2"}
    assert any(event["is_all_day"] for event in events)

    calendar_ids = await calendar_service.list_google_calendar_ids("tok")
    assert calendar_ids == ["primary", "team", "shared"]

    async def _calendar_list_fail(**kwargs):
        del kwargs
        return _FakeResponse(500, {})

    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_calendar_list_fail),
    )
    assert await calendar_service.list_google_calendar_ids("tok") == ["primary"]


@pytest.mark.asyncio
async def test_calendar_user_wrappers_and_appointment_helpers(monkeypatch, db):
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    # Not connected/token-expired wrappers.
    monkeypatch.setattr(
        calendar_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: None,
    )
    not_connected = await calendar_service.get_user_calendar_events(
        db,
        user_id,
        now,
        now + timedelta(hours=1),
    )
    assert not_connected["connected"] is False
    assert not_connected["error"] == "not_connected"

    monkeypatch.setattr(
        calendar_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()),
    )

    async def _no_token(*_args, **_kwargs):
        return None

    monkeypatch.setattr(calendar_service, "get_google_access_token", _no_token)
    expired = await calendar_service.get_user_calendar_events(
        db,
        user_id,
        now,
        now + timedelta(hours=1),
    )
    assert expired["error"] == "token_expired"

    async def _token(*_args, **_kwargs):
        return "tok"

    async def _events(*_args, **kwargs):
        if kwargs.get("calendar_id") == "primary":
            return [
                {"id": "evt1", "start": now, "end": now + timedelta(minutes=30), "summary": "One"}
            ]
        return [{"id": "evt1", "start": now, "end": now + timedelta(minutes=30), "summary": "Dup"}]

    async def _calendar_ids(*_args, **_kwargs):
        return ["primary", "team"]

    monkeypatch.setattr(calendar_service, "get_google_access_token", _token)
    monkeypatch.setattr(calendar_service, "list_google_calendar_ids", _calendar_ids)
    monkeypatch.setattr(calendar_service, "get_google_events", _events)

    across = await calendar_service.get_user_calendar_events_across_calendars(
        db,
        user_id,
        now,
        now + timedelta(hours=1),
    )
    assert across["connected"] is True
    assert len(across["events"]) == 1

    # Appointment helper wrappers.
    async def _event_result(**_kwargs):
        return {"id": "evt1", "summary": "Visit", "start": now, "end": now + timedelta(hours=1)}

    monkeypatch.setattr(calendar_service, "create_google_event", _event_result)
    created = await calendar_service.create_appointment_event(
        db,
        user_id,
        "Visit",
        now,
        now + timedelta(hours=1),
        "client@example.com",
    )
    assert created is not None

    monkeypatch.setattr(calendar_service, "update_google_event", _event_result)
    updated = await calendar_service.update_appointment_event(db, user_id, "evt1", start_time=now)
    assert updated is not None

    async def _delete_event(**_kwargs):
        return True

    monkeypatch.setattr(calendar_service, "delete_google_event", _delete_event)
    deleted = await calendar_service.delete_appointment_event(db, user_id, "evt1")
    assert deleted is True

    monkeypatch.setattr(calendar_service, "get_google_access_token", _no_token)
    with pytest.raises(ValueError, match="Google Calendar not connected"):
        await calendar_service.create_appointment_meet_link(
            db,
            user_id,
            "Meet",
            now,
            now + timedelta(hours=1),
            "client@example.com",
        )
