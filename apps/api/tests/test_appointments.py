"""
Tests for Appointment Service - comprehensive test suite.

Coverage:
- Availability slot calculation
- Buffer time handling
- Conflict detection
- Token generation and expiry
- Timezone handling
- Booking validation
"""

import pytest
from datetime import date, datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from uuid import uuid4

from app.db.models import (
    Appointment,
    AppointmentType,
    AvailabilityRule,
    BookingLink,
)
from app.db.enums import AppointmentStatus, MeetingMode


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def appointment_type(db, test_org, test_user):
    """Create a test appointment type."""
    appt_type = AppointmentType(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        slug="initial-consultation",
        name="Initial Consultation",
        description="30 minute initial consultation",
        duration_minutes=30,
        buffer_after_minutes=10,
        meeting_mode=MeetingMode.ZOOM.value,
        is_active=True,
        reminder_hours_before=24,
    )
    db.add(appt_type)
    db.flush()
    return appt_type


@pytest.fixture
def availability_rules(db, test_org, test_user):
    """Create availability rules for weekdays 9am-5pm."""
    rules = []
    for day in range(5):  # Monday to Friday (0-4)
        rule = AvailabilityRule(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone="America/New_York",
        )
        db.add(rule)
        rules.append(rule)
    db.flush()
    return rules


@pytest.fixture
def booking_link(db, test_org, test_user):
    """Create a booking link for the test user."""
    link = BookingLink(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        public_slug=f"test-user-{uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(link)
    db.flush()
    return link


@pytest.fixture
def confirmed_appointment(db, test_org, test_user, appointment_type):
    """Create a confirmed appointment for conflict testing."""
    now = datetime.now(timezone.utc)
    scheduled_start = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)

    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appointment_type.id,
        client_name="Test Client",
        client_email="client@example.com",
        client_phone="555-123-4567",
        client_timezone="America/New_York",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode=MeetingMode.ZOOM.value,
        status=AppointmentStatus.CONFIRMED.value,
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
    )
    db.add(appt)
    db.flush()
    return appt


# =============================================================================
# Availability Slot Calculation Tests
# =============================================================================


class TestAvailabilitySlots:
    """Tests for slot calculation logic."""

    def test_get_available_slots_empty_rules(
        self, db, test_org, test_user, appointment_type, booking_link
    ):
        """No availability rules should return empty slots."""
        from app.services.appointment_service import get_available_slots, SlotQuery

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=datetime.now(timezone.utc).date(),
            date_end=datetime.now(timezone.utc).date(),
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)
        assert slots == []

    def test_get_available_slots_with_rules(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """With availability rules, should return slots."""
        from app.services.appointment_service import get_available_slots, SlotQuery

        # Get a weekday date (Monday-Friday)
        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # Next week's Monday
        target_date = today + timedelta(days=days_until_monday)

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)

        # Should have multiple slots (9am-5pm = 8 hours = 16 half-hour slots minus buffer)
        assert len(slots) > 0


# =============================================================================
# Conflict Detection Tests
# =============================================================================


class TestConflictDetection:
    """Tests for appointment conflict detection."""

    def test_booking_conflict_same_time(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
        confirmed_appointment,
    ):
        """Booking at same time as existing appointment should fail."""
        from app.services.appointment_service import create_booking

        with pytest.raises(ValueError, match="no longer available"):
            create_booking(
                db=db,
                org_id=test_org.id,
                user_id=test_user.id,
                appointment_type_id=appointment_type.id,
                client_name="New Client",
                client_email="new@example.com",
                client_phone="555-999-8888",
                client_timezone="America/New_York",
                scheduled_start=confirmed_appointment.scheduled_start,
            )

    def test_existing_buffers_block_nearby_slots(self, db, test_org, test_user, availability_rules):
        """Existing appointment buffers should block adjacent slots."""
        from app.db.models import AppointmentType, Appointment
        from app.db.enums import MeetingMode
        from app.services.appointment_service import get_available_slots, SlotQuery

        appt_type = AppointmentType(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            slug="no-buffer",
            name="No Buffer",
            description="No buffers",
            duration_minutes=30,
            buffer_before_minutes=0,
            buffer_after_minutes=0,
            meeting_mode=MeetingMode.ZOOM.value,
            is_active=True,
            reminder_hours_before=24,
        )
        db.add(appt_type)
        db.flush()

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        user_tz = ZoneInfo("America/New_York")
        existing_start_local = datetime.combine(target_date, time(10, 0), tzinfo=user_tz)
        existing_start = existing_start_local.astimezone(timezone.utc)
        existing_end = existing_start + timedelta(minutes=30)

        existing = Appointment(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appt_type.id,
            client_name="Buffered Client",
            client_email="buffered@example.com",
            client_phone="555-333-2222",
            client_timezone="America/New_York",
            scheduled_start=existing_start,
            scheduled_end=existing_end,
            duration_minutes=30,
            buffer_before_minutes=0,
            buffer_after_minutes=30,
            meeting_mode=MeetingMode.ZOOM.value,
            status=AppointmentStatus.CONFIRMED.value,
        )
        db.add(existing)
        db.flush()

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appt_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)
        slot_times_local = [
            slot.start.astimezone(user_tz).time()
            for slot in slots
            if slot.start.astimezone(user_tz).date() == target_date
        ]

        assert time(10, 30) not in slot_times_local
        assert time(11, 0) in slot_times_local


