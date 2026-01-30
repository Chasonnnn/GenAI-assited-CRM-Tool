"""Add validation_mode to surrogate imports.

Revision ID: 20260131_1600
Revises: 20260131_1500
Create Date: 2026-01-31 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260131_1600"
down_revision: Union[str, Sequence[str], None] = "20260131_1500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "surrogate_imports",
        sa.Column(
            "validation_mode",
            sa.String(length=30),
            server_default=sa.text("'skip_invalid_rows'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("surrogate_imports", "validation_mode")
