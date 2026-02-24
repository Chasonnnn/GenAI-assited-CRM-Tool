"""drop match compatibility score

Revision ID: 20260224_1710
Revises: 20260224_0105
Create Date: 2026-02-24 17:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260224_1710"
down_revision: str | Sequence[str] | None = "20260224_0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_column("matches", "compatibility_score"):
        op.drop_column("matches", "compatibility_score")


def downgrade() -> None:
    if not _has_column("matches", "compatibility_score"):
        op.add_column(
            "matches",
            sa.Column("compatibility_score", sa.Numeric(precision=5, scale=2), nullable=True),
        )