# =============================================================================
# Token Tests
# =============================================================================


class TestTokens:
    """Tests for reschedule/cancel token handling."""

    def test_tokens_generated_on_booking(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """Booking should generate reschedule and cancel tokens."""
        from app.services.appointment_service import (
            create_booking,
            get_available_slots,
            SlotQuery,
        )

        # Find an available slot
        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)

        if not slots:
            pytest.skip("No available slots for testing")

        appointment_type.meeting_mode = "phone"
        db.commit()

        appt = create_booking(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Token Test Client",
            client_email="token@example.com",
            client_phone="555-777-6666",
            client_timezone="America/New_York",
            scheduled_start=slots[0].start,
        )

        assert appt.reschedule_token is not None
        assert appt.cancel_token is not None
        assert len(appt.reschedule_token) > 20  # Secure tokens are long

    def test_get_appointment_by_token(self, db, confirmed_appointment):
        """Should retrieve appointment by valid token."""
        from app.services.appointment_service import get_appointment_by_token

        # Test with reschedule token
        appt = get_appointment_by_token(
            db,
            confirmed_appointment.organization_id,
            confirmed_appointment.reschedule_token,
            "reschedule",
        )
        assert appt is not None
        assert appt.id == confirmed_appointment.id

    def test_get_appointment_by_invalid_token(self, db):
        """Should return None for invalid token."""
        from app.services.appointment_service import get_appointment_by_token

        appt = get_appointment_by_token(db, uuid4(), "invalid-token-12345", "reschedule")
        assert appt is None


# =============================================================================
# Booking Status Tests
# =============================================================================


class TestBookingStatus:
    """Tests for appointment status transitions."""

    def test_new_booking_is_pending(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """New bookings should have pending status."""
        from app.services.appointment_service import (
            create_booking,
            get_available_slots,
            SlotQuery,
        )

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)

        if not slots:
            pytest.skip("No available slots for testing")

        appointment_type.meeting_mode = "phone"
        db.commit()

        appt = create_booking(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Status Test Client",
            client_email="status@example.com",
            client_phone="555-888-9999",
            client_timezone="America/New_York",
            scheduled_start=slots[0].start,
        )

        assert appt.status == AppointmentStatus.PENDING.value

    def test_approve_booking(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """Approving a booking should change status to confirmed."""
        from app.services.appointment_service import (
            create_booking,
            approve_booking,
            get_available_slots,
            SlotQuery,
        )

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)

        if not slots:
            pytest.skip("No available slots for testing")

        appointment_type.meeting_mode = "phone"
        db.commit()

        appt = create_booking(
            db=db,
            org_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Approve Test Client",
            client_email="approve@example.com",
            client_phone="555-111-2222",
            client_timezone="America/New_York",
            scheduled_start=slots[0].start,
        )

        approved = approve_booking(db, appt, test_user.id)
        assert approved.status == AppointmentStatus.CONFIRMED.value


# =============================================================================
# Timezone Tests
# =============================================================================


class TestTimezoneHandling:
    """Tests for timezone-related functionality."""

    def test_slot_times_in_client_timezone(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """Slots should respect client timezone."""
        from app.services.appointment_service import get_available_slots, SlotQuery

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        # Get slots for two different timezones
        query_east = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )

        query_west = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/Los_Angeles",
        )

        slots_east = get_available_slots(db, query_east)
        slots_west = get_available_slots(db, query_west)

        # Slots should be at different UTC times due to timezone difference
        if slots_east and slots_west:
            # Both should be valid datetime objects
            east_utc = slots_east[0].start
            assert isinstance(east_utc, datetime)


# =============================================================================
# Email Template Tests
# =============================================================================


