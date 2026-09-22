"""Google v2 transport never guesses resource identity or a partial cursor."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.services import google_scheduling_adapter as adapter


def _transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        adapter.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def _event(event_id, props, *, etag='"v1"'):
    return {
        "id": event_id,
        "etag": etag,
        "status": "confirmed",
        "start": {"dateTime": "2026-10-01T12:00:00Z"},
        "end": {"dateTime": "2026-10-01T12:30:00Z"},
        "organizer": {"email": "team@group.calendar.google.com"},
        "attendees": [{"email": "client@example.com"}],
        "extendedProperties": {"private": props},
        "conferenceData": {"createRequest": {"status": {"statusCode": "pending"}}},
    }


@pytest.mark.asyncio
async def test_insert_uses_stable_google_id_private_ownership_and_one_meet_request(monkeypatch):
    org_id, appointment_id, binding_id = uuid4(), uuid4(), uuid4()
    event_id = adapter.deterministic_event_id(org_id, appointment_id)
    assert event_id == adapter.deterministic_event_id(org_id, appointment_id)
    assert event_id.isalnum() and set(event_id) <= set("0123456789abcdefghijklmnopqrstuv")
    props = adapter.ownership_properties(org_id, appointment_id, binding_id)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "POST"
        assert request.url.raw_path.split(b"?")[0].endswith(
            b"/calendars/team%40group.calendar.google.com/events"
        )
        assert request.url.params["sendUpdates"] == "all"
        assert request.url.params["conferenceDataVersion"] == "1"
        body = json.loads(request.content)
        assert body["id"] == event_id
        assert body["extendedProperties"]["private"] == props
        assert body["visibility"] == "private"
        assert body["attendees"] == [{"email": "client@example.com"}]
        assert body["conferenceData"]["createRequest"]["requestId"] == event_id + "meet"
        return httpx.Response(201, json=_event(event_id, props))

    _transport(monkeypatch, handler)
    result = await adapter.insert_event(
        "synthetic-token",
        "team@group.calendar.google.com",
        event_id=event_id,
        organization_id=org_id,
        appointment_id=appointment_id,
        binding_id=binding_id,
        start=datetime(2026, 10, 1, 12, tzinfo=UTC),
        end=datetime(2026, 10, 1, 12, 30, tzinfo=UTC),
        timezone_name="UTC",
        client_email="client@example.com",
    )
    assert len(calls) == 1
    assert result["conference_pending"] is True
    assert adapter.owns_event(
        result,
        organization_id=org_id,
        appointment_id=appointment_id,
        binding_id=binding_id,
        event_id=event_id,
        calendar_id="team@group.calendar.google.com",
        client_email="client@example.com",
    )


@pytest.mark.asyncio
async def test_insert_collision_never_adopts_without_exact_read(monkeypatch):
    _transport(monkeypatch, lambda _request: httpx.Response(409))
    with pytest.raises(adapter.GoogleResourceCollision):
        await adapter.insert_event(
            "token",
            "secondary",
            event_id="crm123456",
            organization_id=uuid4(),
            appointment_id=uuid4(),
            binding_id=uuid4(),
            start=datetime(2026, 10, 1, 12, tzinfo=UTC),
            end=datetime(2026, 10, 1, 13, tzinfo=UTC),
            timezone_name="UTC",
            client_email="client@example.com",
        )


@pytest.mark.asyncio
async def test_phone_event_uses_explicit_calendar_without_conference(monkeypatch):
    org_id, appointment_id, binding_id = uuid4(), uuid4(), uuid4()
    event_id = adapter.deterministic_event_id(org_id, appointment_id)
    props = adapter.ownership_properties(org_id, appointment_id, binding_id)

    def handler(request):
        body = json.loads(request.content)
        assert body["id"] == event_id
        assert "conferenceData" not in body
        assert "conferenceDataVersion" not in request.url.params
        assert request.url.params["sendUpdates"] == "all"
        response = _event(event_id, props)
        response.pop("conferenceData")
        return httpx.Response(201, json=response)

    _transport(monkeypatch, handler)
    result = await adapter.insert_event(
        "synthetic-token",
        "team@group.calendar.google.com",
        event_id=event_id,
        organization_id=org_id,
        appointment_id=appointment_id,
        binding_id=binding_id,
        start=datetime(2026, 10, 1, 12, tzinfo=UTC),
        end=datetime(2026, 10, 1, 12, 30, tzinfo=UTC),
        timezone_name="UTC",
        client_email="client@example.com",
        create_meet=False,
    )
    assert result["conference_pending"] is False


@pytest.mark.asyncio
async def test_writable_check_requires_exact_selected_calendar(monkeypatch):
    def handler(request):
        assert request.url.raw_path.endswith(b"/team%40group.calendar.google.com")
        return httpx.Response(
            200, json={"id": "team@group.calendar.google.com", "accessRole": "writer"}
        )

    _transport(monkeypatch, handler)
    assert await adapter.verify_writable_calendar(
        "synthetic-token", "team@group.calendar.google.com"
    )


@pytest.mark.asyncio
async def test_discovery_keeps_missing_timezone_unknown(monkeypatch):
    _transport(
        monkeypatch,
        lambda _request: httpx.Response(
            200,
            json={"items": [{"id": "secondary", "summary": "Interviews", "accessRole": "owner"}]},
        ),
    )

    async def token(_db, _user_id):
        return "synthetic-token"

    monkeypatch.setattr(adapter.calendar_service, "get_google_access_token", token)
    calendars = await adapter.discover_calendars(None, uuid4())
    assert calendars[0]["timezone"] is None


@pytest.mark.asyncio
async def test_conditional_update_and_delete_require_exact_etag(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["If-Match"] == '"v1"'
        assert request.url.path.endswith("/calendars/secondary/events/crm123456")
        return httpx.Response(412)

    _transport(monkeypatch, handler)
    with pytest.raises(adapter.GooglePreconditionFailed):
        await adapter.patch_interval(
            "token",
            "secondary",
            "crm123456",
            etag='"v1"',
            start=datetime(2026, 10, 1, 12, tzinfo=UTC),
            end=datetime(2026, 10, 1, 13, tzinfo=UTC),
            timezone_name="UTC",
        )
    with pytest.raises(adapter.GooglePreconditionFailed):
        await adapter.delete_event("token", "secondary", "crm123456", etag='"v1"')
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_failed_meet_retry_patches_same_event_conditionally(monkeypatch):
    event_id = "crm123456"

    def handler(request):
        assert request.method == "PATCH"
        assert request.url.path.endswith(f"/calendars/secondary/events/{event_id}")
        assert request.headers["If-Match"] == '"v1"'
        assert request.url.params["conferenceDataVersion"] == "1"
        body = json.loads(request.content)
        assert body["conferenceData"]["createRequest"]["requestId"] == "crm123456meet2"
        return httpx.Response(412)

    _transport(monkeypatch, handler)
    with pytest.raises(adapter.GooglePreconditionFailed):
        await adapter.request_meet_conference(
            "synthetic-token",
            "secondary",
            event_id,
            etag='"v1"',
            request_id="crm123456meet2",
        )


@pytest.mark.asyncio
async def test_incremental_snapshot_requires_last_page_cursor(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.params["showDeleted"] == "true"
        assert request.url.params["syncToken"] == "old-token"
        if len(requests) == 1:
            return httpx.Response(
                200, json={"items": [{"id": "gone", "status": "cancelled"}], "nextPageToken": "p2"}
            )
        assert request.url.params["pageToken"] == "p2"
        return httpx.Response(200, json={"items": [], "nextSyncToken": "new-token"})

    _transport(monkeypatch, handler)

    async def token(_db, _user_id):
        return "synthetic-token"

    monkeypatch.setattr(adapter.calendar_service, "get_google_access_token", token)
    result = await adapter.read_incremental_events(None, uuid4(), "secondary", "old-token")
    assert result["next_sync_token"] == "new-token"
    assert result["events"][0]["id"] == "gone"
    assert result["events"][0]["etag"] == ""
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_expired_cursor_is_distinct_from_incomplete_snapshot(monkeypatch):
    async def token(_db, _user_id):
        return "synthetic-token"

    monkeypatch.setattr(adapter.calendar_service, "get_google_access_token", token)
    _transport(monkeypatch, lambda _request: httpx.Response(410))
    with pytest.raises(adapter.GoogleSyncTokenExpired):
        await adapter.read_incremental_events(None, uuid4(), "secondary", "old-token")
