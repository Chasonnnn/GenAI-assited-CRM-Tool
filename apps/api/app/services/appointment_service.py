"""Appointment service - business logic for scheduling and booking.

Handles:
- Appointment types management
- Availability rules and overrides
- Slot calculation with conflict detection
- Booking creation with idempotency
- Approval, reschedule, and cancellation workflows
"""

import hashlib
import secrets
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import NamedTuple
from uuid import UUID
import re

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import (
    AppointmentType,
    AvailabilityRule,
    AvailabilityOverride,
    BookingLink,
    Appointment,
    AppointmentEmailLog,
    Task,
    UserIntegration,
    Surrogate,
    IntendedParent,
    Organization,
)
from app.schemas.appointment import AppointmentRead, AppointmentListItem
from app.db.enums import AppointmentStatus, MeetingMode
from app.services import appointment_integrations


# =============================================================================
# Types
# =============================================================================


class TimeSlot(NamedTuple):
    """Available time slot."""

    start: datetime
    end: datetime


class SlotQuery(NamedTuple):
    """Parameters for slot calculation."""

    user_id: UUID
    org_id: UUID
    appointment_type_id: UUID
    date_start: date
    date_end: date
    client_timezone: str


# =============================================================================
# Slugs and Tokens
# =============================================================================


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    # Lowercase, replace spaces with hyphens, remove special chars
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:100]  # Max length


def generate_token(length: int = 32) -> str:
    """Generate cryptographically secure token."""
    return secrets.token_urlsafe(length)


def generate_public_slug() -> str:
    """Generate 16-char random slug for booking links."""
    return secrets.token_urlsafe(12)[:16]


def _get_timezone(name: str | None) -> ZoneInfo:
    """Get a ZoneInfo timezone with safe fallback."""
    if not name:
        return ZoneInfo("America/Los_Angeles")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("America/Los_Angeles")


def _validate_timezone_name(name: str, label: str = "timezone") -> None:
    """Validate an IANA timezone name."""
    if not name:
        raise ValueError(f"Invalid {label}: missing value")
    try:
        ZoneInfo(name)
    except Exception as exc:
        raise ValueError(f"Invalid {label}: {name}") from exc


def validate_timezone_name(name: str, label: str = "timezone") -> None:
    """Public helper to validate timezones for API inputs."""
    _validate_timezone_name(name, label)


def _normalize_idempotency_key(org_id: UUID, user_id: UUID, key: str) -> str:
    """Normalize idempotency key to avoid cross-tenant collisions."""
    raw = f"{org_id}:{user_id}:{key}".encode()
    return hashlib.sha256(raw).hexdigest()


def _normalize_scheduled_start(
    scheduled_start: datetime,
    client_timezone: str,
) -> datetime:
    """Ensure scheduled_start is timezone-aware and normalized to UTC."""
    if scheduled_start.tzinfo is None:
        tz = _get_timezone(client_timezone)
        scheduled_start = scheduled_start.replace(tzinfo=tz)
    return scheduled_start.astimezone(timezone.utc)


def _validate_time_range(start: time, end: time, label: str) -> None:
    """Ensure end time is after start time."""
    if end <= start:
        raise ValueError(f"{label} end_time must be after start_time")


def _normalize_meeting_modes(
    meeting_modes: list[str] | None,
    meeting_mode: str | None,
    current_default: str | None = None,
) -> tuple[list[str], str]:
    """Normalize meeting modes list and default meeting mode."""
    if meeting_modes is None or len(meeting_modes) == 0:
        default_mode = meeting_mode or current_default or MeetingMode.ZOOM.value
        return [default_mode], default_mode

    normalized: list[str] = []
    for mode in meeting_modes:
        if mode not in normalized:
            normalized.append(mode)

    if not normalized:
        raise ValueError("At least one meeting mode is required")

    if meeting_mode and meeting_mode in normalized:
        default_mode = meeting_mode
    elif current_default and current_default in normalized:
        default_mode = current_default
    else:
        default_mode = normalized[0]

    return normalized, default_mode


# =============================================================================
# Appointment Types
# =============================================================================


def create_appointment_type(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    description: str | None = None,
    duration_minutes: int = 30,
    buffer_before_minutes: int = 0,
    buffer_after_minutes: int = 5,
    meeting_mode: str = MeetingMode.ZOOM.value,
    meeting_modes: list[str] | None = None,
    meeting_location: str | None = None,
    dial_in_number: str | None = None,
    auto_approve: bool = False,
    reminder_hours_before: int = 24,
) -> AppointmentType:
    """Create a new appointment type for a user."""
    slug = generate_slug(name)
    # Ensure unique slug for user
    base_slug = slug
    counter = 1
    while (
        db.query(AppointmentType)
        .filter(AppointmentType.user_id == user_id, AppointmentType.slug == slug)
        .first()
    ):
        slug = f"{base_slug}-{counter}"
        counter += 1

    normalized_modes, default_mode = _normalize_meeting_modes(meeting_modes, meeting_mode)

    appt_type = AppointmentType(
        organization_id=org_id,
        user_id=user_id,
        name=name,
        slug=slug,
        description=description,
        duration_minutes=duration_minutes,
        buffer_before_minutes=buffer_before_minutes,
        buffer_after_minutes=buffer_after_minutes,
        meeting_mode=default_mode,
        meeting_modes=normalized_modes,
        meeting_location=meeting_location,
        dial_in_number=dial_in_number,
        auto_approve=auto_approve,
        reminder_hours_before=reminder_hours_before,
        is_active=True,
    )
    db.add(appt_type)
    db.commit()
    db.refresh(appt_type)
    return appt_type


