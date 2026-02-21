"""Appointment integrations (Zoom + Google Calendar)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Coroutine, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.db.enums import AppointmentStatus, MeetingMode
from app.db.models import Appointment, AppointmentType

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _run_async(coro: Coroutine[object, object, T]) -> T | None:
    """
    Run an async coroutine from sync code.

    Returns None on failure (best-effort). Exceptions are intentionally swallowed
    to avoid blocking appointment workflows on third-party outages.
    """
    try:
        return run_async(coro, timeout=30)
    except Exception as exc:
        try:
            coro.close()
        except Exception:
            pass
        logger.warning("Async operation failed: %s", exc)
        return None


async def _await_async(coro: Coroutine[object, object, T]) -> T | None:
    """Await an async coroutine and swallow/log failures for best-effort workflows."""
    try:
        return await coro
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


def backfill_confirmed_appointments_to_google(
    db: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    date_start: date | None = None,
    date_end: date | None = None,
    limit: int = 100,
) -> int:
    """
    Best-effort outbound backfill for confirmed platform appointments missing Google IDs.

    This retries outbound sync on list/reconciliation paths so transient create-time
    failures do not leave appointments permanently unsynced.
    """
    from app.services import calendar_service

    if not calendar_service.check_user_has_google_calendar(db, user_id):
        return 0

    query = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == org_id,
            Appointment.user_id == user_id,
            Appointment.status == AppointmentStatus.CONFIRMED.value,
            Appointment.google_event_id.is_(None),
            Appointment.meeting_mode != MeetingMode.GOOGLE_MEET.value,
        )
        .order_by(Appointment.scheduled_start.asc())
    )

    if date_start:
        start_dt = datetime.combine(date_start, time.min, tzinfo=timezone.utc)
        query = query.filter(Appointment.scheduled_start >= start_dt)
    if date_end:
        end_dt = datetime.combine(date_end, time.max, tzinfo=timezone.utc)
        query = query.filter(Appointment.scheduled_start <= end_dt)

    targets = query.limit(max(1, limit)).all()
    if not targets:
        return 0

    updated_count = 0
    for appt in targets:
        google_event_id = sync_to_google_calendar(db, appt, "create")
        if not google_event_id:
            continue
        if appt.google_event_id == google_event_id:
            continue
        appt.google_event_id = google_event_id
        updated_count += 1

    if updated_count:
        db.flush()
    return updated_count


async def _sync_manual_google_events_for_appointments_async(
    db: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    date_start: date | None = None,
    date_end: date | None = None,
) -> int:
    """
    Import/reconcile timed Google Calendar events into appointments (best-effort).

    Upserts by `(organization_id, user_id, google_event_id)` in-memory scope to
    avoid duplicates across repeated syncs. Google failures are swallowed.
    """
    from app.services import calendar_service

    now = datetime.now(timezone.utc)
    google_cancel_reason = "Cancelled in Google Calendar"

    def _mark_cancelled_from_google(appt: Appointment) -> None:
        appt.status = AppointmentStatus.CANCELLED.value
        appt.cancelled_at = now
        appt.cancelled_by_client = False
        appt.cancellation_reason = google_cancel_reason
        appt.pending_expires_at = None
        appt.reschedule_token = None
        appt.cancel_token = None
        appt.reschedule_token_expires_at = None
        appt.cancel_token_expires_at = None

    time_min = (
        datetime.combine(date_start, time.min, tzinfo=timezone.utc)
        if date_start
        else now - timedelta(days=30)
    )
    time_max = (
        datetime.combine(date_end, time.max, tzinfo=timezone.utc)
        if date_end
        else now + timedelta(days=180)
    )
    if time_max < time_min:
        return 0

    calendar_ids = await _await_async(
        calendar_service.list_user_google_calendar_ids(
            db=db,
            user_id=user_id,
        )
    ) or ["primary"]

    raw_events: list[dict[str, object]] = []
    any_connected = False
    for calendar_id in calendar_ids:
        result = await _await_async(
            calendar_service.get_user_calendar_events(
                db=db,
                user_id=user_id,
                time_min=time_min,
                time_max=time_max,
                calendar_id=calendar_id,
            )
        )
        if not result:
            continue
        if result.get("connected"):
            any_connected = True
            raw_events.extend(result.get("events") or [])

    if not any_connected:
        return 0

    returned_event_ids: set[str] = {event["id"] for event in raw_events if event.get("id")}
    timed_events: list[tuple[str, str, datetime, datetime]] = []
    seen_event_ids: set[str] = set()
    for event in raw_events:
        event_id = event.get("id")
        if not event_id or event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)

        if event.get("is_all_day"):
            continue

        start = event.get("start")
        end = event.get("end")
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        else:
            start = start.astimezone(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        else:
            end = end.astimezone(timezone.utc)
        if end <= start:
            continue

        summary = (event.get("summary") or "(No title)").strip()
        timed_events.append((event_id, summary[:255], start, end))

    # Reconcile deletions/cancellations first for all confirmed appointments with Google IDs.
    google_confirmed = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == org_id,
            Appointment.user_id == user_id,
            Appointment.google_event_id.is_not(None),
            Appointment.status == AppointmentStatus.CONFIRMED.value,
            Appointment.scheduled_start >= time_min,
            Appointment.scheduled_start <= time_max,
        )
        .all()
    )
    cancelled_count = 0
    for appt in google_confirmed:
        if appt.google_event_id and appt.google_event_id not in returned_event_ids:
            _mark_cancelled_from_google(appt)
            cancelled_count += 1

    if not timed_events:
        if cancelled_count:
            db.flush()
        return cancelled_count

    event_ids = [event_id for event_id, _, _, _ in timed_events]
    existing = (
        db.query(Appointment)
        .filter(
            Appointment.organization_id == org_id,
            Appointment.user_id == user_id,
            Appointment.google_event_id.in_(event_ids),
        )
        .all()
    )
    existing_by_event_id = {appt.google_event_id: appt for appt in existing if appt.google_event_id}

    synced_count = 0
    for event_id, summary, start, end in timed_events:
        duration_minutes = max(1, int((end - start).total_seconds() // 60))
        appt = existing_by_event_id.get(event_id)
        if appt:
            changed = False
            if appt.status == AppointmentStatus.CANCELLED.value:
                # Re-open only rows previously cancelled by Google sync.
                if appt.cancellation_reason == google_cancel_reason:
                    appt.status = AppointmentStatus.CONFIRMED.value
                    appt.cancelled_at = None
                    appt.cancelled_by_client = False
                    appt.cancellation_reason = None
                    changed = True
                else:
                    continue
            elif appt.status != AppointmentStatus.CONFIRMED.value:
                continue

            if appt.scheduled_start != start:
                appt.scheduled_start = start
                changed = True
            if appt.scheduled_end != end:
                appt.scheduled_end = end
                changed = True
            if appt.duration_minutes != duration_minutes:
                appt.duration_minutes = duration_minutes
                changed = True
            if appt.meeting_mode != MeetingMode.GOOGLE_MEET.value:
                appt.meeting_mode = MeetingMode.GOOGLE_MEET.value
                changed = True

            if appt.appointment_type_id is None:
                if appt.client_name != summary:
                    appt.client_name = summary
                    changed = True
                appt.cancelled_at = None
                appt.cancelled_by_client = False
                appt.cancellation_reason = None

            if changed:
                synced_count += 1
            continue

        appt = Appointment(
            organization_id=org_id,
            user_id=user_id,
            appointment_type_id=None,
            client_name=summary,
            client_email="google-calendar-sync@local.invalid",
            client_phone="google-calendar",
            client_timezone="UTC",
            scheduled_start=start,
            scheduled_end=end,
            duration_minutes=duration_minutes,
            meeting_mode=MeetingMode.GOOGLE_MEET.value,
            status=AppointmentStatus.CONFIRMED.value,
            google_event_id=event_id,
        )
        db.add(appt)
        synced_count += 1

    total_changed = synced_count + cancelled_count
    if total_changed:
        db.flush()
    return total_changed


def sync_manual_google_events_for_appointments(
    db: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    date_start: date | None = None,
    date_end: date | None = None,
) -> int:
    """Sync-safe wrapper for Google Calendar appointment reconciliation."""
    coro = _sync_manual_google_events_for_appointments_async(
        db=db,
        user_id=user_id,
        org_id=org_id,
        date_start=date_start,
        date_end=date_end,
    )
    try:
        return run_async(coro, timeout=45)
    except Exception as exc:
        try:
            coro.close()
        except Exception:
            pass
        logger.warning(
            "Google calendar appointment sync failed user=%s org=%s error=%s",
            user_id,
            org_id,
            exc,
        )
        return 0


async def sync_manual_google_events_for_appointments_async(
    db: Session,
    *,
    user_id: UUID,
    org_id: UUID,
    date_start: date | None = None,
    date_end: date | None = None,
) -> int:
    """Async-safe Google Calendar appointment reconciliation."""
    try:
        return await _sync_manual_google_events_for_appointments_async(
            db=db,
            user_id=user_id,
            org_id=org_id,
            date_start=date_start,
            date_end=date_end,
        )
    except Exception as exc:
        logger.warning(
            "Google calendar appointment async sync failed user=%s org=%s error=%s",
            user_id,
            org_id,
            exc,
        )
        return 0


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
