"""add_transcript_json_to_interviews

Revision ID: 629a8e7a77e2
Revises: j1a2b3c4d5e6
Create Date: 2026-01-05 23:09:58.912540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '629a8e7a77e2'
down_revision: Union[str, Sequence[str], None] = 'j1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'case_interviews',
        sa.Column('transcript_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('case_interviews', 'transcript_json')
