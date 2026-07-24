"""Add the leased transactional email delivery outbox.

Revision ID: 20260723_0130
Revises: 20260723_0115
Create Date: 2026-07-23 01:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID


revision = "20260723_0130"
down_revision = "20260723_0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "email_logs",
        "idempotency_key",
        existing_type=sa.String(length=255),
        type_=sa.String(length=256),
        existing_nullable=True,
    )
    op.add_column("email_logs", sa.Column("text_body", sa.Text(), nullable=True))
    op.add_column("email_logs", sa.Column("from_email", sa.String(length=320), nullable=True))
    op.add_column(
        "email_logs",
        sa.Column("reply_to_email", sa.String(length=320), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column(
            "headers",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "email_logs",
        sa.Column(
            "safe_tags",
            JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "email_logs",
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column("email_logs", sa.Column("purpose", sa.String(length=50), nullable=True))
    op.add_column("email_logs", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.add_column("email_logs", sa.Column("source_id", UUID(as_uuid=True), nullable=True))
    op.add_column("email_logs", sa.Column("provider", sa.String(length=20), nullable=True))
    op.add_column(
        "email_logs",
        sa.Column("provider_scope", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("provider_account_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_email_logs_org_id",
        "email_logs",
        ["organization_id", "id"],
    )

    op.create_table(
        "email_deliveries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_log_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_scope", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "run_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default=sa.text("5"),
            nullable=False,
        ),
        sa.Column("lease_token", UUID(as_uuid=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("first_attempt_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_attempt_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error_type", sa.String(length=100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "email_log_id"],
            ["email_logs.organization_id", "email_logs.id"],
            name="fk_email_deliveries_org_email_log",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending', 'leased', 'retry_scheduled', 'sent', 'failed', "
            "'cancelled', 'reconciliation_required')",
            name="ck_email_deliveries_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
            name="ck_email_deliveries_attempt_bounds",
        ),
        sa.CheckConstraint(
            "(status = 'leased' AND lease_token IS NOT NULL "
            "AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'leased' AND lease_token IS NULL "
            "AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_email_deliveries_lease_coherence",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_email_deliveries_org_id",
        ),
        sa.UniqueConstraint(
            "email_log_id",
            name="uq_email_deliveries_email_log",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_account_id",
            "idempotency_key",
            name="uq_email_deliveries_provider_idempotency",
        ),
    )
    op.create_index(
        "idx_email_deliveries_due",
        "email_deliveries",
        ["status", "run_at"],
        postgresql_where=sa.text("status IN ('pending', 'retry_scheduled')"),
    )
    op.create_index(
        "idx_email_deliveries_expired_lease",
        "email_deliveries",
        ["lease_expires_at"],
        postgresql_where=sa.text("status = 'leased'"),
    )
    op.create_index(
        "idx_email_deliveries_org_created",
        "email_deliveries",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "uq_email_deliveries_provider_message",
        "email_deliveries",
        ["provider", "provider_account_id", "provider_message_id"],
        unique=True,
        postgresql_where=sa.text("provider_message_id IS NOT NULL"),
    )

    op.create_table(
        "email_delivery_attempts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delivery_id", UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("lease_token", UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "outcome",
            sa.String(length=30),
            server_default=sa.text("'in_progress'"),
            nullable=False,
        ),
        sa.Column("provider_http_status", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "delivery_id"],
            ["email_deliveries.organization_id", "email_deliveries.id"],
            name="fk_email_delivery_attempts_org_delivery",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_email_delivery_attempt_number",
        ),
        sa.CheckConstraint(
            "outcome IN "
            "('in_progress', 'succeeded', 'retryable_error', "
            "'terminal_error', 'lease_expired')",
            name="ck_email_delivery_attempt_outcome",
        ),
        sa.CheckConstraint(
            "retry_after_seconds IS NULL OR retry_after_seconds >= 0",
            name="ck_email_delivery_attempt_retry_after",
        ),
        sa.UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_email_delivery_attempt_number",
        ),
    )
    op.create_index(
        "idx_email_delivery_attempts_org_delivery",
        "email_delivery_attempts",
        ["organization_id", "delivery_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_email_delivery_attempts_org_delivery",
        table_name="email_delivery_attempts",
    )
    op.drop_table("email_delivery_attempts")

    op.drop_index(
        "uq_email_deliveries_provider_message",
        table_name="email_deliveries",
    )
    op.drop_index(
        "idx_email_deliveries_org_created",
        table_name="email_deliveries",
    )
    op.drop_index(
        "idx_email_deliveries_expired_lease",
        table_name="email_deliveries",
    )
    op.drop_index("idx_email_deliveries_due", table_name="email_deliveries")
    op.drop_table("email_deliveries")

    op.drop_constraint("uq_email_logs_org_id", "email_logs", type_="unique")
    op.drop_column("email_logs", "provider_account_id")
    op.drop_column("email_logs", "provider_scope")
    op.drop_column("email_logs", "provider")
    op.drop_column("email_logs", "source_id")
    op.drop_column("email_logs", "source_type")
    op.drop_column("email_logs", "purpose")
    op.drop_column("email_logs", "content_fingerprint")
    op.drop_column("email_logs", "safe_tags")
    op.drop_column("email_logs", "headers")
    op.drop_column("email_logs", "reply_to_email")
    op.drop_column("email_logs", "from_email")
    op.drop_column("email_logs", "text_body")
    op.alter_column(
        "email_logs",
        "idempotency_key",
        existing_type=sa.String(length=256),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
