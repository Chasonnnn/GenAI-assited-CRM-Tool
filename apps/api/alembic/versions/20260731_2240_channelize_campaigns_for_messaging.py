"""channelize campaigns for messaging

Revision ID: 20260731_2240
Revises: 20260731_2235
Create Date: 2026-07-31 17:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_2240"
down_revision: str | Sequence[str] | None = "20260731_2235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "channel",
            sa.String(length=20),
            server_default=sa.text("'email'"),
            nullable=False,
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column("message_template_version_id", sa.UUID(), nullable=True),
    )
    op.alter_column("campaigns", "email_template_id", existing_type=sa.UUID(), nullable=True)
    op.create_foreign_key(
        "fk_campaigns_message_template_version_id",
        "campaigns",
        "message_templates",
        ["message_template_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_campaigns_channel",
        "campaigns",
        "channel IN ('email', 'messaging')",
    )
    op.create_check_constraint(
        "ck_campaigns_channel_template",
        "campaigns",
        "(channel = 'email' AND email_template_id IS NOT NULL "
        "AND message_template_version_id IS NULL) OR "
        "(channel = 'messaging' AND email_template_id IS NULL "
        "AND message_template_version_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_campaigns_messaging_no_unsubscribe_bypass",
        "campaigns",
        "channel = 'email' OR include_unsubscribed = false",
    )

    op.add_column(
        "campaign_runs",
        sa.Column("message_template_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaign_runs_message_template_version_id",
        "campaign_runs",
        "message_templates",
        ["message_template_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.alter_column(
        "campaign_recipients",
        "recipient_email",
        existing_type=sa.dialects.postgresql.CITEXT(),
        nullable=True,
    )
    op.add_column(
        "campaign_recipients",
        sa.Column("recipient_phone_last4", sa.String(length=4), nullable=True),
    )
    op.add_column(
        "campaign_recipients",
        sa.Column("message_delivery_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaign_recipients_message_delivery_id",
        "campaign_recipients",
        "message_deliveries",
        ["message_delivery_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_campaign_recipients_message_delivery",
        "campaign_recipients",
        ["message_delivery_id"],
        unique=True,
        postgresql_where=sa.text("message_delivery_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM campaigns WHERE channel = 'messaging'")
    op.drop_index("idx_campaign_recipients_message_delivery", table_name="campaign_recipients")
    op.drop_constraint(
        "fk_campaign_recipients_message_delivery_id",
        "campaign_recipients",
        type_="foreignkey",
    )
    op.drop_column("campaign_recipients", "message_delivery_id")
    op.drop_column("campaign_recipients", "recipient_phone_last4")
    op.alter_column(
        "campaign_recipients",
        "recipient_email",
        existing_type=sa.dialects.postgresql.CITEXT(),
        nullable=False,
    )

    op.drop_constraint(
        "fk_campaign_runs_message_template_version_id",
        "campaign_runs",
        type_="foreignkey",
    )
    op.drop_column("campaign_runs", "message_template_version_id")

    op.drop_constraint(
        "ck_campaigns_messaging_no_unsubscribe_bypass",
        "campaigns",
        type_="check",
    )
    op.drop_constraint("ck_campaigns_channel_template", "campaigns", type_="check")
    op.drop_constraint("ck_campaigns_channel", "campaigns", type_="check")
    op.drop_constraint(
        "fk_campaigns_message_template_version_id",
        "campaigns",
        type_="foreignkey",
    )
    op.drop_column("campaigns", "message_template_version_id")
    op.alter_column("campaigns", "email_template_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("campaigns", "channel")