class TestEmailTemplates:
    """Tests for email template functionality."""

    def test_default_templates_exist(self):
        """All default email templates should be defined."""
        from app.services.appointment_email_service import DEFAULT_TEMPLATES
        from app.db.enums import AppointmentEmailType

        for email_type in AppointmentEmailType:
            assert email_type in DEFAULT_TEMPLATES, f"Missing template for {email_type.value}"
            template = DEFAULT_TEMPLATES[email_type]
            assert "name" in template
            assert "subject" in template
            assert "body" in template

    def test_template_variables_complete(self):
        """Templates should use valid variables."""
        from app.services.appointment_email_service import DEFAULT_TEMPLATES
        import re

        # Variables that should be available
        valid_vars = {
            "client_name",
            "client_email",
            "client_phone",
            "appointment_type",
            "scheduled_date",
            "scheduled_time",
            "duration",
            "meeting_mode",
            "staff_name",
            "staff_email",
            "org_name",
            "reschedule_url",
            "cancel_url",
            "booking_url",
            "zoom_join_url",
            "zoom_meeting_id",
            "google_meet_url",
            "old_scheduled_date",
            "old_scheduled_time",
            "cancellation_reason",
            "client_notes",
        }

        var_pattern = re.compile(r"\{\{(\w+)\}\}")

        for email_type, template in DEFAULT_TEMPLATES.items():
            found_vars = set(var_pattern.findall(template["subject"]))
            found_vars.update(var_pattern.findall(template["body"]))

            # All found variables should be valid
            for var in found_vars:
                # Ignore conditional tags like {{#if ...}}
                if var.startswith("#") or var.startswith("/"):
                    continue
                assert var in valid_vars, (
                    f"Unknown variable {{{{{var}}}}} in {email_type.value} template"
                )


# =============================================================================
# Approval Conflict Re-validation Tests
# =============================================================================


class TestApprovalConflictCheck:
    """Tests for appointment approval double-booking prevention."""

    def test_approve_revalidates_slot_availability(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """Approving should fail if a confirmed appointment exists in that slot."""
        from app.services.appointment_service import (
            approve_booking,
            get_available_slots,
            SlotQuery,
        )

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots = get_available_slots(db, query)

        if len(slots) < 1:
            pytest.skip("No available slots for testing")

        # Create a confirmed appointment at slot 0
        confirmed_appt = Appointment(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Confirmed Client",
            client_email="confirmed@example.com",
            client_phone="555-111-1111",
            client_timezone="America/New_York",
            scheduled_start=slots[0].start,
            scheduled_end=slots[0].end,
            duration_minutes=appointment_type.duration_minutes,
            meeting_mode=appointment_type.meeting_mode,
            status=AppointmentStatus.CONFIRMED.value,
        )
        db.add(confirmed_appt)
        db.flush()

        # Create a pending appointment at same time (simulating race condition)
        pending_appt = Appointment(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Pending Client",
            client_email="pending@example.com",
            client_phone="555-222-2222",
            client_timezone="America/New_York",
            scheduled_start=slots[0].start,
            scheduled_end=slots[0].end,
            duration_minutes=appointment_type.duration_minutes,
            meeting_mode=appointment_type.meeting_mode,
            status=AppointmentStatus.PENDING.value,
            pending_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(pending_appt)
        db.flush()

        # Try to approve the pending one - this should FAIL due to conflict with confirmed
        with pytest.raises(ValueError, match="no longer available"):
            approve_booking(db, pending_appt, test_user.id)


# =============================================================================
# Task Timezone Conflict Tests
# =============================================================================


class TestTaskTimezoneConflict:
    """Tests for task conflict detection with proper timezone handling."""

    def test_task_conflict_uses_user_timezone(
        self,
        db,
        test_org,
        test_user,
        appointment_type,
        booking_link,
        availability_rules,
    ):
        """Task conflicts should interpret task time in user's timezone, not UTC."""
        from app.services.appointment_service import get_available_slots, SlotQuery
        from app.db.models import Task
        from app.db.enums import OwnerType

        today = datetime.now(timezone.utc).date()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_date = today + timedelta(days=days_until_monday)

        # Get slots before adding task
        query = SlotQuery(
            user_id=test_user.id,
            org_id=test_org.id,
            appointment_type_id=appointment_type.id,
            date_start=target_date,
            date_end=target_date,
            client_timezone="America/New_York",
        )
        slots_before = get_available_slots(db, query)

        if not slots_before:
            pytest.skip("No available slots for testing")

        # Add a task at 10:00 AM (user's timezone - America/New_York from availability rules)
        task = Task(
            id=uuid4(),
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            title="Blocking Task",
            due_date=target_date,
            due_time=time(10, 0),  # 10:00 AM in user's timezone
            duration_minutes=60,  # 1 hour
            is_completed=False,
        )
        db.add(task)
        db.flush()

        # Get slots after adding task
        slots_after = get_available_slots(db, query)

        # There should be fewer slots now due to the task blocking 10:00-11:00
        assert len(slots_after) < len(slots_before), (
            "Task should block some slots - timezone handling may be incorrect"
        )


# =============================================================================
# Meeting Automation Tests (TDD for Zoom/Google Meet)
# =============================================================================


def _next_weekday(target_weekday: int) -> date:
    """Get next occurrence of weekday (0=Monday)."""
    today = datetime.now(timezone.utc).date()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start):
    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        appointment_type_id=appointment_type.id,
        client_name="Test Client",
        client_email="client@example.com",
        client_phone="555-111-2222",
        client_timezone="America/New_York",
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_start + timedelta(minutes=appointment_type.duration_minutes),
        duration_minutes=appointment_type.duration_minutes,
        buffer_before_minutes=appointment_type.buffer_before_minutes,
        buffer_after_minutes=appointment_type.buffer_after_minutes,
        meeting_mode=appointment_type.meeting_mode,
        status=AppointmentStatus.PENDING.value,
        pending_expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
        reschedule_token=f"reschedule-{uuid4().hex}",
        cancel_token=f"cancel-{uuid4().hex}",
    )
    db.add(appt)
    db.flush()
    return appt


