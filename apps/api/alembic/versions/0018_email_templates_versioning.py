"""Add current_version to email_templates

Revision ID: 0018_email_templates_versioning
Revises: 0017_add_entity_versions
Create Date: 2025-12-17

Adds version control to email templates.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018_email_templates_versioning'
down_revision: Union[str, Sequence[str], None] = '0017_add_entity_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add current_version column to email_templates."""
    op.add_column('email_templates', sa.Column('current_version', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    """Remove current_version from email_templates."""
    op.drop_column('email_templates', 'current_version')
