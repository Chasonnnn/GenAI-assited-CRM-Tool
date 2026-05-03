"""add surrogate personal address fields

Revision ID: 20260503_0900
Revises: 20260502_1200
Create Date: 2026-05-03 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0900"
down_revision: str | Sequence[str] | None = "20260502_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("surrogates", sa.Column("address_line1", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("address_line2", sa.Text(), nullable=True))
    op.add_column("surrogates", sa.Column("address_city", sa.String(length=100), nullable=True))
    op.add_column("surrogates", sa.Column("address_state", sa.String(length=2), nullable=True))
    op.add_column("surrogates", sa.Column("address_postal", sa.String(length=20), nullable=True))
    op.add_column("surrogates", sa.Column("partner_date_of_birth", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("surrogates", "partner_date_of_birth")
    op.drop_column("surrogates", "address_postal")
    op.drop_column("surrogates", "address_state")
    op.drop_column("surrogates", "address_city")
    op.drop_column("surrogates", "address_line2")
    op.drop_column("surrogates", "address_line1")
