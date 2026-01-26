"""Appointment and scheduling enums."""

from enum import Enum


class MeetingMode(str, Enum):
    """Meeting mode for appointments."""

    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    PHONE = "phone"
    IN_PERSON = "in_person"


class AppointmentStatus(str, Enum):
    """
    Appointment lifecycle status.

    Flow: pending → confirmed → completed
              ↘ cancelled
              ↘ no_show
              ↘ expired
    """

    PENDING = "pending"  # Awaiting approval
    CONFIRMED = "confirmed"  # Approved, scheduled
    COMPLETED = "completed"  # Meeting took place
    CANCELLED = "cancelled"  # Cancelled by client or staff
    NO_SHOW = "no_show"  # Client didn't show up
    EXPIRED = "expired"  # Pending request expired before approval


class AppointmentEmailType(str, Enum):
    """Types of emails sent for appointments."""

    REQUEST_RECEIVED = "request_received"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    REMINDER = "reminder"


# Default appointment status
DEFAULT_APPOINTMENT_STATUS = AppointmentStatus.PENDING
