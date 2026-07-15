import uuid

import httpx
import pytest


@pytest.mark.asyncio
async def test_google_calendar_sync_job_handler_invokes_reconciler(db, test_auth, monkeypatch):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_sync_manual_google_events_for_appointments_async(
        db,
        *,
        user_id,
        org_id,
        date_start=None,
        date_end=None,
        strict=False,
    ):
        called["user_id"] = user_id
        called["org_id"] = org_id
        called["date_start"] = date_start
        called["date_end"] = date_end
        called["strict"] = strict
        return 2

    monkeypatch.setattr(
        "app.services.appointment_integrations.sync_manual_google_events_for_appointments_async",
        fake_sync_manual_google_events_for_appointments_async,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_calendar_sync(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["org_id"] == test_auth.org.id
    assert called["date_start"] is None
    assert called["date_end"] is None
    assert called["strict"] is True


@pytest.mark.asyncio
async def test_google_calendar_sync_job_handler_propagates_incomplete_sync(
    db, test_auth, monkeypatch
):
    from app.jobs.handlers import appointments as appointments_handler
    from app.services import appointment_integrations, calendar_service

    request = httpx.Request("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList")

    async def fail_calendar_discovery(**_kwargs):
        raise httpx.ReadTimeout("calendar discovery unavailable", request=request)

    monkeypatch.setattr(
        calendar_service,
        "list_user_google_calendar_ids",
        fail_calendar_discovery,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    with pytest.raises(
        appointment_integrations.CalendarSyncIncompleteError,
        match="Google Calendar discovery incomplete",
    ):
        await appointments_handler.process_google_calendar_sync(db, job)


@pytest.mark.asyncio
async def test_google_calendar_sync_job_handler_propagates_incomplete_event_snapshot(
    db, test_auth, monkeypatch
):
    from app.jobs.handlers import appointments as appointments_handler
    from app.services import appointment_integrations, calendar_service

    async def calendar_ids(**_kwargs):
        return ["primary"]

    async def incomplete_events(**_kwargs):
        return {
            "connected": True,
            "events": [],
            "error": "incomplete",
            "complete": False,
        }

    monkeypatch.setattr(calendar_service, "list_user_google_calendar_ids", calendar_ids)
    monkeypatch.setattr(calendar_service, "get_user_calendar_events", incomplete_events)

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    with pytest.raises(
        appointment_integrations.CalendarSyncIncompleteError,
        match="Google Calendar event snapshot incomplete",
    ):
        await appointments_handler.process_google_calendar_sync(db, job)


@pytest.mark.asyncio
async def test_google_calendar_watch_refresh_job_handler_invokes_watch_ensure(
    db, test_auth, monkeypatch
):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_ensure_google_calendar_watch(*, db, user_id, calendar_id="primary"):
        called["user_id"] = user_id
        called["calendar_id"] = calendar_id
        return True

    monkeypatch.setattr(
        "app.services.calendar_service.ensure_google_calendar_watch",
        fake_ensure_google_calendar_watch,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_calendar_watch_refresh(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["calendar_id"] == "primary"


@pytest.mark.asyncio
async def test_google_tasks_sync_job_handler_invokes_reconciler(db, test_auth, monkeypatch):
    from app.jobs.handlers import appointments as appointments_handler

    called: dict[str, object] = {}

    async def fake_sync_google_tasks_for_user_async(db, *, user_id, org_id):
        called["user_id"] = user_id
        called["org_id"] = org_id
        return 3

    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.sync_google_tasks_for_user_async",
        fake_sync_google_tasks_for_user_async,
    )

    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": test_auth.org.id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    await appointments_handler.process_google_tasks_sync(db, job)

    assert called["user_id"] == test_auth.user.id
    assert called["org_id"] == test_auth.org.id
