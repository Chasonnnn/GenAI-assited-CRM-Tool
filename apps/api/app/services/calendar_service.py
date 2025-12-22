"""Calendar service - Google Calendar integration for appointments.

Handles:
- Freebusy queries to check availability
- Event creation/update/deletion
- OAuth token management

Note: Requires calendar.readonly and calendar.events scopes.
"""

import httpx
from datetime import datetime, timezone
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import UserIntegration
from app.core.config import settings


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
    from app.core.encryption import decrypt_value
    
    integration = db.query(UserIntegration).filter(
        UserIntegration.user_id == user_id,
        UserIntegration.provider == "google",
    ).first()
    
    if not integration or not integration.access_token_encrypted:
        return None
    
    # Check if token is expired
    if integration.token_expires_at and integration.token_expires_at < datetime.now(timezone.utc):
        # Try to refresh
        if integration.refresh_token_encrypted:
            new_token = await _refresh_google_token(
                decrypt_value(integration.refresh_token_encrypted)
            )
            if new_token:
                from app.core.encryption import encrypt_value
                integration.access_token_encrypted = encrypt_value(new_token["access_token"])
                integration.token_expires_at = datetime.now(timezone.utc) + \
                    timedelta(seconds=new_token.get("expires_in", 3600))
                db.commit()
                return new_token["access_token"]
        return None
    
    return decrypt_value(integration.access_token_encrypted)


async def _refresh_google_token(refresh_token: str) -> dict | None:
    """Refresh a Google OAuth token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return None


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
    except Exception:
        return []


# =============================================================================
# Event Management
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
) -> CalendarEvent | None:
    """
    Create a Google Calendar event.
    
    Returns the created event or None on failure.
    """
    event_body = {
        "summary": summary,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC",
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
    except Exception:
        pass
    
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
    except Exception:
        pass
    
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
    except Exception:
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
) -> CalendarEvent | None:
    """
    Create a calendar event for an appointment.
    
    Convenience wrapper that gets the token and creates the event.
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
