"""Join permission v2 with the current platform and OPS CLI migrations.

Revision ID: 20260920_0310_permission_heads
Revises: 20260920_0300_platform_heads, 20260919_0200_permission_heads
Create Date: 2026-09-20 03:08:46.405154

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260920_0310_permission_heads"
down_revision: str | Sequence[str] | None = (
    "20260920_0300_platform_heads",
    "20260919_0200_permission_heads",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
