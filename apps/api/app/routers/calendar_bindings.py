"""Authenticated V2 Google Calendar binding settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_session, get_db, require_csrf_header
from app.schemas.auth import UserSession
from app.schemas.calendar_binding import (
    CalendarBindingRead,
    CalendarBindingsResponse,
    CalendarBindingsUpdate,
    CalendarBindingSyncResponse,
    GoogleCalendarDiscoveryItem,
    GoogleCalendarDiscoveryResponse,
)
from app.services import calendar_binding_service

router = APIRouter(prefix="/integrations/google-calendar", tags=["Google Calendar bindings"])


def _read(binding) -> CalendarBindingRead:
    return CalendarBindingRead(
        id=binding.id,
        integration_id=binding.integration_id,
        account_email=binding.account_email,
        calendar_id=binding.calendar_id,
        display_name=binding.display_name,
        access_role=binding.access_role,
        timezone=binding.timezone,
        check_busy=binding.check_busy,
        show_events=binding.show_events,
        write_bookings=binding.write_bookings,
        is_active=binding.is_active,
        synced_at=binding.synced_at,
        sync_error=binding.sync_error,
    )


@router.get("/calendars", response_model=GoogleCalendarDiscoveryResponse)
async def discover_google_calendars(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> GoogleCalendarDiscoveryResponse:
    if not getattr(settings, "SCHEDULING_V2_ENABLED", False):
        return GoogleCalendarDiscoveryResponse(items=[])
    try:
        calendars = await calendar_binding_service.discover_calendars(db, user_id=session.user_id)
    except Exception as exc:
        raise HTTPException(409, "Google Calendar discovery is unavailable") from exc
    return GoogleCalendarDiscoveryResponse(
        items=[GoogleCalendarDiscoveryItem.model_validate(item) for item in calendars]
    )


@router.get("/bindings", response_model=CalendarBindingsResponse)
def get_google_calendar_bindings(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> CalendarBindingsResponse:
    enabled = bool(getattr(settings, "SCHEDULING_V2_ENABLED", False))
    bindings = (
        calendar_binding_service.list_bindings(db, org_id=session.org_id, user_id=session.user_id)
        if enabled
        else []
    )
    return CalendarBindingsResponse(enabled=enabled, items=[_read(binding) for binding in bindings])


@router.put(
    "/bindings",
    response_model=CalendarBindingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def update_google_calendar_bindings(
    data: CalendarBindingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> CalendarBindingsResponse:
    try:
        bindings = await calendar_binding_service.replace_bindings(
            db,
            org_id=session.org_id,
            user_id=session.user_id,
            items=data.items,
        )
    except calendar_binding_service.CalendarBindingError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "Google Calendar configuration could not be verified") from exc
    return CalendarBindingsResponse(enabled=True, items=[_read(binding) for binding in bindings])


@router.post(
    "/bindings/sync",
    response_model=CalendarBindingSyncResponse,
    dependencies=[Depends(require_csrf_header)],
)
def queue_google_calendar_binding_sync(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> CalendarBindingSyncResponse:
    if not getattr(settings, "SCHEDULING_V2_ENABLED", False):
        raise HTTPException(404, "Scheduling v2 is not enabled")
    queued = 0
    try:
        for binding in calendar_binding_service.list_bindings(
            db, org_id=session.org_id, user_id=session.user_id
        ):
            if not binding.is_active:
                continue
            calendar_binding_service.enqueue_binding_sync(
                db, binding_id=binding.id, org_id=session.org_id, commit=False
            )
            queued += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(409, "Google Calendar synchronization could not be queued") from exc
    return CalendarBindingSyncResponse(queued=queued)
