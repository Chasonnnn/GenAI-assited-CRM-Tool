"""Drop the account-level send-rate slots; Twilio queues and rate-limits sends itself.

Revision ID: 20261007_1800_drop_messaging_provider_admission
Revises: 20261007_1500_scheduling_template_keys
"""

import sqlalchemy as sa

from alembic import op

revision = "20261007_1800_drop_messaging_provider_admission"
down_revision = "20261007_1500_scheduling_template_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_messaging_provider_next_slot", table_name="messaging_provider_admission")
    op.drop_table("messaging_provider_admission")


def downgrade() -> None:
    # The slots held only timing, so the table comes back empty.
    op.create_table(
        "messaging_provider_admission",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_sid_hash", sa.String(length=64), nullable=False),
        sa.Column("next_slot_at", sa.TIMESTAMP(timezone=True), nullable=False),
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
        sa.UniqueConstraint("account_sid_hash", name="uq_messaging_provider_admission_account"),
    )
    op.create_index(
        "idx_messaging_provider_next_slot",
        "messaging_provider_admission",
        ["next_slot_at"],
        unique=False,
    )
