"""Shared local reschedule and cancellation changes.

Callers own authorization, availability, workflow policy, audit, and the final commit.
Provider identity is checked before taking row locks; this module only persists
local changes and an existing Google sync job in the caller's transaction.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import AppointmentEmailType, AppointmentStatus
from app.db.models import Appointment, AppointmentType
from app.services import appointment_email_service, appointment_google_sync_service


@dataclass(frozen=True, repr=False)
class AppointmentSnapshot:
    id: UUID
    organization_id: UUID
    user_id: UUID
    appointment_type_id: UUID | None
    surrogate_id: UUID | None
    intended_parent_id: UUID | None
    donor_id: UUID | None
    match_id: UUID | None
    attempt_id: UUID | None
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    client_timezone: str
    client_email: str
    pending_expires_at: datetime | None
    reschedule_token: str | None
    cancel_token: str | None
    reschedule_token_expires_at: datetime | None
    cancel_token_expires_at: datetime | None
    meeting_mode: str
    zoom_meeting_id: str | None
    zoom_join_url: str | None
    google_meet_url: str | None
    google_event_id: str | None
    google_calendar_id: str | None
    google_account_email: str | None
    google_integration_id: UUID | None
    google_event_etag: str | None
    google_sync_revision: int
    google_sync_state: str | None

    @classmethod
    def from_appointment(cls, appointment: Appointment) -> AppointmentSnapshot:
        return cls(**{field: getattr(appointment, field) for field in cls.__dataclass_fields__})


@dataclass(frozen=True, repr=False)
class PreparedAppointmentChange:
    snapshot: AppointmentSnapshot
    google_link: appointment_google_sync_service.PreparedGoogleLink | None


def prepare_change(
    db: Session,
    appointment: Appointment,
    *,
    verify_google_link: bool,
) -> PreparedAppointmentChange:
    """Capture the local state and optionally verify an exact Google link before locks."""
    snapshot = AppointmentSnapshot.from_appointment(appointment)
    google_link = (
        appointment_google_sync_service.prepare_link(db, appointment)
        if verify_google_link and appointment.google_event_id
        else None
    )
    return PreparedAppointmentChange(snapshot=snapshot, google_link=google_link)


def lock_and_validate(
    db: Session,
    prepared: PreparedAppointmentChange,
    *,
    stale_message: str,
) -> Appointment:
    """Lock the exact tenant row and reject any change since provider preflight."""
    snapshot = prepared.snapshot
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == snapshot.id,
            Appointment.organization_id == snapshot.organization_id,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if appointment is None:
        raise ValueError(stale_message)
    validate_change(appointment, prepared, stale_message=stale_message)
    return appointment


def validate_change(
    appointment: Appointment,
    prepared: PreparedAppointmentChange,
    *,
    stale_message: str,
) -> None:
    """Validate a refreshed appointment; the caller chooses whether to lock it."""
    snapshot = prepared.snapshot
    if AppointmentSnapshot.from_appointment(appointment) != snapshot:
        raise ValueError(stale_message)
    link = prepared.google_link
    if link and (
        appointment.google_event_id != link.event_id
        or appointment.google_integration_id not in {None, link.integration_id}
        or appointment.google_calendar_id not in {None, link.calendar_id}
        or appointment.scheduled_start != link.start
        or appointment.scheduled_end != link.end
    ):
        raise ValueError(stale_message)


def apply_reschedule(
    db: Session,
    appointment: Appointment,
    prepared: PreparedAppointmentChange,
    *,
    new_start: datetime,
    new_end: datetime,
    make_token: Callable[[], str],
    update_pending_expiry: bool,
    pending_expires_at: datetime | None,
    email_reason_type: str,
    email_reason_message: str,
    email_types: tuple[AppointmentEmailType, ...] | None,
) -> None:
    """Apply one local reschedule and its dependent intents without committing."""
    if (
        appointment.id != prepared.snapshot.id
        or appointment.organization_id != prepared.snapshot.organization_id
    ):
        raise ValueError("Appointment changed; refresh and try again")
    appointment.scheduled_start = new_start
    appointment.scheduled_end = new_end
    if update_pending_expiry and appointment.status == AppointmentStatus.PENDING.value:
        appointment.pending_expires_at = pending_expires_at
    appointment.reschedule_token = make_token()
    appointment.cancel_token = make_token()
    token_expires = new_end + timedelta(days=7)
    appointment.reschedule_token_expires_at = token_expires
    appointment.cancel_token_expires_at = token_expires
    appointment_email_service.cancel_queued_appointment_emails(
        db,
        appointment,
        reason_type=email_reason_type,
        reason_message=email_reason_message,
        email_types=email_types,
        commit=False,
    )
    if prepared.google_link:
        appointment_google_sync_service.enqueue(
            db, appointment, action="reschedule", link=prepared.google_link
        )


def apply_cancel(
    db: Session,
    appointment: Appointment,
    prepared: PreparedAppointmentChange,
    *,
    cancelled_at: datetime,
    by_client: bool,
    reason: str | None,
    email_reason_type: str,
    email_reason_message: str,
    email_types: tuple[AppointmentEmailType, ...] | None,
) -> None:
    """Apply one local cancellation and its dependent intents without committing."""
    if (
        appointment.id != prepared.snapshot.id
        or appointment.organization_id != prepared.snapshot.organization_id
    ):
        raise ValueError("Appointment changed; refresh and try again")
    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.cancelled_at = cancelled_at
    appointment.cancelled_by_client = by_client
    appointment.cancellation_reason = reason
    appointment.reschedule_token = None
    appointment.cancel_token = None
    appointment.reschedule_token_expires_at = None
    appointment.cancel_token_expires_at = None
    appointment_email_service.cancel_queued_appointment_emails(
        db,
        appointment,
        reason_type=email_reason_type,
        reason_message=email_reason_message,
        email_types=email_types,
        commit=False,
    )
    if prepared.google_link:
        appointment_google_sync_service.enqueue(
            db, appointment, action="cancel", link=prepared.google_link
        )


def apply_external_change(
    db: Session,
    appointment: Appointment,
    *,
    scheduled_start: datetime | None,
    scheduled_end: datetime | None,
    status: str,
    actor_user_id: UUID | None = None,
    timezone: str | None = None,
) -> Appointment:
    """Accept a verified Google organizer change without committing or echoing it."""
    from app.db.enums import AuditEventType
    from app.services import appointment_service, audit_service, org_service

    if status == AppointmentStatus.CANCELLED.value:
        if appointment.status == AppointmentStatus.CANCELLED.value:
            return appointment
        if appointment.status != AppointmentStatus.CONFIRMED.value:
            raise ValueError("Only confirmed appointments accept external cancellation")
        prepared = prepare_change(db, appointment, verify_google_link=False)
        apply_cancel(
            db,
            appointment,
            prepared,
            cancelled_at=datetime.now(UTC),
            by_client=False,
            reason="Cancelled in Google Calendar",
            email_reason_type="appointment_cancelled",
            email_reason_message="Appointment was cancelled",
            email_types=None,
        )
        event_type = AuditEventType.APPOINTMENT_CANCELLED
    elif status == AppointmentStatus.CONFIRMED.value:
        if appointment.status != AppointmentStatus.CONFIRMED.value:
            raise ValueError("Only confirmed appointments accept external rescheduling")
        if not scheduled_start or not scheduled_end:
            raise ValueError("External appointment interval is missing")
        if scheduled_start.tzinfo is None or scheduled_end.tzinfo is None:
            raise ValueError("External appointment interval must include a timezone")
        start = scheduled_start.astimezone(UTC)
        end = scheduled_end.astimezone(UTC)
        if end <= start or (end - start).total_seconds() % 60:
            raise ValueError("External appointment interval is invalid")
        resolved_timezone = timezone or appointment.client_timezone
        appointment_service.validate_timezone_name(resolved_timezone, "timezone")
        if (
            appointment.scheduled_start == start
            and appointment.scheduled_end == end
            and appointment.client_timezone == resolved_timezone
        ):
            return appointment
        if not appointment.appointment_type_id:
            raise ValueError("Appointment type not found")
        duration = int((end - start).total_seconds() // 60)
        local_date = start.astimezone(appointment_service._get_timezone(resolved_timezone)).date()
        slots = appointment_service.get_available_slots(
            db,
            appointment_service.SlotQuery(
                user_id=appointment.user_id,
                org_id=appointment.organization_id,
                appointment_type_id=appointment.appointment_type_id,
                date_start=local_date,
                date_end=local_date,
                client_timezone=resolved_timezone,
            ),
            exclude_appointment_id=appointment.id,
            duration_minutes=duration,
            buffer_before_minutes=appointment.buffer_before_minutes,
            buffer_after_minutes=appointment.buffer_after_minutes,
        )
        if not any(slot.start == start for slot in slots):
            raise ValueError("External appointment time is unavailable")
        prepared = prepare_change(db, appointment, verify_google_link=False)
        apply_reschedule(
            db,
            appointment,
            prepared,
            new_start=start,
            new_end=end,
            make_token=lambda: secrets.token_urlsafe(32),
            update_pending_expiry=False,
            pending_expires_at=None,
            email_reason_type="appointment_rescheduled",
            email_reason_message="Appointment was rescheduled",
            email_types=None,
        )
        appointment.client_timezone = resolved_timezone
        appointment.duration_minutes = duration
        appointment_type = db.get(AppointmentType, appointment.appointment_type_id)
        if appointment_type and appointment_type.reminder_hours_before > 0:
            org = org_service.get_org_by_id(db, appointment.organization_id)
            appointment_email_service.schedule_reminder_email(
                db,
                appointment,
                base_url=org_service.get_org_portal_base_url(org),
                hours_before=appointment_type.reminder_hours_before,
                commit=False,
            )
        event_type = AuditEventType.APPOINTMENT_RESCHEDULED
    else:
        raise ValueError("Unsupported external appointment status")

    appointment.revision += 1
    audit_service.log_event(
        db=db,
        org_id=appointment.organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type="appointment",
        target_id=appointment.id,
        details={"source": "google_calendar", "revision": appointment.revision},
    )
    return appointment
