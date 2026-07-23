"""Add durable provider-account email admission.

Revision ID: 20260723_0160
Revises: 20260723_0150
Create Date: 2026-07-23 02:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID


revision = "20260723_0160"
down_revision = "20260723_0150"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_logs",
        sa.Column(
            "suppression_policy",
            sa.String(length=20),
            server_default=sa.text("'enforce_all'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_email_logs_suppression_policy",
        "email_logs",
        "suppression_policy IN ('enforce_all', 'allow_opt_out')",
    )

    op.create_table(
        "email_provider_admission",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column(
            "next_slot_at",
            TIMESTAMP(timezone=True),
            nullable=False,
        ),
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
        sa.UniqueConstraint(
            "provider",
            "provider_account_id",
            name="uq_email_provider_admission_account",
        ),
    )
    op.create_index(
        "idx_email_provider_admission_next_slot",
        "email_provider_admission",
        ["next_slot_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_email_provider_admission_next_slot",
        table_name="email_provider_admission",
    )
    op.drop_table("email_provider_admission")
    op.execute("ALTER TABLE email_logs DROP CONSTRAINT IF EXISTS ck_email_logs_suppression_policy")
    op.execute("ALTER TABLE email_logs DROP COLUMN IF EXISTS suppression_policy")
