"""Bind provider retries to the credential used for the first attempt.

Revision ID: 20260723_0200
Revises: 20260723_0190
Create Date: 2026-07-23 04:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260723_0200"
down_revision = "20260723_0190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_deliveries",
        sa.Column(
            "provider_credential_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("email_deliveries", "provider_credential_fingerprint")
