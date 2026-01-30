"""Appointment integrations (Zoom + Google Calendar)."""

from __future__ import annotations

import logging
from typing import Coroutine, TypeVar

from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.db.models import Appointment, AppointmentType

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _run_async(coro: Coroutine[object, object, T]) -> T | None:
    """
    Run an async coroutine from sync code.

    Works whether called from sync or async context.
    Returns None on failure (best-effort). Exceptions are intentionally swallowed
    to avoid blocking appointment workflows on third-party outages.
    """
    try:
        return run_async(coro, timeout=30)
    except Exception as exc:
        logger.warning("Async operation failed: %s", exc)
        return None


def sync_to_google_calendar(
    db: Session,
    appointment: Appointment,
    action: str,  # "create", "update", "delete"
) -> str | None:
    """
    Sync appointment to Google Calendar (best-effort).

    Returns google_event_id on create/update success, None otherwise.
    Does NOT raise exceptions - calendar sync failures are logged but don't block.
    """
    from app.services import calendar_service

    user_id = appointment.user_id
    client_tz = appointment.client_timezone or "UTC"

    if action == "create":
        # Build event summary and description
        appt_type_name = "Appointment"
        if appointment.appointment_type_id:
            appt_type = (
                db.query(AppointmentType)
                .filter(AppointmentType.id == appointment.appointment_type_id)
                .first()
            )
            if appt_type:
                appt_type_name = appt_type.name

        summary = f"{appt_type_name} with {appointment.client_name}"
        description = f"Client: {appointment.client_name}\nEmail: {appointment.client_email}"
        if appointment.client_phone:
            description += f"\nPhone: {appointment.client_phone}"
        if appointment.client_notes:
            description += f"\n\nNotes: {appointment.client_notes}"
        location = appointment.meeting_location or appointment.dial_in_number

        event = _run_async(
            calendar_service.create_appointment_event(
                db=db,
                user_id=user_id,
                appointment_summary=summary,
                start_time=appointment.scheduled_start,
                end_time=appointment.scheduled_end,
                client_email=appointment.client_email,
                description=description,
                location=location,
                timezone_name=client_tz,
            )
        )

        if event:
            logger.info(
                "Created Google Calendar event %s for appointment %s",
                event["id"],
                appointment.id,
            )
            return event["id"]
        logger.warning("Failed to create Google Calendar event for appointment %s", appointment.id)
        return None

    if action == "update":
        if not appointment.google_event_id:
            logger.debug("No google_event_id for appointment %s, skipping update", appointment.id)
            return None

        result = _run_async(
            calendar_service.update_appointment_event(
                db=db,
                user_id=user_id,
                event_id=appointment.google_event_id,
                start_time=appointment.scheduled_start,
                end_time=appointment.scheduled_end,
            )
        )

        if result:
            logger.info("Updated Google Calendar event %s", appointment.google_event_id)
            return appointment.google_event_id

        # Event may have been deleted in Google - clear the ID
        logger.warning(
            "Failed to update Google Calendar event %s, clearing",
            appointment.google_event_id,
        )
        return None

    if action == "delete":
        if not appointment.google_event_id:
            return None

        success = _run_async(
            calendar_service.delete_appointment_event(
                db=db,
                user_id=user_id,
                event_id=appointment.google_event_id,
            )
        )

        if success:
            logger.info("Deleted Google Calendar event %s", appointment.google_event_id)
        else:
            logger.warning("Failed to delete Google Calendar event %s", appointment.google_event_id)
        return None

    return None


def create_zoom_meeting(
    db: Session,
    appointment: Appointment,
    appt_type_name: str,
) -> None:
    from app.services import zoom_service

    if not zoom_service.check_user_has_zoom(db, appointment.user_id):
        raise ValueError("Zoom not connected. Please connect in Settings → Integrations.")

    access_token = _run_async(zoom_service.get_user_zoom_token(db, appointment.user_id))
    if not access_token:
        raise ValueError("Failed to get Zoom access token. Please reconnect Zoom.")

    meeting = _run_async(
        zoom_service.create_zoom_meeting(
            access_token=access_token,
            topic=f"{appt_type_name} with {appointment.client_name}",
            start_time=appointment.scheduled_start,
            duration=appointment.duration_minutes,
            timezone_name=appointment.client_timezone or "America/Los_Angeles",
        )
    )
    if meeting:
        appointment.zoom_meeting_id = str(meeting.id)
        appointment.zoom_join_url = meeting.join_url


def create_google_meet_link(
    db: Session,
    appointment: Appointment,
    appt_type_name: str,
) -> None:
    from app.services import calendar_service

    if not calendar_service.check_user_has_google_calendar(db, appointment.user_id):
        raise ValueError(
            "Google Calendar not connected. Please connect in Settings → Integrations."
        )

    result = _run_async(
        calendar_service.create_google_meet_link(
            access_token=_run_async(
                calendar_service.get_google_access_token(db, appointment.user_id)
            ),
            calendar_id="primary",
            summary=f"{appt_type_name} with {appointment.client_name}",
            start_time=appointment.scheduled_start,
            end_time=appointment.scheduled_end,
            timezone_name=appointment.client_timezone or "America/Los_Angeles",
            attendee_emails=[appointment.client_email],
        )
    )
    if result:
        appointment.google_event_id = result["event_id"]
        appointment.google_meet_url = result["meet_url"]


def regenerate_zoom_meeting_on_reschedule(
    db: Session,
    appointment: Appointment,
    appt_type_name: str,
    new_start,
) -> None:
    from app.services import zoom_service

    try:
        if zoom_service.check_user_has_zoom(db, appointment.user_id):
            access_token = _run_async(zoom_service.get_user_zoom_token(db, appointment.user_id))
            if access_token:
                meeting = _run_async(
                    zoom_service.create_zoom_meeting(
                        access_token=access_token,
                        topic=f"{appt_type_name} with {appointment.client_name}",
                        start_time=new_start,
                        duration=appointment.duration_minutes,
                        timezone_name=appointment.client_timezone or "America/Los_Angeles",
                    )
                )
                if meeting:
                    appointment.zoom_meeting_id = str(meeting.id)
                    appointment.zoom_join_url = meeting.join_url
    except Exception as exc:
        logger.warning("Failed to regenerate Zoom meeting on reschedule: %s", exc)


def update_google_meet_event(
    db: Session,
    appointment: Appointment,
    new_start,
    new_end,
) -> None:
    from app.services import calendar_service

    _run_async(
        calendar_service.update_appointment_event(
            db=db,
            user_id=appointment.user_id,
            event_id=appointment.google_event_id,
            start_time=new_start,
            end_time=new_end,
        )
    )


def delete_zoom_meeting(db: Session, appointment: Appointment) -> None:
    from app.services import zoom_service

    try:
        access_token = _run_async(zoom_service.get_user_zoom_token(db, appointment.user_id))
        if access_token:
            _run_async(zoom_service.delete_zoom_meeting(access_token, appointment.zoom_meeting_id))
    except Exception as exc:
        logger.warning("Failed to delete Zoom meeting %s: %s", appointment.zoom_meeting_id, exc)
