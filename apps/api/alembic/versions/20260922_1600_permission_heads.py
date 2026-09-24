"""Join permission v2 with donor reporting and Google appointment delivery.

Revision ID: 20260922_1600_permission_heads
Revises: 20260920_0310_permission_heads, 20260921_0100_google_appointment_sync
"""

from collections.abc import Sequence

revision: str = "20260922_1600_permission_heads"
down_revision: str | Sequence[str] | None = (
    "20260920_0310_permission_heads",
    "20260921_0100_google_appointment_sync",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
