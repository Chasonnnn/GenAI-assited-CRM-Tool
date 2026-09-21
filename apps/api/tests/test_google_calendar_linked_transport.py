"""Provider contract tests for safe mutations of an existing Google event."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.services import calendar_service


def _transport(monkeypatch, handler):
    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.asyncio
async def test_linked_reschedule_preserves_event_and_requires_observed_version(monkeypatch):
    start = datetime(2026, 10, 2, 15, tzinfo=UTC)
    end = datetime(2026, 10, 2, 16, tzinfo=UTC)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "PATCH"
        assert (
            request.url.path
            == "/calendar/v3/calendars/team@group.calendar.google.com/events/event-123"
        )
        assert request.headers["If-Match"] == '"version-1"'
        assert request.url.params["sendUpdates"] == "all"
        body = json.loads(request.content)
        assert set(body) == {"start", "end"}
        return httpx.Response(200, json={"id": "event-123", "etag": '"version-2"', **body})

    _transport(monkeypatch, handler)
    result = await calendar_service.update_linked_google_event(
        "synthetic-token",
        "team@group.calendar.google.com",
        "event-123",
        etag='"version-1"',
        start=start,
        end=end,
    )
    assert result["id"] == "event-123"
    assert (result["start"], result["end"]) == (start, end)
    assert result["etag"] == '"version-2"'
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["reschedule", "cancel"])
async def test_linked_write_does_not_retry_a_precondition_conflict(monkeypatch, action):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["If-Match"] == '"observed-version"'
        return httpx.Response(412, json={"error": {"code": 412}})

    _transport(monkeypatch, handler)
    with pytest.raises(calendar_service.GoogleEventConflict):
        if action == "cancel":
            await calendar_service.delete_linked_google_event(
                "synthetic-token", "secondary", "existing-event", etag='"observed-version"'
            )
        else:
            await calendar_service.update_linked_google_event(
                "synthetic-token",
                "secondary",
                "existing-event",
                etag='"observed-version"',
                start=datetime(2026, 10, 2, 15, tzinfo=UTC),
                end=datetime(2026, 10, 2, 16, tzinfo=UTC),
            )
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_linked_cancel_uses_exact_calendar_and_notifies_attendees(monkeypatch):
    def handler(request):
        assert request.method == "DELETE"
        assert request.url.path.endswith("/calendars/secondary/events/existing-event")
        assert request.headers["If-Match"] == '"observed-version"'
        assert request.url.params["sendUpdates"] == "all"
        return httpx.Response(204)

    _transport(monkeypatch, handler)
    await calendar_service.delete_linked_google_event(
        "synthetic-token", "secondary", "existing-event", etag='"observed-version"'
    )


@pytest.mark.asyncio
async def test_cancelled_google_tombstone_does_not_require_times(monkeypatch):
    _transport(
        monkeypatch,
        lambda _: httpx.Response(
            200, json={"id": "existing-event", "status": "cancelled", "etag": '"deleted"'}
        ),
    )
    event = await calendar_service.get_linked_google_event(
        "synthetic-token", "secondary", "existing-event"
    )
    assert event["status"] == "cancelled"
    assert event["start"] is None and event["end"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 410])
async def test_missing_google_event_is_distinct_from_access_error(monkeypatch, status):
    _transport(monkeypatch, lambda _: httpx.Response(status))
    assert (
        await calendar_service.get_linked_google_event("synthetic-token", "secondary", "event")
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_event_access_or_provider_failure_is_not_treated_as_deleted(monkeypatch, status):
    _transport(monkeypatch, lambda _: httpx.Response(status))
    with pytest.raises(RuntimeError, match="lookup failed"):
        await calendar_service.get_linked_google_event("synthetic-token", "secondary", "event")


@pytest.mark.asyncio
async def test_writable_calendar_discovery_requires_complete_paginated_result(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.params["minAccessRole"] == "writer"
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "secondary", "accessRole": "writer"},
                        {"id": "readonly", "accessRole": "reader"},
                    ],
                    "nextPageToken": "second-page",
                },
            )
        assert request.url.params["pageToken"] == "second-page"
        return httpx.Response(503)

    _transport(monkeypatch, handler)
    with pytest.raises(calendar_service.CalendarDiscoveryError):
        await calendar_service.list_writable_google_calendar_ids("synthetic-token")
    assert len(calls) == 2
