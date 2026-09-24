"""V2 external-calendar boundary tests."""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.db.enums import AppointmentStatus, JobType, MeetingMode
from app.db.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    CalendarBinding,
    ExternalCalendarEvent,
    Job,
    UserIntegration,
)
from app.schemas.calendar_binding import CalendarBindingInput
from app.services import calendar_binding_service


@pytest.fixture(autouse=True)
def enable_scheduling_v2(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)


@pytest.fixture
def binding(db, test_org, test_user):
    integration = UserIntegration(
        user_id=test_user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="scheduler@example.com",
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        organization_id=test_org.id,
        user_id=test_user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="team-calendar",
        display_name="Team Calendar",
        access_role="owner",
        check_busy=True,
        show_events=True,
        write_bookings=True,
        is_active=True,
    )
    db.add(binding)
    db.commit()
    return binding


@pytest.mark.asyncio
async def test_replace_bindings_switches_existing_booking_destination(
    db, test_org, test_user, binding, monkeypatch
):
    destination = CalendarBinding(
        id=UUID(int=1),
        organization_id=test_org.id,
        user_id=test_user.id,
        integration_id=binding.integration_id,
        account_email=binding.account_email,
        calendar_id="new-booking-calendar",
        display_name="New Booking Calendar",
        access_role="owner",
        timezone="UTC",
        write_bookings=False,
    )
    db.add(destination)
    db.commit()
    assert destination.id < binding.id
    monkeypatch.setattr(
        calendar_binding_service,
        "discover_calendars",
        lambda *_args, **_kwargs: _async_result(
            [
                {
                    "calendar_id": row.calendar_id,
                    "display_name": row.display_name,
                    "access_role": "owner",
                    "timezone": "UTC",
                }
                for row in (binding, destination)
            ]
        ),
    )

    await calendar_binding_service.replace_bindings(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        items=[
            CalendarBindingInput(calendar_id=binding.calendar_id, write_bookings=False),
            CalendarBindingInput(calendar_id=destination.calendar_id, write_bookings=True),
        ],
    )

    db.expire_all()
    selected = calendar_binding_service.get_booking_binding(db, test_org.id, test_user.id)
    assert selected.id == destination.id
    assert binding.is_active
    assert not binding.write_bookings


def _appointment(binding, *, event_id="linked-event"):
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)
    return Appointment(
        organization_id=binding.organization_id,
        user_id=binding.user_id,
        client_name="External calendar QA",
        client_email=f"calendar-{uuid4().hex[:8]}@example.com",
        client_phone="555-0100",
        client_timezone="UTC",
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.PHONE.value,
        status=AppointmentStatus.CONFIRMED.value,
        google_integration_id=binding.integration_id,
        google_account_email=binding.account_email,
        google_calendar_id=binding.calendar_id,
        google_event_id=event_id,
        google_event_etag='"etag-1"',
    )


def _remote_event(*, event_id="linked-event", start=None, end=None):
    start = start or datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)
    end = end or start + timedelta(minutes=30)
    return {
        "id": event_id,
        "etag": '"etag-2"',
        "status": "confirmed",
        "start": start,
        "end": end,
        "calendar_id": "team-calendar",
        "timezone": "UTC",
        "organizer_email": "scheduler@example.com",
        "organizer_self": True,
        "attendee_emails": [],
        "private_properties": {},
        "conference_url": None,
        "conference_pending": False,
        "conference_failed": False,
        "summary": "External event",
        "html_link": "https://calendar.example/events/linked-event",
        "is_all_day": False,
        "start_date": None,
        "end_date": None,
        "is_private": True,
        "is_busy": True,
        "recurring_event_id": None,
        "original_start": None,
    }


