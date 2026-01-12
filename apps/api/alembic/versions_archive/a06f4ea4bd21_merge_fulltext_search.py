"""merge_fulltext_search

Revision ID: a06f4ea4bd21
Revises: 5764ba19b573, b2c4d5e6f7a8
Create Date: 2025-12-27 19:28:19.996438

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "a06f4ea4bd21"
down_revision: Union[str, Sequence[str], None] = ("5764ba19b573", "b2c4d5e6f7a8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
