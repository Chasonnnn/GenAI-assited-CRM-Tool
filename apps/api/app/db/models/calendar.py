"""Explicit calendar bindings, external projections, and scheduling receipts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Appointment, Organization, User, UserIntegration


class CalendarBinding(Base):
    """An organization's authorized use of one connected Google calendar."""

    __tablename__ = "calendar_bindings"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_calendar_bindings_org_id"),
        UniqueConstraint(
            "organization_id",
            "integration_id",
            "calendar_id",
            name="uq_calendar_bindings_org_integration_calendar",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_calendar_bindings_membership_scope",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["user_id", "integration_id"],
            ["user_integrations.user_id", "user_integrations.id"],
            name="fk_calendar_bindings_integration_owner",
            ondelete="CASCADE",
        ),
        Index("idx_calendar_bindings_org_user", "organization_id", "user_id"),
        Index(
            "uq_calendar_bindings_active_booking_owner",
            "organization_id",
            "user_id",
            unique=True,
            postgresql_where=text("is_active AND write_bookings"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_integrations.id", ondelete="CASCADE"), nullable=False
    )
    account_email: Mapped[str] = mapped_column(String(255), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_role: Mapped[str] = mapped_column(String(50), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50), default="UTC", server_default=text("'UTC'"), nullable=False
    )
    check_busy: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    show_events: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    write_bookings: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()
    integration: Mapped[UserIntegration] = relationship(foreign_keys=[integration_id])


class ExternalCalendarEvent(Base):
    """Busy/display projection from one explicit calendar binding."""

    __tablename__ = "external_calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "binding_id", "event_id", name="uq_external_calendar_events_binding_event"
        ),
        ForeignKeyConstraint(
            ["organization_id", "binding_id"],
            ["calendar_bindings.organization_id", "calendar_bindings.id"],
            name="fk_external_calendar_events_binding_scope",
            ondelete="CASCADE",
        ),
        Index("idx_external_calendar_events_org_interval", "organization_id", "scheduled_start"),
        Index("idx_external_calendar_events_binding_interval", "binding_id", "scheduled_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scheduled_start: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    html_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_private: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    is_busy: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    recurring_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    organization: Mapped[Organization] = relationship()
    binding: Mapped[CalendarBinding] = relationship(viewonly=True)


class SchedulingRequestReceipt(Base):
    """Idempotency receipt for an accepted scheduling domain mutation."""

    __tablename__ = "scheduling_request_receipts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "actor_scope",
            "request_key",
            name="uq_scheduling_request_receipts_scope_key",
        ),
        ForeignKeyConstraint(
            ["organization_id", "appointment_id"],
            ["appointments.organization_id", "appointments.id"],
            name="fk_scheduling_request_receipts_appointment_scope",
            ondelete="CASCADE",
        ),
        Index("idx_scheduling_request_receipts_appointment", "organization_id", "appointment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    request_key: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped[Organization] = relationship()
    appointment: Mapped[Appointment] = relationship(viewonly=True)
