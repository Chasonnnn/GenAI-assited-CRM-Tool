"""canonicalize surrogate height precision

Revision ID: 20260406_1700
Revises: 20260329_2230
Create Date: 2026-04-06 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260406_1700"
down_revision: str | Sequence[str] | None = "20260329_2230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "surrogates",
        "height_ft",
        existing_type=sa.Numeric(precision=3, scale=1),
        type_=sa.Numeric(precision=4, scale=2),
        existing_nullable=True,
    )
    op.execute(
        """
        UPDATE surrogates
        SET height_ft = ROUND(ROUND(height_ft * 12)::numeric / 12.0, 2)
        WHERE height_ft IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE surrogates
        SET height_ft = ROUND(height_ft::numeric, 1)
        WHERE height_ft IS NOT NULL
        """
    )
    op.alter_column(
        "surrogates",
        "height_ft",
        existing_type=sa.Numeric(precision=4, scale=2),
        type_=sa.Numeric(precision=3, scale=1),
        existing_nullable=True,
    )
