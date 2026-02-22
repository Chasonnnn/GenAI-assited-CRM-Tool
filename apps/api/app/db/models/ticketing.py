"""Ticketing and email-ingest ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    EmailDirection,
    EmailOccurrenceState,
    LinkConfidence,
    MailboxKind,
    MailboxProvider,
    RecipientSource,
    SurrogateEmailContactSource,
    TicketLinkStatus,
    TicketPriority,
    TicketStatus,
)
from app.db.types import EncryptedString

if TYPE_CHECKING:
    from app.db.models import Attachment, Organization, Queue, Surrogate, User, UserIntegration


def _enum_type(enum_cls, *, name: str) -> Enum:
    """Bind Python str-enums to PostgreSQL enum value strings."""
    return Enum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda members: [member.value for member in members],
    )


class MailboxCredential(Base):
    """Org-scoped mailbox credential for journal ingestion."""

    __tablename__ = "mailbox_credentials"
    __table_args__ = (
        Index("idx_mailbox_credentials_org_provider", "organization_id", "provider"),
        UniqueConstraint(
            "organization_id", "provider", "account_email", name="uq_mailbox_cred_email"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[MailboxProvider] = mapped_column(
        _enum_type(MailboxProvider, name="mailbox_provider"), nullable=False
    )
    account_email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    granted_scopes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()


class Mailbox(Base):
    """Mailbox source tracked by the ingest engine."""

    __tablename__ = "mailboxes"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "kind", "email_address", name="uq_mailboxes_org_kind_email"
        ),
        Index("idx_mailboxes_org_enabled", "organization_id", "is_enabled"),
        Index("idx_mailboxes_org_kind", "organization_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[MailboxKind] = mapped_column(
        _enum_type(MailboxKind, name="mailbox_kind"), nullable=False
    )
    provider: Mapped[MailboxProvider] = mapped_column(
        _enum_type(MailboxProvider, name="mailbox_provider"), nullable=False
    )
    email_address: Mapped[str] = mapped_column(CITEXT, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mailbox_credentials.id", ondelete="SET NULL"), nullable=True
    )
    user_integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_integrations.id", ondelete="SET NULL"), nullable=True
    )
    default_queue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="SET NULL"), nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    ingestion_paused_until: Mapped[datetime | None] = mapped_column(nullable=True)
    ingestion_pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_history_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gmail_watch_expiration_at: Mapped[datetime | None] = mapped_column(nullable=True)
    gmail_watch_last_renewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    gmail_watch_topic_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_watch_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_incremental_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    credential: Mapped["MailboxCredential | None"] = relationship()
    user_integration: Mapped["UserIntegration | None"] = relationship()
    default_queue: Mapped["Queue | None"] = relationship()


class EmailRawBlob(Base):
    """Raw RFC822 blob metadata (bytes stored in attachment storage backend)."""

    __tablename__ = "email_raw_blobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "sha256_hex", name="uq_email_raw_blob_sha"),
        Index("idx_email_raw_blobs_org_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="message/rfc822")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()


class EmailMessage(Base):
    """Canonical email message entity shared by ticketing flows."""

    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "fingerprint_sha256",
            "signature_sha256",
            name="uq_email_messages_fingerprint_signature",
        ),
        Index("idx_email_messages_org_created", "organization_id", "created_at"),
        Index("idx_email_messages_org_rfc", "organization_id", "rfc_message_id"),
        Index("idx_email_messages_org_thread", "organization_id", "gmail_thread_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[EmailDirection] = mapped_column(
        _enum_type(EmailDirection, name="email_direction"), nullable=False
    )
    rfc_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_norm: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    collision_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()


class EmailMessageContent(Base):
    """Parsed/sanitized body + participant metadata for canonical messages."""

    __tablename__ = "email_message_contents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "message_id",
            "content_version",
            name="uq_email_message_content_version",
        ),
        Index("idx_email_message_contents_org_message", "organization_id", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    parser_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    parsed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    date_header: Mapped[datetime | None] = mapped_column(nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_norm: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    from_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_emails: Mapped[list[str]] = mapped_column(
        ARRAY(CITEXT), nullable=False, server_default=text("'{}'")
    )
    to_emails: Mapped[list[str]] = mapped_column(
        ARRAY(CITEXT), nullable=False, server_default=text("'{}'")
    )
    cc_emails: Mapped[list[str]] = mapped_column(
        ARRAY(CITEXT), nullable=False, server_default=text("'{}'")
    )
    headers_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False
    )
    attachment_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship()
    message: Mapped["EmailMessage"] = relationship()


class EmailMessageThreadRef(Base):
    """In-Reply-To / References pointer rows."""

    __tablename__ = "email_message_thread_refs"
    __table_args__ = (
        Index("idx_email_message_thread_refs_org_message", "organization_id", "message_id"),
        Index(
            "idx_email_message_thread_refs_org_rfc",
            "organization_id",
            "ref_rfc_message_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    ref_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ref_rfc_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    message: Mapped["EmailMessage"] = relationship()


class EmailMessageOccurrence(Base):
    """A mailbox-specific occurrence of a canonical message."""

    __tablename__ = "email_message_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "mailbox_id",
            "gmail_message_id",
            name="uq_email_occurrence_gmail_message",
        ),
        Index("idx_email_occurrence_org_state", "organization_id", "state"),
        Index("idx_email_occurrence_org_message", "organization_id", "message_id"),
        Index("idx_email_occurrence_org_ticket", "organization_id", "ticket_id"),
        Index("idx_email_occurrence_org_thread", "organization_id", "gmail_thread_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    mailbox_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False
    )
    gmail_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    gmail_thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    gmail_history_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gmail_internal_date: Mapped[datetime | None] = mapped_column(nullable=True)
    label_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    state: Mapped[EmailOccurrenceState] = mapped_column(
        _enum_type(EmailOccurrenceState, name="email_occurrence_state"),
        nullable=False,
        server_default=text("'discovered'"),
    )
    raw_blob_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_raw_blobs.id", ondelete="SET NULL"), nullable=True
    )
    raw_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    raw_fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True
    )
    parsed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    stitched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    stitch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    link_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_recipient: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    original_recipient_source: Mapped[RecipientSource] = mapped_column(
        _enum_type(RecipientSource, name="ticket_recipient_source"),
        nullable=False,
        server_default=text("'unknown'"),
    )
    original_recipient_confidence: Mapped[LinkConfidence] = mapped_column(
        _enum_type(LinkConfidence, name="ticket_link_confidence"),
        nullable=False,
        server_default=text("'low'"),
    )
    original_recipient_evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    mailbox: Mapped["Mailbox"] = relationship()
    raw_blob: Mapped["EmailRawBlob | None"] = relationship()
    message: Mapped["EmailMessage | None"] = relationship()


class EmailMessageAttachment(Base):
    """Attachment links for parsed canonical messages."""

    __tablename__ = "email_message_attachments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "message_id",
            "attachment_id",
            name="uq_email_message_attachment",
        ),
        Index("idx_email_message_attachments_org_message", "organization_id", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    is_inline: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    content_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    message: Mapped["EmailMessage"] = relationship()
    attachment: Mapped["Attachment"] = relationship()


class Ticket(Base):
    """Ticket entity built on canonical message threads."""

    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("organization_id", "ticket_code", name="uq_tickets_code"),
        Index("idx_tickets_org_status", "organization_id", "status"),
        Index(
            "idx_tickets_org_assignee", "organization_id", "assignee_user_id", "assignee_queue_id"
        ),
        Index("idx_tickets_org_surrogate", "organization_id", "surrogate_id"),
        Index("idx_tickets_org_activity", "organization_id", "last_activity_at"),
        Index("idx_tickets_org_link_status", "organization_id", "surrogate_link_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    ticket_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        _enum_type(TicketStatus, name="ticket_status"),
        nullable=False,
        server_default=text("'new'"),
    )
    priority: Mapped[TicketPriority] = mapped_column(
        _enum_type(TicketPriority, name="ticket_priority"),
        nullable=False,
        server_default=text("'normal'"),
    )
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_norm: Mapped[str | None] = mapped_column(Text, nullable=True)
    requester_email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    requester_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assignee_queue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="SET NULL"), nullable=True
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="SET NULL"), nullable=True
    )
    surrogate_link_status: Mapped[TicketLinkStatus] = mapped_column(
        _enum_type(TicketLinkStatus, name="ticket_link_status"),
        nullable=False,
        server_default=text("'unlinked'"),
    )
    stitch_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stitch_confidence: Mapped[LinkConfidence] = mapped_column(
        _enum_type(LinkConfidence, name="ticket_link_confidence"),
        nullable=False,
        server_default=text("'low'"),
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    first_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship()
    assignee_user: Mapped["User | None"] = relationship(foreign_keys=[assignee_user_id])
    assignee_queue: Mapped["Queue | None"] = relationship(foreign_keys=[assignee_queue_id])
    surrogate: Mapped["Surrogate | None"] = relationship()


class TicketMessage(Base):
    """Join table linking canonical messages to tickets."""

    __tablename__ = "ticket_messages"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "ticket_id", "message_id", name="uq_ticket_messages_unique"
        ),
        Index("idx_ticket_messages_org_ticket", "organization_id", "ticket_id"),
        Index("idx_ticket_messages_org_message", "organization_id", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    stitched_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    stitch_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    stitch_confidence: Mapped[LinkConfidence] = mapped_column(
        _enum_type(LinkConfidence, name="ticket_link_confidence"), nullable=False
    )

    organization: Mapped["Organization"] = relationship()
    ticket: Mapped["Ticket"] = relationship()
    message: Mapped["EmailMessage"] = relationship()


class TicketEvent(Base):
    """Immutable event entries for ticket actions."""

    __tablename__ = "ticket_events"
    __table_args__ = (
        Index("idx_ticket_events_org_ticket_created", "organization_id", "ticket_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    event_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    organization: Mapped["Organization"] = relationship()
    ticket: Mapped["Ticket"] = relationship()
    actor: Mapped["User | None"] = relationship()


class TicketNote(Base):
    """Internal ticket notes."""

    __tablename__ = "ticket_notes"
    __table_args__ = (
        Index("idx_ticket_notes_org_ticket_created", "organization_id", "ticket_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    body_html_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    ticket: Mapped["Ticket"] = relationship()
    author: Mapped["User | None"] = relationship()


class TicketSavedView(Base):
    """Saved filter views for inbox."""

    __tablename__ = "ticket_saved_views"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_ticket_saved_view_name"),
        Index("idx_ticket_saved_views_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    filters_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()


class TicketSurrogateLinkCandidate(Base):
    """Candidate surrogate links for review/override flows."""

    __tablename__ = "ticket_surrogate_link_candidates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "ticket_id", "surrogate_id", name="uq_ticket_surrogate_candidate"
        ),
        Index("idx_ticket_surrogate_candidates_org_ticket", "organization_id", "ticket_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[LinkConfidence] = mapped_column(
        _enum_type(LinkConfidence, name="ticket_link_confidence"), nullable=False
    )
    evidence_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    ticket: Mapped["Ticket"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()


class SurrogateEmailContact(Base):
    """Surrogate email contacts (system derived + manual additions)."""

    __tablename__ = "surrogate_email_contacts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "surrogate_id",
            "email_hash",
            "source",
            name="uq_surrogate_email_contact_unique",
        ),
        Index("idx_surrogate_email_contacts_org_surrogate", "organization_id", "surrogate_id"),
        Index("idx_surrogate_email_contacts_org_hash", "organization_id", "email_hash"),
        Index(
            "idx_surrogate_email_contacts_org_active",
            "organization_id",
            "is_active",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[SurrogateEmailContactSource] = mapped_column(
        _enum_type(
            SurrogateEmailContactSource,
            name="surrogate_email_contact_source",
        ),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    contact_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    organization: Mapped["Organization"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    created_by: Mapped["User | None"] = relationship()
