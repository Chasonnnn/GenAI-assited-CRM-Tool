"""Exact-resource Google Calendar transport for scheduling v2.

The adapter has no CRM transaction ownership. Callers supply a concrete calendar
and retain the identity and ETag used for every write.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import NotRequired, TypedDict
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.services import calendar_service

_BASE = "https://www.googleapis.com/calendar/v3"
_TIMEOUT = 30.0
_MAX_PAGES = 100


class GoogleProviderError(RuntimeError):
    """A provider operation failed without proving a resource state."""


class GooglePreconditionFailed(GoogleProviderError):
    """The observed ETag is no longer current."""


class GoogleResourceCollision(GoogleProviderError):
    """A create ID is occupied and must be read before adoption."""


class GoogleSyncTokenExpired(GoogleProviderError):
    """An incremental cursor expired; rebuild the projection only."""


class GoogleCalendarInfo(TypedDict):
    calendar_id: str
    display_name: str
    access_role: str
    primary: bool
    timezone: str | None


class GoogleEvent(TypedDict):
    calendar_id: str | None
    id: str
    etag: str
    status: str
    start: datetime | None
    end: datetime | None
    timezone: str | None
    organizer_email: str | None
    organizer_self: bool
    attendee_emails: list[str]
    private_properties: dict[str, str]
    conference_url: str | None
    conference_pending: bool
    conference_failed: bool
    summary: str | None
    html_link: str | None
    is_all_day: bool
    start_date: str | None
    end_date: str | None
    is_private: bool
    is_busy: bool
    recurring_event_id: str | None
    original_start: str | None


class GoogleIncrementalResult(TypedDict):
    events: list[GoogleEvent]
    next_sync_token: str
    calendar_id: str
    complete: NotRequired[bool]


def deterministic_event_id(organization_id: UUID, appointment_id: UUID) -> str:
    """Google permits lowercase base32hex IDs; stable IDs make POST replay safe."""
    digest = hashlib.sha256(
        b"crm-scheduling-v2:" + organization_id.bytes + appointment_id.bytes
    ).digest()
    return "crm" + base64.b32hexencode(digest).decode("ascii").rstrip("=").lower()


def ownership_properties(
    organization_id: UUID, appointment_id: UUID, binding_id: UUID
) -> dict[str, str]:
    return {
        "crm_organization_id": str(organization_id),
        "crm_appointment_id": str(appointment_id),
        "crm_binding_id": str(binding_id),
        "crm_scheduling_version": "2",
    }


def owns_event(
    event: GoogleEvent,
    *,
    organization_id: UUID,
    appointment_id: UUID,
    binding_id: UUID,
    event_id: str,
    calendar_id: str,
    client_email: str | None = None,
) -> bool:
    if event["id"] != event_id:
        return False
    if any(
        event["private_properties"].get(key) != value
        for key, value in ownership_properties(organization_id, appointment_id, binding_id).items()
    ):
        return False
    if event["status"] == "cancelled":
        return True
    organizer = (event["organizer_email"] or "").casefold()
    if not (event["organizer_self"] or organizer == calendar_id.casefold()):
        return False
    return client_email is None or client_email.casefold() in {
        email.casefold() for email in event["attendee_emails"]
    }


def _events_url(calendar_id: str) -> str:
    return f"{_BASE}/calendars/{quote(calendar_id, safe='')}/events"


def _event_url(calendar_id: str, event_id: str) -> str:
    return f"{_events_url(calendar_id)}/{quote(event_id, safe='')}"


def _headers(token: str, etag: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if etag:
        headers["If-Match"] = etag
    return headers


def _time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        raise GoogleProviderError("Google event time is invalid") from None


def parse_event(data: dict, *, response_etag: str | None = None) -> GoogleEvent:
    event_id = data.get("id")
    status = data.get("status") or "confirmed"
    etag = data.get("etag") or response_etag
    if not isinstance(event_id, str) or not event_id:
        raise GoogleProviderError("Google event identity is incomplete")
    if (not isinstance(etag, str) or not etag) and status != "cancelled":
        raise GoogleProviderError("Google event version is unavailable")
    if not isinstance(etag, str):
        etag = ""
    start_data = data.get("start") or {}
    end_data = data.get("end") or {}
    start = _time(start_data.get("dateTime"))
    end = _time(end_data.get("dateTime"))
    is_all_day = bool(start_data.get("date") or end_data.get("date"))
    if status != "cancelled" and not is_all_day and (start is None or end is None or end <= start):
        raise GoogleProviderError("Google event interval is incomplete")
    organizer = data.get("organizer") or {}
    private = (data.get("extendedProperties") or {}).get("private") or {}
    if not isinstance(private, dict):
        private = {}
    conference = data.get("conferenceData") or {}
    create_request = conference.get("createRequest") or {}
    conference_status = (create_request.get("status") or {}).get("statusCode")
    conference_url = data.get("hangoutLink")
    if not conference_url:
        conference_url = next(
            (
                point.get("uri")
                for point in conference.get("entryPoints") or []
                if point.get("entryPointType") == "video" and isinstance(point.get("uri"), str)
            ),
            None,
        )
    return GoogleEvent(
        calendar_id=None,
        id=event_id,
        etag=etag,
        status=status,
        start=start,
        end=end,
        timezone=start_data.get("timeZone")
        if isinstance(start_data.get("timeZone"), str)
        else None,
        organizer_email=organizer.get("email"),
        organizer_self=organizer.get("self") is True,
        attendee_emails=[
            attendee["email"]
            for attendee in data.get("attendees") or []
            if isinstance(attendee, dict) and isinstance(attendee.get("email"), str)
        ],
        private_properties={str(key): str(value) for key, value in private.items()},
        conference_url=conference_url if isinstance(conference_url, str) else None,
        conference_pending=bool(create_request) and conference_status == "pending",
        conference_failed=bool(create_request) and conference_status == "failure",
        summary=data.get("summary") if isinstance(data.get("summary"), str) else None,
        html_link=data.get("htmlLink") if isinstance(data.get("htmlLink"), str) else None,
        is_all_day=is_all_day,
        start_date=start_data.get("date") if isinstance(start_data.get("date"), str) else None,
        end_date=end_data.get("date") if isinstance(end_data.get("date"), str) else None,
        is_private=data.get("visibility") == "private",
        is_busy=data.get("transparency") != "transparent",
        recurring_event_id=data.get("recurringEventId"),
        original_start=(data.get("originalStartTime") or {}).get("dateTime")
        or (data.get("originalStartTime") or {}).get("date"),
    )


async def _token(db: Session, user_id: UUID) -> str:
    token = await calendar_service.get_google_access_token(db, user_id)
    if not token:
        raise GoogleProviderError("Google credentials unavailable")
    return token


async def discover_calendars(db: Session, user_id: UUID) -> list[GoogleCalendarInfo]:
    token = await _token(db, user_id)
    results: list[GoogleCalendarInfo] = []
    page_token: str | None = None
    seen_pages: set[str] = set()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for _ in range(_MAX_PAGES):
            params = {"maxResults": "250"}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                f"{_BASE}/users/me/calendarList", headers=_headers(token), params=params
            )
            if response.status_code != 200:
                raise GoogleProviderError("Google calendar discovery failed")
            data = response.json()
            for item in data.get("items") or []:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                    continue
                results.append(
                    GoogleCalendarInfo(
                        calendar_id=item["id"],
                        display_name=str(
                            item.get("summaryOverride") or item.get("summary") or item["id"]
                        ),
                        access_role=str(item.get("accessRole") or "none"),
                        primary=item.get("primary") is True,
                        timezone=item.get("timeZone")
                        if isinstance(item.get("timeZone"), str)
                        else None,
                    )
                )
            next_page = data.get("nextPageToken")
            if not next_page:
                return results
            if not isinstance(next_page, str) or next_page in seen_pages:
                break
            seen_pages.add(next_page)
            page_token = next_page
    raise GoogleProviderError("Google calendar discovery incomplete")


async def verify_writable_calendar(token: str, calendar_id: str) -> bool:
    """Check the exact selected calendar before every mutating job."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{_BASE}/users/me/calendarList/{quote(calendar_id, safe='')}",
            headers=_headers(token),
        )
    if response.status_code == 404:
        return False
    if response.status_code != 200:
        raise GoogleProviderError("Google calendar access unavailable")
    data = response.json()
    return data.get("id") == calendar_id and data.get("accessRole") in {"owner", "writer"}


