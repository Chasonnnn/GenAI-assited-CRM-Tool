"""Join the platform upgrade and OPS CLI migration histories.

Revision ID: 20260920_0300_platform_heads
Revises: 20260919_0100_platform_heads, 20260919_0300_ops_cli_login
Create Date: 2026-09-20 03:03:18.010730

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260920_0300_platform_heads"
down_revision: str | Sequence[str] | None = (
    "20260919_0100_platform_heads",
    "20260919_0300_ops_cli_login",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
