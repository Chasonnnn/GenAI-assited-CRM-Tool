"""merge_match_events_and_org_timezone

Revision ID: 866add7e8baa
Revises: 0045_add_org_timezone_and_matched_stage, fdd16771f703
Create Date: 2025-12-22 17:20:08.709279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '866add7e8baa'
down_revision: Union[str, Sequence[str], None] = ('0045_add_org_timezone_and_matched_stage', 'fdd16771f703')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
