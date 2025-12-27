"""Add MFA fields to users table

Revision ID: a1b2c3d4e5f6
Revises: e7c6d4a1b2c3
Create Date: 2024-12-26 18:25:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e7c6d4a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add MFA fields to users table
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), 
                                      server_default=sa.text('false'), nullable=False))
    op.add_column('users', sa.Column('totp_secret', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('totp_enabled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('duo_user_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('duo_enrolled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('mfa_recovery_codes', postgresql.JSONB(), nullable=True))
    op.add_column('users', sa.Column('mfa_required_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'mfa_required_at')
    op.drop_column('users', 'mfa_recovery_codes')
    op.drop_column('users', 'duo_enrolled_at')
    op.drop_column('users', 'duo_user_id')
    op.drop_column('users', 'totp_enabled_at')
    op.drop_column('users', 'totp_secret')
    op.drop_column('users', 'mfa_enabled')
