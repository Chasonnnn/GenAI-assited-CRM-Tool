"""Join the Google SDK upgrade and released donor-profile migration histories.

Revision ID: 20260919_0100_platform_heads
Revises: 20260907_1200, 20260914_1200_donor_profile
Create Date: 2026-09-19 03:32:00.077153

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260919_0100_platform_heads"
down_revision: str | Sequence[str] | None = ("20260907_1200", "20260914_1200_donor_profile")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