@pytest.mark.asyncio
async def test_complete_incremental_sync_projects_events_without_creating_crm_records(
    db, test_org, binding, monkeypatch
):
    from app.services import appointment_google_sync_service, google_scheduling_adapter

    appointment = _appointment(binding)
    db.add(appointment)
    db.commit()
    baseline_appointments = db.query(Appointment).count()
    observed = Mock()
    remote = _remote_event()
    monkeypatch.setattr(appointment_google_sync_service, "observe_remote", observed, raising=False)
    monkeypatch.setattr(
        google_scheduling_adapter,
        "read_incremental_events",
        lambda **_kwargs: _async_result(
            {
                "complete": True,
                "calendar_id": binding.calendar_id,
                "events": [remote],
                "next_sync_token": "cursor-1",
            }
        ),
    )

    changed = await calendar_binding_service.sync_binding(
        db, binding_id=binding.id, org_id=test_org.id
    )

    projection = db.query(ExternalCalendarEvent).filter_by(binding_id=binding.id).one()
    assert changed == 1
    assert db.query(Appointment).count() == baseline_appointments
    assert projection.event_id == appointment.google_event_id
    assert projection.summary == "External event"
    db.refresh(binding)
    assert binding.sync_token == "cursor-1"
    observed.assert_called_once_with(db, appointment, remote)


@pytest.mark.asyncio
async def test_expired_cursor_rebuilds_only_projection_cache_never_cancels_appointment(
    db, test_org, binding, monkeypatch
):
    from app.services import google_scheduling_adapter

    appointment = _appointment(binding)
    binding.sync_token = "expired-cursor"
    db.add_all(
        [
            appointment,
            ExternalCalendarEvent(
                organization_id=test_org.id,
                binding_id=binding.id,
                event_id="old-projection",
                status="confirmed",
                summary="Old event",
                scheduled_start=appointment.scheduled_start,
                scheduled_end=appointment.scheduled_end,
            ),
        ]
    )
    db.commit()
    calls = []

    async def read_incremental_events(**kwargs):
        calls.append(kwargs["sync_token"])
        if kwargs["sync_token"]:
            raise google_scheduling_adapter.GoogleSyncTokenExpired("expired")
        return {
            "complete": True,
            "calendar_id": binding.calendar_id,
            "events": [],
            "next_sync_token": "rebuilt-cursor",
        }

    monkeypatch.setattr(
        google_scheduling_adapter, "read_incremental_events", read_incremental_events
    )
    await calendar_binding_service.sync_binding(db, binding_id=binding.id, org_id=test_org.id)

    db.refresh(appointment)
    db.refresh(binding)
    assert calls == ["expired-cursor", None]
    assert appointment.status == AppointmentStatus.CONFIRMED.value
    assert db.query(ExternalCalendarEvent).filter_by(binding_id=binding.id).count() == 0
    assert binding.sync_token == "rebuilt-cursor"


def test_busy_intervals_fail_closed_then_exclude_exact_linked_copy(db, test_org, binding):
    appointment = _appointment(binding)
    db.add(appointment)
    db.commit()
    with pytest.raises(calendar_binding_service.CalendarAvailabilityUnavailable):
        calendar_binding_service.busy_intervals(
            db,
            test_org.id,
            binding.user_id,
            appointment.scheduled_start,
            appointment.scheduled_end,
        )

    binding.synced_at = datetime.now(UTC)
    db.add(
        ExternalCalendarEvent(
            organization_id=test_org.id,
            binding_id=binding.id,
            event_id=appointment.google_event_id,
            status="confirmed",
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            is_busy=True,
        )
    )
    db.commit()
    assert (
        calendar_binding_service.busy_intervals(
            db,
            test_org.id,
            binding.user_id,
            appointment.scheduled_start,
            appointment.scheduled_end,
            exclude_appointment=appointment,
        )
        == []
    )


