"""merge intelligent suggestion heads

Revision ID: 20260303_1000
Revises: 20260301_1200, 20260302_0900
Create Date: 2026-03-02 22:50:49.243297

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '20260303_1000'
down_revision: Union[str, Sequence[str], None] = ('20260301_1200', '20260302_0900')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