def update_appointment_type(
    db: Session,
    appt_type: AppointmentType,
    name: str | None = None,
    description: str | None = None,
    duration_minutes: int | None = None,
    buffer_before_minutes: int | None = None,
    buffer_after_minutes: int | None = None,
    meeting_mode: str | None = None,
    meeting_modes: list[str] | None = None,
    meeting_location: str | None = None,
    dial_in_number: str | None = None,
    auto_approve: bool | None = None,
    reminder_hours_before: int | None = None,
    is_active: bool | None = None,
) -> AppointmentType:
    """Update an appointment type."""
    if name is not None:
        appt_type.name = name
        new_slug = generate_slug(name)
        base_slug = new_slug
        counter = 1
        while (
            db.query(AppointmentType)
            .filter(
                AppointmentType.user_id == appt_type.user_id,
                AppointmentType.slug == new_slug,
                AppointmentType.id != appt_type.id,
            )
            .first()
        ):
            new_slug = f"{base_slug}-{counter}"
            counter += 1
        appt_type.slug = new_slug
    if description is not None:
        appt_type.description = description
    if duration_minutes is not None:
        appt_type.duration_minutes = duration_minutes
    if buffer_before_minutes is not None:
        appt_type.buffer_before_minutes = buffer_before_minutes
    if buffer_after_minutes is not None:
        appt_type.buffer_after_minutes = buffer_after_minutes
    if meeting_modes is not None:
        normalized_modes, default_mode = _normalize_meeting_modes(
            meeting_modes,
            meeting_mode,
            current_default=appt_type.meeting_mode,
        )
        appt_type.meeting_modes = normalized_modes
        appt_type.meeting_mode = default_mode
    elif meeting_mode is not None:
        current_modes = appt_type.meeting_modes or [appt_type.meeting_mode]
        if meeting_mode not in current_modes:
            raise ValueError("Meeting mode not available for this appointment type")
        appt_type.meeting_mode = meeting_mode
    if meeting_location is not None:
        appt_type.meeting_location = meeting_location
    if dial_in_number is not None:
        appt_type.dial_in_number = dial_in_number
    if auto_approve is not None:
        appt_type.auto_approve = auto_approve
    if reminder_hours_before is not None:
        appt_type.reminder_hours_before = reminder_hours_before
    if is_active is not None:
        appt_type.is_active = is_active

    db.commit()
    db.refresh(appt_type)
    return appt_type


def get_appointment_context(
    db: Session,
    appointments: list[Appointment],
) -> dict[str, dict[UUID, str | None]]:
    """Fetch related data for appointments in bulk."""
    if not appointments:
        return {
            "type_names": {},
            "user_names": {},
            "surrogate_numbers": {},
            "intended_parent_names": {},
        }

    type_ids = {a.appointment_type_id for a in appointments if a.appointment_type_id}
    approved_by_ids = {a.approved_by_user_id for a in appointments if a.approved_by_user_id}
    surrogate_ids = {a.surrogate_id for a in appointments if a.surrogate_id}
    ip_ids = {a.intended_parent_id for a in appointments if a.intended_parent_id}

    type_names = {}
    if type_ids:
        types = db.query(AppointmentType).filter(AppointmentType.id.in_(type_ids)).all()
        type_names = {t.id: t.name for t in types}

    user_names = {}
    if approved_by_ids:
        from app.db.models import User

        users = db.query(User).filter(User.id.in_(approved_by_ids)).all()
        user_names = {u.id: u.display_name for u in users}

    surrogate_numbers = {}
    if surrogate_ids:
        cases = db.query(Surrogate).filter(Surrogate.id.in_(surrogate_ids)).all()
        surrogate_numbers = {c.id: c.surrogate_number for c in cases}

    intended_parent_names = {}
    if ip_ids:
        ips = db.query(IntendedParent).filter(IntendedParent.id.in_(ip_ids)).all()
        intended_parent_names = {ip.id: ip.full_name for ip in ips}

    return {
        "type_names": type_names,
        "user_names": user_names,
        "surrogate_numbers": surrogate_numbers,
        "intended_parent_names": intended_parent_names,
    }


def to_appointment_read(
    appt: Appointment,
    context: dict[str, dict[UUID, str | None]],
) -> AppointmentRead:
    """Convert Appointment model to read schema."""
    return AppointmentRead(
        id=appt.id,
        user_id=appt.user_id,
        appointment_type_id=appt.appointment_type_id,
        appointment_type_name=context["type_names"].get(appt.appointment_type_id),
        client_name=appt.client_name,
        client_email=appt.client_email,
        client_phone=appt.client_phone,
        client_timezone=appt.client_timezone,
        client_notes=appt.client_notes,
        scheduled_start=appt.scheduled_start,
        scheduled_end=appt.scheduled_end,
        duration_minutes=appt.duration_minutes,
        meeting_mode=appt.meeting_mode,
        meeting_location=appt.meeting_location,
        dial_in_number=appt.dial_in_number,
        status=appt.status,
        pending_expires_at=appt.pending_expires_at,
        approved_at=appt.approved_at,
        approved_by_user_id=appt.approved_by_user_id,
        approved_by_name=context["user_names"].get(appt.approved_by_user_id),
        cancelled_at=appt.cancelled_at,
        cancelled_by_client=appt.cancelled_by_client,
        cancellation_reason=appt.cancellation_reason,
        zoom_join_url=appt.zoom_join_url,
        google_event_id=appt.google_event_id,
        google_meet_url=appt.google_meet_url,
        meeting_started_at=appt.meeting_started_at,
        meeting_ended_at=appt.meeting_ended_at,
        surrogate_id=appt.surrogate_id,
        surrogate_number=context["surrogate_numbers"].get(appt.surrogate_id),
        intended_parent_id=appt.intended_parent_id,
        intended_parent_name=context["intended_parent_names"].get(appt.intended_parent_id),
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


def to_appointment_list_item(
    appt: Appointment,
    context: dict[str, dict[UUID, str | None]],
) -> AppointmentListItem:
    """Convert Appointment model to list item schema."""
    return AppointmentListItem(
        id=appt.id,
        appointment_type_name=context["type_names"].get(appt.appointment_type_id),
        client_name=appt.client_name,
        client_email=appt.client_email,
        client_phone=appt.client_phone,
        client_timezone=appt.client_timezone,
        scheduled_start=appt.scheduled_start,
        scheduled_end=appt.scheduled_end,
        duration_minutes=appt.duration_minutes,
        meeting_mode=appt.meeting_mode,
        meeting_location=appt.meeting_location,
        dial_in_number=appt.dial_in_number,
        status=appt.status,
        zoom_join_url=appt.zoom_join_url,
        google_meet_url=appt.google_meet_url,
        surrogate_id=appt.surrogate_id,
        surrogate_number=context["surrogate_numbers"].get(appt.surrogate_id),
        intended_parent_id=appt.intended_parent_id,
        intended_parent_name=context["intended_parent_names"].get(appt.intended_parent_id),
        created_at=appt.created_at,
    )


def get_appointment_type(
    db: Session,
    appt_type_id: UUID,
    org_id: UUID,
) -> AppointmentType | None:
    """Get appointment type by ID."""
    return (
        db.query(AppointmentType)
        .filter(
            AppointmentType.id == appt_type_id,
            AppointmentType.organization_id == org_id,
        )
        .first()
    )


def list_appointment_types(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    active_only: bool = True,
) -> list[AppointmentType]:
    """List appointment types for a user."""
    query = db.query(AppointmentType).filter(
        AppointmentType.user_id == user_id,
        AppointmentType.organization_id == org_id,
    )
    if active_only:
        query = query.filter(AppointmentType.is_active.is_(True))
    return query.order_by(AppointmentType.name).all()


# =============================================================================
# Availability Rules
# =============================================================================


def set_availability_rules(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    rules: list[dict],
    timezone_name: str = "America/Los_Angeles",
) -> list[AvailabilityRule]:
    """
    Replace all availability rules for a user.

    rules format: [{"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}, ...]
    """
    _validate_timezone_name(timezone_name, "timezone")

    # Delete existing rules
    db.query(AvailabilityRule).filter(
        AvailabilityRule.user_id == user_id,
        AvailabilityRule.organization_id == org_id,
    ).delete()

    # Create new rules
    new_rules = []
    for rule_data in rules:
        start = time.fromisoformat(rule_data["start_time"])
        end = time.fromisoformat(rule_data["end_time"])
        _validate_time_range(start, end, "Availability rule")
        rule = AvailabilityRule(
            organization_id=org_id,
            user_id=user_id,
            day_of_week=rule_data["day_of_week"],
            start_time=start,
            end_time=end,
            timezone=timezone_name,
        )
        db.add(rule)
        new_rules.append(rule)

    db.commit()
    for rule in new_rules:
        db.refresh(rule)
    return new_rules


def get_availability_rules(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> list[AvailabilityRule]:
    """Get all availability rules for a user."""
    rules = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.user_id == user_id,
            AvailabilityRule.organization_id == org_id,
        )
        .order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
        .all()
    )
    if rules:
        return rules

    org = db.query(Organization).filter(Organization.id == org_id).first()
    timezone_name = org.timezone if org and org.timezone else "America/Los_Angeles"
    try:
        ZoneInfo(timezone_name)
    except Exception:
        timezone_name = "America/Los_Angeles"

    default_rules = []
    for day in range(5):  # Monday-Friday
        rule = AvailabilityRule(
            organization_id=org_id,
            user_id=user_id,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            timezone=timezone_name,
        )
        db.add(rule)
        default_rules.append(rule)

    db.commit()
    for rule in default_rules:
        db.refresh(rule)
    return default_rules


