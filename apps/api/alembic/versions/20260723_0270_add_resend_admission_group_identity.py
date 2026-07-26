"""Add optional shared Resend admission-group identity.

Revision ID: 20260723_0270
Revises: 20260723_0260
Create Date: 2026-07-23 22:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0270"
down_revision = "20260723_0260"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resend_settings",
        sa.Column(
            "rate_limit_group_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_resend_settings_rate_limit_group_fingerprint",
        "resend_settings",
        ("rate_limit_group_fingerprint IS NULL OR rate_limit_group_fingerprint ~ '^[0-9a-f]{64}$'"),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_resend_settings_rate_limit_group_fingerprint",
        "resend_settings",
        type_="check",
    )
    op.drop_column("resend_settings", "rate_limit_group_fingerprint")
