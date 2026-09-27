"""Join scheduling v2 schema with permission v2.

Revision ID: 20260924_0930_scheduling_permission_heads
Revises: 20260922_1000_scheduling_v2_schema, 20260922_1600_permission_heads
"""

from collections.abc import Sequence

revision: str = "20260924_0930_scheduling_permission_heads"
down_revision: str | Sequence[str] | None = (
    "20260922_1000_scheduling_v2_schema",
    "20260922_1600_permission_heads",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
