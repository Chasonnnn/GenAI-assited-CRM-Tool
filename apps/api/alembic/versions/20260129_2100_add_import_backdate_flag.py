"""Add backdate flag to surrogate imports.

Revision ID: 20260129_2100
Revises: 20260129_1900
Create Date: 2026-01-29 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260129_2100"
down_revision: Union[str, None] = "20260129_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "surrogate_imports",
        sa.Column(
            "backdate_created_at",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("surrogate_imports", "backdate_created_at")