# =============================================================================
# Availability Overrides
# =============================================================================


def set_availability_override(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    override_date: date,
    is_unavailable: bool = True,
    start_time: time | None = None,
    end_time: time | None = None,
    reason: str | None = None,
) -> AvailabilityOverride:
    """Create or update an availability override for a specific date."""
    if is_unavailable:
        start_time = None
        end_time = None
    else:
        if not start_time or not end_time:
            raise ValueError("start_time and end_time are required when is_unavailable is false")
        _validate_time_range(start_time, end_time, "Availability override")
    existing = (
        db.query(AvailabilityOverride)
        .filter(
            AvailabilityOverride.user_id == user_id,
            AvailabilityOverride.organization_id == org_id,
            AvailabilityOverride.override_date == override_date,
        )
        .first()
    )

    if existing:
        existing.is_unavailable = is_unavailable
        existing.start_time = start_time
        existing.end_time = end_time
        existing.reason = reason
        db.commit()
        db.refresh(existing)
        return existing

    override = AvailabilityOverride(
        organization_id=org_id,
        user_id=user_id,
        override_date=override_date,
        is_unavailable=is_unavailable,
        start_time=start_time,
        end_time=end_time,
        reason=reason,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return override


def delete_availability_override(
    db: Session,
    override_id: UUID,
    user_id: UUID,
    org_id: UUID,
) -> bool:
    """Delete an availability override."""
    override = (
        db.query(AvailabilityOverride)
        .filter(
            AvailabilityOverride.id == override_id,
            AvailabilityOverride.user_id == user_id,
            AvailabilityOverride.organization_id == org_id,
        )
        .first()
    )
    if override:
        db.delete(override)
        db.commit()
        return True
    return False


def get_availability_overrides(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    date_start: date | None = None,
    date_end: date | None = None,
) -> list[AvailabilityOverride]:
    """Get availability overrides for a user within a date range."""
    query = db.query(AvailabilityOverride).filter(
        AvailabilityOverride.user_id == user_id,
        AvailabilityOverride.organization_id == org_id,
    )
    if date_start:
        query = query.filter(AvailabilityOverride.override_date >= date_start)
    if date_end:
        query = query.filter(AvailabilityOverride.override_date <= date_end)
    return query.order_by(AvailabilityOverride.override_date).all()


# =============================================================================
# Booking Links
# =============================================================================


def get_or_create_booking_link(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> BookingLink:
    """Get or create a booking link for a user."""
    existing = (
        db.query(BookingLink)
        .filter(
            BookingLink.user_id == user_id,
            BookingLink.organization_id == org_id,
        )
        .first()
    )

    if existing:
        return existing

    link = BookingLink(
        organization_id=org_id,
        user_id=user_id,
        public_slug=generate_public_slug(),
        is_active=True,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def regenerate_booking_link(
    db: Session,
    user_id: UUID,
    org_id: UUID,
) -> BookingLink | None:
    """Return the existing booking link without rotating its slug."""
    link = (
        db.query(BookingLink)
        .filter(
            BookingLink.user_id == user_id,
            BookingLink.organization_id == org_id,
        )
        .first()
    )

    if not link:
        return None

    return link


def get_booking_link_by_slug(
    db: Session,
    public_slug: str,
) -> BookingLink | None:
    """Get a booking link by its public slug."""
    return (
        db.query(BookingLink)
        .filter(
            BookingLink.public_slug == public_slug,
            BookingLink.is_active.is_(True),
        )
        .first()
    )


# =============================================================================
# Slot Calculation
# =============================================================================


def get_available_slots(
    db: Session,
    query: SlotQuery,
    slot_interval_minutes: int = 30,
    exclude_appointment_id: UUID | None = None,
    duration_minutes: int | None = None,
    buffer_before_minutes: int | None = None,
    buffer_after_minutes: int | None = None,
) -> list[TimeSlot]:
    """
    Calculate available time slots for booking.

    Checks:
    - User's availability rules
    - Date-specific overrides
    - Existing appointments (confirmed/pending with buffers)
    - Tasks with scheduled times
    - (Future: Google Calendar freebusy)
    """
    appt_type = (
        db.query(AppointmentType)
        .filter(
            AppointmentType.id == query.appointment_type_id,
            AppointmentType.organization_id == query.org_id,
        )
        .first()
    )

    if not appt_type or not appt_type.is_active:
        return []

    duration = duration_minutes if duration_minutes is not None else appt_type.duration_minutes
    buffer_before = (
        buffer_before_minutes
        if buffer_before_minutes is not None
        else appt_type.buffer_before_minutes
    )
    buffer_after = (
        buffer_after_minutes if buffer_after_minutes is not None else appt_type.buffer_after_minutes
    )

    client_tz = _get_timezone(query.client_timezone)

    # Get all rules and overrides
    rules = get_availability_rules(db, query.user_id, query.org_id)
    user_tz_name = rules[0].timezone if rules else query.client_timezone
    user_tz = _get_timezone(user_tz_name)

    client_start = datetime.combine(query.date_start, time.min, tzinfo=client_tz)
    client_end = datetime.combine(query.date_end, time.max, tzinfo=client_tz)
    user_date_start = client_start.astimezone(user_tz).date()
    user_date_end = client_end.astimezone(user_tz).date()

    overrides = get_availability_overrides(
        db, query.user_id, query.org_id, user_date_start, user_date_end
    )
    override_map = {o.override_date: o for o in overrides}

    # Get existing appointments
    existing_appointments = _get_conflicting_appointments(
        db,
        query.org_id,
        query.user_id,
        user_date_start,
        user_date_end,
        exclude_appointment_id=exclude_appointment_id,
    )

    # Get tasks with scheduled times (use user timezone dates for consistency)
    existing_tasks = _get_conflicting_tasks(
        db, query.user_id, query.org_id, user_date_start, user_date_end
    )

    # Build slots day by day
    slots: list[TimeSlot] = []
    current_date = user_date_start

    while current_date <= user_date_end:
        # Skip past dates
        today = datetime.now(user_tz).date()
        if current_date < today:
            current_date += timedelta(days=1)
            continue

        day_of_week = current_date.weekday()  # Monday=0, Sunday=6

        # Check override first
        override = override_map.get(current_date)
        if override:
            if override.is_unavailable:
                current_date += timedelta(days=1)
                continue
            if not override.start_time or not override.end_time:
                current_date += timedelta(days=1)
                continue
            # Custom hours
            day_slots = _build_day_slots(
                current_date,
                override.start_time,
                override.end_time,
                duration,
                buffer_before,
                buffer_after,
                slot_interval_minutes,
                existing_appointments,
                existing_tasks,
                user_tz,
            )
            slots.extend(day_slots)
        else:
            # Use regular rules for this day
            day_rules = [r for r in rules if r.day_of_week == day_of_week]
            for rule in day_rules:
                day_slots = _build_day_slots(
                    current_date,
                    rule.start_time,
                    rule.end_time,
                    duration,
                    buffer_before,
                    buffer_after,
                    slot_interval_minutes,
                    existing_appointments,
                    existing_tasks,
                    user_tz,
                )
                slots.extend(day_slots)

        current_date += timedelta(days=1)

    client_start_utc = client_start.astimezone(timezone.utc)
    client_end_utc = client_end.astimezone(timezone.utc)
    slots = [slot for slot in slots if client_start_utc <= slot.start <= client_end_utc]

    return slots


def get_reschedule_slots_for_appointment(
    db: Session,
    appointment: Appointment,
    date_start: date,
    date_end: date | None = None,
    client_timezone: str | None = None,
) -> tuple[list[TimeSlot], AppointmentType | None]:
    """Get available reschedule slots for an existing appointment."""
    if not appointment.appointment_type_id:
        raise ValueError("Appointment type not found")

    if not date_end:
        date_end = date_start

    # Keep reschedule windows bounded to a practical range.
    if (date_end - date_start).days > 14:
        date_end = date_start + timedelta(days=14)

    tz = client_timezone or appointment.client_timezone or "America/Los_Angeles"
    _validate_timezone_name(tz, "client timezone")

    query = SlotQuery(
        user_id=appointment.user_id,
        org_id=appointment.organization_id,
        appointment_type_id=appointment.appointment_type_id,
        date_start=date_start,
        date_end=date_end,
        client_timezone=tz,
    )
    slots = get_available_slots(
        db,
        query,
        exclude_appointment_id=appointment.id,
        duration_minutes=appointment.duration_minutes,
        buffer_before_minutes=appointment.buffer_before_minutes,
        buffer_after_minutes=appointment.buffer_after_minutes,
    )

    appt_type = get_appointment_type(db, appointment.appointment_type_id, appointment.organization_id)
    return slots, appt_type


def _build_day_slots(
    slot_date: date,
    start_time: time,
    end_time: time,
    duration_minutes: int,
    buffer_before: int,
    buffer_after: int,
    interval_minutes: int,
    appointments: list["Appointment"],
    tasks: list["Task"],
    user_tz: ZoneInfo,
) -> list[TimeSlot]:
    """Build available slots for a single day."""
    slots = []

    # Create datetime objects in user's timezone, then normalize to UTC
    day_start_local = datetime.combine(slot_date, start_time, tzinfo=user_tz)
    day_end_local = datetime.combine(slot_date, end_time, tzinfo=user_tz)
    day_start = day_start_local.astimezone(timezone.utc)
    day_end = day_end_local.astimezone(timezone.utc)

    # Skip if booking would be in the past
    now = datetime.now(timezone.utc)
    if day_end <= now:
        return slots

    # Start from now if today
    if day_start < now:
        # Round up to next interval, using timedelta to avoid minute=60 ValueError
        minutes_into_interval = now.minute % interval_minutes
        minutes_to_add = interval_minutes - minutes_into_interval if minutes_into_interval else 0
        day_start = now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)

    current = day_start
    total_block = buffer_before + duration_minutes + buffer_after

    while current + timedelta(minutes=total_block) <= day_end + timedelta(minutes=buffer_after):
        slot_start = current + timedelta(minutes=buffer_before)
        slot_end = slot_start + timedelta(minutes=duration_minutes)

        # Check for conflicts with appointments
        has_conflict = False
        for appt in appointments:
            # Include buffer in conflict check
            appt_buffer_before = (
                appt.buffer_before_minutes
                if appt.buffer_before_minutes is not None
                else buffer_before
            )
            appt_buffer_after = (
                appt.buffer_after_minutes if appt.buffer_after_minutes is not None else buffer_after
            )
            appt_block_start = appt.scheduled_start - timedelta(minutes=appt_buffer_before)
            appt_block_end = appt.scheduled_end + timedelta(minutes=appt_buffer_after)

            if not (slot_end <= appt_block_start or slot_start >= appt_block_end):
                has_conflict = True
                break

        # Check for conflicts with tasks
        # Tasks store due_time as local time (user's timezone), not UTC
        if not has_conflict:
            for task in tasks:
                if task.due_date == slot_date and task.due_time and task.duration_minutes:
                    # Task time is in user's local timezone, convert to UTC for comparison
                    task_start_local = datetime.combine(
                        task.due_date, task.due_time, tzinfo=user_tz
                    )
                    task_start = task_start_local.astimezone(timezone.utc)
                    task_end = task_start + timedelta(minutes=task.duration_minutes)
                    if not (slot_end <= task_start or slot_start >= task_end):
                        has_conflict = True
                        break

        if not has_conflict:
            slots.append(TimeSlot(start=slot_start, end=slot_end))

        current += timedelta(minutes=interval_minutes)

    return slots


def _get_conflicting_appointments(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    date_start: date,
    date_end: date,
    exclude_appointment_id: UUID | None = None,
) -> list["Appointment"]:
    """Get appointments that could conflict with new bookings."""
    start_dt = datetime.combine(date_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(date_end, time.max, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    query = db.query(Appointment).filter(
        Appointment.organization_id == org_id,
        Appointment.user_id == user_id,
        Appointment.scheduled_start < end_dt,
        Appointment.scheduled_end > start_dt,
        or_(
            Appointment.status == AppointmentStatus.CONFIRMED.value,
            and_(
                Appointment.status == AppointmentStatus.PENDING.value,
                or_(
                    Appointment.pending_expires_at.is_(None),
                    Appointment.pending_expires_at > now,
                ),
            ),
        ),
    )
    if exclude_appointment_id:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return query.all()


def _get_conflicting_tasks(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    date_start: date,
    date_end: date,
) -> list["Task"]:
    """Get tasks with scheduled times that could conflict."""
    from app.db.enums import OwnerType

    return (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.owner_type == OwnerType.USER.value,
            Task.owner_id == user_id,
            Task.is_completed.is_(False),
            Task.due_date >= date_start,
            Task.due_date <= date_end,
            Task.due_time.isnot(None),
            Task.duration_minutes.isnot(None),
        )
        .all()
    )


# =============================================================================
# Booking
# =============================================================================


def expire_pending_appointments(
    db: Session,
    org_id: UUID | None = None,
    user_id: UUID | None = None,
) -> int:
    """Expire pending appointments past their approval window."""
    now = datetime.now(timezone.utc)
    query = db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.PENDING.value,
        Appointment.pending_expires_at.isnot(None),
        Appointment.pending_expires_at <= now,
    )
    if org_id:
        query = query.filter(Appointment.organization_id == org_id)
    if user_id:
        query = query.filter(Appointment.user_id == user_id)

    updated = query.update(
        {
            Appointment.status: AppointmentStatus.EXPIRED.value,
            Appointment.pending_expires_at: None,
            Appointment.reschedule_token: None,
            Appointment.cancel_token: None,
            Appointment.reschedule_token_expires_at: None,
            Appointment.cancel_token_expires_at: None,
        },
        synchronize_session=False,
    )
    if updated:
        db.commit()
    return updated


def create_booking(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    appointment_type_id: UUID,
    client_name: str,
    client_email: str,
    client_phone: str,
    client_timezone: str,
    scheduled_start: datetime,
    client_notes: str | None = None,
    idempotency_key: str | None = None,
    meeting_mode: str | None = None,
) -> Appointment:
    """
    Create a new appointment booking (pending approval).

    Includes:
    - Idempotency check
    - Token generation for self-service
    - Pending expiry (60 min TTL)
    """
    expire_pending_appointments(db, org_id=org_id, user_id=user_id)

    # Check idempotency
    if idempotency_key:
        idempotency_key = _normalize_idempotency_key(org_id, user_id, idempotency_key)
        existing = (
            db.query(Appointment)
            .filter(
                Appointment.idempotency_key == idempotency_key,
                Appointment.organization_id == org_id,
                Appointment.user_id == user_id,
            )
            .first()
        )
        if existing:
            return existing

    # Get appointment type
    appt_type = (
        db.query(AppointmentType)
        .filter(
            AppointmentType.id == appointment_type_id,
            AppointmentType.organization_id == org_id,
        )
        .first()
    )

    if not appt_type:
        raise ValueError("Appointment type not found")

    allowed_meeting_modes = list(appt_type.meeting_modes or [])
    if appt_type.meeting_mode and appt_type.meeting_mode not in allowed_meeting_modes:
        allowed_meeting_modes.append(appt_type.meeting_mode)
    selected_meeting_mode = meeting_mode or appt_type.meeting_mode
    if selected_meeting_mode not in allowed_meeting_modes:
        raise ValueError("Meeting mode not available for this appointment type")

    _validate_timezone_name(client_timezone, "client timezone")
    scheduled_start = _normalize_scheduled_start(scheduled_start, client_timezone)
    scheduled_end = scheduled_start + timedelta(minutes=appt_type.duration_minutes)
    pending_expires = datetime.now(timezone.utc) + timedelta(minutes=60)
    token_expires = scheduled_end + timedelta(days=7)

    slot_query = SlotQuery(
        user_id=user_id,
        org_id=org_id,
        appointment_type_id=appointment_type_id,
        date_start=scheduled_start.astimezone(_get_timezone(client_timezone)).date(),
        date_end=scheduled_start.astimezone(_get_timezone(client_timezone)).date(),
        client_timezone=client_timezone,
    )
    slots = get_available_slots(db, slot_query)
    if not any(slot.start == scheduled_start for slot in slots):
        raise ValueError("Selected time is no longer available")

    appointment = Appointment(
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appointment_type_id,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        client_notes=client_notes,
        client_timezone=client_timezone,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        duration_minutes=appt_type.duration_minutes,
        buffer_before_minutes=appt_type.buffer_before_minutes,
        buffer_after_minutes=appt_type.buffer_after_minutes,
        meeting_mode=selected_meeting_mode,
        meeting_location=appt_type.meeting_location,
        dial_in_number=appt_type.dial_in_number,
        status=AppointmentStatus.PENDING.value,
        pending_expires_at=pending_expires,
        reschedule_token=generate_token(),
        cancel_token=generate_token(),
        reschedule_token_expires_at=token_expires,
        cancel_token_expires_at=token_expires,
        idempotency_key=idempotency_key,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    if appt_type.auto_approve:
        try:
            appointment = approve_booking(db, appointment, approved_by_user_id=user_id)
        except Exception:
            db.delete(appointment)
            db.commit()
            raise
        return appointment

    # Notify staff about new appointment request
    from app.services import notification_facade

    notification_facade.notify_appointment_requested(
        db=db,
        org_id=org_id,
        staff_user_id=user_id,
        appointment_id=appointment.id,
        client_name=client_name,
        appointment_type=appt_type.name,
        requested_time=scheduled_start.strftime("%Y-%m-%d %H:%M"),
    )

    return appointment


def approve_booking(
    db: Session,
    appointment: Appointment,
    approved_by_user_id: UUID,
) -> Appointment:
    """
    Approve a pending appointment.

    - Re-validates slot availability to prevent double-booking
    - Creates Zoom meeting or Google Meet link based on meeting mode
    - Sets status to confirmed
    - Schedules reminder email
    - Clears pending expiry
    """
    from app.services import appointment_email_service

    if appointment.status != AppointmentStatus.PENDING.value:
        raise ValueError(f"Cannot approve appointment with status {appointment.status}")
    if appointment.pending_expires_at and appointment.pending_expires_at <= datetime.now(
        timezone.utc
    ):
        appointment.status = AppointmentStatus.EXPIRED.value
        appointment.pending_expires_at = None
        appointment.reschedule_token = None
        appointment.cancel_token = None
        appointment.reschedule_token_expires_at = None
        appointment.cancel_token_expires_at = None
        db.commit()
        raise ValueError("Appointment request has expired")

    # Re-validate slot availability to prevent double-booking
    # Another appointment/task may have been created since the request
    if appointment.appointment_type_id:
        # Convert to client timezone before getting date to avoid midnight boundary issues
        client_tz_name = appointment.client_timezone or "UTC"
        try:
            client_tz = ZoneInfo(client_tz_name)
        except Exception:
            client_tz = ZoneInfo("UTC")
        scheduled_date_local = appointment.scheduled_start.astimezone(client_tz).date()

        slot_query = SlotQuery(
            user_id=appointment.user_id,
            org_id=appointment.organization_id,
            appointment_type_id=appointment.appointment_type_id,
            date_start=scheduled_date_local,
            date_end=scheduled_date_local,
            client_timezone=client_tz_name,
        )
        available_slots = get_available_slots(
            db,
            slot_query,
            exclude_appointment_id=appointment.id,  # Exclude this pending appt itself
            duration_minutes=appointment.duration_minutes,
            buffer_before_minutes=appointment.buffer_before_minutes,
            buffer_after_minutes=appointment.buffer_after_minutes,
        )
        if not any(slot.start == appointment.scheduled_start for slot in available_slots):
            raise ValueError(
                "This time slot is no longer available - another appointment or task has been scheduled"
            )

    # Create meeting link based on meeting mode (before changing status)
    meeting_mode = appointment.meeting_mode
    appt_type = (
        db.query(AppointmentType)
        .filter(AppointmentType.id == appointment.appointment_type_id)
        .first()
    )
    appt_type_name = appt_type.name if appt_type else "Appointment"

    if meeting_mode == MeetingMode.ZOOM.value:
        appointment_integrations.create_zoom_meeting(db, appointment, appt_type_name)

    elif meeting_mode == MeetingMode.GOOGLE_MEET.value:
        appointment_integrations.create_google_meet_link(db, appointment, appt_type_name)

    appointment.status = AppointmentStatus.CONFIRMED.value
    appointment.approved_at = datetime.now(timezone.utc)
    appointment.approved_by_user_id = approved_by_user_id
    appointment.pending_expires_at = None

    # Rotate tokens for security
    appointment.reschedule_token = generate_token()
    appointment.cancel_token = generate_token()
    token_expires = appointment.scheduled_end + timedelta(days=7)
    appointment.reschedule_token_expires_at = token_expires
    appointment.cancel_token_expires_at = token_expires

    db.commit()
    db.refresh(appointment)

    # Sync to Google Calendar for non-Google Meet modes (best-effort, after commit)
    if meeting_mode != MeetingMode.GOOGLE_MEET.value:
        google_event_id = appointment_integrations.sync_to_google_calendar(
            db, appointment, "create"
        )
        if google_event_id:
            appointment.google_event_id = google_event_id
            db.commit()
            db.refresh(appointment)

    # Schedule reminder email
    if appt_type and appt_type.reminder_hours_before > 0:
        from app.core.config import settings

        appointment_email_service.schedule_reminder_email(
            db=db,
            appointment=appointment,
            base_url=settings.FRONTEND_URL,
            hours_before=appt_type.reminder_hours_before,
        )

    # Notify staff about confirmed appointment
    from app.services import notification_facade

    notification_facade.notify_appointment_confirmed(
        db=db,
        org_id=appointment.organization_id,
        staff_user_id=appointment.user_id,
        appointment_id=appointment.id,
        client_name=appointment.client_name,
        appointment_type=appt_type_name,
        confirmed_time=appointment.scheduled_start.strftime("%Y-%m-%d %H:%M"),
    )

    # Fire workflow trigger for appointment scheduled
    from app.services import workflow_triggers

    workflow_triggers.trigger_appointment_scheduled(db, appointment)

    return appointment


def reschedule_booking(
    db: Session,
    appointment: Appointment,
    new_start: datetime,
    by_client: bool = False,
    token: str | None = None,
) -> Appointment:
    """Reschedule an appointment to a new time.

    For Zoom appointments, creates a new meeting link.
    For Google Meet, updates the calendar event.
    """
    # Validate token if client-initiated
    if by_client:
        if not token or appointment.reschedule_token != token:
            raise ValueError("Invalid reschedule token")
        if (
            appointment.reschedule_token_expires_at
            and appointment.reschedule_token_expires_at <= datetime.now(timezone.utc)
        ):
            raise ValueError("Reschedule link has expired")

    if appointment.status not in [
        AppointmentStatus.PENDING.value,
        AppointmentStatus.CONFIRMED.value,
    ]:
        raise ValueError(f"Cannot reschedule appointment with status {appointment.status}")
    if appointment.status == AppointmentStatus.PENDING.value and appointment.pending_expires_at:
        if appointment.pending_expires_at <= datetime.now(timezone.utc):
            appointment.status = AppointmentStatus.EXPIRED.value
            appointment.pending_expires_at = None
            appointment.reschedule_token = None
            appointment.cancel_token = None
            appointment.reschedule_token_expires_at = None
            appointment.cancel_token_expires_at = None
            db.commit()
            raise ValueError("Appointment request has expired")
    if not appointment.appointment_type_id:
        raise ValueError("Appointment type not found")

    # Calculate new end time
    new_start = _normalize_scheduled_start(new_start, appointment.client_timezone)
    new_end = new_start + timedelta(minutes=appointment.duration_minutes)

    slot_query = SlotQuery(
        user_id=appointment.user_id,
        org_id=appointment.organization_id,
        appointment_type_id=appointment.appointment_type_id,
        date_start=new_start.astimezone(_get_timezone(appointment.client_timezone)).date(),
        date_end=new_start.astimezone(_get_timezone(appointment.client_timezone)).date(),
        client_timezone=appointment.client_timezone,
    )
    slots = get_available_slots(
        db,
        slot_query,
        exclude_appointment_id=appointment.id,
        duration_minutes=appointment.duration_minutes,
        buffer_before_minutes=appointment.buffer_before_minutes,
        buffer_after_minutes=appointment.buffer_after_minutes,
    )
    if not any(slot.start == new_start for slot in slots):
        raise ValueError("Selected time is no longer available")

    appointment.scheduled_start = new_start
    appointment.scheduled_end = new_end
    if appointment.status == AppointmentStatus.PENDING.value:
        appointment.pending_expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)

    # Regenerate meeting link for Zoom appointments (confirmed only)
    meeting_mode = appointment.meeting_mode
    if (
        meeting_mode == MeetingMode.ZOOM.value
        and appointment.status == AppointmentStatus.CONFIRMED.value
    ):
        appt_type = (
            db.query(AppointmentType)
            .filter(AppointmentType.id == appointment.appointment_type_id)
            .first()
        )
        appt_type_name = appt_type.name if appt_type else "Appointment"
        appointment_integrations.regenerate_zoom_meeting_on_reschedule(
            db,
            appointment,
            appt_type_name,
            new_start,
        )
    elif (
        meeting_mode == MeetingMode.GOOGLE_MEET.value
        and appointment.status == AppointmentStatus.CONFIRMED.value
        and not appointment.google_event_id
    ):
        appt_type = (
            db.query(AppointmentType)
            .filter(AppointmentType.id == appointment.appointment_type_id)
            .first()
        )
        appt_type_name = appt_type.name if appt_type else "Appointment"
        owner_context_message = (
            "Google Meet link creation failed for appointment owner "
            f"{appointment.user_id}. Please reconnect Google Calendar for appointment owner account."
        )
        try:
            appointment_integrations.create_google_meet_link(db, appointment, appt_type_name)
        except ValueError as exc:
            raise ValueError(f"{owner_context_message} Root cause: {exc}") from exc
        if not appointment.google_event_id:
            raise ValueError(
                f"{owner_context_message} Root cause: Google Meet link was not generated."
            )

    # Rotate tokens after reschedule
    appointment.reschedule_token = generate_token()
    appointment.cancel_token = generate_token()
    token_expires = new_end + timedelta(days=7)
    appointment.reschedule_token_expires_at = token_expires
    appointment.cancel_token_expires_at = token_expires

    db.commit()
    db.refresh(appointment)

    # Sync to Google Calendar (best-effort, after commit)
    if appointment.google_event_id and meeting_mode != MeetingMode.GOOGLE_MEET.value:
        updated_event_id = appointment_integrations.sync_to_google_calendar(
            db,
            appointment,
            "update",
        )
        if not updated_event_id:
            # Event may have been deleted in Google - clear ID and optionally recreate
            appointment.google_event_id = None
            db.commit()
            db.refresh(appointment)
    elif meeting_mode == MeetingMode.GOOGLE_MEET.value and appointment.google_event_id:
        # Update Google Meet event time
        appointment_integrations.update_google_meet_event(
            db,
            appointment,
            new_start,
            new_end,
        )

    return appointment


def cancel_booking(
    db: Session,
    appointment: Appointment,
    reason: str | None = None,
    by_client: bool = False,
    token: str | None = None,
) -> Appointment:
    """Cancel an appointment.

    Also deletes associated Zoom meeting if present.
    """
    # Validate token if client-initiated
    if by_client:
        if not token or appointment.cancel_token != token:
            raise ValueError("Invalid cancel token")
        if (
            appointment.cancel_token_expires_at
            and appointment.cancel_token_expires_at <= datetime.now(timezone.utc)
        ):
            raise ValueError("Cancel link has expired")

    if appointment.status not in [
        AppointmentStatus.PENDING.value,
        AppointmentStatus.CONFIRMED.value,
    ]:
        raise ValueError(f"Cannot cancel appointment with status {appointment.status}")
    if appointment.status == AppointmentStatus.PENDING.value and appointment.pending_expires_at:
        if appointment.pending_expires_at <= datetime.now(timezone.utc):
            appointment.status = AppointmentStatus.EXPIRED.value
            appointment.pending_expires_at = None
            appointment.reschedule_token = None
            appointment.cancel_token = None
            appointment.reschedule_token_expires_at = None
            appointment.cancel_token_expires_at = None
            db.commit()
            raise ValueError("Appointment request has expired")

    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancelled_at = datetime.now(timezone.utc)
    appointment.cancelled_by_client = by_client
    appointment.cancellation_reason = reason
    appointment.reschedule_token = None
    appointment.cancel_token = None
    appointment.reschedule_token_expires_at = None
    appointment.cancel_token_expires_at = None

    db.commit()
    db.refresh(appointment)

    # Delete Zoom meeting (best-effort, after commit)
    if appointment.zoom_meeting_id:
        appointment_integrations.delete_zoom_meeting(db, appointment)

    # Delete from Google Calendar (best-effort, after commit)
    if appointment.google_event_id:
        appointment_integrations.sync_to_google_calendar(db, appointment, "delete")
        appointment.google_event_id = None
        db.commit()
        db.refresh(appointment)

    # Notify staff about cancelled appointment
    from app.services import notification_facade

    appt_type = (
        db.query(AppointmentType)
        .filter(AppointmentType.id == appointment.appointment_type_id)
        .first()
    )
    notification_facade.notify_appointment_cancelled(
        db=db,
        org_id=appointment.organization_id,
        staff_user_id=appointment.user_id,
        appointment_id=appointment.id,
        client_name=appointment.client_name,
        appointment_type=appt_type.name if appt_type else "Appointment",
        cancelled_time=appointment.scheduled_start.strftime("%Y-%m-%d %H:%M"),
    )

    return appointment


def get_appointment(
    db: Session,
    appointment_id: UUID,
    org_id: UUID,
) -> Appointment | None:
    """Get appointment by ID."""
    return (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.organization_id == org_id,
        )
        .first()
    )


def get_appointment_by_token(
    db: Session,
    org_id: UUID,
    token: str,
    token_type: str,  # "reschedule" or "cancel"
) -> Appointment | None:
    """Get appointment by self-service token scoped to org."""
    now = datetime.now(timezone.utc)
    if token_type == "reschedule":  # nosec B105
        appt = (
            db.query(Appointment)
            .filter(
                Appointment.reschedule_token == token,
                Appointment.organization_id == org_id,
            )
            .first()
        )
        if not appt:
            return None
        if appt.reschedule_token_expires_at and appt.reschedule_token_expires_at <= now:
            return None
    elif token_type == "cancel":  # nosec B105
        appt = (
            db.query(Appointment)
            .filter(
                Appointment.cancel_token == token,
                Appointment.organization_id == org_id,
            )
            .first()
        )
        if not appt:
            return None
        if appt.cancel_token_expires_at and appt.cancel_token_expires_at <= now:
            return None
    else:
        return None

    return _validate_self_service_appointment_state(db, appt, now)


def get_appointment_by_manage_token(
    db: Session,
    org_id: UUID,
    token: str,
) -> Appointment | None:
    """Get appointment by either self-service token (reschedule/cancel)."""
    now = datetime.now(timezone.utc)
    appt = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == org_id,
            or_(Appointment.reschedule_token == token, Appointment.cancel_token == token),
        )
        .first()
    )
    if not appt:
        return None

    # Token-specific expiry checks
    if (
        appt.reschedule_token == token
        and appt.reschedule_token_expires_at
        and appt.reschedule_token_expires_at <= now
    ):
        return None
    if (
        appt.cancel_token == token
        and appt.cancel_token_expires_at
        and appt.cancel_token_expires_at <= now
    ):
        return None

    return _validate_self_service_appointment_state(db, appt, now)


