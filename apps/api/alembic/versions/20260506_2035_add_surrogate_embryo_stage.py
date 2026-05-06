"""add surrogate embryo stage

Revision ID: 20260506_2035
Revises: 20260503_0900
Create Date: 2026-05-06 20:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260506_2035"
down_revision: str | Sequence[str] | None = "20260503_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("surrogates", sa.Column("embryo_stage", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_surrogates_embryo_stage",
        "surrogates",
        "embryo_stage IS NULL OR embryo_stage IN ('day_3', 'day_5', 'day_6', 'unknown')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_surrogates_embryo_stage", "surrogates", type_="check")
    op.drop_column("surrogates", "embryo_stage")
