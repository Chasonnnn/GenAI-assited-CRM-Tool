import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db.models import Appointment


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
@pytest.mark.parametrize("snapshot_has_event", [True, False])
async def test_importer_fences_pending_managed_google_edit(
    db, test_auth, monkeypatch, snapshot_has_event
):
    from app.services import appointment_integrations, calendar_service

    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)
    appointment = Appointment(
        organization_id=test_auth.org.id,
        user_id=test_auth.user.id,
        appointment_type_id=None,
        client_name="Linked interview",
        client_email="client@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode="phone",
        status="confirmed",
        google_event_id="managed-google-event",
        google_calendar_id="qa-interviews@group.calendar.google.com",
        google_sync_revision=1,
        google_sync_state="pending",
    )
    db.add(appointment)
    db.commit()

    async def calendars(**_kwargs):
        return ["qa-interviews@group.calendar.google.com"]

    async def events(**_kwargs):
        return {
            "connected": True,
            "error": None,
            "complete": True,
            "events": [
                {
                    "id": "managed-google-event",
                    "summary": "Old Google snapshot",
                    "start": start - timedelta(hours=1),
                    "end": start - timedelta(minutes=30),
                }
            ]
            if snapshot_has_event
            else [],
        }

    monkeypatch.setattr(calendar_service, "list_user_google_calendar_ids", calendars)
    monkeypatch.setattr(calendar_service, "get_user_calendar_events", events)
    changed = await appointment_integrations.sync_manual_google_events_for_appointments_async(
        db, user_id=test_auth.user.id, org_id=test_auth.org.id, strict=True
    )

    db.refresh(appointment)
    assert changed == 0
    assert appointment.status == "confirmed"
    assert appointment.scheduled_start == start
    assert appointment.meeting_mode == "phone"


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


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", ["other_org", "inactive_membership", "inactive_user"])
async def test_google_tasks_sync_job_rejects_user_outside_exact_active_membership(
    db,
    test_auth,
    monkeypatch,
    denial,
):
    from app.db.models import Membership
    from app.jobs.handlers import appointments as appointments_handler

    called = False
    org_id = test_auth.org.id
    if denial == "other_org":
        org_id = uuid.uuid4()
    elif denial == "inactive_membership":
        membership = (
            db.query(Membership).filter_by(organization_id=org_id, user_id=test_auth.user.id).one()
        )
        membership.is_active = False
    else:
        test_auth.user.is_active = False
    db.flush()

    async def fake_get_access_token_async(*_args, **_kwargs):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr(
        "app.services.oauth_service.get_access_token_async",
        fake_get_access_token_async,
    )
    job = type(
        "Job",
        (),
        {
            "id": uuid.uuid4(),
            "organization_id": org_id,
            "payload": {"user_id": str(test_auth.user.id)},
        },
    )()

    with pytest.raises(ValueError, match="no active membership"):
        await appointments_handler.process_google_tasks_sync(db, job)

    assert called is False


@pytest.mark.asyncio
async def test_google_tasks_sync_job_propagates_timeout_for_worker_retry(
    db, test_auth, monkeypatch
):
    from app.jobs.handlers import appointments as appointments_handler

    async def timeout(*_args, **_kwargs):
        raise RuntimeError("Google Tasks sync failed (TimeoutError)")

    monkeypatch.setattr(
        "app.services.google_tasks_sync_service.sync_google_tasks_for_user_async", timeout
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
    with pytest.raises(RuntimeError, match="Google Tasks sync failed"):
        await appointments_handler.process_google_tasks_sync(db, job)
