"""Add is_active to memberships.

Revision ID: 20260112_1631
Revises: 20260111_2137
Create Date: 2026-01-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260112_1631"
down_revision: Union[str, Sequence[str], None] = "20260111_2137"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("memberships", "is_active")
