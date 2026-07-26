"""Track Resend's provider idempotency window.

Revision ID: 20260723_0170
Revises: 20260723_0160
Create Date: 2026-07-23 02:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP


revision = "20260723_0170"
down_revision = "20260723_0160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_deliveries",
        sa.Column(
            "idempotency_expires_at",
            TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("email_deliveries", "idempotency_expires_at")
