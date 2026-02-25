"""Add mailbox ingestion and ticketing schema.

Revision ID: 20260222_1200
Revises: 20260220_0930
Create Date: 2026-02-22 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260222_1200"
down_revision: Union[str, Sequence[str], None] = "20260220_0930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_enum(name: str, values: list[str]) -> None:
    quoted = ", ".join(f"'{value}'" for value in values)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                CREATE TYPE {name} AS ENUM ({quoted});
            END IF;
        END
        $$;
        """
    )


def _drop_enum(name: str) -> None:
    op.execute(f"DROP TYPE IF EXISTS {name};")


def upgrade() -> None:
    _create_enum("mailbox_kind", ["journal", "user_sent"])
    _create_enum("mailbox_provider", ["gmail"])
    _create_enum("email_direction", ["inbound", "outbound"])
    _create_enum(
        "email_occurrence_state",
        ["discovered", "raw_fetched", "parsed", "stitched", "linked", "failed"],
    )
    _create_enum(
        "ticket_recipient_source",
        ["workspace_header", "delivered_to", "x_original_to", "to_cc_scan", "unknown"],
    )
    _create_enum("ticket_link_confidence", ["high", "medium", "low"])
    _create_enum("ticket_status", ["new", "open", "pending", "resolved", "closed", "spam"])
    _create_enum("ticket_priority", ["low", "normal", "high", "urgent"])
    _create_enum("ticket_link_status", ["unlinked", "linked", "needs_review"])
    _create_enum("surrogate_email_contact_source", ["system", "manual"])

    op.add_column(
        "user_integrations", sa.Column("granted_scopes", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "user_integrations", sa.Column("gmail_sent_last_history_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "user_integrations",
        sa.Column("gmail_sent_last_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("user_integrations", sa.Column("gmail_sent_sync_error", sa.Text(), nullable=True))

    op.create_table(
        "mailbox_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM("gmail", name="mailbox_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("account_email", postgresql.CITEXT(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_scopes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "account_email",
            name="uq_mailbox_cred_email",
        ),
    )
    op.create_index(
        "idx_mailbox_credentials_org_provider",
        "mailbox_credentials",
        ["organization_id", "provider"],
        unique=False,
    )

    op.create_table(
        "mailboxes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("journal", "user_sent", name="mailbox_kind", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM("gmail", name="mailbox_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("email_address", postgresql.CITEXT(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_integration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_queue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("ingestion_paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingestion_pause_reason", sa.Text(), nullable=True),
        sa.Column("gmail_history_id", sa.BigInteger(), nullable=True),
        sa.Column("last_incremental_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["mailbox_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["user_integration_id"], ["user_integrations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["default_queue_id"], ["queues.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "kind",
            "email_address",
            name="uq_mailboxes_org_kind_email",
        ),
    )
    op.create_index(
        "idx_mailboxes_org_enabled", "mailboxes", ["organization_id", "is_enabled"], unique=False
    )
    op.create_index(
        "idx_mailboxes_org_kind", "mailboxes", ["organization_id", "kind"], unique=False
    )

    op.create_table(
        "email_raw_blobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "sha256_hex", name="uq_email_raw_blob_sha"),
    )
    op.create_index(
        "idx_email_raw_blobs_org_created",
        "email_raw_blobs",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "email_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "direction",
            postgresql.ENUM("inbound", "outbound", name="email_direction", create_type=False),
            nullable=False,
        ),
        sa.Column("rfc_message_id", sa.Text(), nullable=True),
        sa.Column("gmail_thread_id", sa.Text(), nullable=True),
        sa.Column("subject_norm", sa.Text(), nullable=True),
        sa.Column("fingerprint_sha256", sa.String(length=64), nullable=False),
        sa.Column("signature_sha256", sa.String(length=64), nullable=False),
        sa.Column("collision_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "fingerprint_sha256",
            "signature_sha256",
            name="uq_email_messages_fingerprint_signature",
        ),
    )
    op.create_index(
        "idx_email_messages_org_created",
        "email_messages",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_email_messages_org_rfc",
        "email_messages",
        ["organization_id", "rfc_message_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_messages_org_thread",
        "email_messages",
        ["organization_id", "gmail_thread_id"],
        unique=False,
    )

    op.create_table(
        "email_message_contents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("parser_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "parsed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("date_header", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("subject_norm", sa.Text(), nullable=True),
        sa.Column("from_email", postgresql.CITEXT(), nullable=True),
        sa.Column("from_name", sa.Text(), nullable=True),
        sa.Column(
            "reply_to_emails",
            postgresql.ARRAY(postgresql.CITEXT()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "to_emails",
            postgresql.ARRAY(postgresql.CITEXT()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "cc_emails",
            postgresql.ARRAY(postgresql.CITEXT()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "headers_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html_sanitized", sa.Text(), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("attachment_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "message_id",
            "content_version",
            name="uq_email_message_content_version",
        ),
    )
    op.create_index(
        "idx_email_message_contents_org_message",
        "email_message_contents",
        ["organization_id", "message_id"],
        unique=False,
    )

    op.create_table(
        "email_message_thread_refs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ref_type", sa.String(length=30), nullable=False),
        sa.Column("ref_rfc_message_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_email_message_thread_refs_org_message",
        "email_message_thread_refs",
        ["organization_id", "message_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_message_thread_refs_org_rfc",
        "email_message_thread_refs",
        ["organization_id", "ref_rfc_message_id"],
        unique=False,
    )

    op.create_table(
        "tickets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_code", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "new",
                "open",
                "pending",
                "resolved",
                "closed",
                "spam",
                name="ticket_status",
                create_type=False,
            ),
            server_default=sa.text("'new'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low",
                "normal",
                "high",
                "urgent",
                name="ticket_priority",
                create_type=False,
            ),
            server_default=sa.text("'normal'"),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("subject_norm", sa.Text(), nullable=True),
        sa.Column("requester_email", postgresql.CITEXT(), nullable=True),
        sa.Column("requester_name", sa.Text(), nullable=True),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignee_queue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "surrogate_link_status",
            postgresql.ENUM(
                "unlinked",
                "linked",
                "needs_review",
                name="ticket_link_status",
                create_type=False,
            ),
            server_default=sa.text("'unlinked'"),
            nullable=False,
        ),
        sa.Column("stitch_reason", sa.Text(), nullable=True),
        sa.Column(
            "stitch_confidence",
            postgresql.ENUM(
                "high",
                "medium",
                "low",
                name="ticket_link_confidence",
                create_type=False,
            ),
            server_default=sa.text("'low'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_queue_id"], ["queues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "ticket_code", name="uq_tickets_code"),
    )
    op.create_index(
        "idx_tickets_org_status", "tickets", ["organization_id", "status"], unique=False
    )
    op.create_index(
        "idx_tickets_org_assignee",
        "tickets",
        ["organization_id", "assignee_user_id", "assignee_queue_id"],
        unique=False,
    )
    op.create_index(
        "idx_tickets_org_surrogate", "tickets", ["organization_id", "surrogate_id"], unique=False
    )
    op.create_index(
        "idx_tickets_org_activity", "tickets", ["organization_id", "last_activity_at"], unique=False
    )
    op.create_index(
        "idx_tickets_org_link_status",
        "tickets",
        ["organization_id", "surrogate_link_status"],
        unique=False,
    )

    op.create_table(
        "email_message_occurrences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mailbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gmail_message_id", sa.Text(), nullable=False),
        sa.Column("gmail_thread_id", sa.Text(), nullable=True),
        sa.Column("gmail_history_id", sa.BigInteger(), nullable=True),
        sa.Column("gmail_internal_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "label_ids", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "state",
            postgresql.ENUM(
                "discovered",
                "raw_fetched",
                "parsed",
                "stitched",
                "linked",
                "failed",
                name="email_occurrence_state",
                create_type=False,
            ),
            server_default=sa.text("'discovered'"),
            nullable=False,
        ),
        sa.Column("raw_blob_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_fetch_error", sa.Text(), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stitched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stitch_error", sa.Text(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("link_error", sa.Text(), nullable=True),
        sa.Column("original_recipient", postgresql.CITEXT(), nullable=True),
        sa.Column(
            "original_recipient_source",
            postgresql.ENUM(
                "workspace_header",
                "delivered_to",
                "x_original_to",
                "to_cc_scan",
                "unknown",
                name="ticket_recipient_source",
                create_type=False,
            ),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "original_recipient_confidence",
            postgresql.ENUM(
                "high",
                "medium",
                "low",
                name="ticket_link_confidence",
                create_type=False,
            ),
            server_default=sa.text("'low'"),
            nullable=False,
        ),
        sa.Column(
            "original_recipient_evidence",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raw_blob_id"], ["email_raw_blobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "mailbox_id",
            "gmail_message_id",
            name="uq_email_occurrence_gmail_message",
        ),
    )
    op.create_index(
        "idx_email_occurrence_org_state",
        "email_message_occurrences",
        ["organization_id", "state"],
        unique=False,
    )
    op.create_index(
        "idx_email_occurrence_org_message",
        "email_message_occurrences",
        ["organization_id", "message_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_occurrence_org_ticket",
        "email_message_occurrences",
        ["organization_id", "ticket_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_occurrence_org_thread",
        "email_message_occurrences",
        ["organization_id", "gmail_thread_id"],
        unique=False,
    )

    op.create_table(
        "email_message_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_inline", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("content_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "message_id",
            "attachment_id",
            name="uq_email_message_attachment",
        ),
    )
    op.create_index(
        "idx_email_message_attachments_org_message",
        "email_message_attachments",
        ["organization_id", "message_id"],
        unique=False,
    )

    op.create_table(
        "ticket_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "stitched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stitch_reason", sa.String(length=50), nullable=False),
        sa.Column(
            "stitch_confidence",
            postgresql.ENUM(
                "high",
                "medium",
                "low",
                name="ticket_link_confidence",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["email_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "ticket_id",
            "message_id",
            name="uq_ticket_messages_unique",
        ),
    )
    op.create_index(
        "idx_ticket_messages_org_ticket",
        "ticket_messages",
        ["organization_id", "ticket_id"],
        unique=False,
    )
    op.create_index(
        "idx_ticket_messages_org_message",
        "ticket_messages",
        ["organization_id", "message_id"],
        unique=False,
    )

    op.create_table(
        "ticket_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "event_data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ticket_events_org_ticket_created",
        "ticket_events",
        ["organization_id", "ticket_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "ticket_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_html_sanitized", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ticket_notes_org_ticket_created",
        "ticket_notes",
        ["organization_id", "ticket_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "ticket_saved_views",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "filters_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_ticket_saved_view_name"),
    )
    op.create_index(
        "idx_ticket_saved_views_org", "ticket_saved_views", ["organization_id"], unique=False
    )

    op.create_table(
        "ticket_surrogate_link_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "confidence",
            postgresql.ENUM(
                "high",
                "medium",
                "low",
                name="ticket_link_confidence",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_selected", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "ticket_id",
            "surrogate_id",
            name="uq_ticket_surrogate_candidate",
        ),
    )
    op.create_index(
        "idx_ticket_surrogate_candidates_org_ticket",
        "ticket_surrogate_link_candidates",
        ["organization_id", "ticket_id"],
        unique=False,
    )

    op.create_table(
        "surrogate_email_contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surrogate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=True),
        sa.Column(
            "source",
            postgresql.ENUM(
                "system",
                "manual",
                name="surrogate_email_contact_source",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("contact_type", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["surrogate_id"], ["surrogates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "surrogate_id",
            "email_hash",
            "source",
            name="uq_surrogate_email_contact_unique",
        ),
    )
    op.create_index(
        "idx_surrogate_email_contacts_org_surrogate",
        "surrogate_email_contacts",
        ["organization_id", "surrogate_id"],
        unique=False,
    )
    op.create_index(
        "idx_surrogate_email_contacts_org_hash",
        "surrogate_email_contacts",
        ["organization_id", "email_hash"],
        unique=False,
    )
    op.create_index(
        "idx_surrogate_email_contacts_org_active",
        "surrogate_email_contacts",
        ["organization_id", "is_active"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("idx_surrogate_email_contacts_org_active", table_name="surrogate_email_contacts")
    op.drop_index("idx_surrogate_email_contacts_org_hash", table_name="surrogate_email_contacts")
    op.drop_index(
        "idx_surrogate_email_contacts_org_surrogate", table_name="surrogate_email_contacts"
    )
    op.drop_table("surrogate_email_contacts")

    op.drop_index(
        "idx_ticket_surrogate_candidates_org_ticket", table_name="ticket_surrogate_link_candidates"
    )
    op.drop_table("ticket_surrogate_link_candidates")

    op.drop_index("idx_ticket_saved_views_org", table_name="ticket_saved_views")
    op.drop_table("ticket_saved_views")

    op.drop_index("idx_ticket_notes_org_ticket_created", table_name="ticket_notes")
    op.drop_table("ticket_notes")

    op.drop_index("idx_ticket_events_org_ticket_created", table_name="ticket_events")
    op.drop_table("ticket_events")

    op.drop_index("idx_ticket_messages_org_message", table_name="ticket_messages")
    op.drop_index("idx_ticket_messages_org_ticket", table_name="ticket_messages")
    op.drop_table("ticket_messages")

    op.drop_index(
        "idx_email_message_attachments_org_message", table_name="email_message_attachments"
    )
    op.drop_table("email_message_attachments")

    op.drop_index("idx_email_occurrence_org_thread", table_name="email_message_occurrences")
    op.drop_index("idx_email_occurrence_org_ticket", table_name="email_message_occurrences")
    op.drop_index("idx_email_occurrence_org_message", table_name="email_message_occurrences")
    op.drop_index("idx_email_occurrence_org_state", table_name="email_message_occurrences")
    op.drop_table("email_message_occurrences")

    op.drop_index("idx_tickets_org_link_status", table_name="tickets")
    op.drop_index("idx_tickets_org_activity", table_name="tickets")
    op.drop_index("idx_tickets_org_surrogate", table_name="tickets")
    op.drop_index("idx_tickets_org_assignee", table_name="tickets")
    op.drop_index("idx_tickets_org_status", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index("idx_email_message_thread_refs_org_rfc", table_name="email_message_thread_refs")
    op.drop_index(
        "idx_email_message_thread_refs_org_message", table_name="email_message_thread_refs"
    )
    op.drop_table("email_message_thread_refs")

    op.drop_index("idx_email_message_contents_org_message", table_name="email_message_contents")
    op.drop_table("email_message_contents")

    op.drop_index("idx_email_messages_org_thread", table_name="email_messages")
    op.drop_index("idx_email_messages_org_rfc", table_name="email_messages")
    op.drop_index("idx_email_messages_org_created", table_name="email_messages")
    op.drop_table("email_messages")

    op.drop_index("idx_email_raw_blobs_org_created", table_name="email_raw_blobs")
    op.drop_table("email_raw_blobs")

    op.drop_index("idx_mailboxes_org_kind", table_name="mailboxes")
    op.drop_index("idx_mailboxes_org_enabled", table_name="mailboxes")
    op.drop_table("mailboxes")

    op.drop_index("idx_mailbox_credentials_org_provider", table_name="mailbox_credentials")
    op.drop_table("mailbox_credentials")

    op.drop_column("user_integrations", "gmail_sent_sync_error")
    op.drop_column("user_integrations", "gmail_sent_last_sync_at")
    op.drop_column("user_integrations", "gmail_sent_last_history_id")
    op.drop_column("user_integrations", "granted_scopes")

    _drop_enum("surrogate_email_contact_source")
    _drop_enum("ticket_link_status")
    _drop_enum("ticket_priority")
    _drop_enum("ticket_status")
    _drop_enum("ticket_link_confidence")
    _drop_enum("ticket_recipient_source")
    _drop_enum("email_occurrence_state")
    _drop_enum("email_direction")
    _drop_enum("mailbox_kind")
    _drop_enum("mailbox_provider")
