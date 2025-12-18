"""Add queues table and case ownership fields

Revision ID: 0023_add_queues_ownership
Revises: 0022_standardize_timestamps_tz
Create Date: 2025-12-18

Salesforce-style single owner model:
- Queue model for work queues
- Case.owner_type (user|queue) + Case.owner_id
- Backfill: existing cases get owner_type="user", owner_id=assigned_to or created_by
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0023_add_queues_ownership'
down_revision = '0022_standardize_timestamps_tz'
branch_labels = None
depends_on = None


def upgrade():
    # Create queues table
    op.create_table(
        'queues',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_queue_name')
    )
    op.create_index('idx_queues_org_active', 'queues', ['organization_id', 'is_active'])
    
    # Add ownership columns to cases (nullable for migration)
    op.add_column('cases', sa.Column('owner_type', sa.String(length=10), nullable=True))
    op.add_column('cases', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Backfill: set owner_type="user" and owner_id=assigned_to or created_by
    op.execute("""
        UPDATE cases 
        SET owner_type = 'user',
            owner_id = COALESCE(assigned_to_user_id, created_by_user_id)
        WHERE owner_type IS NULL
    """)
    
    # Create ownership index
    op.create_index('idx_cases_org_owner', 'cases', ['organization_id', 'owner_type', 'owner_id'])


def downgrade():
    # Drop ownership index and columns
    op.drop_index('idx_cases_org_owner', table_name='cases')
    op.drop_column('cases', 'owner_id')
    op.drop_column('cases', 'owner_type')
    
    # Drop queues table
    op.drop_index('idx_queues_org_active', table_name='queues')
    op.drop_table('queues')
