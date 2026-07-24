"""Add durable Resend webhook events.

Revision ID: 20260723_0048
Revises: 20260701_1025
Create Date: 2026-07-23 00:48:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID


revision = "20260723_0048"
down_revision = "20260701_1025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_logs",
        sa.Column("resend_status_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.alter_column(
        "email_logs",
        "bounce_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.create_table(
        "resend_webhook_events",
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
        sa.Column(
            "email_log_id",
            UUID(as_uuid=True),
            sa.ForeignKey("email_logs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "received_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "provider_event_id",
            name="uq_resend_webhook_events_org_provider_event",
        ),
    )
    op.create_index(
        "idx_resend_webhook_events_org_email_time",
        "resend_webhook_events",
        ["organization_id", "email_log_id", "event_created_at"],
    )
    op.create_index(
        "idx_resend_webhook_events_processed_at",
        "resend_webhook_events",
        ["processed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_resend_webhook_events_processed_at",
        table_name="resend_webhook_events",
    )
    op.drop_index(
        "idx_resend_webhook_events_org_email_time",
        table_name="resend_webhook_events",
    )
    op.drop_table("resend_webhook_events")

    op.alter_column(
        "email_logs",
        "bounce_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.drop_column("email_logs", "resend_status_at")
