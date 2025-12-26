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
    AppointmentType, AvailabilityRule, AvailabilityOverride,
    BookingLink, Appointment, AppointmentEmailLog, Task, UserIntegration
)
from app.db.enums import AppointmentStatus, AppointmentEmailType, MeetingMode


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
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
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
    reminder_hours_before: int = 24,
) -> AppointmentType:
    """Create a new appointment type for a user."""
    # Check Gmail connection requirement
    gmail_connected = _check_gmail_connected(db, user_id)
    if not gmail_connected:
        raise ValueError("Gmail must be connected to create appointment types")
    
    slug = generate_slug(name)
    # Ensure unique slug for user
    base_slug = slug
    counter = 1
    while db.query(AppointmentType).filter(
        AppointmentType.user_id == user_id,
        AppointmentType.slug == slug
    ).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    appt_type = AppointmentType(
        organization_id=org_id,
        user_id=user_id,
        name=name,
        slug=slug,
        description=description,
        duration_minutes=duration_minutes,
        buffer_before_minutes=buffer_before_minutes,
        buffer_after_minutes=buffer_after_minutes,
        meeting_mode=meeting_mode,
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
    reminder_hours_before: int | None = None,
    is_active: bool | None = None,
) -> AppointmentType:
    """Update an appointment type."""
    if name is not None:
        appt_type.name = name
        new_slug = generate_slug(name)
        base_slug = new_slug
        counter = 1
        while db.query(AppointmentType).filter(
            AppointmentType.user_id == appt_type.user_id,
            AppointmentType.slug == new_slug,
            AppointmentType.id != appt_type.id,
        ).first():
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
    if meeting_mode is not None:
        appt_type.meeting_mode = meeting_mode
    if reminder_hours_before is not None:
        appt_type.reminder_hours_before = reminder_hours_before
    if is_active is not None:
        appt_type.is_active = is_active
    
    db.commit()
    db.refresh(appt_type)
    return appt_type


def get_appointment_type(
    db: Session,
    appt_type_id: UUID,
    org_id: UUID,
) -> AppointmentType | None:
    """Get appointment type by ID."""
    return db.query(AppointmentType).filter(
        AppointmentType.id == appt_type_id,
        AppointmentType.organization_id == org_id,
    ).first()


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
        query = query.filter(AppointmentType.is_active == True)
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
    # Delete existing rules
    db.query(AvailabilityRule).filter(
        AvailabilityRule.user_id == user_id,
        AvailabilityRule.organization_id == org_id,
    ).delete()
    
    # Create new rules
    new_rules = []
    for rule_data in rules:
        rule = AvailabilityRule(
            organization_id=org_id,
            user_id=user_id,
            day_of_week=rule_data["day_of_week"],
            start_time=time.fromisoformat(rule_data["start_time"]),
            end_time=time.fromisoformat(rule_data["end_time"]),
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
    return db.query(AvailabilityRule).filter(
        AvailabilityRule.user_id == user_id,
        AvailabilityRule.organization_id == org_id,
    ).order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time).all()


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
    existing = db.query(AvailabilityOverride).filter(
        AvailabilityOverride.user_id == user_id,
        AvailabilityOverride.organization_id == org_id,
        AvailabilityOverride.override_date == override_date,
    ).first()
    
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
    override = db.query(AvailabilityOverride).filter(
        AvailabilityOverride.id == override_id,
        AvailabilityOverride.user_id == user_id,
        AvailabilityOverride.organization_id == org_id,
    ).first()
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
    existing = db.query(BookingLink).filter(
        BookingLink.user_id == user_id,
        BookingLink.organization_id == org_id,
    ).first()
    
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
) -> BookingLink | None:
    """Regenerate a booking link with a new slug."""
    link = db.query(BookingLink).filter(
        BookingLink.user_id == user_id,
    ).first()
    
    if not link:
        return None
    
    link.public_slug = generate_public_slug()
    db.commit()
    db.refresh(link)
    return link


