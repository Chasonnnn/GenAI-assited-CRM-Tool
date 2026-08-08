"""Add durable inbound MMS processing state.

Revision ID: 20260731_2250
Revises: 20260731_2240
Create Date: 2026-07-31 22:50:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260731_2250"
down_revision = "20260731_2240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "message_media_links",
        sa.Column("provider_media_sid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "message_media_links",
        sa.Column("provider_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "message_media_links",
        sa.Column(
            "processing_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_message_media_link_processing_status",
        "message_media_links",
        "processing_status IN ('pending', 'stored', 'quarantined', 'delete_failed')",
    )
    op.drop_constraint(
        "ck_message_reconciliation_case_type",
        "message_reconciliation_cases",
        type_="check",
    )
    op.create_check_constraint(
        "ck_message_reconciliation_case_type",
        "message_reconciliation_cases",
        "case_type IN ('ambiguous_delivery', 'orphan_webhook', 'unlinked_inbound', "
        "'media_processing')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_message_reconciliation_case_type",
        "message_reconciliation_cases",
        type_="check",
    )
    op.create_check_constraint(
        "ck_message_reconciliation_case_type",
        "message_reconciliation_cases",
        "case_type IN ('ambiguous_delivery', 'orphan_webhook', 'unlinked_inbound')",
    )
    op.drop_constraint(
        "ck_message_media_link_processing_status",
        "message_media_links",
        type_="check",
    )
    op.drop_column("message_media_links", "processing_status")
    op.drop_column("message_media_links", "provider_deleted_at")
    op.drop_column("message_media_links", "provider_media_sid")