def test_busy_intervals_reject_stale_sync_and_include_all_day_calendar_range(db, test_org, binding):
    start = datetime(2026, 9, 24, 12, tzinfo=UTC)
    end = start + timedelta(hours=1)
    binding.timezone = "America/New_York"
    binding.synced_at = datetime.now(UTC) - timedelta(minutes=11)
    db.commit()
    with pytest.raises(calendar_binding_service.CalendarAvailabilityUnavailable):
        calendar_binding_service.busy_intervals(db, test_org.id, binding.user_id, start, end)

    binding.synced_at = datetime.now(UTC)
    db.add(
        ExternalCalendarEvent(
            organization_id=test_org.id,
            binding_id=binding.id,
            event_id="all-day-busy",
            status="confirmed",
            all_day=True,
            start_date=date(2026, 9, 24),
            end_date=date(2026, 9, 25),
            is_busy=True,
        )
    )
    db.commit()

    assert calendar_binding_service.busy_intervals(
        db, test_org.id, binding.user_id, start, end
    ) == [
        (
            datetime(2026, 9, 24, 4, tzinfo=UTC),
            datetime(2026, 9, 25, 4, tzinfo=UTC),
        )
    ]


@pytest.mark.asyncio
async def test_sync_fence_discards_provider_snapshot_after_binding_is_revoked(
    db, test_org, binding, monkeypatch
):
    from app.services import google_scheduling_adapter

    async def read_incremental_events(**_kwargs):
        db.query(CalendarBinding).filter(CalendarBinding.id == binding.id).update(
            {"is_active": False}
        )
        db.commit()
        return {
            "complete": True,
            "calendar_id": binding.calendar_id,
            "events": [_remote_event()],
            "next_sync_token": "cursor-1",
        }

    monkeypatch.setattr(
        google_scheduling_adapter, "read_incremental_events", read_incremental_events
    )
    assert (
        await calendar_binding_service.sync_binding(db, binding_id=binding.id, org_id=test_org.id)
        == 0
    )
    assert db.query(ExternalCalendarEvent).filter_by(binding_id=binding.id).count() == 0


@pytest.mark.asyncio
async def test_sync_deduplicates_repeated_event_ids_before_projection_insert(
    db, test_org, binding, monkeypatch
):
    from app.services import google_scheduling_adapter

    duplicate = _remote_event(event_id="duplicate")
    newer = dict(duplicate, etag='"etag-new"', summary="Newer event")
    monkeypatch.setattr(
        google_scheduling_adapter,
        "read_incremental_events",
        lambda **_kwargs: _async_result(
            {
                "complete": True,
                "calendar_id": binding.calendar_id,
                "events": [duplicate, newer],
                "next_sync_token": "cursor-1",
            }
        ),
    )
    assert (
        await calendar_binding_service.sync_binding(db, binding_id=binding.id, org_id=test_org.id)
        == 1
    )
    projections = db.query(ExternalCalendarEvent).filter_by(binding_id=binding.id).all()
    assert [(projection.event_id, projection.summary) for projection in projections] == [
        ("duplicate", "Newer event")
    ]


