"""Scoped Google Calendar bindings, projections, and availability observations.

This service owns the external-calendar boundary.  It never creates or cancels
CRM appointments from a calendar listing: provider reconciliation is limited to
an exact, already-linked CRM resource.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings

if TYPE_CHECKING:
    from app.db.models import Appointment
    from app.schemas.calendar_binding import CalendarBindingInput


class CalendarBindingError(ValueError):
    """A safe, user-presentable binding configuration error."""


class CalendarAvailabilityUnavailable(CalendarBindingError):
    """A required busy source has no complete current projection."""


DEFAULT_BUSY_PROJECTION_FRESHNESS = timedelta(minutes=10)


def _enabled() -> bool:
    return bool(getattr(settings, "SCHEDULING_V2_ENABLED", False))


def _models():
    from app.db.models import CalendarBinding, ExternalCalendarEvent, Membership, UserIntegration

    return CalendarBinding, ExternalCalendarEvent, Membership, UserIntegration


def _active_binding_query(db: Session, *, org_id: UUID, user_id: UUID):
    CalendarBinding, _ExternalCalendarEvent, Membership, UserIntegration = _models()
    return (
        db.query(CalendarBinding)
        .join(
            Membership,
            (Membership.organization_id == CalendarBinding.organization_id)
            & (Membership.user_id == CalendarBinding.user_id),
        )
        .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
        .filter(
            CalendarBinding.organization_id == org_id,
            CalendarBinding.user_id == user_id,
            CalendarBinding.is_active.is_(True),
            Membership.is_active.is_(True),
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.account_email == CalendarBinding.account_email,
        )
    )


def get_booking_binding(db: Session, org_id: UUID, user_id: UUID):
    """Return the explicit active destination, never an inferred primary calendar."""
    if not _enabled():
        return None
    bindings = (
        _active_binding_query(db, org_id=org_id, user_id=user_id)
        .filter(_models()[0].write_bookings.is_(True))
        .all()
    )
    if len(bindings) > 1:
        raise CalendarBindingError("Review Google Calendar booking destinations")
    return bindings[0] if bindings else None


def list_bindings(db: Session, *, org_id: UUID, user_id: UUID):
    if not _enabled():
        return []
    CalendarBinding, _ExternalCalendarEvent, Membership, UserIntegration = _models()
    return (
        db.query(CalendarBinding)
        .join(
            Membership,
            (Membership.organization_id == CalendarBinding.organization_id)
            & (Membership.user_id == CalendarBinding.user_id),
        )
        .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
        .filter(
            CalendarBinding.organization_id == org_id,
            CalendarBinding.user_id == user_id,
            Membership.is_active.is_(True),
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "google_calendar",
        )
        .order_by(CalendarBinding.display_name, CalendarBinding.calendar_id)
        .all()
    )


def get_active_bindings_last_sync_at(
    db: Session, *, org_id: UUID, user_id: UUID
) -> datetime | None:
    """Return the oldest completed active-binding snapshot for this tenant user.

    A displayed calendar sync is only complete when every active binding has
    completed at least one reconciliation.  The oldest successful snapshot is
    conservative: it cannot claim a newer state than one required calendar has.
    A later sync error does not erase the most recent completed snapshot; callers
    present readiness/errors separately.
    """
    if not _enabled():
        return None
    CalendarBinding, _ExternalCalendarEvent, _Membership, _UserIntegration = _models()
    synced_at_values = (
        _active_binding_query(db, org_id=org_id, user_id=user_id)
        .filter(CalendarBinding.is_active.is_(True))
        .with_entities(CalendarBinding.synced_at)
        .all()
    )
    if not synced_at_values or any(synced_at is None for (synced_at,) in synced_at_values):
        return None
    return min(synced_at for (synced_at,) in synced_at_values if synced_at is not None)


async def discover_calendars(db: Session, *, user_id: UUID) -> list[dict[str, Any]]:
    """Discover concrete calendars for the current user's connected account."""
    if not _enabled():
        return []
    from app.services import google_scheduling_adapter

    return await google_scheduling_adapter.discover_calendars(db=db, user_id=user_id)


