"""merge heads

Revision ID: e7c6d4a1b2c3
Revises: c3e9f2a1b8d4, 07e0a3628b1b, ab9ee2996572, bd48fc289751, 201ff7c41d70, f3bc6a65a816
Create Date: 2025-12-27 00:00:00.000000

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = "e7c6d4a1b2c3"
down_revision: Union[str, Sequence[str], None] = (
    "c3e9f2a1b8d4",
    "07e0a3628b1b",
    "ab9ee2996572",
    "bd48fc289751",
    "201ff7c41d70",
    "f3bc6a65a816",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads."""
    pass


def downgrade() -> None:
    """Split heads."""
    pass
