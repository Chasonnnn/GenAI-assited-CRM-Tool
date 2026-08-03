"""Encrypted conversations, immutable content, and durable Twilio delivery state."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedString, EncryptedText


class MessageTemplate(Base):
    """One immutable version of an organization messaging template."""

    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "template_key", "version", name="uq_message_template_version"
        ),
        CheckConstraint(
            "purpose IN ('operational', 'promotional')",
            name="ck_message_templates_purpose",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_message_templates_status",
        ),
        CheckConstraint(
            "content_classification IN ('no_phi', 'phi')",
            name="ck_message_templates_classification",
        ),
        Index("idx_message_templates_org_status", "organization_id", "status", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    template_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column("body_encrypted", EncryptedText, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))
    is_enrollment_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    content_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'no_phi'")
    )
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class MessageMediaAsset(Base):
    """Immutable, checksummed messaging media stored outside Twilio."""

    __tablename__ = "message_media_assets"
    __table_args__ = (
        UniqueConstraint("organization_id", "checksum_sha256", name="uq_message_media_checksum"),
        CheckConstraint(
            "scan_status IN ('pending', 'clean', 'quarantined', 'rejected')",
            name="ck_message_media_scan_status",
        ),
        CheckConstraint(
            "content_classification IN ('no_phi', 'phi')",
            name="ck_message_media_classification",
        ),
        CheckConstraint("byte_size >= 0", name="ck_message_media_size"),
        Index("idx_message_media_org_scan", "organization_id", "scan_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    quarantine_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'no_phi'")
    )
    provider_media_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class MessagingConversation(Base):
    """Read-only conversation grouped by contact and purpose-bound route."""

    __tablename__ = "messaging_conversations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "contact_id", "route_id", name="uq_messaging_conversation_route"
        ),
        Index("idx_messaging_conversations_org_activity", "organization_id", "last_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("twilio_routes.id", ondelete="RESTRICT"), nullable=False
    )
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_message_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    messages: Mapped[list[MessagingMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessagingMessage(Base):
    """Encrypted inbound or outbound message content."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_messages_org_id"),
        CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_messages_direction"),
        CheckConstraint("purpose IN ('operational', 'promotional')", name="ck_messages_purpose"),
        Index("idx_messages_conversation_time", "conversation_id", "created_at"),
        Index(
            "uq_messages_provider_sid",
            "organization_id",
            "provider_message_sid",
            unique=True,
            postgresql_where=text("provider_message_sid IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messaging_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("twilio_routes.id", ondelete="RESTRICT"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    body: Mapped[str] = mapped_column("body_encrypted", EncryptedText, nullable=False)
    provider_message_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    from_phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    from_phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    to_phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    to_phone_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    provider_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_unread: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    conversation: Mapped[MessagingConversation] = relationship(back_populates="messages")
    media_links: Mapped[list[MessageMediaLink]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class MessageMediaLink(Base):
    """Ordered immutable media attached to one message."""

    __tablename__ = "message_media_links"
    __table_args__ = (
        UniqueConstraint("message_id", "position", name="uq_message_media_position"),
        UniqueConstraint("message_id", "media_asset_id", name="uq_message_media_asset"),
        CheckConstraint(
            "processing_status IN ('pending', 'stored', 'quarantined', 'delete_failed')",
            name="ck_message_media_link_processing_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message_media_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_media_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    processing_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )

    message: Mapped[MessagingMessage] = relationship(back_populates="media_links")
    media_asset: Mapped[MessageMediaAsset] = relationship()


class MessageDelivery(Base):
    """Fenced outbox row for one immutable outbound message."""

    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_message_deliveries_org_id"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_message_delivery_idempotency"
        ),
        UniqueConstraint("message_id", name="uq_message_delivery_message"),
        CheckConstraint(
            "status IN ('pending', 'leased', 'retry_scheduled', 'submitted', 'delivered', "
            "'failed', 'cancelled', 'reconciliation_required')",
            name="ck_message_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
            name="ck_message_delivery_attempt_bounds",
        ),
        CheckConstraint(
            "(status = 'leased' AND lease_token IS NOT NULL AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status <> 'leased' AND lease_token IS NULL AND lease_owner IS NULL "
            "AND lease_expires_at IS NULL)",
            name="ck_message_delivery_lease_coherence",
        ),
        Index(
            "idx_message_deliveries_due",
            "status",
            "run_at",
            postgresql_where=text("status IN ('pending', 'retry_scheduled')"),
        ),
        Index("idx_message_deliveries_org_created", "organization_id", "created_at"),
        Index(
            "uq_message_delivery_enrollment_epoch",
            "organization_id",
            "contact_id",
            "purpose",
            "consent_evidence_id",
            unique=True,
            postgresql_where=text(
                "is_enrollment_confirmation = true AND consent_evidence_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("twilio_routes.id", ondelete="RESTRICT"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    template_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_templates.id", ondelete="RESTRICT"), nullable=True
    )
    consent_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messaging_consent_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    is_enrollment_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'pending'")
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    provider_message_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    message: Mapped[MessagingMessage] = relationship()
    attempts: Mapped[list[MessageDeliveryAttempt]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )


class MessageDeliveryAttempt(Base):
    """PII-free record of one fenced provider call."""

    __tablename__ = "message_delivery_attempts"
    __table_args__ = (
        UniqueConstraint("delivery_id", "attempt_number", name="uq_message_attempt_number"),
        CheckConstraint("attempt_number >= 1", name="ck_message_attempt_number"),
        CheckConstraint(
            "outcome IN ('in_progress', 'succeeded', 'retryable_error', "
            "'terminal_error', 'ambiguous', 'lease_expired')",
            name="ck_message_attempt_outcome",
        ),
        ForeignKeyConstraint(
            ["organization_id", "delivery_id"],
            ["message_deliveries.organization_id", "message_deliveries.id"],
            name="fk_message_attempt_org_delivery",
            ondelete="CASCADE",
        ),
        Index("idx_message_attempt_delivery", "organization_id", "delivery_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'in_progress'")
    )
    provider_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    delivery: Mapped[MessageDelivery] = relationship(back_populates="attempts")


class MessagingProviderAdmission(Base):
    """One account-level next-request slot for rate admission."""

    __tablename__ = "messaging_provider_admission"
    __table_args__ = (
        UniqueConstraint("account_sid_hash", name="uq_messaging_provider_admission_account"),
        Index("idx_messaging_provider_next_slot", "next_slot_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    account_sid_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    next_slot_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class MessageWebhookEvent(Base):
    """Append-only verified Twilio webhook input with encrypted original fields."""

    __tablename__ = "message_webhook_events"
    __table_args__ = (
        UniqueConstraint("account_sid_hash", "event_key", name="uq_message_webhook_event"),
        CheckConstraint(
            "event_type IN ('inbound', 'status')", name="ck_message_webhook_event_type"
        ),
        Index("idx_message_webhook_org_received", "organization_id", "received_at"),
        Index("idx_message_webhook_message_sid", "organization_id", "provider_message_sid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("twilio_routes.id", ondelete="RESTRICT"), nullable=False
    )
    account_sid_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_message_sid: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_fields: Mapped[str] = mapped_column("raw_fields_encrypted", EncryptedText, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class MessageReconciliationCase(Base):
    """PII-free operator case for ambiguous sends and unlinked events."""

    __tablename__ = "message_reconciliation_cases"
    __table_args__ = (
        CheckConstraint(
            "case_type IN ('ambiguous_delivery', 'orphan_webhook', 'unlinked_inbound', "
            "'media_processing')",
            name="ck_message_reconciliation_case_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'action_required', 'resolved', 'dismissed')",
            name="ck_message_reconciliation_status",
        ),
        Index(
            "idx_message_reconciliation_org_status",
            "organization_id",
            "status",
            "detected_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    case_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'pending'")
    )
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_deliveries.id", ondelete="CASCADE"), nullable=True
    )
    webhook_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("message_webhook_events.id", ondelete="CASCADE"),
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
