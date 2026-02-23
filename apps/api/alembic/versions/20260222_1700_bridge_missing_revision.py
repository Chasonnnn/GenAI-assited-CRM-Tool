"""bridge missing local revision stamp

Revision ID: 20260222_1700
Revises: 20260222_1200
Create Date: 2026-02-22 17:00:00.000000

This migration is intentionally a no-op and exists to bridge environments
whose alembic_version was previously stamped to 20260222_1700.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260222_1700"
down_revision: str | Sequence[str] | None = "20260222_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
