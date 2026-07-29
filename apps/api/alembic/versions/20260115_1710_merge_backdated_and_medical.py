"""Merge backdated stage support and medical fields heads.

Revision ID: 20260115_1710
Revises: 20260115_1600, 20260115_1700
Create Date: 2026-01-15 17:10:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260115_1710"
down_revision: str | None = ("20260115_1600", "20260115_1700")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