def _validate_self_service_appointment_state(
    db: Session,
    appt: Appointment,
    now: datetime,
) -> Appointment | None:
    """Validate appointment state for all self-service token flows."""
    if appt.status in [
        AppointmentStatus.CANCELLED.value,
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.NO_SHOW.value,
        AppointmentStatus.EXPIRED.value,
    ]:
        return None

    if (
        appt.status == AppointmentStatus.PENDING.value
        and appt.pending_expires_at
        and appt.pending_expires_at <= now
    ):
        appt.status = AppointmentStatus.EXPIRED.value
        appt.pending_expires_at = None
        appt.reschedule_token = None
        appt.cancel_token = None
        appt.reschedule_token_expires_at = None
        appt.cancel_token_expires_at = None
        db.commit()
        return None

    return appt


def list_appointments(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    status: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Appointment], int]:
    """List appointments for a user with pagination.

    When surrogate_id and/or intended_parent_id are provided, filters to appointments
    matching EITHER the surrogate_id OR the intended_parent_id (used for match-scoped views).
    """
    if status in (
        None,
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.PENDING.value,
    ):
        appointment_integrations.backfill_confirmed_appointments_to_google(
            db=db,
            user_id=user_id,
            org_id=org_id,
            date_start=date_start,
            date_end=date_end,
        )
        appointment_integrations.sync_manual_google_events_for_appointments(
            db=db,
            user_id=user_id,
            org_id=org_id,
            date_start=date_start,
            date_end=date_end,
        )

    expire_pending_appointments(db, org_id=org_id, user_id=user_id)
    query = db.query(Appointment).filter(
        Appointment.user_id == user_id,
        Appointment.organization_id == org_id,
    )

    if status:
        query = query.filter(Appointment.status == status)

    if date_start:
        start_dt = datetime.combine(date_start, time.min, tzinfo=timezone.utc)
        query = query.filter(Appointment.scheduled_start >= start_dt)

    if date_end:
        end_dt = datetime.combine(date_end, time.max, tzinfo=timezone.utc)
        query = query.filter(Appointment.scheduled_start <= end_dt)

    # Filter by surrogate_id OR intended_parent_id (for match-scoped views)
    if surrogate_id and intended_parent_id:
        query = query.filter(
            or_(
                Appointment.surrogate_id == surrogate_id,
                Appointment.intended_parent_id == intended_parent_id,
            )
        )
    elif surrogate_id:
        query = query.filter(Appointment.surrogate_id == surrogate_id)
    elif intended_parent_id:
        query = query.filter(Appointment.intended_parent_id == intended_parent_id)

    total = query.count()
    appointments = (
        query.order_by(Appointment.scheduled_start.desc()).offset(offset).limit(limit).all()
    )

    return appointments, total


