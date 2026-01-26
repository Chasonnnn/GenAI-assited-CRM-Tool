"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import IntendedParent, Organization, Surrogate, User


class Match(Base):
    """
    Proposed match between a surrogate and intended parent.

    Tracks the matching workflow from proposal through acceptance/rejection.
    Only one accepted match is allowed per surrogate.
    """

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "surrogate_id",
            "intended_parent_id",
            name="uq_match_org_surrogate_ip",
        ),
        UniqueConstraint(
            "organization_id",
            "match_number",
            name="uq_match_number",
        ),
        # Only one accepted match allowed per surrogate per org
        Index(
            "uq_one_accepted_match_per_surrogate",
            "organization_id",
            "surrogate_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
        ),
        Index("ix_matches_match_number", "match_number"),
        Index("ix_matches_surrogate_id", "surrogate_id"),
        Index("ix_matches_ip_id", "intended_parent_id"),
        Index("ix_matches_status", "status"),
        Index("idx_matches_org_status", "organization_id", "status"),
        Index("idx_matches_org_created", "organization_id", "created_at"),
        Index("idx_matches_org_updated", "organization_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    intended_parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_number: Mapped[str] = mapped_column(String(10), nullable=False)

    # Status workflow: proposed → reviewing → accepted/rejected/cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="proposed")
    compatibility_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),  # 0.00 to 100.00
        nullable=True,
    )

    # Who proposed and when
    proposed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    proposed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Review details
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Notes and rejection reason
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    intended_parent: Mapped["IntendedParent"] = relationship()
    proposed_by: Mapped["User"] = relationship(foreign_keys=[proposed_by_user_id])
    reviewed_by: Mapped["User"] = relationship(foreign_keys=[reviewed_by_user_id])

    # Match events relationship
    events: Mapped[list["MatchEvent"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchEvent.starts_at",
    )


class MatchEvent(Base):
    """
    Calendar events for a match between surrogate and intended parents.

    Tracks important dates like medications, medical exams, legal milestones,
    and delivery dates with color coding for person type and event type.

    Timezone-safe: stores starts_at/ends_at in UTC with timezone string for display.
    For all-day events, use start_date/end_date (date only, no timezone conversion).
    """

    __tablename__ = "match_events"
    __table_args__ = (
        Index("ix_match_events_match_starts", "match_id", "starts_at"),
        Index("ix_match_events_org_starts", "organization_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )

    # Who and what
    person_type: Mapped[str] = mapped_column(
        String(20),  # "surrogate" or "ip"
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(20),  # medication, medical_exam, legal, delivery, custom
        nullable=False,
    )

    # Event details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timezone-aware datetime (for timed events)
    starts_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="America/Los_Angeles")

    # All-day events (date only, no timezone conversion)
    all_day: Mapped[bool] = mapped_column(nullable=False, default=False)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    # Audit
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    match: Mapped["Match"] = relationship(back_populates="events")
    created_by: Mapped["User"] = relationship()


# =============================================================================
# Attachments
# =============================================================================
