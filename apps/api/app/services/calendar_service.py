"""Calendar service - Google Calendar integration for appointments.

Handles:
- Freebusy queries to check availability
- Event creation/update/deletion
- OAuth token management

Note: Requires calendar.readonly and calendar.events scopes.
"""

import logging

import httpx

logger = logging.getLogger(__name__)
from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.services import oauth_service


# =============================================================================
# Types
# =============================================================================


class BusyBlock(TypedDict):
    """A blocked time period from Google Calendar."""

    start: datetime
    end: datetime


class CalendarEvent(TypedDict):
    """A calendar event."""

    id: str
    summary: str
    start: datetime
    end: datetime
    html_link: str
    is_all_day: bool


class CalendarEventsResult(TypedDict):
    """Calendar fetch result with connection state."""

    connected: bool
    events: list[CalendarEvent]
    error: str | None


# =============================================================================
# Token Management
# =============================================================================


async def get_google_access_token(
    db: Session,
    user_id: UUID,
) -> str | None:
    """
    Get a valid Google access token for a user.

    Refreshes the token if expired.
    Returns None if no integration exists.
    """
    return await oauth_service.get_access_token_async(db, user_id, "gmail")


# =============================================================================
# Freebusy Queries
# =============================================================================


async def get_google_busy_slots(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> list[BusyBlock]:
    """
    Get busy time slots from Google Calendar.

    Uses the freebusy API to check availability.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/freeBusy",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "timeMin": time_min.isoformat(),
                    "timeMax": time_max.isoformat(),
                    "items": [{"id": calendar_id}],
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            calendars = data.get("calendars", {})
            calendar_data = calendars.get(calendar_id, {})
            busy_list = calendar_data.get("busy", [])

            return [
                BusyBlock(
                    start=datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                    end=datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
                )
                for b in busy_list
            ]
    except Exception as e:
        logger.exception(f"Google freebusy query failed for calendar={calendar_id}: {e}")
        return []


# =============================================================================
# Event Fetching (Read)
# =============================================================================


async def get_google_events(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
    max_results_per_page: int = 250,
    max_total_results: int = 500,
) -> list[CalendarEvent]:
    """
    Fetch events from Google Calendar for display.

    Features:
    - singleEvents=true: Expands recurring events into individual instances
    - Handles pagination via nextPageToken
    - Detects all-day events (date vs dateTime)
    - Caps total results to prevent runaway loops

    Returns empty list if API fails.
    """
    events: list[CalendarEvent] = []
    page_token: str | None = None

    try:
        async with httpx.AsyncClient() as client:
            while len(events) < max_total_results:
                params = {
                    "timeMin": time_min.isoformat(),
                    "timeMax": time_max.isoformat(),
                    "singleEvents": "true",  # Expand recurring events
                    "showDeleted": "false",
                    "orderBy": "startTime",
                    "maxResults": str(
                        min(max_results_per_page, max_total_results - len(events))
                    ),
                }
                if page_token:
                    params["pageToken"] = page_token

                response = await client.get(
                    f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                )

                if response.status_code != 200:
                    break

                data = response.json()
                items = data.get("items", [])

                for item in items:
                    if len(events) >= max_total_results:
                        break

                    # Parse start/end - handle all-day vs timed events
                    start_data = item.get("start", {})
                    end_data = item.get("end", {})

                    is_all_day = "date" in start_data and "dateTime" not in start_data

                    if is_all_day:
                        # All-day event: date only, convert to datetime at midnight UTC
                        start_str = start_data.get("date", "")
                        end_str = end_data.get("date", "")
                        try:
                            start_dt = datetime.fromisoformat(start_str).replace(
                                tzinfo=timezone.utc
                            )
                            end_dt = datetime.fromisoformat(end_str).replace(
                                tzinfo=timezone.utc
                            )
                        except ValueError:
                            continue
                    else:
                        # Timed event
                        start_str = start_data.get("dateTime", "")
                        end_str = end_data.get("dateTime", "")
                        try:
                            start_dt = datetime.fromisoformat(
                                start_str.replace("Z", "+00:00")
                            )
                            end_dt = datetime.fromisoformat(
                                end_str.replace("Z", "+00:00")
                            )
                        except ValueError:
                            continue

                    events.append(
                        CalendarEvent(
                            id=item.get("id", ""),
                            summary=item.get("summary", "(No title)"),
                            start=start_dt,
                            end=end_dt,
                            html_link=item.get("htmlLink", ""),
                            is_all_day=is_all_day,
                        )
                    )

                # Check for more pages
                page_token = data.get("nextPageToken")
                if not page_token:
                    break

    except Exception as e:
        logger.exception(f"Google Calendar events fetch failed for calendar={calendar_id}: {e}")

    return events


async def get_user_calendar_events(
    db: Session,
    user_id: UUID,
    time_min: datetime,
    time_max: datetime,
    calendar_id: str = "primary",
) -> CalendarEventsResult:
    """
    Convenience wrapper to fetch calendar events for a user.

    Returns connection state + events for UI handling.
    """
    integration = oauth_service.get_user_integration(db, user_id, "gmail")
    if not integration:
        return {"connected": False, "events": [], "error": "not_connected"}

    access_token = await get_google_access_token(db, user_id)
    if not access_token:
        return {"connected": False, "events": [], "error": "token_expired"}

    events = await get_google_events(
        access_token=access_token,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
    )
    return {"connected": True, "events": events, "error": None}


# =============================================================================
# Event Management (Write)
# =============================================================================


async def create_google_event(
    access_token: str,
    calendar_id: str,
    summary: str,
    start_time: datetime,
    end_time: datetime,
    description: str | None = None,
    location: str | None = None,
    attendee_emails: list[str] | None = None,
    timezone_name: str = "UTC",
) -> CalendarEvent | None:
    """
    Create a Google Calendar event.

    Returns the created event or None on failure.
    """
    event_body = {
        "summary": summary,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": timezone_name,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": timezone_name,
        },
    }

    if description:
        event_body["description"] = description

    if location:
        event_body["location"] = location

    if attendee_emails:
        event_body["attendees"] = [{"email": e} for e in attendee_emails]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=event_body,
                params={"sendUpdates": "all"} if attendee_emails else {},
            )

            if response.status_code in [200, 201]:
                data = response.json()
                return CalendarEvent(
                    id=data["id"],
                    summary=data.get("summary", ""),
                    start=datetime.fromisoformat(
                        data["start"].get("dateTime", "").replace("Z", "+00:00")
                    ),
                    end=datetime.fromisoformat(
                        data["end"].get("dateTime", "").replace("Z", "+00:00")
                    ),
                    html_link=data.get("htmlLink", ""),
                )
    except Exception as e:
        logger.exception(f"Google Calendar event creation failed for calendar={calendar_id}: {e}")

    return None


async def update_google_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
    summary: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
) -> CalendarEvent | None:
    """
    Update a Google Calendar event.

    Returns the updated event or None on failure.
    """
    # First get the current event
    try:
        async with httpx.AsyncClient() as client:
            get_response = await client.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if get_response.status_code != 200:
                return None

            event_body = get_response.json()

            # Update fields
            if summary:
                event_body["summary"] = summary
            if start_time:
                event_body["start"] = {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                }
            if end_time:
                event_body["end"] = {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                }
            if description is not None:
                event_body["description"] = description
            if location is not None:
                event_body["location"] = location

            # Update the event
            response = await client.put(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=event_body,
                params={"sendUpdates": "all"},
            )

            if response.status_code == 200:
                data = response.json()
                return CalendarEvent(
                    id=data["id"],
                    summary=data.get("summary", ""),
                    start=datetime.fromisoformat(
                        data["start"].get("dateTime", "").replace("Z", "+00:00")
                    ),
                    end=datetime.fromisoformat(
                        data["end"].get("dateTime", "").replace("Z", "+00:00")
                    ),
                    html_link=data.get("htmlLink", ""),
                )
    except Exception as e:
        logger.exception(f"Google Calendar event update failed for calendar={calendar_id} event={event_id}: {e}")

    return None


async def delete_google_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
) -> bool:
    """
    Delete a Google Calendar event.

    Returns True on success, False on failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"sendUpdates": "all"},
            )
            return response.status_code in [200, 204, 410]  # 410 = already deleted
    except Exception as e:
        logger.exception(f"Google Calendar event deletion failed for calendar={calendar_id} event={event_id}: {e}")
        return False


