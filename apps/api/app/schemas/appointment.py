"""Appointment schemas - Pydantic models for appointments API."""

from datetime import date, datetime, time
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# =============================================================================
# Appointment Types
# =============================================================================

class AppointmentTypeCreate(BaseModel):
    """Schema for creating an appointment type."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    duration_minutes: int = Field(30, ge=15, le=480)
    buffer_before_minutes: int = Field(0, ge=0, le=60)
    buffer_after_minutes: int = Field(5, ge=0, le=60)
    meeting_mode: Literal["zoom", "phone", "in_person"] = "zoom"
    reminder_hours_before: int = Field(24, ge=0, le=168)


class AppointmentTypeUpdate(BaseModel):
    """Schema for updating an appointment type."""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    duration_minutes: int | None = Field(None, ge=15, le=480)
    buffer_before_minutes: int | None = Field(None, ge=0, le=60)
    buffer_after_minutes: int | None = Field(None, ge=0, le=60)
    meeting_mode: Literal["zoom", "phone", "in_person"] | None = None
    reminder_hours_before: int | None = Field(None, ge=0, le=168)
    is_active: bool | None = None


class AppointmentTypeRead(BaseModel):
    """Schema for reading an appointment type."""
    id: UUID
    user_id: UUID
    name: str
    slug: str
    description: str | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    meeting_mode: str
    reminder_hours_before: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Availability Rules
# =============================================================================

class AvailabilityRuleInput(BaseModel):
    """Schema for a single availability rule."""
    day_of_week: int = Field(..., ge=0, le=6, description="Monday=0, Sunday=6")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM format")


class AvailabilityRulesSet(BaseModel):
    """Schema for setting all availability rules."""
    rules: list[AvailabilityRuleInput]
    timezone: str = Field("America/Los_Angeles", max_length=50)


class AvailabilityRuleRead(BaseModel):
    """Schema for reading an availability rule."""
    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    timezone: str


# =============================================================================
# Availability Overrides
# =============================================================================

class AvailabilityOverrideCreate(BaseModel):
    """Schema for creating an availability override."""
    override_date: date
    is_unavailable: bool = True
    start_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    reason: str | None = Field(None, max_length=255)


class AvailabilityOverrideRead(BaseModel):
    """Schema for reading an availability override."""
    id: UUID
    override_date: date
    is_unavailable: bool
    start_time: time | None
    end_time: time | None
    reason: str | None
    created_at: datetime


# =============================================================================
# Booking Links
# =============================================================================

class BookingLinkRead(BaseModel):
    """Schema for reading a booking link."""
    id: UUID
    user_id: UUID
    public_slug: str
    is_active: bool
    full_url: str | None = None  # Populated by API
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Appointments
# =============================================================================

class AppointmentCreate(BaseModel):
    """Schema for creating an appointment (public booking)."""
    appointment_type_id: UUID
    client_name: str = Field(..., min_length=1, max_length=255)
    client_email: EmailStr
    client_phone: str = Field(..., min_length=5, max_length=20)
    client_timezone: str = Field(..., max_length=50)
    scheduled_start: datetime
    client_notes: str | None = Field(None, max_length=2000)
    idempotency_key: str | None = Field(None, max_length=64)


class AppointmentReschedule(BaseModel):
    """Schema for rescheduling an appointment."""
    scheduled_start: datetime


class AppointmentCancel(BaseModel):
    """Schema for cancelling an appointment."""
    reason: str | None = Field(None, max_length=1000)


class AppointmentRead(BaseModel):
    """Schema for reading an appointment."""
    id: UUID
    user_id: UUID
    appointment_type_id: UUID | None
    appointment_type_name: str | None = None
    client_name: str
    client_email: str
    client_phone: str
    client_timezone: str
    client_notes: str | None
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    meeting_mode: str
    status: str
    pending_expires_at: datetime | None
    approved_at: datetime | None
    approved_by_user_id: UUID | None
    approved_by_name: str | None = None
    cancelled_at: datetime | None
    cancelled_by_client: bool
    cancellation_reason: str | None
    zoom_join_url: str | None
    google_event_id: str | None
    created_at: datetime
    updated_at: datetime


class AppointmentListItem(BaseModel):
    """Schema for appointment list item."""
    id: UUID
    appointment_type_name: str | None
    client_name: str
    client_email: str
    client_phone: str
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    meeting_mode: str
    status: str
    created_at: datetime


class AppointmentListResponse(BaseModel):
    """Schema for appointment list response."""
    items: list[AppointmentListItem]
    total: int
    page: int
    per_page: int
    pages: int


# =============================================================================
# Time Slots
# =============================================================================

class TimeSlotRead(BaseModel):
    """Schema for an available time slot."""
    start: datetime
    end: datetime


class AvailableSlotsResponse(BaseModel):
    """Schema for available slots response."""
    slots: list[TimeSlotRead]
    appointment_type: AppointmentTypeRead | None


# =============================================================================
# Public Booking Page
# =============================================================================

class StaffInfoRead(BaseModel):
    """Schema for staff info on public booking page."""
    user_id: UUID
    display_name: str
    avatar_url: str | None


class PublicBookingPageRead(BaseModel):
    """Schema for public booking page data."""
    staff: StaffInfoRead
    appointment_types: list[AppointmentTypeRead]
    org_name: str | None
    org_timezone: str | None