def get_booking_link_by_slug(
    db: Session,
    public_slug: str,
) -> BookingLink | None:
    """Get a booking link by its public slug."""
    return db.query(BookingLink).filter(
        BookingLink.public_slug == public_slug,
        BookingLink.is_active == True,
    ).first()


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
    appt_type = db.query(AppointmentType).filter(
        AppointmentType.id == query.appointment_type_id,
        AppointmentType.organization_id == query.org_id,
    ).first()
    
    if not appt_type or not appt_type.is_active:
        return []
    
    duration = duration_minutes if duration_minutes is not None else appt_type.duration_minutes
    buffer_before = buffer_before_minutes if buffer_before_minutes is not None else appt_type.buffer_before_minutes
    buffer_after = buffer_after_minutes if buffer_after_minutes is not None else appt_type.buffer_after_minutes
    
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
        db, query.user_id, query.org_id,
        user_date_start, user_date_end
    )
    override_map = {o.override_date: o for o in overrides}
    
    # Get existing appointments
    existing_appointments = _get_conflicting_appointments(
        db,
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
    slots = [
        slot for slot in slots
        if client_start_utc <= slot.start <= client_end_utc
    ]

    return slots


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
        day_start = (now.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add))
    
    current = day_start
    total_block = buffer_before + duration_minutes + buffer_after
    
    while current + timedelta(minutes=total_block) <= day_end + timedelta(minutes=buffer_after):
        slot_start = current + timedelta(minutes=buffer_before)
        slot_end = slot_start + timedelta(minutes=duration_minutes)
        
        # Check for conflicts with appointments
        has_conflict = False
        for appt in appointments:
            # Include buffer in conflict check
            appt_buffer_before = appt.buffer_before_minutes if appt.buffer_before_minutes is not None else buffer_before
            appt_buffer_after = appt.buffer_after_minutes if appt.buffer_after_minutes is not None else buffer_after
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
                    task_start_local = datetime.combine(task.due_date, task.due_time, tzinfo=user_tz)
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
    
    return db.query(Task).filter(
        Task.organization_id == org_id,
        Task.owner_type == OwnerType.USER.value,
        Task.owner_id == user_id,
        Task.is_completed == False,
        Task.due_date >= date_start,
        Task.due_date <= date_end,
        Task.due_time.isnot(None),
        Task.duration_minutes.isnot(None),
    ).all()


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
        existing = db.query(Appointment).filter(
            Appointment.idempotency_key == idempotency_key,
            Appointment.organization_id == org_id,
            Appointment.user_id == user_id,
        ).first()
        if existing:
            return existing
    
    # Get appointment type
    appt_type = db.query(AppointmentType).filter(
        AppointmentType.id == appointment_type_id,
        AppointmentType.organization_id == org_id,
    ).first()
    
    if not appt_type:
        raise ValueError("Appointment type not found")
    
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
        meeting_mode=appt_type.meeting_mode,
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
    
    # Notify staff about new appointment request
    from app.services import notification_service
    notification_service.notify_appointment_requested(
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
    - Sets status to confirmed
    - Clears pending expiry
    - (Future: Create Zoom meeting, add to Google Calendar)
    """
    if appointment.status != AppointmentStatus.PENDING.value:
        raise ValueError(f"Cannot approve appointment with status {appointment.status}")
    if appointment.pending_expires_at and appointment.pending_expires_at <= datetime.now(timezone.utc):
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
            db, slot_query,
            exclude_appointment_id=appointment.id,  # Exclude this pending appt itself
            duration_minutes=appointment.duration_minutes,
            buffer_before_minutes=appointment.buffer_before_minutes,
            buffer_after_minutes=appointment.buffer_after_minutes,
        )
        if not any(slot.start == appointment.scheduled_start for slot in available_slots):
            raise ValueError("This time slot is no longer available - another appointment or task has been scheduled")
    
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
    
    # Notify staff about confirmed appointment
    from app.services import notification_service
    appt_type = db.query(AppointmentType).filter(
        AppointmentType.id == appointment.appointment_type_id
    ).first()
    notification_service.notify_appointment_confirmed(
        db=db,
        org_id=appointment.organization_id,
        staff_user_id=appointment.user_id,
        appointment_id=appointment.id,
        client_name=appointment.client_name,
        appointment_type=appt_type.name if appt_type else "Appointment",
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
    """Reschedule an appointment to a new time."""
    # Validate token if client-initiated
    if by_client:
        if not token or appointment.reschedule_token != token:
            raise ValueError("Invalid reschedule token")
        if appointment.reschedule_token_expires_at and appointment.reschedule_token_expires_at <= datetime.now(timezone.utc):
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
    
    # Rotate tokens after reschedule
    appointment.reschedule_token = generate_token()
    appointment.cancel_token = generate_token()
    token_expires = new_end + timedelta(days=7)
    appointment.reschedule_token_expires_at = token_expires
    appointment.cancel_token_expires_at = token_expires
    
    db.commit()
    db.refresh(appointment)
    
    return appointment


def cancel_booking(
    db: Session,
    appointment: Appointment,
    reason: str | None = None,
    by_client: bool = False,
    token: str | None = None,
) -> Appointment:
    """Cancel an appointment."""
    # Validate token if client-initiated
    if by_client:
        if not token or appointment.cancel_token != token:
            raise ValueError("Invalid cancel token")
        if appointment.cancel_token_expires_at and appointment.cancel_token_expires_at <= datetime.now(timezone.utc):
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
    
    # Notify staff about cancelled appointment
    from app.services import notification_service
    appt_type = db.query(AppointmentType).filter(
        AppointmentType.id == appointment.appointment_type_id
    ).first()
    notification_service.notify_appointment_cancelled(
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
    return db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == org_id,
    ).first()


def get_appointment_by_token(
    db: Session,
    token: str,
    token_type: str,  # "reschedule" or "cancel"
) -> Appointment | None:
    """Get appointment by self-service token."""
    now = datetime.now(timezone.utc)
    if token_type == "reschedule":
        appt = db.query(Appointment).filter(
            Appointment.reschedule_token == token
        ).first()
        if not appt:
            return None
        if appt.reschedule_token_expires_at and appt.reschedule_token_expires_at <= now:
            return None
    elif token_type == "cancel":
        appt = db.query(Appointment).filter(
            Appointment.cancel_token == token
        ).first()
        if not appt:
            return None
        if appt.cancel_token_expires_at and appt.cancel_token_expires_at <= now:
            return None
    else:
        return None

    if appt.status in [
        AppointmentStatus.CANCELLED.value,
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.NO_SHOW.value,
        AppointmentStatus.EXPIRED.value,
    ]:
        return None

    if appt.status == AppointmentStatus.PENDING.value and appt.pending_expires_at and appt.pending_expires_at <= now:
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
    case_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Appointment], int]:
    """List appointments for a user with pagination.
    
    When case_id and/or intended_parent_id are provided, filters to appointments
    matching EITHER the case_id OR the intended_parent_id (used for match-scoped views).
    """
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
    
    # Filter by case_id OR intended_parent_id (for match-scoped views)
    if case_id and intended_parent_id:
        query = query.filter(
            or_(
                Appointment.case_id == case_id,
                Appointment.intended_parent_id == intended_parent_id,
            )
        )
    elif case_id:
        query = query.filter(Appointment.case_id == case_id)
    elif intended_parent_id:
        query = query.filter(Appointment.intended_parent_id == intended_parent_id)
    
    total = query.count()
    appointments = query.order_by(
        Appointment.scheduled_start.desc()
    ).offset(offset).limit(limit).all()
    
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
    integration = db.query(UserIntegration).filter(
        UserIntegration.user_id == user_id,
        UserIntegration.integration_type == "gmail",
    ).first()
    return integration is not None and integration.access_token_encrypted is not None
