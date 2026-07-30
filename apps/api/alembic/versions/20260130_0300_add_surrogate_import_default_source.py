"""Add default source to surrogate imports.

Revision ID: 20260130_0300
Revises: 20260130_0230
Create Date: 2026-01-30 03:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260130_0300"
down_revision: str | Sequence[str] | None = "20260130_0230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "surrogate_imports", sa.Column("default_source", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("surrogate_imports", "default_source")
