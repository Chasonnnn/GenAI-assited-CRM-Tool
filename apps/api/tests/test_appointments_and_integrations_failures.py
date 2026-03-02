from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import AppointmentStatus, MeetingMode
from app.db.models import Appointment, AppointmentType
from app.services import appointment_integrations, appointment_service


def _create_appointment_type(db, org_id, user_id) -> AppointmentType:
    appt_type = AppointmentType(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        slug=f"consult-{uuid4().hex[:6]}",
        name="Consult",
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        meeting_modes=[MeetingMode.ZOOM.value, MeetingMode.GOOGLE_MEET.value],
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()
    return appt_type


def _create_appointment(db, org_id, user_id, appt_type_id=None, *, status=AppointmentStatus.CONFIRMED.value):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    appt = Appointment(
        id=uuid4(),
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appt_type_id,
        client_name="Client",
        client_email="client@example.com",
        client_phone="555-111-2222",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=status,
    )
    db.add(appt)
    db.flush()
    return appt


def test_appointment_service_helper_paths():
    assert appointment_service.generate_slug("Initial Consultation!") == "initial-consultation"
    assert appointment_service.generate_token()
    assert appointment_service.generate_public_slug()

    appointment_service.validate_timezone_name("UTC")
    with pytest.raises(ValueError, match="Invalid timezone"):
        appointment_service.validate_timezone_name("Not/AZone")

    modes, default_mode = appointment_service._normalize_meeting_modes(None, MeetingMode.ZOOM.value)
    assert modes == [MeetingMode.ZOOM.value]
    assert default_mode == MeetingMode.ZOOM.value

    modes, default_mode = appointment_service._normalize_meeting_modes(
        [MeetingMode.ZOOM.value, MeetingMode.GOOGLE_MEET.value, MeetingMode.ZOOM.value],
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
    )
    assert modes == [MeetingMode.ZOOM.value, MeetingMode.GOOGLE_MEET.value]
    assert default_mode == MeetingMode.GOOGLE_MEET.value

    modes, default_mode = appointment_service._normalize_meeting_modes([], meeting_mode=None)
    assert modes == [MeetingMode.ZOOM.value]
    assert default_mode == MeetingMode.ZOOM.value

    normalized = appointment_service._normalize_scheduled_start(
        datetime(2026, 1, 1, 10, 0, 0),
        "America/New_York",
    )
    assert normalized.tzinfo == timezone.utc


def test_appointment_type_create_update_and_invalid_mode(db, test_org, test_user):
    created = appointment_service.create_appointment_type(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Intake Visit",
        meeting_mode=MeetingMode.ZOOM.value,
        meeting_modes=[MeetingMode.ZOOM.value, MeetingMode.GOOGLE_MEET.value],
    )
    assert created.id is not None
    assert created.slug.startswith("intake-visit")

    updated = appointment_service.update_appointment_type(
        db=db,
        appt_type=created,
        name="Intake Visit Updated",
        meeting_modes=[MeetingMode.GOOGLE_MEET.value],
        meeting_mode=MeetingMode.GOOGLE_MEET.value,
    )
    assert updated.meeting_mode == MeetingMode.GOOGLE_MEET.value
    assert updated.meeting_modes == [MeetingMode.GOOGLE_MEET.value]

    with pytest.raises(ValueError, match="Meeting mode not available"):
        appointment_service.update_appointment_type(
            db=db,
            appt_type=created,
            meeting_mode=MeetingMode.ZOOM.value,
            meeting_modes=None,
        )


def test_appointment_integrations_run_async_wrapper(monkeypatch):
    async def _ok():
        return "ok"

    def _run_ok(coro, timeout=30):
        del timeout
        coro.close()
        return "ok"

    def _run_fail(coro, timeout=30):
        del timeout
        coro.close()
        raise RuntimeError("fail")

    monkeypatch.setattr(appointment_integrations, "run_async", _run_ok)
    assert appointment_integrations._run_async(_ok()) == "ok"
    monkeypatch.setattr(appointment_integrations, "run_async", _run_fail)
    assert appointment_integrations._run_async(_ok()) is None


@pytest.mark.asyncio
async def test_appointment_integrations_await_async_wrapper():
    async def _ok():
        return "ok"

    async def _explode():
        raise RuntimeError("fail")

    assert await appointment_integrations._await_async(_ok()) == "ok"
    assert await appointment_integrations._await_async(_explode()) is None


def test_sync_to_google_calendar_create_update_delete_branches(db, test_org, test_user, monkeypatch):
    appt_type = _create_appointment_type(db, test_org.id, test_user.id)
    appointment = _create_appointment(db, test_org.id, test_user.id, appt_type.id)

    created_calls: list[dict] = []
    updated_calls: list[dict] = []
    deleted_calls: list[dict] = []

    async def _create_event(**kwargs):
        created_calls.append(kwargs)
        return {"id": "evt_1"}

    async def _update_event(**kwargs):
        updated_calls.append(kwargs)
        return {"id": kwargs["event_id"]}

    async def _delete_event(**kwargs):
        deleted_calls.append(kwargs)
        return True

    monkeypatch.setattr("app.services.calendar_service.create_appointment_event", _create_event)
    monkeypatch.setattr("app.services.calendar_service.update_appointment_event", _update_event)
    monkeypatch.setattr("app.services.calendar_service.delete_appointment_event", _delete_event)

    created_event_id = appointment_integrations.sync_to_google_calendar(db, appointment, "create")
    assert created_event_id == "evt_1"
    assert created_calls

    # Update path with missing google_event_id should no-op.
    appointment.google_event_id = None
    assert appointment_integrations.sync_to_google_calendar(db, appointment, "update") is None

    appointment.google_event_id = "evt_1"
    updated_event_id = appointment_integrations.sync_to_google_calendar(db, appointment, "update")
    assert updated_event_id == "evt_1"
    assert updated_calls

    assert appointment_integrations.sync_to_google_calendar(db, appointment, "delete") is None
    assert deleted_calls


def test_backfill_confirmed_appointments_and_sync_wrapper(db, test_org, test_user, monkeypatch):
    appt_type = _create_appointment_type(db, test_org.id, test_user.id)
    appt = _create_appointment(db, test_org.id, test_user.id, appt_type.id, status=AppointmentStatus.CONFIRMED.value)
    appt.google_event_id = None
    db.commit()

    monkeypatch.setattr(
        "app.services.calendar_service.check_user_has_google_calendar",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(appointment_integrations, "sync_to_google_calendar", lambda *_args, **_kwargs: "evt_backfill")

    updated = appointment_integrations.backfill_confirmed_appointments_to_google(
        db,
        user_id=test_user.id,
        org_id=test_org.id,
        date_start=date.today(),
        date_end=date.today() + timedelta(days=2),
    )
    assert updated == 1
    assert appt.google_event_id == "evt_backfill"

    monkeypatch.setattr(
        appointment_integrations,
        "run_async",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    wrapped = appointment_integrations.sync_manual_google_events_for_appointments(
        db,
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert wrapped == 0


@pytest.mark.asyncio
async def test_sync_manual_google_events_async_reconcile_paths(db, test_org, test_user, monkeypatch):
    existing = _create_appointment(db, test_org.id, test_user.id, None, status=AppointmentStatus.CONFIRMED.value)
    existing.google_event_id = "evt_old"
    db.commit()

    async def _calendar_ids(**_kwargs):
        return ["primary"]

    async def _calendar_events(**_kwargs):
        start = datetime.now(timezone.utc) + timedelta(hours=2)
        return {
            "connected": True,
            "events": [
                {"id": "evt_new", "summary": "Manual Event", "start": start, "end": start + timedelta(minutes=45), "is_all_day": False},
                {"id": "evt_all_day", "summary": "All Day", "start": start, "end": start + timedelta(days=1), "is_all_day": True},
            ],
            "error": None,
        }

    monkeypatch.setattr("app.services.calendar_service.list_user_google_calendar_ids", _calendar_ids)
    monkeypatch.setattr("app.services.calendar_service.get_user_calendar_events", _calendar_events)

    changed = await appointment_integrations._sync_manual_google_events_for_appointments_async(
        db,
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert changed >= 1
    db.refresh(existing)
    assert existing.status in {AppointmentStatus.CANCELLED.value, AppointmentStatus.CONFIRMED.value}

    async def _not_connected(**_kwargs):
        return {"connected": False, "events": [], "error": "not_connected"}

    monkeypatch.setattr("app.services.calendar_service.get_user_calendar_events", _not_connected)
    changed_none = await appointment_integrations._sync_manual_google_events_for_appointments_async(
        db,
        user_id=test_user.id,
        org_id=test_org.id,
    )
    assert changed_none == 0


def test_zoom_and_google_meet_creation_failure_paths(monkeypatch):
    appointment = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        client_name="Client",
        client_email="client@example.com",
        client_timezone="UTC",
        scheduled_start=datetime.now(timezone.utc),
        scheduled_end=datetime.now(timezone.utc) + timedelta(minutes=30),
        duration_minutes=30,
        zoom_meeting_id=None,
        zoom_join_url=None,
        google_event_id=None,
        google_meet_url=None,
    )

    monkeypatch.setattr("app.services.zoom_service.check_user_has_zoom", lambda *_args, **_kwargs: False)
    with pytest.raises(ValueError, match="Zoom not connected"):
        appointment_integrations.create_zoom_meeting(SimpleNamespace(), appointment, "Consult")

    monkeypatch.setattr("app.services.zoom_service.check_user_has_zoom", lambda *_args, **_kwargs: True)

    def _run_none(coro):
        coro.close()
        return None

    monkeypatch.setattr(appointment_integrations, "_run_async", _run_none)
    with pytest.raises(ValueError, match="Failed to get Zoom access token"):
        appointment_integrations.create_zoom_meeting(SimpleNamespace(), appointment, "Consult")

    monkeypatch.setattr(
        "app.services.calendar_service.check_user_has_google_calendar",
        lambda *_args, **_kwargs: False,
    )
    with pytest.raises(ValueError, match="Google Calendar not connected"):
        appointment_integrations.create_google_meet_link(SimpleNamespace(), appointment, "Consult")

    monkeypatch.setattr(
        "app.services.calendar_service.check_user_has_google_calendar",
        lambda *_args, **_kwargs: True,
    )
    def _run_meet(coro):
        coro.close()
        return {"event_id": "evt_1", "meet_url": "https://meet.google.com/abc"}

    monkeypatch.setattr(appointment_integrations, "_run_async", _run_meet)
    appointment_integrations.create_google_meet_link(SimpleNamespace(), appointment, "Consult")
    assert appointment.google_event_id == "evt_1"
    assert appointment.google_meet_url.startswith("https://meet.google.com/")

    def _run_raise(coro):
        coro.close()
        raise RuntimeError("boom")

    monkeypatch.setattr(appointment_integrations, "_run_async", _run_raise)
    # These should not raise.
    appointment_integrations.regenerate_zoom_meeting_on_reschedule(
        SimpleNamespace(), appointment, "Consult", datetime.now(timezone.utc) + timedelta(days=1)
    )
    appointment_integrations.delete_zoom_meeting(SimpleNamespace(), appointment)