async def read_incremental_events(
    db: Session, user_id: UUID, calendar_id: str, sync_token: str | None
) -> GoogleIncrementalResult:
    token = await _token(db, user_id)
    events: list[GoogleEvent] = []
    page_token: str | None = None
    seen_pages: set[str] = set()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for _ in range(_MAX_PAGES):
            params = {"maxResults": "2500", "showDeleted": "true"}
            if sync_token:
                params["syncToken"] = sync_token
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                _events_url(calendar_id), headers=_headers(token), params=params
            )
            if response.status_code == 410:
                raise GoogleSyncTokenExpired("Google incremental cursor expired")
            if response.status_code != 200:
                raise GoogleProviderError("Google event snapshot incomplete")
            data = response.json()
            for item in data.get("items") or []:
                if isinstance(item, dict):
                    event = parse_event(item)
                    event["calendar_id"] = calendar_id
                    events.append(event)
            next_page = data.get("nextPageToken")
            if not next_page:
                next_sync = data.get("nextSyncToken")
                if not isinstance(next_sync, str) or not next_sync:
                    raise GoogleProviderError("Google event cursor missing")
                return GoogleIncrementalResult(
                    events=events,
                    next_sync_token=next_sync,
                    calendar_id=calendar_id,
                    complete=True,
                )
            if not isinstance(next_page, str) or next_page in seen_pages:
                break
            seen_pages.add(next_page)
            page_token = next_page
    raise GoogleProviderError("Google event snapshot incomplete")


