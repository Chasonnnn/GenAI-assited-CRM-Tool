"""Authenticated Google Calendar binding contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GoogleCalendarDiscoveryItem(BaseModel):
    calendar_id: str
    display_name: str
    access_role: str
    timezone: str | None = None
    primary: bool = False


class GoogleCalendarDiscoveryResponse(BaseModel):
    items: list[GoogleCalendarDiscoveryItem]


class CalendarBindingInput(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    check_busy: bool = True
    show_events: bool = True
    write_bookings: bool = False
    is_active: bool = True


class CalendarBindingsUpdate(BaseModel):
    items: list[CalendarBindingInput]

    @model_validator(mode="after")
    def require_one_destination_at_most(self):
        destinations = [item for item in self.items if item.is_active and item.write_bookings]
        if len(destinations) > 1:
            raise ValueError("Select at most one active booking destination")
        if len({item.calendar_id for item in self.items}) != len(self.items):
            raise ValueError("Each calendar may be configured once")
        return self


class CalendarBindingRead(BaseModel):
    id: UUID
    integration_id: UUID
    account_email: str
    calendar_id: str
    display_name: str
    access_role: str
    timezone: str
    check_busy: bool
    show_events: bool
    write_bookings: bool
    is_active: bool
    synced_at: datetime | None
    sync_error: str | None


class CalendarBindingsResponse(BaseModel):
    enabled: bool
    items: list[CalendarBindingRead]


class CalendarBindingSyncResponse(BaseModel):
    accepted: bool = True
    queued: int = 0
