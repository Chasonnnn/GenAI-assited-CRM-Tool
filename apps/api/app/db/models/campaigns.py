"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import EmailTemplate, Organization, User


class Campaign(Base):
    """
    Bulk email campaign definition.

    Allows sending targeted emails to groups of cases or intended parents
    with filtering, scheduling, and tracking.
    """

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_campaign_name"),
        Index("idx_campaigns_org_status", "organization_id", "status"),
        Index("idx_campaigns_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Campaign details
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Template
    email_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Recipient filtering
    recipient_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'case' | 'intended_parent'
    filter_criteria: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )  # {stage_id, state, created_after, tags, etc.}

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'draft'"), nullable=False
    )  # 'draft' | 'scheduled' | 'sending' | 'completed' | 'cancelled' | 'failed'

    # Audit
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    email_template: Mapped["EmailTemplate"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    runs: Mapped[list["CampaignRun"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignRun.started_at.desc()",
    )


class CampaignRun(Base):
    """
    Execution record for a campaign send.

    Tracks the progress and results of a campaign execution.
    """

    __tablename__ = "campaign_runs"
    __table_args__ = (
        Index("idx_campaign_runs_campaign", "campaign_id", "started_at"),
        Index("idx_campaign_runs_org", "organization_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Execution timing
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'running'"), nullable=False
    )  # 'running' | 'completed' | 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Email provider locked at run creation: 'resend' | 'gmail'
    email_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Counts
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    campaign: Mapped["Campaign"] = relationship(back_populates="runs")
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CampaignRecipient(Base):
    """
    Per-recipient status for a campaign run.

    Tracks the delivery status of each email sent.
    """

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        Index("idx_campaign_recipients_run", "run_id"),
        Index("idx_campaign_recipients_entity", "entity_type", "entity_id"),
        Index("idx_campaign_recipients_tracking_token", "tracking_token", unique=True),
        UniqueConstraint("run_id", "entity_type", "entity_id", name="uq_campaign_recipient"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Recipient reference
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'case' | 'intended_parent'
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipient_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # 'pending' | 'sent' | 'delivered' | 'failed' | 'skipped'
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    skip_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # External ID from email service
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tracking - unique index 'idx_campaign_recipients_tracking_token' created by migration c3e9f2a1b8d4
    tracking_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    click_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    run: Mapped["CampaignRun"] = relationship(back_populates="recipients")
    tracking_events: Mapped[list["CampaignTrackingEvent"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )


class CampaignTrackingEvent(Base):
    """
    Individual email open/click events for campaign analytics.

    Records each time an email is opened or a link is clicked,
    capturing IP address and user agent for device analytics.
    """

    __tablename__ = "campaign_tracking_events"
    __table_args__ = (
        Index("idx_tracking_events_recipient", "recipient_id"),
        Index("idx_tracking_events_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Event type
    event_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'open' | 'click'

    # For clicks: the URL that was clicked
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analytics data
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    recipient: Mapped["CampaignRecipient"] = relationship(back_populates="tracking_events")


# =============================================================================
# Interview Models
# =============================================================================
