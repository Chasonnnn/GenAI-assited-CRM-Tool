"""Two-session locking regression coverage for inbound calendar changes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from threading import Event
from time import sleep
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.db.enums import AppointmentStatus, MeetingMode, Role
from app.db.models import (
    Appointment,
    AppointmentType,
    AuditLog,
    AvailabilityRule,
    CalendarBinding,
    Membership,
    Organization,
    User,
    UserIntegration,
)
from app.db.session import SessionLocal
from app.services import calendar_binding_service, scheduling_v2_service


def _future_weekday(hour: int) -> datetime:
    value = (datetime.now(UTC) + timedelta(days=7)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    while value.weekday() > 4:
        value += timedelta(days=1)
    return value


@dataclass(frozen=True)
class InboundRaceFixture:
    organization_id: UUID
    user_id: UUID
    appointment_id: UUID
    appointment_type_id: UUID
    binding_id: UUID
    original_start: datetime
    target_start: datetime
    event_id: str


@pytest.fixture(autouse=True)
def enable_scheduling_v2(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)


@pytest.fixture
def committed_inbound_race(db_engine):
    """Committed, uniquely identified rows visible to two real database sessions."""
    org_id, user_id, appointment_id, appointment_type_id, binding_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    original_start = _future_weekday(10)
    target_start = original_start.replace(hour=14)
    event_id = f"inbound-race-{appointment_id.hex}"
    try:
        with SessionLocal(bind=db_engine) as db:
            organization = Organization(
                id=org_id,
                name="Inbound scheduling race QA",
                slug=f"inbound-race-{org_id.hex}",
                timezone="UTC",
            )
            user = User(
                id=user_id,
                email=f"inbound-race-{user_id.hex}@example.test",
                display_name="Inbound scheduling owner",
                is_active=True,
            )
            db.add_all([organization, user])
            db.flush()
            db.add(
                Membership(
                    user_id=user_id,
                    organization_id=org_id,
                    role=Role.DEVELOPER.value,
                )
            )
            appointment_type = AppointmentType(
                id=appointment_type_id,
                organization_id=org_id,
                user_id=user_id,
                name="Inbound race appointment",
                slug=f"inbound-race-{appointment_type_id.hex[:12]}",
                duration_minutes=30,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                meeting_mode=MeetingMode.PHONE.value,
                meeting_modes=[MeetingMode.PHONE.value],
                reminder_hours_before=0,
                is_active=True,
            )
            integration = UserIntegration(
                user_id=user_id,
                integration_type="google_calendar",
                access_token_encrypted="synthetic-not-used",
                account_email=f"inbound-race-{user_id.hex}@example.test",
            )
            db.add_all(
                [
                    appointment_type,
                    integration,
                    AvailabilityRule(
                        organization_id=org_id,
                        user_id=user_id,
                        day_of_week=target_start.weekday(),
                        start_time=time(8),
                        end_time=time(18),
                        timezone="UTC",
                    ),
                ]
            )
            db.flush()
            binding = CalendarBinding(
                id=binding_id,
                organization_id=org_id,
                user_id=user_id,
                integration_id=integration.id,
                account_email=integration.account_email,
                calendar_id="inbound-race-calendar",
                display_name="Inbound race calendar",
                access_role="owner",
                timezone="UTC",
                check_busy=False,
                show_events=False,
                write_bookings=True,
                is_active=True,
            )
            appointment = Appointment(
                id=appointment_id,
                organization_id=org_id,
                user_id=user_id,
                appointment_type_id=appointment_type_id,
                client_name="Existing client",
                client_email=f"existing-{appointment_id.hex}@example.test",
                client_phone="555-0100",
                client_timezone="UTC",
                scheduled_start=original_start,
                scheduled_end=original_start + timedelta(minutes=30),
                duration_minutes=30,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                meeting_mode=MeetingMode.PHONE.value,
                status=AppointmentStatus.CONFIRMED.value,
                origin="crm",
                revision=1,
                google_integration_id=integration.id,
                google_account_email=integration.account_email,
                google_calendar_id=binding.calendar_id,
                google_event_id=event_id,
                google_event_etag='"etag-original"',
                google_sync_revision=1,
                google_sync_state="completed",
                google_last_synced={
                    "start": original_start.isoformat(),
                    "end": (original_start + timedelta(minutes=30)).isoformat(),
                    "status": AppointmentStatus.CONFIRMED.value,
                    "timezone": "UTC",
                    "etag": '"etag-original"',
                },
            )
            db.add_all([binding, appointment])
            db.commit()
        yield InboundRaceFixture(
            organization_id=org_id,
            user_id=user_id,
            appointment_id=appointment_id,
            appointment_type_id=appointment_type_id,
            binding_id=binding_id,
            original_start=original_start,
            target_start=target_start,
            event_id=event_id,
        )
    finally:
        with SessionLocal(bind=db_engine) as db:
            db.execute(text("SET LOCAL session_replication_role = replica"))
            for model in (
                AuditLog,
                Appointment,
                CalendarBinding,
                AppointmentType,
                AvailabilityRule,
                UserIntegration,
                Membership,
                Organization,
                User,
            ):
                if model is User:
                    db.query(model).filter(model.id == user_id).delete(synchronize_session=False)
                elif model is Organization:
                    db.query(model).filter(model.id == org_id).delete(synchronize_session=False)
                elif hasattr(model, "organization_id"):
                    db.query(model).filter(model.organization_id == org_id).delete(
                        synchronize_session=False
                    )
            db.execute(text("SET LOCAL session_replication_role = origin"))
            db.commit()


def _remote_event(fixture: InboundRaceFixture) -> dict:
    end = fixture.target_start + timedelta(minutes=30)
    return {
        "id": fixture.event_id,
        "etag": '"etag-external"',
        "status": "confirmed",
        "start": fixture.target_start,
        "end": end,
        "calendar_id": "inbound-race-calendar",
        "timezone": "UTC",
        "organizer_email": f"inbound-race-{fixture.user_id.hex}@example.test",
        "organizer_self": True,
        "attendee_emails": [f"existing-{fixture.appointment_id.hex}@example.test"],
        "private_properties": {
            "crm_organization_id": str(fixture.organization_id),
            "crm_appointment_id": str(fixture.appointment_id),
            "crm_binding_id": str(fixture.binding_id),
            "crm_scheduling_version": "2",
        },
        "conference_url": None,
        "conference_pending": False,
        "conference_failed": False,
        "summary": "Synthetic inbound move",
        "html_link": None,
        "is_all_day": False,
        "start_date": None,
        "end_date": None,
        "is_private": True,
        "is_busy": True,
        "recurring_event_id": None,
        "original_start": None,
    }


def test_inbound_move_serializes_before_concurrent_staff_booking(
    db_engine, committed_inbound_race, monkeypatch
):
    """A staff create cannot commit the slot while inbound reconciliation owns it."""
    from app.services import appointment_google_sync_service, google_scheduling_adapter

    fixture = committed_inbound_race
    remote = _remote_event(fixture)
    inbound_holds_owner = Event()
    release_inbound = Event()
    staff_started = Event()
    original_observe = appointment_google_sync_service.observe_remote

    async def read_incremental_events(**_kwargs):
        return {
            "complete": True,
            "calendar_id": remote["calendar_id"],
            "events": [remote],
            "next_sync_token": "inbound-race-cursor",
        }

    def hold_owner_lock(db, appointment, observed_remote):
        inbound_holds_owner.set()
        assert release_inbound.wait(10), "staff operation did not reach the owner lock"
        return original_observe(db, appointment, observed_remote)

    monkeypatch.setattr(
        google_scheduling_adapter, "read_incremental_events", read_incremental_events
    )
    monkeypatch.setattr(appointment_google_sync_service, "observe_remote", hold_owner_lock)

    def apply_inbound():
        with SessionLocal(bind=db_engine) as db:
            return asyncio.run(
                calendar_binding_service.sync_binding(
                    db, binding_id=fixture.binding_id, org_id=fixture.organization_id
                )
            )

    def create_staff_booking():
        staff_started.set()
        with SessionLocal(bind=db_engine) as db:
            try:
                scheduling_v2_service.create_booking(
                    db,
                    org_id=fixture.organization_id,
                    user_id=fixture.user_id,
                    appointment_type_id=fixture.appointment_type_id,
                    client_name="Concurrent client",
                    client_email=f"concurrent-{fixture.appointment_id.hex}@example.test",
                    client_phone="555-0101",
                    client_timezone="UTC",
                    scheduled_start=fixture.target_start,
                    client_notes=None,
                    idempotency_key=None,
                    meeting_mode=MeetingMode.PHONE.value,
                    record_links=None,
                    actor_scope=scheduling_v2_service.staff_actor_scope(fixture.user_id),
                    actor_user_id=fixture.user_id,
                    request_id=None,
                    expected_revision=0,
                    override_availability=False,
                    override_reason=None,
                )
            except ValueError as exc:
                db.rollback()
                return str(exc)
            raise AssertionError("staff booking unexpectedly committed")

    with ThreadPoolExecutor(max_workers=2) as pool:
        inbound = pool.submit(apply_inbound)
        assert inbound_holds_owner.wait(10)
        staff = pool.submit(create_staff_booking)
        assert staff_started.wait(10)
        sleep(0.1)
        assert not staff.done(), "staff booking must wait for the inbound owner lock"
        release_inbound.set()
        assert inbound.result(timeout=10) == 1
        assert staff.result(timeout=10) == "Selected time is no longer available"

    with SessionLocal(bind=db_engine) as db:
        appointment = db.get(Appointment, fixture.appointment_id)
        assert appointment is not None
        assert appointment.scheduled_start == fixture.target_start
        assert (
            db.query(Appointment)
            .filter(
                Appointment.organization_id == fixture.organization_id,
                Appointment.client_name == "Concurrent client",
            )
            .count()
            == 0
        )
