"""add_is_priority_to_cases

Revision ID: 0b97aee1ec96
Revises: 4930ef3426b5
Create Date: 2025-12-15 00:49:09.455086

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0b97aee1ec96'
down_revision: Union[str, Sequence[str], None] = '4930ef3426b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_priority boolean column to cases table."""
    op.add_column('cases', sa.Column('is_priority', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False))


def downgrade() -> None:
    """Remove is_priority column from cases table."""
    op.drop_column('cases', 'is_priority')
