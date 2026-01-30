"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    MeetingMode,
    AppointmentStatus,
)

if TYPE_CHECKING:
    from app.db.models import IntendedParent, Organization, Surrogate, User


class AppointmentType(Base):
    """
    Appointment type template (e.g., "Initial Consultation", "Follow-up").

    Defines duration, meeting mode, buffer times, and reminder settings.
    Each user can have multiple appointment types.
    """

    __tablename__ = "appointment_types"
    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_appointment_type_slug"),
        Index("idx_appointment_types_user", "user_id", "is_active"),
        Index("idx_appointment_types_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Type details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)  # URL-safe identifier
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scheduling
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Meeting mode
    meeting_mode: Mapped[str] = mapped_column(
        String(20), server_default=text(f"'{MeetingMode.ZOOM.value}'"), nullable=False
    )
    meeting_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dial_in_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    auto_approve: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )

    # Notifications
    reminder_hours_before: Mapped[int] = mapped_column(Integer, default=24, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class AvailabilityRule(Base):
    """
    Weekly availability rule (e.g., "Monday 9am-5pm").

    Uses ISO weekday: Monday=0, Sunday=6.
    Multiple rules per user (one per day or multiple time blocks per day).
    """

    __tablename__ = "availability_rules"
    __table_args__ = (
        Index("idx_availability_rules_user", "user_id"),
        Index("idx_availability_rules_org", "organization_id"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_valid_day_of_week"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Day of week (ISO: Monday=0, Sunday=6)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)

    # Time range (in user's timezone, stored as time)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # User's timezone for interpretation
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles", nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class AvailabilityOverride(Base):
    """
    Date-specific override for availability.

    Can mark a day as unavailable or provide custom hours.
    """

    __tablename__ = "availability_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "override_date", name="uq_availability_override_date"),
        Index("idx_availability_overrides_user", "user_id"),
        Index("idx_availability_overrides_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Date being overridden
    override_date: Mapped[date] = mapped_column(Date, nullable=False)

    # If unavailable, both times are NULL. If custom hours, both are set.
    is_unavailable: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Reason (optional, e.g., "Holiday", "Vacation")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class BookingLink(Base):
    """
    Secure public booking link for a user.

    Public slug is used in URLs (/book/{public_slug}).
    Can be regenerated to invalidate old links.
    """

    __tablename__ = "booking_links"
    __table_args__ = (
        UniqueConstraint("public_slug", name="uq_booking_link_slug"),
        UniqueConstraint("user_id", name="uq_booking_link_user"),
        Index("idx_booking_links_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Public URL slug (cryptographically random)
    public_slug: Mapped[str] = mapped_column(String(32), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class Appointment(Base):
    """
    Booked appointment.

    Lifecycle: pending → confirmed → completed/cancelled/no_show
    Includes tokens for client self-service (reschedule/cancel).
    """

    __tablename__ = "appointments"
    __table_args__ = (
        Index("idx_appointments_user_date", "user_id", "scheduled_start"),
        Index("idx_appointments_org_status", "organization_id", "status"),
        Index("idx_appointments_org_user", "organization_id", "user_id"),
        Index("idx_appointments_org_created", "organization_id", "created_at"),
        Index("idx_appointments_org_updated", "organization_id", "updated_at"),
        Index("idx_appointments_type", "appointment_type_id"),
        Index("idx_appointments_surrogate", "surrogate_id"),
        Index("idx_appointments_ip", "intended_parent_id"),
        Index(
            "idx_appointments_pending_expiry",
            "pending_expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
        UniqueConstraint("idempotency_key", name="uq_appointment_idempotency"),
        UniqueConstraint("reschedule_token", name="uq_appointment_reschedule_token"),
        UniqueConstraint("cancel_token", name="uq_appointment_cancel_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointment_types.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional link to surrogate/IP for match-scoped filtering
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Client info
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    client_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    client_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_timezone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Scheduling (stored in UTC)
    scheduled_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    buffer_after_minutes: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    # Meeting mode (snapshot from appointment type)
    meeting_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    meeting_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dial_in_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{AppointmentStatus.PENDING.value}'"),
        nullable=False,
    )

    # Pending expiry (60 min TTL for unapproved requests)
    pending_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Approval tracking
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Cancellation tracking
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_by_client: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Integration IDs
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_meet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    zoom_meeting_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zoom_join_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Meeting lifecycle timestamps (from webhook events)
    meeting_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    meeting_ended_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Self-service tokens (one-time use tokens for client actions)
    reschedule_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reschedule_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    cancel_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Idempotency (prevent duplicate bookings)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    appointment_type: Mapped["AppointmentType | None"] = relationship()
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    email_logs: Mapped[list["AppointmentEmailLog"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan"
    )


class AppointmentEmailLog(Base):
    """
    Log of emails sent for an appointment.

    Tracks: request received, confirmed, rescheduled, cancelled, reminder.
    """

    __tablename__ = "appointment_email_logs"
    __table_args__ = (
        Index("idx_appointment_email_logs_appt", "appointment_id"),
        Index("idx_appointment_email_logs_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Email details
    email_type: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # pending, sent, failed
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # External ID from email service
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    appointment: Mapped["Appointment"] = relationship(back_populates="email_logs")


# =============================================================================
# Campaigns Module
# =============================================================================


class ZoomMeeting(Base):
    """
    Zoom meetings created via the app.

    Tracks meetings scheduled for cases or intended parents,
    storing Zoom's meeting details for history and management.
    """

    __tablename__ = "zoom_meetings"
    __table_args__ = (
        Index("ix_zoom_meetings_user_id", "user_id"),
        Index("ix_zoom_meetings_surrogate_id", "surrogate_id"),
        Index("ix_zoom_meetings_org_created", "organization_id", "created_at"),
        Index(
            "uq_zoom_meetings_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Allow null if user deleted
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Zoom meeting details
    zoom_meeting_id: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(nullable=True)
    duration: Mapped[int] = mapped_column(default=30, nullable=False)  # minutes
    timezone: Mapped[str] = mapped_column(
        String(100), default="America/Los_Angeles", nullable=False
    )
    join_url: Mapped[str] = mapped_column(String(500), nullable=False)
    start_url: Mapped[str] = mapped_column(Text, nullable=False)  # Can be very long
    password: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()


class ZoomWebhookEvent(Base):
    """
    Zoom webhook events for deduplication and audit trail.

    Stores processed webhook events to prevent duplicate processing
    and track meeting lifecycle (started/ended timestamps).
    """

    __tablename__ = "zoom_webhook_events"
    __table_args__ = (
        Index("ix_zoom_webhook_events_zoom_meeting_id", "zoom_meeting_id"),
        Index("ix_zoom_webhook_events_processed_at", "processed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )  # Dedupe key from Zoom
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # meeting.started, meeting.ended
    zoom_meeting_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )


# =============================================================================
# Matching
# =============================================================================
