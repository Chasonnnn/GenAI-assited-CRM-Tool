"""Add actual_delivery_date to surrogates for Journey tracking.

Revision ID: 20260117_0900
Revises: 20260116_1500
Create Date: 2026-01-17 09:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260117_0900"
down_revision = "20260116_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add actual_delivery_date field for tracking when delivery actually occurred
    # Uses sa.Text() because it's stored encrypted (EncryptedDate type)
    op.add_column("surrogates", sa.Column("actual_delivery_date", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("surrogates", "actual_delivery_date")