async def replace_bindings(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    items: list[CalendarBindingInput],
):
    """Persist only explicitly discovered calendars under one active membership."""
    if not _enabled():
        raise CalendarBindingError("Scheduling v2 is not enabled")
    CalendarBinding, _ExternalCalendarEvent, Membership, UserIntegration = _models()
    integration = (
        db.query(UserIntegration)
        .join(
            Membership,
            (Membership.user_id == UserIntegration.user_id)
            & (Membership.organization_id == org_id),
        )
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "google_calendar",
            Membership.is_active.is_(True),
        )
        .one_or_none()
    )
    if integration is None or not integration.account_email:
        raise CalendarBindingError("Connect Google Calendar before configuring calendars")

    discovered = {
        item["calendar_id"]: item for item in await discover_calendars(db, user_id=user_id)
    }
    unknown = [item.calendar_id for item in items if item.calendar_id not in discovered]
    if unknown:
        raise CalendarBindingError("Selected Google Calendar is no longer available")
    invalid_timezone = [
        item.calendar_id
        for item in items
        if not isinstance(discovered[item.calendar_id].get("timezone"), str)
        or _timezone_is_invalid(discovered[item.calendar_id]["timezone"])
    ]
    if invalid_timezone:
        raise CalendarBindingError("Selected Google Calendar timezone is unavailable")
    destinations = [item for item in items if item.is_active and item.write_bookings]
    if len(destinations) > 1:
        raise CalendarBindingError("Select at most one active booking destination")

    existing = {
        row.calendar_id: row
        for row in (
            db.query(CalendarBinding)
            .filter(
                CalendarBinding.organization_id == org_id,
                CalendarBinding.integration_id == integration.id,
            )
            .with_for_update()
            .all()
        )
    }
    selected_ids = {item.calendar_id for item in items}
    destination_id = destinations[0].calendar_id if destinations else None
    for calendar_id, binding in existing.items():
        if calendar_id not in selected_ids:
            binding.is_active = False
        if calendar_id != destination_id:
            binding.write_bookings = False
    # Release the immediate unique booking destination before enabling its replacement.
    db.flush()

    for item in items:
        discovered_item = discovered[item.calendar_id]
        binding = existing.get(item.calendar_id)
        if binding is None:
            binding = CalendarBinding(
                organization_id=org_id,
                user_id=user_id,
                integration_id=integration.id,
                account_email=integration.account_email,
                calendar_id=item.calendar_id,
                display_name=item.display_name or discovered_item["display_name"],
                access_role=discovered_item["access_role"],
                timezone=discovered_item["timezone"],
            )
            db.add(binding)
        binding.account_email = integration.account_email
        binding.display_name = item.display_name or discovered_item["display_name"]
        binding.access_role = discovered_item["access_role"]
        binding.timezone = discovered_item["timezone"]
        binding.check_busy = item.check_busy
        binding.show_events = item.show_events
        binding.write_bookings = item.write_bookings
        binding.is_active = item.is_active

    db.commit()
    return list_bindings(db, org_id=org_id, user_id=user_id)