async def get_event(token: str, calendar_id: str, event_id: str) -> GoogleEvent | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(_event_url(calendar_id, event_id), headers=_headers(token))
    if response.status_code in {404, 410}:
        return None
    if response.status_code != 200:
        raise GoogleProviderError("Google event lookup failed")
    event = parse_event(response.json(), response_etag=response.headers.get("ETag"))
    event["calendar_id"] = calendar_id
    return event


async def insert_event(
    token: str,
    calendar_id: str,
    *,
    event_id: str,
    organization_id: UUID,
    appointment_id: UUID,
    binding_id: UUID,
    start: datetime,
    end: datetime,
    timezone_name: str,
    client_email: str,
    summary: str = "Appointment",
    create_meet: bool = True,
) -> GoogleEvent:
    body = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
        "attendees": [{"email": client_email}],
        "visibility": "private",
        "guestsCanModify": False,
        "extendedProperties": {
            "private": ownership_properties(organization_id, appointment_id, binding_id)
        },
    }
    if create_meet:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": event_id + "meet",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            _events_url(calendar_id),
            headers=_headers(token),
            params={
                "sendUpdates": "all",
                **({"conferenceDataVersion": "1"} if create_meet else {}),
            },
            json=body,
        )
    if response.status_code == 409:
        raise GoogleResourceCollision("Google event ID already exists")
    if response.status_code not in {200, 201}:
        raise GoogleProviderError("Google event creation failed")
    event = parse_event(response.json(), response_etag=response.headers.get("ETag"))
    event["calendar_id"] = calendar_id
    return event


async def patch_interval(
    token: str,
    calendar_id: str,
    event_id: str,
    *,
    etag: str,
    start: datetime,
    end: datetime,
    timezone_name: str,
) -> GoogleEvent:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.patch(
            _event_url(calendar_id, event_id),
            headers=_headers(token, etag),
            params={"sendUpdates": "all", "conferenceDataVersion": "1"},
            json={
                "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
                "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
            },
        )
    if response.status_code == 412:
        raise GooglePreconditionFailed("Google event changed")
    if response.status_code != 200:
        raise GoogleProviderError("Google event update failed")
    event = parse_event(response.json(), response_etag=response.headers.get("ETag"))
    event["calendar_id"] = calendar_id
    return event


async def request_meet_conference(
    token: str, calendar_id: str, event_id: str, *, etag: str, request_id: str
) -> GoogleEvent:
    """Retry a failed Meet allocation on the same event and observed version."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.patch(
            _event_url(calendar_id, event_id),
            headers=_headers(token, etag),
            params={"conferenceDataVersion": "1", "sendUpdates": "all"},
            json={
                "conferenceData": {
                    "createRequest": {
                        "requestId": request_id,
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }
            },
        )
    if response.status_code == 412:
        raise GooglePreconditionFailed("Google event changed")
    if response.status_code != 200:
        raise GoogleProviderError("Google conference creation failed")
    event = parse_event(response.json(), response_etag=response.headers.get("ETag"))
    event["calendar_id"] = calendar_id
    return event


async def delete_event(token: str, calendar_id: str, event_id: str, *, etag: str) -> None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.delete(
            _event_url(calendar_id, event_id),
            headers=_headers(token, etag),
            params={"sendUpdates": "all"},
        )
    if response.status_code == 412:
        raise GooglePreconditionFailed("Google event changed")
    if response.status_code not in {200, 204}:
        raise GoogleProviderError("Google event deletion outcome unknown")
