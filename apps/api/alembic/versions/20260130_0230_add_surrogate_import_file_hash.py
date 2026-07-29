"""Add file hash to surrogate imports.

Revision ID: 20260130_0230
Revises: 20260130_0105
Create Date: 2026-01-30 02:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260130_0230"
down_revision: str | Sequence[str] | None = "20260130_0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("surrogate_imports", sa.Column("file_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "idx_surrogate_imports_org_file_hash",
        "surrogate_imports",
        ["organization_id", "file_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_surrogate_imports_org_file_hash", table_name="surrogate_imports")
    op.drop_column("surrogate_imports", "file_hash")