# =============================================================================
# Helper Functions
# =============================================================================


async def create_appointment_event(
    db: Session,
    user_id: UUID,
    appointment_summary: str,
    start_time: datetime,
    end_time: datetime,
    client_email: str,
    description: str | None = None,
    location: str | None = None,
    timezone_name: str = "UTC",
) -> CalendarEvent | None:
    """
    Create a calendar event for an appointment.

    Convenience wrapper that gets the token and creates the event.
    Returns None if no Gmail integration or API failure.
    """
    access_token = await get_google_access_token(db, user_id)
    if not access_token:
        return None

    return await create_google_event(
        access_token=access_token,
        calendar_id="primary",  # User's primary calendar
        summary=appointment_summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
        location=location,
        attendee_emails=[client_email],
        timezone_name=timezone_name,
    )


async def update_appointment_event(
    db: Session,
    user_id: UUID,
    event_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> CalendarEvent | None:
    """Update an appointment's calendar event."""
    access_token = await get_google_access_token(db, user_id)
    if not access_token:
        return None

    return await update_google_event(
        access_token=access_token,
        calendar_id="primary",
        event_id=event_id,
        start_time=start_time,
        end_time=end_time,
    )


async def delete_appointment_event(
    db: Session,
    user_id: UUID,
    event_id: str,
) -> bool:
    """Delete an appointment's calendar event."""
    access_token = await get_google_access_token(db, user_id)
    if not access_token:
        return False

    return await delete_google_event(
        access_token=access_token,
        calendar_id="primary",
        event_id=event_id,
    )