@pytest.mark.asyncio
async def test_sync_makes_completed_snapshot_fresh_before_observing_remote(
    db, test_org, binding, monkeypatch
):
    from app.services import google_scheduling_adapter

    start = (datetime.now(UTC) + timedelta(days=14)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    appointment_type = AppointmentType(
        organization_id=test_org.id,
        user_id=binding.user_id,
        name="Inbound sync availability",
        slug=f"inbound-sync-{uuid4().hex[:8]}",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        meeting_mode=MeetingMode.PHONE.value,
        meeting_modes=[MeetingMode.PHONE.value],
        reminder_hours_before=0,
        is_active=True,
    )
    db.add_all(
        [
            appointment_type,
            AvailabilityRule(
                organization_id=test_org.id,
                user_id=binding.user_id,
                day_of_week=start.weekday(),
                start_time=time(8),
                end_time=time(18),
                timezone="UTC",
            ),
        ]
    )
    db.flush()
    appointment = _appointment(binding)
    appointment.appointment_type_id = appointment_type.id
    appointment.scheduled_start = start
    appointment.scheduled_end = start + timedelta(minutes=30)
    appointment.origin = "crm"
    binding.synced_at = datetime.now(UTC) - timedelta(minutes=11)
    binding.sync_error = "sync_fetch_failed"
    db.add(appointment)
    db.flush()
    event_id = google_scheduling_adapter.deterministic_event_id(test_org.id, appointment.id)
    appointment.google_event_id = event_id
    appointment.google_last_synced = {
        "start": appointment.scheduled_start.isoformat(),
        "end": appointment.scheduled_end.isoformat(),
        "status": "confirmed",
        "timezone": "UTC",
        "etag": '"etag-1"',
    }
    appointment.google_event_etag = '"etag-1"'
    db.commit()
    remote_start = start + timedelta(hours=4)
    remote = _remote_event(
        event_id=event_id, start=remote_start, end=remote_start + timedelta(minutes=30)
    )
    remote["private_properties"] = google_scheduling_adapter.ownership_properties(
        test_org.id, appointment.id, binding.id
    )
    remote["attendee_emails"] = [appointment.client_email]
    monkeypatch.setattr(
        google_scheduling_adapter,
        "read_incremental_events",
        lambda **_kwargs: _async_result(
            {
                "complete": True,
                "calendar_id": binding.calendar_id,
                "events": [remote],
                "next_sync_token": "fresh-cursor",
            }
        ),
    )

    assert (
        await calendar_binding_service.sync_binding(db, binding_id=binding.id, org_id=test_org.id)
        == 1
    )
    db.refresh(appointment)
    assert appointment.scheduled_start == remote_start
    assert appointment.google_sync_state == "completed"


@pytest.mark.asyncio
async def test_sync_projects_other_page_events_before_remote_availability_check(
    db, test_org, binding, monkeypatch
):
    from app.services import appointment_google_sync_service, google_scheduling_adapter

    appointment = _appointment(binding)
    db.add(appointment)
    db.commit()
    linked = _remote_event()
    busy = _remote_event(event_id="other-busy")

    def observe(_db, current, _remote):
        assert calendar_binding_service.busy_intervals(
            _db,
            test_org.id,
            current.user_id,
            current.scheduled_start,
            current.scheduled_end,
            exclude_appointment=current,
        ) == [(busy["start"], busy["end"])]

    monkeypatch.setattr(appointment_google_sync_service, "observe_remote", observe)
    monkeypatch.setattr(
        google_scheduling_adapter,
        "read_incremental_events",
        lambda **_kwargs: _async_result(
            {
                "complete": True,
                "calendar_id": binding.calendar_id,
                "events": [linked, busy],
                "next_sync_token": "complete-page",
            }
        ),
    )

    assert (
        await calendar_binding_service.sync_binding(db, binding_id=binding.id, org_id=test_org.id)
        == 2
    )


def test_v2_scheduler_queues_explicit_binding_sync_and_retains_tasks(db, binding):
    from app.services import google_calendar_sync_service

    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    counts = google_calendar_sync_service.schedule_google_calendar_sync_jobs(db, now=now)
    jobs = db.query(Job).all()

    assert counts == {
        "connected_users": 1,
        "jobs_created": 1,
        "duplicates_skipped": 0,
        "task_jobs_created": 1,
        "task_duplicates_skipped": 0,
        "watch_jobs_created": 1,
        "watch_duplicates_skipped": 0,
    }
    assert {
        (job.job_type, job.payload.get("binding_id"))
        for job in jobs
        if job.job_type
        in {JobType.GOOGLE_CALENDAR_SYNC.value, JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value}
    } == {
        (JobType.GOOGLE_CALENDAR_SYNC.value, str(binding.id)),
        (JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value, str(binding.id)),
    }
    task = next(job for job in jobs if job.job_type == JobType.GOOGLE_TASKS_SYNC.value)
    assert task.payload == {"user_id": str(binding.user_id)}

    duplicate_counts = google_calendar_sync_service.schedule_google_calendar_sync_jobs(db, now=now)
    assert duplicate_counts["jobs_created"] == 0
    assert duplicate_counts["duplicates_skipped"] == 1
    assert duplicate_counts["watch_jobs_created"] == 0
    assert duplicate_counts["watch_duplicates_skipped"] == 1
    assert duplicate_counts["task_jobs_created"] == 0
    assert duplicate_counts["task_duplicates_skipped"] == 1


async def _async_result(value):
    return value
