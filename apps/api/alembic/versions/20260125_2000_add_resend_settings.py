"""add_resend_settings

Revision ID: 20260125_2000
Revises: 20260125_1915
Create Date: 2026-01-25 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260125_2000"
down_revision: Union[str, Sequence[str], None] = "20260125_1915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ResendSettings table and extend EmailLog/CampaignRun."""
    # Create resend_settings table
    op.create_table(
        "resend_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_provider", sa.String(20), nullable=True),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("from_email", sa.String(255), nullable=True),
        sa.Column("from_name", sa.String(100), nullable=True),
        sa.Column("reply_to_email", sa.String(255), nullable=True),
        sa.Column("verified_domain", sa.String(255), nullable=True),
        sa.Column("last_key_validated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("default_sender_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "webhook_id",
            sa.String(36),
            server_default=sa.text("gen_random_uuid()::text"),
            nullable=False,
        ),
        sa.Column("webhook_secret_encrypted", sa.Text, nullable=True),
        sa.Column("current_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["default_sender_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index(
        "idx_resend_settings_webhook_id",
        "resend_settings",
        ["webhook_id"],
        unique=True,
    )

    # Extend email_logs with Resend tracking fields
    op.add_column(
        "email_logs",
        sa.Column("resend_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("bounced_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("bounce_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "email_logs",
        sa.Column("complained_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Extend campaign_runs with email_provider
    op.add_column(
        "campaign_runs",
        sa.Column("email_provider", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    """Remove ResendSettings table and related columns."""
    # Remove campaign_runs column
    op.drop_column("campaign_runs", "email_provider")

    # Remove email_logs columns
    op.drop_column("email_logs", "complained_at")
    op.drop_column("email_logs", "bounce_type")
    op.drop_column("email_logs", "bounced_at")
    op.drop_column("email_logs", "delivered_at")
    op.drop_column("email_logs", "resend_status")

    # Drop resend_settings table
    op.drop_index("idx_resend_settings_webhook_id", table_name="resend_settings")
    op.drop_table("resend_settings")
