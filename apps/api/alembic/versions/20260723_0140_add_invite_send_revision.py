"""Add monotonic invite send revision.

Revision ID: 20260723_0140
Revises: 20260723_0130
Create Date: 2026-07-23 01:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0140"
down_revision = "20260723_0130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_invites",
        sa.Column(
            "send_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Monotonic email-send occurrence used for provider idempotency",
        ),
    )
    op.execute("UPDATE org_invites SET send_revision = resend_count")
    op.create_check_constraint(
        "ck_org_invites_send_revision_nonnegative",
        "org_invites",
        "send_revision >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_org_invites_send_revision_nonnegative",
        "org_invites",
        type_="check",
    )
    op.drop_column("org_invites", "send_revision")