# =============================================================================
# Email Logging
# =============================================================================


def log_appointment_email(
    db: Session,
    org_id: UUID,
    appointment_id: UUID,
    email_type: str,
    recipient_email: str,
    subject: str,
) -> AppointmentEmailLog:
    """Log an appointment email."""
    log = AppointmentEmailLog(
        organization_id=org_id,
        appointment_id=appointment_id,
        email_type=email_type,
        recipient_email=recipient_email,
        subject=subject,
        status="pending",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def mark_email_sent(
    db: Session,
    log: AppointmentEmailLog,
    external_message_id: str | None = None,
) -> AppointmentEmailLog:
    """Mark an appointment email as sent."""
    log.status = "sent"
    log.sent_at = datetime.now(timezone.utc)
    log.external_message_id = external_message_id
    db.commit()
    db.refresh(log)
    return log


def mark_email_failed(
    db: Session,
    log: AppointmentEmailLog,
    error: str,
) -> AppointmentEmailLog:
    """Mark an appointment email as failed."""
    log.status = "failed"
    log.error = error
    db.commit()
    db.refresh(log)
    return log


# =============================================================================
# Helpers
# =============================================================================


def _check_gmail_connected(db: Session, user_id: UUID) -> bool:
    """Check if user has Gmail connected."""
    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "gmail",
        )
        .first()
    )
    return integration is not None and integration.access_token_encrypted is not None
