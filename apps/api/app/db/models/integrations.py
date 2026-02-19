"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models import Organization, User


class ResendSettings(Base):
    """
    Org-level email provider configuration (Resend or Gmail).

    Stores encrypted API keys and webhook secrets.
    Only one settings record per organization.
    """

    __tablename__ = "resend_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Provider selection: 'resend' | 'gmail' | None (not configured)
    email_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Resend configuration
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_key_validated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Gmail configuration: org-level default sender (must be admin)
    default_sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Webhook configuration (unique ID for URL routing)
    webhook_id: Mapped[str] = mapped_column(
        String(36), server_default=text("gen_random_uuid()::text"), nullable=False
    )
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Version control (same as AI settings)
    current_version: Mapped[int] = mapped_column(default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship()
    default_sender: Mapped["User | None"] = relationship()

    __table_args__ = (Index("idx_resend_settings_webhook_id", "webhook_id", unique=True),)


class ZapierWebhookSettings(Base):
    """
    Org-level Zapier webhook configuration.

    Stores a per-org webhook ID for routing and an encrypted shared secret.
    """

    __tablename__ = "zapier_webhook_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    webhook_id: Mapped[str] = mapped_column(
        String(36), server_default=text("gen_random_uuid()::text"), nullable=False
    )
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))

    # Outbound webhook configuration (CRM -> Zapier)
    outbound_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    outbound_webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    outbound_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    outbound_send_hashed_pii: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    outbound_event_mapping: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()

    __table_args__ = (Index("idx_zapier_webhook_settings_webhook_id", "webhook_id", unique=True),)


class ZapierInboundWebhook(Base):
    """
    Org-level Zapier inbound webhook endpoints.

    Supports multiple inbound webhook URLs per organization for lead intake.
    """

    __tablename__ = "zapier_inbound_webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    webhook_id: Mapped[str] = mapped_column(
        String(36), server_default=text("gen_random_uuid()::text"), nullable=False
    )
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()

    __table_args__ = (
        Index("idx_zapier_inbound_webhooks_webhook_id", "webhook_id", unique=True),
        Index("idx_zapier_inbound_webhooks_org_id", "organization_id"),
    )


class UserIntegration(Base):
    """
    Per-user OAuth integrations.

    Stores encrypted tokens for Gmail, Zoom, Google Calendar, etc.
    Each user can connect their own accounts.
    """

    __tablename__ = "user_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    integration_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # gmail, zoom, google_calendar
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Google Calendar push channel metadata (events.watch)
    google_calendar_channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_calendar_resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_calendar_channel_token_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    google_calendar_watch_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    # Version control
    current_version: Mapped[int] = mapped_column(
        default=1, server_default=text("1"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "integration_type"),)


# =============================================================================
# Audit Trail
# =============================================================================
