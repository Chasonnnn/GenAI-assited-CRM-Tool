"""Atomic management of stage-created surrogate interview appointments."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.db.enums import AppointmentStatus, AuditEventType, Role, SurrogateActivityType
from app.db.models import Appointment, AppointmentType, AuditLog, Surrogate, User
from app.schemas.interview_appointment import SurrogateInterviewAppointmentAction


class InterviewAppointmentError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


ACTIVE_STATUSES = (AppointmentStatus.PENDING.value, AppointmentStatus.CONFIRMED.value)
logger = logging.getLogger(__name__)


def get_latest(db: Session, org_id: UUID, surrogate_id: UUID) -> Appointment | None:
    """Prefer the current active initial interview, then the most recent historical one."""
    return (
        db.query(Appointment)
        .join(AppointmentType, AppointmentType.id == Appointment.appointment_type_id)
        .filter(
            Appointment.organization_id == org_id,
            Appointment.surrogate_id == surrogate_id,
            AppointmentType.organization_id == org_id,
            AppointmentType.slug == "initial-interview",
        )
        .order_by(
            case((Appointment.status.in_(ACTIVE_STATUSES), 0), else_=1),
            Appointment.created_at.desc(),
            Appointment.id.desc(),
        )
        .first()
    )


def _same_time(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    return left.astimezone(UTC) == right.astimezone(UTC)


def _result_state(surrogate: Surrogate, appointment: Appointment) -> dict[str, str]:
    return {
        "stage_id": str(surrogate.stage_id),
        "status": appointment.status,
        "start": appointment.scheduled_start.astimezone(UTC).isoformat(),
        "end": appointment.scheduled_end.astimezone(UTC).isoformat(),
    }


def _assert_no_conflict(
    db: Session, appointment: Appointment, start: datetime, end: datetime
) -> None:
    conflict = (
        db.query(Appointment.id)
        .filter(
            Appointment.organization_id == appointment.organization_id,
            Appointment.user_id == appointment.user_id,
            Appointment.id != appointment.id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.scheduled_start
            - func.make_interval(0, 0, 0, 0, 0, Appointment.buffer_before_minutes)
            < end + timedelta(minutes=appointment.buffer_after_minutes),
            Appointment.scheduled_end
            + func.make_interval(0, 0, 0, 0, 0, Appointment.buffer_after_minutes)
            > start - timedelta(minutes=appointment.buffer_before_minutes),
        )
        .first()
    )
    if conflict:
        raise InterviewAppointmentError("Selected time is no longer available", 409)


def manage(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
    actor_user_id: UUID,
    actor_role: Role | str,
    data: SurrogateInterviewAppointmentAction,
) -> Surrogate:
    from app.services import (
        activity_service,
        appointment_email_service,
        appointment_google_sync_service,
        audit_service,
        pipeline_service,
        surrogate_status_service,
    )

    # Resolve provider identity before taking the surrogate/appointment locks.
    # Token refresh and Google discovery can perform I/O or commit internally.
    preview_surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id)
        .one_or_none()
    )
    if preview_surrogate is None:
        raise InterviewAppointmentError("Surrogate not found", 404)
    if preview_surrogate.is_archived:
        raise InterviewAppointmentError("Archived surrogates cannot manage appointments", 403)
    preview = get_latest(db, org_id, surrogate_id)
    role = actor_role.value if hasattr(actor_role, "value") else actor_role
    if preview and role not in {Role.ADMIN.value, Role.DEVELOPER.value}:
        if preview.user_id != actor_user_id:
            raise InterviewAppointmentError(
                "Only the appointment owner can manage this interview", 403
            )
    request_digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    exact_retry = False
    if preview:
        receipt = (
            db.query(AuditLog)
            .filter(
                AuditLog.organization_id == org_id,
                AuditLog.target_type == "appointment",
                AuditLog.target_id == preview.id,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .first()
        )
        exact_retry = bool(
            receipt
            and receipt.actor_user_id == actor_user_id
            and receipt.details
            and receipt.details.get("request_digest") == request_digest
            and receipt.details.get("surrogate_id") == str(surrogate_id)
            and receipt.details.get("result") == _result_state(preview_surrogate, preview)
        )
    prepared_link = None
    preview_google_revision = preview.google_sync_revision if preview else None
    preview_google_account = preview.google_account_email if preview else None
    preview_google_calendar = preview.google_calendar_id if preview else None
    if (
        preview
        and not exact_retry
        and data.action in {"reschedule", "cancel"}
        and preview.status in ACTIVE_STATUSES
        and preview.google_event_id
        and not preview.zoom_meeting_id
        and not preview.zoom_join_url
    ):
        try:
            prepared_link = appointment_google_sync_service.prepare_link(db, preview)
        except appointment_google_sync_service.GoogleLinkError as exc:
            raise InterviewAppointmentError(str(exc), 409) from None
    surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if surrogate is None:
        raise InterviewAppointmentError("Surrogate not found", 404)
    if surrogate.is_archived:
        raise InterviewAppointmentError("Archived surrogates cannot manage appointments", 403)
    appointment = get_latest(db, org_id, surrogate.id)
    if appointment:
        db.refresh(appointment, with_for_update=True)

    if appointment and role not in {Role.ADMIN.value, Role.DEVELOPER.value}:
        if appointment.user_id != actor_user_id:
            raise InterviewAppointmentError(
                "Only the appointment owner can manage this interview", 403
            )

    # The audit receipt is committed atomically with the mutation. Match the actor,
    # entire request and current result, not merely a coincidentally matching time.
    if appointment:
        receipt = (
            db.query(AuditLog)
            .filter(
                AuditLog.organization_id == org_id,
                AuditLog.target_type == "appointment",
                AuditLog.target_id == appointment.id,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .first()
        )
        if (
            receipt
            and receipt.actor_user_id == actor_user_id
            and receipt.details
            and receipt.details.get("request_digest") == request_digest
            and receipt.details.get("surrogate_id") == str(surrogate.id)
            and receipt.details.get("result") == _result_state(surrogate, appointment)
        ):
            return surrogate

    if data.action == "schedule" and appointment and appointment.google_event_id:
        if appointment_google_sync_service.status(db, appointment) in {
            "pending",
            "failed",
            "conflict",
            "unlinked",
        }:
            raise InterviewAppointmentError(
                "Finish reviewing Google synchronization before booking another interview", 409
            )

    if surrogate.stage_id != data.expected_stage_id:
        raise InterviewAppointmentError("Surrogate stage changed; refresh and try again", 409)
    if (appointment.id if appointment else None) != data.expected_appointment_id or not _same_time(
        appointment.scheduled_start if appointment else None, data.expected_scheduled_start
    ):
        raise InterviewAppointmentError("Interview appointment changed; refresh and try again", 409)

    current_stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)
    pipeline_id = current_stage.pipeline_id if current_stage else None
    scheduled_stage = (
        pipeline_service.get_stage_by_key(db, pipeline_id, "interview_scheduled")
        if pipeline_id
        else None
    )
    reschedule_stage = (
        pipeline_service.get_stage_by_key(db, pipeline_id, "reschedule_needed")
        if pipeline_id
        else None
    )
    current_key = pipeline_service.get_stage_semantic_key(current_stage) if current_stage else None
    if current_key not in {"interview_scheduled", "reschedule_needed"}:
        raise InterviewAppointmentError("Interview cannot be managed from the current stage", 409)

    if data.move_stage:
        target = reschedule_stage if data.action == "cancel" else scheduled_stage
        if target is None or not target.is_active:
            raise InterviewAppointmentError("Required interview stage is not available", 409)

    now = datetime.now(UTC)
    owner_id = (
        appointment.user_id
        if appointment and data.action != "schedule"
        else (surrogate.owner_id if surrogate.owner_type == "user" else actor_user_id)
    )
    db.query(User).filter(User.id == owner_id).with_for_update().one()
    prior_start = appointment.scheduled_start if appointment else None
    if data.action == "schedule":
        if appointment and appointment.status in ACTIVE_STATUSES:
            raise InterviewAppointmentError("An active interview appointment already exists", 409)
        if not data.move_stage and current_key != "interview_scheduled":
            raise InterviewAppointmentError(
                "Scheduling requires moving to Interview Scheduled", 400
            )
        if data.scheduled_start <= now:
            raise InterviewAppointmentError("Interview date and time must be in the future")
        after_commit = None
        if current_key == "interview_scheduled":
            surrogate_status_service._schedule_interview_appointment(
                db,
                surrogate=surrogate,
                actor_user_id=actor_user_id,
                interview_scheduled_at=data.scheduled_start,
                recorded_at=now,
                org_timezone_str=surrogate_status_service._get_org_timezone(db, org_id),
            )
        else:
            result = surrogate_status_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=scheduled_stage.id,
                user_id=actor_user_id,
                user_role=actor_role,
                interview_scheduled_at=data.scheduled_start,
                commit=False,
            )
            after_commit = result.get("after_commit")
        created = get_latest(db, org_id, surrogate.id)
        if created is None:
            raise InterviewAppointmentError("Interview appointment could not be scheduled")
        _assert_no_conflict(db, created, created.scheduled_start, created.scheduled_end)
        appointment = created
    else:
        if appointment is None or appointment.status not in ACTIVE_STATUSES:
            raise InterviewAppointmentError("No active interview appointment was found", 409)
        # Stage-created interviews can inherit a video mode without a provider meeting.
        if (
            appointment.zoom_meeting_id
            or appointment.zoom_join_url
            or (appointment.google_meet_url and not appointment.google_event_id)
        ):
            raise InterviewAppointmentError(
                "This interview is linked to an external meeting and cannot be changed here", 409
            )
        if appointment.google_event_id and (
            prepared_link is None
            or appointment.google_sync_revision != preview_google_revision
            or appointment.google_account_email != preview_google_account
            or appointment.google_calendar_id != preview_google_calendar
            or appointment.google_event_id != prepared_link.event_id
            or appointment.google_integration_id not in {None, prepared_link.integration_id}
            or appointment.google_calendar_id not in {None, prepared_link.calendar_id}
            or not _same_time(appointment.scheduled_start, prepared_link.start)
            or not _same_time(appointment.scheduled_end, prepared_link.end)
        ):
            raise InterviewAppointmentError(
                "Google appointment changed; refresh and try again", 409
            )
        after_commit = None
        if data.action == "reschedule":
            assert data.scheduled_start is not None
            start = data.scheduled_start.astimezone(UTC)
            if start <= now:
                raise InterviewAppointmentError("Interview date and time must be in the future")
            end = start + timedelta(minutes=appointment.duration_minutes)
            _assert_no_conflict(db, appointment, start, end)
            appointment.scheduled_start = start
            appointment.scheduled_end = end
            appointment.reschedule_token = secrets.token_urlsafe(32)
            appointment.cancel_token = secrets.token_urlsafe(32)
            appointment.reschedule_token_expires_at = end + timedelta(days=7)
            appointment.cancel_token_expires_at = end + timedelta(days=7)
        else:
            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.cancelled_at = now
            appointment.cancelled_by_client = False
            appointment.cancellation_reason = "Cancelled from surrogate interview management"
            appointment.reschedule_token = None
            appointment.cancel_token = None
            appointment.reschedule_token_expires_at = None
            appointment.cancel_token_expires_at = None

        if data.move_stage and surrogate.stage_id != target.id:
            result = surrogate_status_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=target.id,
                user_id=actor_user_id,
                user_role=actor_role,
                interview_scheduled_at=data.scheduled_start
                if data.action == "reschedule"
                else None,
                # This service already updated the existing appointment and owns
                # its reschedule activity; the stage service must not book it again.
                schedule_interview_appointment=False,
                commit=False,
            )
            after_commit = result.get("after_commit")

        appointment_email_service.cancel_queued_appointment_emails(
            db,
            appointment,
            reason_type=f"appointment_{data.action}",
            reason_message="Interview appointment changed",
            commit=False,
        )
        if prepared_link:
            appointment_google_sync_service.enqueue(
                db, appointment, action=data.action, link=prepared_link
            )

    audit_service.log_event(
        db=db,
        org_id=org_id,
        actor_user_id=actor_user_id,
        event_type={
            "schedule": AuditEventType.APPOINTMENT_CREATED,
            "reschedule": AuditEventType.APPOINTMENT_RESCHEDULED,
            "cancel": AuditEventType.APPOINTMENT_CANCELLED,
        }[data.action],
        target_type="appointment",
        target_id=appointment.id,
        details={
            "surrogate_id": str(surrogate.id),
            "action": data.action,
            "request_digest": request_digest,
            "result": _result_state(surrogate, appointment),
        },
    )
    if data.action != "schedule" or current_key == "interview_scheduled":
        activity_service.log_activity(
            db=db,
            surrogate_id=surrogate.id,
            organization_id=org_id,
            activity_type={
                "schedule": SurrogateActivityType.INTERVIEW_SCHEDULED,
                "reschedule": SurrogateActivityType.INTERVIEW_RESCHEDULED,
                "cancel": SurrogateActivityType.INTERVIEW_CANCELLED,
            }[data.action],
            actor_user_id=actor_user_id,
            details={
                "source": "interview_management",
                "action": data.action,
                "appointment_id": str(appointment.id),
                "prior_scheduled_start": prior_start.isoformat() if prior_start else None,
                "scheduled_start": appointment.scheduled_start.isoformat(),
            },
        )

    try:
        db.commit()
        db.refresh(surrogate)
    except Exception:
        db.rollback()
        raise
    if data.action in {"reschedule", "cancel"}:
        from app.services import org_service

        try:
            org = org_service.get_org_by_id(db, org_id)
            base_url = org_service.get_org_portal_base_url(org)
            if data.action == "reschedule":
                appointment_email_service.send_rescheduled(db, appointment, prior_start, base_url)
            else:
                appointment_email_service.send_cancelled(db, appointment, base_url)
        except Exception:
            db.rollback()
            logger.warning("Interview changed but client notification failed")
    if after_commit:
        after_commit()
    if data.action == "reschedule":
        appointment_type = db.get(AppointmentType, appointment.appointment_type_id)
        if appointment_type and appointment_type.reminder_hours_before > 0:
            from app.services import org_service

            try:
                org = org_service.get_org_by_id(db, org_id)
                appointment_email_service.replace_reminder_after_reschedule(
                    db,
                    appointment,
                    base_url=org_service.get_org_portal_base_url(org),
                    hours_before=appointment_type.reminder_hours_before,
                )
            except Exception:
                db.rollback()
                logger.warning("Interview rescheduled but reminder replacement failed")
    return surrogate
