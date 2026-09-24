"""Join permission authority with the refreshed platform and donor-profile history.

Revision ID: 20260919_0200_permission_heads
Revises: 20260919_0100_platform_heads, 20260907_2220_work_authority
Create Date: 2026-09-19 03:39:22.860193

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260919_0200_permission_heads"
down_revision: str | Sequence[str] | None = (
    "20260919_0100_platform_heads",
    "20260907_2220_work_authority",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
