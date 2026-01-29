"""Merge multiple heads.

Revision ID: 20260130_0105
Revises: 20260129_0051, 20260130_0010
Create Date: 2026-01-30 01:05:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260130_0105"
down_revision: Union[str, Sequence[str], None] = ("20260129_0051", "20260130_0010")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge revision; no schema changes."""
    pass


def downgrade() -> None:
    """Merge revision; no schema changes."""
    pass