def _as_utc(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _as_date(value: object | None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _busy_projection_freshness() -> timedelta:
    seconds = getattr(settings, "SCHEDULING_BUSY_MAX_AGE_SECONDS", 600)
    try:
        return timedelta(seconds=max(1, int(seconds)))
    except TypeError, ValueError:
        return DEFAULT_BUSY_PROJECTION_FRESHNESS


def _binding_timezone(binding: object) -> ZoneInfo | None:
    timezone_name = getattr(binding, "timezone", None)
    try:
        return ZoneInfo(timezone_name) if timezone_name else None
    except TypeError, ValueError:
        return None


def _timezone_is_invalid(timezone_name: str) -> bool:
    try:
        ZoneInfo(timezone_name)
    except TypeError, ValueError:
        return True
    return False


def _all_day_interval(event: object, *, timezone: ZoneInfo) -> tuple[datetime, datetime] | None:
    start_date = getattr(event, "start_date", None)
    end_date = getattr(event, "end_date", None)
    if start_date is None:
        return None
    if end_date is None:
        end_date = start_date + timedelta(days=1)
    if end_date <= start_date:
        return None
    return (
        datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC),
        datetime.combine(end_date, time.min, tzinfo=timezone).astimezone(UTC),
    )


def busy_intervals(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    start: datetime,
    end: datetime,
    exclude_appointment: Appointment | None = None,
) -> list[tuple[datetime, datetime]]:
    """Return cached busy projections or fail closed for an incomplete required source."""
    if not _enabled():
        return []
    CalendarBinding, ExternalCalendarEvent, _Membership, _UserIntegration = _models()
    bindings = (
        _active_binding_query(db, org_id=org_id, user_id=user_id)
        .filter(CalendarBinding.check_busy.is_(True))
        .all()
    )
    now = datetime.now(UTC)
    freshness = _busy_projection_freshness()
    for binding in bindings:
        synced_at = _as_utc(binding.synced_at)
        if (
            synced_at is None
            or synced_at < now - freshness
            or binding.sync_error
            or _binding_timezone(binding) is None
        ):
            raise CalendarAvailabilityUnavailable(
                "Required Google Calendar availability is unavailable"
            )

    intervals: list[tuple[datetime, datetime]] = []
    for binding in bindings:
        timezone = _binding_timezone(binding)
        if timezone is None:
            raise CalendarAvailabilityUnavailable(
                "Required Google Calendar availability is unavailable"
            )
        query = db.query(ExternalCalendarEvent).filter(
            ExternalCalendarEvent.organization_id == org_id,
            ExternalCalendarEvent.binding_id == binding.id,
            ExternalCalendarEvent.is_busy.is_(True),
            ExternalCalendarEvent.status != "cancelled",
            or_(
                and_(
                    ExternalCalendarEvent.scheduled_start.is_not(None),
                    ExternalCalendarEvent.scheduled_end.is_not(None),
                    ExternalCalendarEvent.scheduled_start < end,
                    ExternalCalendarEvent.scheduled_end > start,
                ),
                and_(
                    ExternalCalendarEvent.all_day.is_(True),
                    ExternalCalendarEvent.start_date.is_not(None),
                    ExternalCalendarEvent.end_date.is_not(None),
                    ExternalCalendarEvent.start_date <= end.astimezone(timezone).date(),
                    ExternalCalendarEvent.end_date > start.astimezone(timezone).date(),
                ),
            ),
        )
        if (
            exclude_appointment is not None
            and exclude_appointment.google_event_id
            and exclude_appointment.google_calendar_id == binding.calendar_id
            and exclude_appointment.google_integration_id == binding.integration_id
        ):
            query = query.filter(
                ExternalCalendarEvent.event_id != exclude_appointment.google_event_id
            )
        for event in query.all():
            interval = (
                (event.scheduled_start, event.scheduled_end)
                if event.scheduled_start and event.scheduled_end
                else _all_day_interval(event, timezone=timezone)
            )
            if interval is not None and interval[0] < end and interval[1] > start:
                intervals.append(interval)
    return intervals


def list_visible_projection_events(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    start: datetime,
    end: datetime,
) -> tuple[bool, list[dict[str, object]]]:
    """Return visible external projections, excluding exact CRM-linked event copies."""
    if not _enabled():
        return False, []
    CalendarBinding, ExternalCalendarEvent, _Membership, _UserIntegration = _models()
    bindings = list_bindings(db, org_id=org_id, user_id=user_id)
    visible = [binding for binding in bindings if binding.is_active and binding.show_events]
    if not visible:
        return bool(bindings), []

    from app.db.models import Appointment

    binding_by_id = {binding.id: binding for binding in visible}
    linked_ids = {
        (calendar_id, event_id)
        for calendar_id, event_id in db.query(
            Appointment.google_calendar_id, Appointment.google_event_id
        )
        .filter(
            Appointment.organization_id == org_id,
            Appointment.google_calendar_id.is_not(None),
            Appointment.google_event_id.is_not(None),
        )
        .all()
    }
    range_start = start.astimezone(UTC)
    range_end = end.astimezone(UTC)
    projections = (
        db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.organization_id == org_id,
            ExternalCalendarEvent.binding_id.in_(binding_by_id),
            ExternalCalendarEvent.status != "cancelled",
            or_(
                and_(
                    ExternalCalendarEvent.scheduled_start.is_not(None),
                    ExternalCalendarEvent.scheduled_end.is_not(None),
                    ExternalCalendarEvent.scheduled_start < range_end,
                    ExternalCalendarEvent.scheduled_end > range_start,
                ),
                and_(
                    ExternalCalendarEvent.all_day.is_(True),
                    ExternalCalendarEvent.start_date.is_not(None),
                    ExternalCalendarEvent.end_date.is_not(None),
                    ExternalCalendarEvent.start_date <= end.date() + timedelta(days=1),
                    ExternalCalendarEvent.end_date >= start.date() - timedelta(days=1),
                ),
            ),
        )
        .order_by(ExternalCalendarEvent.scheduled_start)
        .all()
    )
    events: list[dict[str, object]] = []
    for projection in projections:
        binding = binding_by_id[projection.binding_id]
        if (binding.calendar_id, projection.event_id) in linked_ids:
            continue
        if projection.all_day:
            timezone = _binding_timezone(binding)
            if timezone is None or projection.start_date is None or projection.end_date is None:
                continue
            event_start = datetime.combine(projection.start_date, time.min, tzinfo=timezone)
            event_end = datetime.combine(projection.end_date, time.min, tzinfo=timezone)
        else:
            if projection.scheduled_start is None or projection.scheduled_end is None:
                continue
            event_start = projection.scheduled_start
            event_end = projection.scheduled_end
        if event_start >= end or event_end <= start:
            continue
        events.append(
            {
                "id": projection.event_id,
                "calendar_id": binding.calendar_id,
                "summary": projection.summary or "Busy",
                "start": event_start,
                "end": event_end,
                "html_link": projection.html_link or "",
                "is_all_day": projection.all_day,
            }
        )
    return True, events


