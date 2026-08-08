"""Merge Twilio messaging and opaque unsubscribe migration heads.

Revision ID: 20260804_0040
Revises: 20260731_2250, 20260803_0100
Create Date: 2026-08-04 00:40:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260804_0040"
down_revision: str | Sequence[str] | None = ("20260731_2250", "20260803_0100")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge revision; no schema changes."""
    pass


def downgrade() -> None:
    """Merge revision; no schema changes."""
    pass
