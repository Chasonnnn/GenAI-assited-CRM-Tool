"""add_notifications_system

Revision ID: 07e0a3628b1b
Revises: 49baca3af89f
Create Date: 2025-12-15 15:18:32.293623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '07e0a3628b1b'
down_revision: Union[str, Sequence[str], None] = '49baca3af89f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notifications and user_notification_settings tables."""
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('dedupe_key', sa.String(length=255), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_notif_dedupe', 'notifications', ['dedupe_key', 'created_at'], unique=False)
    op.create_index('idx_notif_org_user', 'notifications', ['organization_id', 'user_id', 'created_at'], unique=False)
    op.create_index('idx_notif_user_unread', 'notifications', ['user_id', 'read_at', 'created_at'], unique=False)
    
    # Create user_notification_settings table
    op.create_table('user_notification_settings',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('case_assigned', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('case_status_changed', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('case_handoff', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('task_assigned', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    """Drop notifications and user_notification_settings tables."""
    op.drop_table('user_notification_settings')
    op.drop_index('idx_notif_user_unread', table_name='notifications')
    op.drop_index('idx_notif_org_user', table_name='notifications')
    op.drop_index('idx_notif_dedupe', table_name='notifications')
    op.drop_table('notifications')