def enqueue_binding_sync(
    db: Session,
    *,
    binding_id: UUID,
    org_id: UUID,
    commit: bool = True,
    now: datetime | None = None,
):
    """Queue a binding-scoped reconciliation with no ambiguous user/org routing."""
    from app.db.enums import JobType
    from app.services import job_service

    bucket = int((now or datetime.now(UTC)).timestamp()) // (5 * 60)
    return job_service.enqueue_job(
        db,
        org_id=org_id,
        job_type=JobType.GOOGLE_CALENDAR_SYNC,
        payload={"binding_id": str(binding_id), "source": "calendar_binding_v2"},
        idempotency_key=f"google-calendar-binding:{org_id}:{binding_id}:{bucket}",
        commit=commit,
    )


def enqueue_binding_watch_refresh(
    db: Session,
    *,
    binding_id: UUID,
    org_id: UUID,
    commit: bool = True,
    now: datetime | None = None,
):
    """Queue hourly watch renewal for one explicit external calendar binding."""
    from app.db.enums import JobType
    from app.services import job_service

    bucket = int((now or datetime.now(UTC)).timestamp()) // (60 * 60)
    return job_service.enqueue_job(
        db,
        org_id=org_id,
        job_type=JobType.GOOGLE_CALENDAR_WATCH_REFRESH,
        payload={"binding_id": str(binding_id), "source": "calendar_binding_v2"},
        idempotency_key=f"google-calendar-binding-watch:{org_id}:{binding_id}:{bucket}",
        commit=commit,
    )


def _event_value(event: object, name: str, default: object = None) -> object:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def _sync_binding_query(db: Session, *, binding_id: UUID, org_id: UUID):
    CalendarBinding, _ExternalCalendarEvent, Membership, UserIntegration = _models()
    return (
        db.query(CalendarBinding)
        .join(
            Membership,
            (Membership.organization_id == CalendarBinding.organization_id)
            & (Membership.user_id == CalendarBinding.user_id),
        )
        .join(UserIntegration, UserIntegration.id == CalendarBinding.integration_id)
        .filter(
            CalendarBinding.id == binding_id,
            CalendarBinding.organization_id == org_id,
            CalendarBinding.is_active.is_(True),
            Membership.is_active.is_(True),
            UserIntegration.user_id == CalendarBinding.user_id,
            UserIntegration.integration_type == "google_calendar",
            UserIntegration.account_email == CalendarBinding.account_email,
        )
    )


def _same_binding_identity(
    binding: object, identity: tuple[object, ...], cursor: str | None
) -> bool:
    return (
        binding.user_id,
        binding.integration_id,
        binding.account_email,
        binding.calendar_id,
    ) == identity and binding.sync_token == cursor


def _record_sync_error(
    db: Session,
    *,
    binding_id: UUID,
    org_id: UUID,
    identity: tuple[object, ...],
    cursor: str | None,
    error: str,
) -> None:
    binding = (
        _sync_binding_query(db, binding_id=binding_id, org_id=org_id)
        .with_for_update()
        .one_or_none()
    )
    if binding is None or not _same_binding_identity(binding, identity, cursor):
        db.commit()
        return
    binding.sync_error = error
    db.commit()