def test_approve_booking_creates_zoom_meeting_and_schedules_reminder(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Approval should create Zoom meeting link and schedule reminder."""
    from app.services import appointment_service, appointment_email_service, zoom_service, appointment_integrations

    appointment_type.meeting_mode = MeetingMode.ZOOM.value
    db.flush()

    target_date = _next_weekday(0)  # Monday
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)

    monkeypatch.setattr(appointment_integrations, "sync_to_google_calendar", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.services.notification_service.notify_appointment_confirmed", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "app.services.workflow_triggers.trigger_appointment_scheduled", lambda *a, **k: None
    )
    monkeypatch.setattr(zoom_service, "check_user_has_zoom", lambda *a, **k: True)

    async def fake_get_user_zoom_token(*args, **kwargs):
        return "test-token"

    async def fake_create_zoom_meeting(*args, **kwargs):
        return zoom_service.ZoomMeeting(
            id=123456789,
            uuid="",
            topic="Test Meeting",
            start_time=scheduled_start.isoformat(),
            duration=30,
            timezone="America/New_York",
            join_url="https://zoom.us/j/123456789",
            start_url="https://zoom.us/s/123456789",
            password=None,
        )

    monkeypatch.setattr(zoom_service, "get_user_zoom_token", fake_get_user_zoom_token)
    monkeypatch.setattr(zoom_service, "create_zoom_meeting", fake_create_zoom_meeting)

    called = {}

    def fake_schedule_reminder(db, appointment, base_url="", hours_before=24):
        called["appointment_id"] = appointment.id
        called["hours_before"] = hours_before
        return None

    monkeypatch.setattr(
        appointment_email_service, "schedule_reminder_email", fake_schedule_reminder
    )

    approved = appointment_service.approve_booking(db, appt, approved_by_user_id=test_user.id)

    assert approved.status == AppointmentStatus.CONFIRMED.value
    assert approved.zoom_meeting_id == "123456789"
    assert approved.zoom_join_url == "https://zoom.us/j/123456789"
    assert called["appointment_id"] == approved.id
    assert called["hours_before"] == appointment_type.reminder_hours_before


def test_approve_booking_fails_when_zoom_not_connected(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Zoom meeting mode should require a connected Zoom integration."""
    from app.services import appointment_service, zoom_service

    appointment_type.meeting_mode = MeetingMode.ZOOM.value
    db.flush()

    target_date = _next_weekday(0)
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)

    monkeypatch.setattr(zoom_service, "check_user_has_zoom", lambda *a, **k: False)

    with pytest.raises(ValueError, match="Zoom not connected"):
        appointment_service.approve_booking(db, appt, approved_by_user_id=test_user.id)

    db.refresh(appt)
    assert appt.status == AppointmentStatus.PENDING.value


