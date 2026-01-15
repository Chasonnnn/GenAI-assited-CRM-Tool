"""merge_settings_and_notifications

Revision ID: c750cb72a8a6
Revises: c5f4e3d2b1a0, i1a2b3c4d5e6
Create Date: 2026-01-05 17:44:41.068999

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "c750cb72a8a6"
down_revision: Union[str, Sequence[str], None] = ("c5f4e3d2b1a0", "i1a2b3c4d5e6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