async def sync_binding(db: Session, *, binding_id: UUID, org_id: UUID) -> int:
    """Persist one complete incremental projection snapshot and observe exact links only."""
    if not _enabled():
        return 0
    _CalendarBinding, ExternalCalendarEvent, _Membership, _UserIntegration = _models()
    binding = _sync_binding_query(db, binding_id=binding_id, org_id=org_id).one_or_none()
    if binding is None:
        return 0

    identity = (
        binding.user_id,
        binding.integration_id,
        binding.account_email,
        binding.calendar_id,
    )
    cursor = binding.sync_token
    # Do not retain a database transaction while waiting on the provider.
    db.commit()

    from app.services import google_scheduling_adapter

    rebuilding = False
    try:
        result = await google_scheduling_adapter.read_incremental_events(
            db=db,
            user_id=identity[0],
            calendar_id=identity[3],
            sync_token=cursor,
        )
    except google_scheduling_adapter.GoogleSyncTokenExpired:
        rebuilding = True
        try:
            result = await google_scheduling_adapter.read_incremental_events(
                db=db,
                user_id=identity[0],
                calendar_id=identity[3],
                sync_token=None,
            )
        except Exception:
            _record_sync_error(
                db,
                binding_id=binding_id,
                org_id=org_id,
                identity=identity,
                cursor=cursor,
                error="sync_rebuild_failed",
            )
            raise
    except Exception:
        _record_sync_error(
            db,
            binding_id=binding_id,
            org_id=org_id,
            identity=identity,
            cursor=cursor,
            error="sync_fetch_failed",
        )
        raise

    next_cursor = result.get("next_sync_token")
    complete = result.get("complete") is True
    exact_calendar = result.get("calendar_id") == identity[3]
    if not complete or not isinstance(next_cursor, str) or not next_cursor or not exact_calendar:
        _record_sync_error(
            db,
            binding_id=binding_id,
            org_id=org_id,
            identity=identity,
            cursor=cursor,
            error="sync_incomplete",
        )
        return 0

    # Fence without holding a binding lock, then take the shared owner lock before any
    # linked appointment lock. Staff commands use the same owner-first ordering.
    binding = (
        _sync_binding_query(db, binding_id=binding_id, org_id=org_id)
        .populate_existing()
        .one_or_none()
    )
    if binding is None or not _same_binding_identity(binding, identity, cursor):
        db.commit()
        return 0

    from app.db.models import User

    owner = (
        db.query(User.id)
        .filter(User.id == identity[0], User.is_active.is_(True))
        .with_for_update()
        .one_or_none()
    )
    if owner is None:
        db.commit()
        return 0
    binding = (
        _sync_binding_query(db, binding_id=binding_id, org_id=org_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if binding is None or not _same_binding_identity(binding, identity, cursor):
        db.commit()
        return 0

    if rebuilding:
        db.query(ExternalCalendarEvent).filter(
            ExternalCalendarEvent.organization_id == org_id,
            ExternalCalendarEvent.binding_id == binding.id,
        ).delete(synchronize_session=False)

    from app.db.models import Appointment
    from app.services import appointment_google_sync_service

    remotes = {
        event_id: remote
        for remote in result.get("events", [])
        if isinstance((event_id := _event_value(remote, "id")), str)
        and event_id
        and _event_value(remote, "calendar_id") == identity[3]
    }
    existing = {
        projection.event_id: projection
        for projection in db.query(ExternalCalendarEvent)
        .filter(
            ExternalCalendarEvent.organization_id == org_id,
            ExternalCalendarEvent.binding_id == binding.id,
            ExternalCalendarEvent.event_id.in_(remotes),
        )
        .all()
    }
    changed = 0
    for event_id, remote in remotes.items():
        projection = existing.get(event_id)
        if projection is None:
            projection = ExternalCalendarEvent(
                organization_id=org_id, binding_id=binding.id, event_id=event_id
            )
            db.add(projection)
        projection.etag = _event_value(remote, "etag")
        projection.status = str(_event_value(remote, "status", "confirmed"))
        projection.summary = _event_value(remote, "summary")
        projection.scheduled_start = _as_utc(_event_value(remote, "start"))
        projection.scheduled_end = _as_utc(_event_value(remote, "end"))
        projection.all_day = bool(_event_value(remote, "is_all_day", False))
        projection.start_date = _as_date(_event_value(remote, "start_date"))
        projection.end_date = _as_date(_event_value(remote, "end_date"))
        projection.html_link = _event_value(remote, "html_link")
        projection.is_private = bool(_event_value(remote, "is_private", False))
        projection.is_busy = bool(_event_value(remote, "is_busy", True))
        projection.recurring_event_id = _event_value(remote, "recurring_event_id")
        projection.original_start = _event_value(remote, "original_start")
        changed += 1

    # The completed page is the availability snapshot used by inbound reconciliation.
    # Flush every projection and its cursor before observing any linked appointment so
    # the observer sees neither a stale binding nor a partial page.
    binding.sync_token = next_cursor
    binding.synced_at = datetime.now(UTC)
    binding.sync_error = None
    db.flush()

    for event_id, remote in remotes.items():
        appointment = (
            db.query(Appointment)
            .populate_existing()
            .with_for_update()
            .filter(
                Appointment.organization_id == org_id,
                Appointment.google_integration_id == binding.integration_id,
                Appointment.google_calendar_id == binding.calendar_id,
                Appointment.google_event_id == event_id,
            )
            .one_or_none()
        )
        if appointment is not None:
            observed = appointment_google_sync_service.observe_remote(db, appointment, remote)
            if inspect.isawaitable(observed):
                await observed
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return changed