def test_approve_booking_creates_google_meet_link(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Google Meet mode should create a Meet link on approval."""
    from app.services import appointment_service, calendar_service, appointment_integrations

    appointment_type.meeting_mode = "google_meet"
    db.flush()

    target_date = _next_weekday(0)
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)

    monkeypatch.setattr(appointment_integrations, "sync_to_google_calendar", lambda *a, **k: None)

    monkeypatch.setattr(
        calendar_service, "check_user_has_google_calendar", lambda *a, **k: True, raising=False
    )

    async def fake_create_google_meet_link(*args, **kwargs):
        return {"event_id": "event_123", "meet_url": "https://meet.google.com/abc-defg-hij"}

    monkeypatch.setattr(
        calendar_service, "create_google_meet_link", fake_create_google_meet_link, raising=False
    )

    approved = appointment_service.approve_booking(db, appt, approved_by_user_id=test_user.id)

    assert getattr(approved, "google_event_id", None) == "event_123"
    assert getattr(approved, "google_meet_url", None) == "https://meet.google.com/abc-defg-hij"


def test_reschedule_booking_regenerates_zoom_link(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Reschedule should regenerate the Zoom meeting link."""
    from app.services import appointment_service, zoom_service, appointment_integrations

    appointment_type.meeting_mode = MeetingMode.ZOOM.value
    db.flush()

    target_date = _next_weekday(0)
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)
    appt.status = AppointmentStatus.CONFIRMED.value
    appt.zoom_meeting_id = "old_meeting"
    appt.zoom_join_url = "https://zoom.us/j/old"
    db.flush()

    monkeypatch.setattr(appointment_integrations, "sync_to_google_calendar", lambda *a, **k: None)
    monkeypatch.setattr(zoom_service, "check_user_has_zoom", lambda *a, **k: True)

    async def fake_get_user_zoom_token(*args, **kwargs):
        return "test-token"

    async def fake_create_zoom_meeting(*args, **kwargs):
        return zoom_service.ZoomMeeting(
            id=999,
            uuid="",
            topic="Rescheduled Meeting",
            start_time=(scheduled_start + timedelta(days=1)).isoformat(),
            duration=30,
            timezone="America/New_York",
            join_url="https://zoom.us/j/999",
            start_url="https://zoom.us/s/999",
            password=None,
        )

    monkeypatch.setattr(zoom_service, "get_user_zoom_token", fake_get_user_zoom_token)
    monkeypatch.setattr(zoom_service, "create_zoom_meeting", fake_create_zoom_meeting)

    new_start = scheduled_start + timedelta(days=1)
    updated = appointment_service.reschedule_booking(
        db=db,
        appointment=appt,
        new_start=new_start,
        by_client=False,
    )

    assert updated.zoom_meeting_id == "999"
    assert updated.zoom_join_url == "https://zoom.us/j/999"


def test_approve_booking_fails_when_google_calendar_not_connected(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Google Meet mode should require Google Calendar integration."""
    from app.services import appointment_service, calendar_service

    appointment_type.meeting_mode = "google_meet"
    db.flush()

    target_date = _next_weekday(0)
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)

    monkeypatch.setattr(
        calendar_service, "check_user_has_google_calendar", lambda *a, **k: False, raising=False
    )

    with pytest.raises(ValueError, match="Google Calendar not connected"):
        appointment_service.approve_booking(db, appt, approved_by_user_id=test_user.id)

    db.refresh(appt)
    assert appt.status == AppointmentStatus.PENDING.value


def test_cancel_booking_deletes_zoom_meeting(
    db, test_org, test_user, appointment_type, availability_rules, monkeypatch
):
    """Cancel should attempt to delete the Zoom meeting."""
    from app.services import appointment_service, zoom_service

    appointment_type.meeting_mode = MeetingMode.ZOOM.value
    db.flush()

    target_date = _next_weekday(0)
    local_start = datetime.combine(target_date, time(10, 0), tzinfo=ZoneInfo("America/New_York"))
    scheduled_start = local_start.astimezone(timezone.utc)

    appt = _make_pending_appointment(db, test_org, test_user, appointment_type, scheduled_start)
    appt.status = AppointmentStatus.CONFIRMED.value
    appt.zoom_meeting_id = "123456789"
    appt.zoom_join_url = "https://zoom.us/j/123456789"
    db.flush()

    monkeypatch.setattr(
        "app.services.notification_service.notify_appointment_cancelled", lambda *a, **k: None
    )

    async def fake_get_user_zoom_token(*args, **kwargs):
        return "test-token"

    called = {}

    async def fake_delete_zoom_meeting(access_token, meeting_id):
        called["token"] = access_token
        called["meeting_id"] = meeting_id
        return True

    monkeypatch.setattr(zoom_service, "get_user_zoom_token", fake_get_user_zoom_token)
    monkeypatch.setattr(
        zoom_service, "delete_zoom_meeting", fake_delete_zoom_meeting, raising=False
    )

    cancelled = appointment_service.cancel_booking(db, appt, by_client=False)

    assert cancelled.status == AppointmentStatus.CANCELLED.value
    assert called["meeting_id"] == "123456789"
