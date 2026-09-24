"""Transactional scheduling commands used only while scheduling v2 is enabled."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import (
    AppointmentEmailType,
    AppointmentStatus,
    AuditEventType,
    JobType,
    MeetingMode,
    NotificationType,
)
from app.db.models import Appointment, AppointmentType, Membership, User
from app.services import (
    appointment_command_service,
    appointment_email_service,
    audit_service,
    job_service,
    org_service,
)


class SchedulingConflict(ValueError):
    """A request has a stale revision or reuses an idempotency key."""


def public_actor_scope(token: str) -> str:
    return f"public:{hashlib.sha256(token.encode()).hexdigest()}"


def staff_actor_scope(user_id: UUID) -> str:
    return f"staff:{user_id}"


def _request_hash(action: str, payload: dict) -> str:
    encoded = json.dumps({"action": action, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _replay(
    db: Session,
    *,
    org_id: UUID,
    actor_scope: str,
    request_id: str | None,
    request_hash: str,
) -> Appointment | None:
    if not request_id:
        return None
    from app.db.models import SchedulingRequestReceipt

    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"scheduling:{org_id}:{actor_scope}:{request_id}"},
        )
    receipt = (
        db.query(SchedulingRequestReceipt)
        .filter(
            SchedulingRequestReceipt.organization_id == org_id,
            SchedulingRequestReceipt.actor_scope == actor_scope,
            SchedulingRequestReceipt.request_key == request_id,
        )
        .one_or_none()
    )
    if receipt is None:
        return None
    if receipt.request_hash != request_hash:
        raise SchedulingConflict("Request ID was already used for a different action")
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == receipt.appointment_id, Appointment.organization_id == org_id)
        .one_or_none()
    )
    if appointment is None:
        raise SchedulingConflict("Original appointment is no longer available")
    # Only the safe command outcome is replayed. Other read fields remain current.
    appointment._scheduling_replay_result = dict(receipt.result_json)
    return appointment


def _save_receipt(
    db: Session,
    *,
    appointment: Appointment,
    actor_scope: str,
    request_id: str | None,
    request_hash: str,
) -> None:
    if not request_id:
        return
    from app.db.models import SchedulingRequestReceipt

    db.add(
        SchedulingRequestReceipt(
            organization_id=appointment.organization_id,
            request_key=request_id,
            actor_scope=actor_scope,
            request_hash=request_hash,
            appointment_id=appointment.id,
            result_revision=appointment.revision,
            result_json={
                "id": str(appointment.id),
                "revision": appointment.revision,
                "status": appointment.status,
                "scheduled_start": appointment.scheduled_start.isoformat(),
                "scheduled_end": appointment.scheduled_end.isoformat(),
            },
        )
    )
    db.flush()


def replay_public_change(
    db: Session,
    *,
    org_id: UUID,
    token: str,
    request_id: str | None,
    action: str,
    new_start: datetime | None = None,
    reason: str | None = None,
) -> Appointment | None:
    """Replay one exact old-token command after token rotation or cancellation."""
    if not request_id:
        return None
    from app.db.models import SchedulingRequestReceipt

    scope = public_actor_scope(token)
    receipt = (
        db.query(SchedulingRequestReceipt)
        .filter(
            SchedulingRequestReceipt.organization_id == org_id,
            SchedulingRequestReceipt.actor_scope == scope,
            SchedulingRequestReceipt.request_key == request_id,
        )
        .one_or_none()
    )
    if receipt is None:
        return None
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == receipt.appointment_id,
            Appointment.organization_id == org_id,
        )
        .one_or_none()
    )
    if appointment is None:
        raise SchedulingConflict("Original appointment is no longer available")
    if action == "reschedule":
        from app.services import appointment_service

        assert new_start is not None
        normalized = appointment_service._normalize_scheduled_start(
            new_start, appointment.client_timezone
        )
        payload = {
            "appointment_id": appointment.id,
            "new_start": normalized,
            "override_availability": False,
            "override_reason": None,
        }
    elif action == "cancel":
        payload = {"appointment_id": appointment.id, "reason": reason}
    else:
        raise ValueError("Unsupported public scheduling action")
    return _replay(
        db,
        org_id=org_id,
        actor_scope=scope,
        request_id=request_id,
        request_hash=_request_hash(action, payload),
    )


def _check_revision(appointment: Appointment, expected_revision: int | None) -> None:
    if expected_revision is not None and appointment.revision != expected_revision:
        raise SchedulingConflict("Appointment changed; refresh and try again")


def _check_override(override_availability: bool, override_reason: str | None) -> str | None:
    reason = (override_reason or "").strip()
    if override_availability and not reason:
        raise ValueError("A reason is required to override availability")
    if reason and not override_availability:
        raise ValueError("Availability override must be selected for this reason")
    return reason or None


def _lock_owner(db: Session, org_id: UUID, owner_id: UUID) -> None:
    active = (
        db.query(User.id)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            User.id == owner_id,
            User.is_active.is_(True),
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .with_for_update(of=(User, Membership))
        .first()
    )
    if active is None:
        raise ValueError("Appointment owner is unavailable")


def _lock_appointment(db: Session, appointment: Appointment) -> Appointment:
    current = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment.id,
            Appointment.organization_id == appointment.organization_id,
        )
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if current is None:
        raise SchedulingConflict("Appointment changed; refresh and try again")
    if hasattr(current, "_scheduling_replay_result"):
        delattr(current, "_scheduling_replay_result")
    return current


def _check_slot(
    db: Session,
    appointment: Appointment,
    start: datetime,
    *,
    override_availability: bool,
) -> None:
    if override_availability:
        return
    from app.services import appointment_service
    from app.services.calendar_binding_service import CalendarAvailabilityUnavailable

    if not appointment.appointment_type_id:
        raise ValueError("Appointment type not found")
    client_tz = appointment.client_timezone
    local_date = start.astimezone(appointment_service._get_timezone(client_tz)).date()
    try:
        slots = appointment_service.get_available_slots(
            db,
            appointment_service.SlotQuery(
                user_id=appointment.user_id,
                org_id=appointment.organization_id,
                appointment_type_id=appointment.appointment_type_id,
                date_start=local_date,
                date_end=local_date,
                client_timezone=client_tz,
            ),
            exclude_appointment_id=appointment.id,
            duration_minutes=appointment.duration_minutes,
            buffer_before_minutes=appointment.buffer_before_minutes,
            buffer_after_minutes=appointment.buffer_after_minutes,
        )
    except CalendarAvailabilityUnavailable as exc:
        raise SchedulingConflict("Required Google Calendar availability is unavailable") from exc
    if not any(slot.start == start for slot in slots):
        raise ValueError("Selected time is no longer available")


def _base_url(db: Session, org_id: UUID) -> str:
    org = org_service.get_org_by_id(db, org_id)
    return org_service.get_org_portal_base_url(org)


def _google_owned(appointment: Appointment) -> bool:
    return bool(appointment.google_event_id and appointment.google_sync_state != "unlinked")


def _queue_notice(
    db: Session,
    appointment: Appointment,
    email_type: AppointmentEmailType,
    *,
    old_start: datetime | None = None,
) -> None:
    if email_type is not AppointmentEmailType.REQUEST_RECEIVED and _google_owned(appointment):
        return
    appointment_email_service.send_appointment_email(
        db,
        appointment,
        email_type,
        base_url=_base_url(db, appointment.organization_id),
        old_start=old_start,
        commit=False,
    )


def _queue_reminder(db: Session, appointment: Appointment) -> None:
    appointment_type = db.get(AppointmentType, appointment.appointment_type_id)
    if appointment_type and appointment_type.reminder_hours_before > 0:
        appointment_email_service.schedule_reminder_email(
            db,
            appointment,
            base_url=_base_url(db, appointment.organization_id),
            hours_before=appointment_type.reminder_hours_before,
            commit=False,
        )


def _staff_notification(db: Session, appointment: Appointment, action: str) -> None:
    from app.services import notification_service

    if not notification_service.should_notify(
        db, appointment.user_id, appointment.organization_id, "appointments"
    ):
        return
    notification_type = {
        "requested": NotificationType.APPOINTMENT_REQUESTED,
        "confirmed": NotificationType.APPOINTMENT_CONFIRMED,
        "cancelled": NotificationType.APPOINTMENT_CANCELLED,
    }.get(action)
    if notification_type is None:
        return
    job_service.enqueue_job(
        db,
        org_id=appointment.organization_id,
        job_type=JobType.NOTIFICATION,
        payload={
            "user_id": str(appointment.user_id),
            "type": notification_type.value,
            "title": f"Appointment {action}",
            "body": f"Appointment {action}",
            "entity_type": "appointment",
            "entity_id": str(appointment.id),
            "dedupe_key": f"appointment:{appointment.id}:{appointment.revision}:{action}",
        },
        idempotency_key=f"scheduling-notification:{appointment.id}:{appointment.revision}:{action}",
        commit=False,
    )


def _audit(
    db: Session,
    appointment: Appointment,
    event_type: AuditEventType,
    actor_user_id: UUID | None,
    *,
    override_availability: bool = False,
) -> None:
    details = {
        "revision": appointment.revision,
        "availability_override": override_availability,
    }
    if override_availability and appointment.availability_override_reason:
        from app.services import oauth_service

        reason = appointment.availability_override_reason
        details["availability_override_reason_sha256"] = hashlib.sha256(reason.encode()).hexdigest()
        details["availability_override_reason_encrypted"] = oauth_service.encrypt_token(reason)
    audit_service.log_event(
        db=db,
        org_id=appointment.organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type="appointment",
        target_id=appointment.id,
        details=details,
    )


def _queue_expiry(db: Session, appointment: Appointment) -> None:
    if appointment.status != AppointmentStatus.PENDING.value or not appointment.pending_expires_at:
        return
    job_service.enqueue_job(
        db,
        org_id=appointment.organization_id,
        job_type=JobType.APPOINTMENT_EXPIRE,
        payload={"appointment_id": str(appointment.id), "revision": appointment.revision},
        run_at=appointment.pending_expires_at,
        idempotency_key=f"appointment:{appointment.id}:expiry:{appointment.revision}",
        commit=False,
    )


def _enqueue_create(db: Session, appointment: Appointment) -> None:
    from app.services import appointment_google_sync_service, calendar_binding_service

    binding = calendar_binding_service.get_booking_binding(
        db, appointment.organization_id, appointment.user_id
    )
    if appointment.meeting_mode == MeetingMode.GOOGLE_MEET.value or binding is not None:
        appointment_google_sync_service.enqueue_create(db, appointment)


def _enqueue_change(db: Session, appointment: Appointment, action: str) -> None:
    if not _google_owned(appointment):
        return
    from app.services import appointment_google_sync_service

    appointment_google_sync_service.enqueue_v2_change(db, appointment, action=action)


def record_stage_booking(
    db: Session,
    *,
    surrogate,
    appointment: Appointment | None,
    appointment_type: AppointmentType,
    owner_id: UUID,
    actor_user_id: UUID | None,
    scheduled_start: datetime,
    recorded_at: datetime,
    client_timezone: str,
    override_availability: bool = False,
    override_reason: str | None = None,
) -> Appointment:
    """Apply one stage-created interview inside the stage transition transaction."""
    from app.services import appointment_service

    reason = _check_override(override_availability, override_reason)
    if appointment_type.meeting_mode == MeetingMode.ZOOM.value:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    _lock_owner(db, surrogate.organization_id, owner_id)
    end = scheduled_start + timedelta(minutes=appointment_type.duration_minutes)
    if appointment is None:
        appointment = Appointment(
            organization_id=surrogate.organization_id,
            user_id=owner_id,
            appointment_type_id=appointment_type.id,
            surrogate_id=surrogate.id,
            client_name=surrogate.full_name,
            client_email=surrogate.email,
            client_phone=surrogate.phone or "Not provided",
            client_timezone=client_timezone,
            scheduled_start=scheduled_start,
            scheduled_end=end,
            duration_minutes=appointment_type.duration_minutes,
            buffer_before_minutes=appointment_type.buffer_before_minutes,
            buffer_after_minutes=appointment_type.buffer_after_minutes,
            meeting_mode=appointment_type.meeting_mode,
            meeting_location=appointment_type.meeting_location,
            dial_in_number=appointment_type.dial_in_number,
            status=AppointmentStatus.CONFIRMED.value,
            approved_at=recorded_at,
            approved_by_user_id=actor_user_id,
            reschedule_token=appointment_service.generate_token(),
            cancel_token=appointment_service.generate_token(),
            reschedule_token_expires_at=end + timedelta(days=7),
            cancel_token_expires_at=end + timedelta(days=7),
            revision=1,
            origin="crm",
            availability_override_reason=reason,
        )
        _check_slot(db, appointment, scheduled_start, override_availability=override_availability)
        db.add(appointment)
        db.flush()
        _enqueue_create(db, appointment)
        _queue_notice(db, appointment, AppointmentEmailType.CONFIRMED)
        _queue_reminder(db, appointment)
        _staff_notification(db, appointment, "confirmed")
        _audit(
            db,
            appointment,
            AuditEventType.APPOINTMENT_CREATED,
            actor_user_id,
            override_availability=override_availability,
        )
        return appointment

    appointment = _lock_appointment(db, appointment)
    if appointment.user_id != owner_id:
        raise SchedulingConflict("Interview appointment owner changed; refresh and try again")
    if appointment.meeting_mode == MeetingMode.ZOOM.value or appointment.zoom_meeting_id:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    if appointment.google_event_id and appointment.origin != "crm":
        raise SchedulingConflict("Legacy Google appointment ownership requires review")
    if appointment.google_event_id and appointment.google_sync_state == "unlinked":
        raise SchedulingConflict("Review Google synchronization before changing this appointment")
    if appointment.status not in {
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.PENDING.value,
    }:
        raise SchedulingConflict("Interview appointment changed; refresh and try again")
    _check_slot(db, appointment, scheduled_start, override_availability=override_availability)
    old_start = appointment.scheduled_start
    was_pending = appointment.status == AppointmentStatus.PENDING.value
    prepared = appointment_command_service.prepare_change(db, appointment, verify_google_link=False)
    appointment_command_service.apply_reschedule(
        db,
        appointment,
        prepared,
        new_start=scheduled_start,
        new_end=end,
        make_token=appointment_service.generate_token,
        update_pending_expiry=False,
        pending_expires_at=None,
        email_reason_type="appointment_reschedule",
        email_reason_message="Interview appointment changed",
        email_types=None,
    )
    appointment.revision += 1
    appointment.availability_override_reason = reason
    if was_pending:
        appointment.status = AppointmentStatus.CONFIRMED.value
        appointment.approved_at = recorded_at
        appointment.approved_by_user_id = actor_user_id
        appointment.pending_expires_at = None
        _enqueue_create(db, appointment)
        _queue_notice(db, appointment, AppointmentEmailType.CONFIRMED)
    else:
        _enqueue_change(db, appointment, "reschedule")
        _queue_notice(db, appointment, AppointmentEmailType.RESCHEDULED, old_start=old_start)
    _queue_reminder(db, appointment)
    _audit(
        db,
        appointment,
        AuditEventType.APPOINTMENT_RESCHEDULED,
        actor_user_id,
        override_availability=override_availability,
    )
    db.flush()
    return appointment


def create_booking(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    appointment_type_id: UUID,
    client_name: str,
    client_email: str,
    client_phone: str,
    client_timezone: str,
    scheduled_start: datetime,
    client_notes: str | None,
    idempotency_key: str | None,
    meeting_mode: str | None,
    record_links: dict | None,
    actor_scope: str,
    actor_user_id: UUID | None,
    request_id: str | None,
    expected_revision: int | None,
    override_availability: bool,
    override_reason: str | None,
) -> Appointment:
    from app.services import appointment_service

    if expected_revision not in {None, 0}:
        raise SchedulingConflict("New appointments have no prior revision")
    reason = _check_override(override_availability, override_reason)
    appointment_service._validate_new_record_context(db, org_id, record_links or {})
    appointment_type = (
        db.query(AppointmentType)
        .filter(
            AppointmentType.id == appointment_type_id,
            AppointmentType.organization_id == org_id,
            AppointmentType.user_id == user_id,
            AppointmentType.is_active.is_(True),
        )
        .one_or_none()
    )
    if appointment_type is None:
        raise ValueError("Appointment type not found")
    mode = meeting_mode or appointment_type.meeting_mode
    if mode == MeetingMode.ZOOM.value:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    allowed_modes = set(appointment_type.meeting_modes or []) | {appointment_type.meeting_mode}
    if mode not in allowed_modes:
        raise ValueError("Meeting mode not available for this appointment type")
    appointment_service.validate_timezone_name(client_timezone, "client timezone")
    start = appointment_service._normalize_scheduled_start(scheduled_start, client_timezone)
    end = start + timedelta(minutes=appointment_type.duration_minutes)
    request_hash = _request_hash(
        "create",
        {
            "appointment_type_id": appointment_type_id,
            "client_name": client_name,
            "client_email": client_email,
            "client_phone": client_phone,
            "client_timezone": client_timezone,
            "scheduled_start": start,
            "client_notes": client_notes,
            "meeting_mode": mode,
            "record_links": record_links or {},
            "override_availability": override_availability,
            "override_reason": reason,
        },
    )
    replay = _replay(
        db,
        org_id=org_id,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    if replay:
        return replay
    _lock_owner(db, org_id, user_id)
    if idempotency_key:
        normalized_key = appointment_service._normalize_idempotency_key(
            org_id, user_id, idempotency_key
        )
        existing = (
            db.query(Appointment)
            .filter(
                Appointment.organization_id == org_id,
                Appointment.user_id == user_id,
                Appointment.idempotency_key == normalized_key,
            )
            .one_or_none()
        )
        if existing is not None:
            if (
                existing.appointment_type_id != appointment_type_id
                or existing.scheduled_start != start
                or existing.client_name != client_name
                or existing.client_email != client_email
                or existing.client_phone != client_phone
                or existing.client_notes != client_notes
                or existing.client_timezone != client_timezone
                or existing.meeting_mode != mode
                or existing.availability_override_reason != reason
                or any(
                    getattr(existing, field) != value
                    for field, value in (record_links or {}).items()
                )
            ):
                raise SchedulingConflict("Idempotency key was already used for another booking")
            _save_receipt(
                db,
                appointment=existing,
                actor_scope=actor_scope,
                request_id=request_id,
                request_hash=request_hash,
            )
            if request_id:
                db.commit()
            return existing
    else:
        normalized_key = None
    now = datetime.now(UTC)
    appointment = Appointment(
        organization_id=org_id,
        user_id=user_id,
        appointment_type_id=appointment_type_id,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        client_notes=client_notes,
        client_timezone=client_timezone,
        scheduled_start=start,
        scheduled_end=end,
        duration_minutes=appointment_type.duration_minutes,
        buffer_before_minutes=appointment_type.buffer_before_minutes,
        buffer_after_minutes=appointment_type.buffer_after_minutes,
        meeting_mode=mode,
        meeting_location=appointment_type.meeting_location,
        dial_in_number=appointment_type.dial_in_number,
        status=AppointmentStatus.PENDING.value,
        pending_expires_at=now + timedelta(minutes=60),
        reschedule_token=appointment_service.generate_token(),
        cancel_token=appointment_service.generate_token(),
        reschedule_token_expires_at=end + timedelta(days=7),
        cancel_token_expires_at=end + timedelta(days=7),
        idempotency_key=normalized_key,
        origin="crm",
        revision=1,
        availability_override_reason=reason,
    )
    for field, value in (record_links or {}).items():
        setattr(appointment, field, value)
    _check_slot(db, appointment, start, override_availability=override_availability)
    db.add(appointment)
    db.flush()
    if appointment_type.auto_approve:
        appointment.status = AppointmentStatus.CONFIRMED.value
        appointment.approved_at = now
        appointment.approved_by_user_id = actor_user_id or user_id
        appointment.pending_expires_at = None
        _enqueue_create(db, appointment)
        _queue_notice(db, appointment, AppointmentEmailType.CONFIRMED)
        _queue_reminder(db, appointment)
        _staff_notification(db, appointment, "confirmed")
    else:
        _queue_expiry(db, appointment)
        _queue_notice(db, appointment, AppointmentEmailType.REQUEST_RECEIVED)
        _staff_notification(db, appointment, "requested")
    _audit(
        db,
        appointment,
        AuditEventType.APPOINTMENT_CREATED,
        actor_user_id,
        override_availability=override_availability,
    )
    _save_receipt(
        db,
        appointment=appointment,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def approve_booking(
    db: Session,
    appointment: Appointment,
    *,
    approved_by_user_id: UUID,
    expected_revision: int | None,
    request_id: str | None,
) -> Appointment:
    actor_scope = staff_actor_scope(approved_by_user_id)
    request_hash = _request_hash("approve", {"appointment_id": appointment.id})
    replay = _replay(
        db,
        org_id=appointment.organization_id,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    if replay:
        return replay
    _lock_owner(db, appointment.organization_id, appointment.user_id)
    appointment = _lock_appointment(db, appointment)
    _check_revision(appointment, expected_revision)
    if appointment.status != AppointmentStatus.PENDING.value:
        raise ValueError(f"Cannot approve appointment with status {appointment.status}")
    if appointment.pending_expires_at and appointment.pending_expires_at <= datetime.now(UTC):
        _expire_locked(db, appointment)
        db.commit()
        raise ValueError("Appointment request has expired")
    if appointment.meeting_mode == MeetingMode.ZOOM.value:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    _check_slot(
        db,
        appointment,
        appointment.scheduled_start,
        override_availability=bool(appointment.availability_override_reason),
    )
    appointment.status = AppointmentStatus.CONFIRMED.value
    appointment.approved_at = datetime.now(UTC)
    appointment.approved_by_user_id = approved_by_user_id
    appointment.pending_expires_at = None
    appointment.revision += 1
    from app.services import appointment_service

    appointment.reschedule_token = appointment_service.generate_token()
    appointment.cancel_token = appointment_service.generate_token()
    appointment.reschedule_token_expires_at = appointment.scheduled_end + timedelta(days=7)
    appointment.cancel_token_expires_at = appointment.scheduled_end + timedelta(days=7)
    _enqueue_create(db, appointment)
    _queue_notice(db, appointment, AppointmentEmailType.CONFIRMED)
    _queue_reminder(db, appointment)
    _staff_notification(db, appointment, "confirmed")
    _audit(db, appointment, AuditEventType.APPOINTMENT_APPROVED, approved_by_user_id)
    _save_receipt(
        db,
        appointment=appointment,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def _expire_locked(db: Session, appointment: Appointment) -> None:
    appointment.status = AppointmentStatus.EXPIRED.value
    appointment.pending_expires_at = None
    appointment.reschedule_token = None
    appointment.cancel_token = None
    appointment.reschedule_token_expires_at = None
    appointment.cancel_token_expires_at = None
    appointment.revision += 1
    appointment_email_service.cancel_queued_appointment_emails(
        db,
        appointment,
        reason_type="appointment_expired",
        reason_message="Appointment request expired",
        commit=False,
    )
    _audit(db, appointment, AuditEventType.APPOINTMENT_EXPIRED, None)


def expire_booking(
    db: Session, *, appointment_id: UUID, org_id: UUID, revision: int | None = None
) -> bool:
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.organization_id == org_id)
        .with_for_update()
        .one_or_none()
    )
    if (
        appointment is None
        or appointment.status != AppointmentStatus.PENDING.value
        or (revision is not None and appointment.revision != revision)
        or appointment.pending_expires_at is None
        or appointment.pending_expires_at > datetime.now(UTC)
    ):
        return False
    _expire_locked(db, appointment)
    db.commit()
    return True


def expire_pending(db: Session, *, org_id: UUID | None = None, user_id: UUID | None = None) -> int:
    now = datetime.now(UTC)
    query = db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.PENDING.value,
        Appointment.pending_expires_at <= now,
    )
    if org_id:
        query = query.filter(Appointment.organization_id == org_id)
    if user_id:
        query = query.filter(Appointment.user_id == user_id)
    rows = query.with_for_update(skip_locked=True).all()
    for appointment in rows:
        _expire_locked(db, appointment)
    if rows:
        db.commit()
    return len(rows)


def reschedule_booking(
    db: Session,
    appointment: Appointment,
    new_start: datetime,
    *,
    by_client: bool,
    token: str | None,
    actor_user_id: UUID | None,
    expected_revision: int | None,
    request_id: str | None,
    actor_scope: str,
    override_availability: bool,
    override_reason: str | None,
) -> Appointment:
    from app.services import appointment_service

    reason = _check_override(override_availability, override_reason)
    if by_client and override_availability:
        raise ValueError("Public booking cannot override availability")
    new_start = appointment_service._normalize_scheduled_start(
        new_start, appointment.client_timezone
    )
    request_hash = _request_hash(
        "reschedule",
        {
            "appointment_id": appointment.id,
            "new_start": new_start,
            "override_availability": override_availability,
            "override_reason": reason,
        },
    )
    replay = _replay(
        db,
        org_id=appointment.organization_id,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    if replay:
        return replay
    _lock_owner(db, appointment.organization_id, appointment.user_id)
    appointment = _lock_appointment(db, appointment)
    _check_revision(appointment, expected_revision)
    if by_client:
        if not token or appointment.reschedule_token != token:
            raise ValueError("Invalid reschedule token")
        if (
            appointment.reschedule_token_expires_at
            and appointment.reschedule_token_expires_at <= datetime.now(UTC)
        ):
            raise ValueError("Reschedule link has expired")
    if appointment.status not in {
        AppointmentStatus.PENDING.value,
        AppointmentStatus.CONFIRMED.value,
    }:
        raise ValueError(f"Cannot reschedule appointment with status {appointment.status}")
    if appointment.pending_expires_at and appointment.pending_expires_at <= datetime.now(UTC):
        _expire_locked(db, appointment)
        db.commit()
        raise ValueError("Appointment request has expired")
    if appointment.meeting_mode == MeetingMode.ZOOM.value or appointment.zoom_meeting_id:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    if appointment.google_event_id and appointment.origin != "crm":
        raise SchedulingConflict("Legacy Google appointment ownership requires review")
    if appointment.google_event_id and appointment.google_sync_state == "unlinked":
        raise SchedulingConflict("Review Google synchronization before changing this appointment")
    new_end = new_start + timedelta(minutes=appointment.duration_minutes)
    _check_slot(db, appointment, new_start, override_availability=override_availability)
    old_start = appointment.scheduled_start
    prepared = appointment_command_service.prepare_change(db, appointment, verify_google_link=False)
    appointment_command_service.apply_reschedule(
        db,
        appointment,
        prepared,
        new_start=new_start,
        new_end=new_end,
        make_token=appointment_service.generate_token,
        update_pending_expiry=True,
        pending_expires_at=datetime.now(UTC) + timedelta(minutes=60),
        email_reason_type="appointment_rescheduled",
        email_reason_message="Appointment was rescheduled",
        email_types=(
            AppointmentEmailType.REQUEST_RECEIVED,
            AppointmentEmailType.CONFIRMED,
            AppointmentEmailType.RESCHEDULED,
            AppointmentEmailType.REMINDER,
        ),
    )
    appointment.revision += 1
    appointment.availability_override_reason = reason
    _queue_expiry(db, appointment)
    _enqueue_change(db, appointment, "reschedule")
    if appointment.status == AppointmentStatus.CONFIRMED.value:
        _queue_notice(db, appointment, AppointmentEmailType.RESCHEDULED, old_start=old_start)
        _queue_reminder(db, appointment)
    _audit(
        db,
        appointment,
        AuditEventType.APPOINTMENT_RESCHEDULED,
        actor_user_id,
        override_availability=override_availability,
    )
    _save_receipt(
        db,
        appointment=appointment,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_booking(
    db: Session,
    appointment: Appointment,
    *,
    reason: str | None,
    by_client: bool,
    token: str | None,
    actor_user_id: UUID | None,
    expected_revision: int | None,
    request_id: str | None,
    actor_scope: str,
) -> Appointment:
    request_hash = _request_hash("cancel", {"appointment_id": appointment.id, "reason": reason})
    replay = _replay(
        db,
        org_id=appointment.organization_id,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    if replay:
        return replay
    _lock_owner(db, appointment.organization_id, appointment.user_id)
    appointment = _lock_appointment(db, appointment)
    _check_revision(appointment, expected_revision)
    if by_client:
        if not token or appointment.cancel_token != token:
            raise ValueError("Invalid cancel token")
        if (
            appointment.cancel_token_expires_at
            and appointment.cancel_token_expires_at <= datetime.now(UTC)
        ):
            raise ValueError("Cancel link has expired")
    if appointment.status not in {
        AppointmentStatus.PENDING.value,
        AppointmentStatus.CONFIRMED.value,
    }:
        raise ValueError(f"Cannot cancel appointment with status {appointment.status}")
    if appointment.pending_expires_at and appointment.pending_expires_at <= datetime.now(UTC):
        _expire_locked(db, appointment)
        db.commit()
        raise ValueError("Appointment request has expired")
    if appointment.meeting_mode == MeetingMode.ZOOM.value or appointment.zoom_meeting_id:
        raise ValueError("Zoom scheduling is unavailable in scheduling v2")
    if appointment.google_event_id and appointment.origin != "crm":
        raise SchedulingConflict("Legacy Google appointment ownership requires review")
    google_owned = _google_owned(appointment)
    if appointment.google_event_id and appointment.google_sync_state == "unlinked":
        raise SchedulingConflict("Review Google synchronization before changing this appointment")
    prepared = appointment_command_service.prepare_change(db, appointment, verify_google_link=False)
    appointment_command_service.apply_cancel(
        db,
        appointment,
        prepared,
        cancelled_at=datetime.now(UTC),
        by_client=by_client,
        reason=reason,
        email_reason_type="appointment_cancelled",
        email_reason_message="Appointment was cancelled",
        email_types=(
            AppointmentEmailType.REQUEST_RECEIVED,
            AppointmentEmailType.CONFIRMED,
            AppointmentEmailType.RESCHEDULED,
            AppointmentEmailType.REMINDER,
        ),
    )
    appointment.revision += 1
    _enqueue_change(db, appointment, "cancel")
    if not google_owned:
        _queue_notice(db, appointment, AppointmentEmailType.CANCELLED)
    _staff_notification(db, appointment, "cancelled")
    _audit(db, appointment, AuditEventType.APPOINTMENT_CANCELLED, actor_user_id)
    _save_receipt(
        db,
        appointment=appointment,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def complete_booking(
    db: Session,
    appointment: Appointment,
    *,
    status: str,
    actor_user_id: UUID,
    expected_revision: int | None,
    request_id: str | None,
) -> Appointment:
    if status not in {AppointmentStatus.COMPLETED.value, AppointmentStatus.NO_SHOW.value}:
        raise ValueError("Invalid completion status")
    actor_scope = staff_actor_scope(actor_user_id)
    request_hash = _request_hash("complete", {"appointment_id": appointment.id, "status": status})
    replay = _replay(
        db,
        org_id=appointment.organization_id,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    if replay:
        return replay
    _lock_owner(db, appointment.organization_id, appointment.user_id)
    appointment = _lock_appointment(db, appointment)
    _check_revision(appointment, expected_revision)
    if appointment.status != AppointmentStatus.CONFIRMED.value:
        raise ValueError("Only confirmed appointments can be completed")
    appointment.status = status
    appointment.revision += 1
    appointment_email_service.cancel_queued_reminders(
        db,
        appointment,
        reason_type="appointment_completed",
        reason_message="Appointment ended",
        commit=False,
    )
    _audit(
        db,
        appointment,
        AuditEventType.APPOINTMENT_COMPLETED
        if status == AppointmentStatus.COMPLETED.value
        else AuditEventType.APPOINTMENT_NO_SHOW,
        actor_user_id,
    )
    _save_receipt(
        db,
        appointment=appointment,
        actor_scope=actor_scope,
        request_id=request_id,
        request_hash=request_hash,
    )
    db.commit()
    db.refresh(appointment)
    return appointment
