"""merge contact attempts and interview tables

Revision ID: b713579f03ec
Revises: 890beee2b949, g1a2b3c4d5e6
Create Date: 2026-01-04 23:59:44.132744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b713579f03ec'
down_revision: Union[str, Sequence[str], None] = ('890beee2b949', 'g1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
