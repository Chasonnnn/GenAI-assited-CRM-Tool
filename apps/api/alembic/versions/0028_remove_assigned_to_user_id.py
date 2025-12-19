"""Remove legacy assigned_to_user_id field.

Revision ID: 0028_remove_assigned_to_user_id
Revises: 0027_automation_workflows
Create Date: 2024-12-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028_remove_assigned_to_user_id'
down_revision: Union[str, None] = '0027_automation_workflows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove legacy assigned_to_user_id column from cases table.
    
    This column has been replaced by the owner_type/owner_id model.
    Data migration should have already copied values to owner_id where applicable.
    """
    # First, migrate any remaining users that still have assigned_to_user_id set
    # but don't have owner_id set (safety net)
    op.execute("""
        UPDATE cases 
        SET owner_id = assigned_to_user_id, 
            owner_type = 'user'
        WHERE assigned_to_user_id IS NOT NULL 
          AND owner_id IS NULL
    """)
    
    # Drop the old index that references assigned_to_user_id (if it exists)
    op.execute("DROP INDEX IF EXISTS idx_cases_org_assigned")
    
    # Drop the foreign key constraint first
    op.drop_constraint('cases_assigned_to_user_id_fkey', 'cases', type_='foreignkey')
    
    # Drop the legacy column
    op.drop_column('cases', 'assigned_to_user_id')
    
    # Create new index for owner-based filtering (if not exists)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_org_owner ON cases (organization_id, owner_type, owner_id)")


def downgrade() -> None:
    """Re-add legacy assigned_to_user_id column."""
    # Re-add the column
    op.add_column('cases', sa.Column('assigned_to_user_id', sa.UUID(), nullable=True))
    
    # Re-add foreign key
    op.create_foreign_key(
        'cases_assigned_to_user_id_fkey',
        'cases',
        'users',
        ['assigned_to_user_id'],
        ['id']
    )
    
    # Migrate owner_id back to assigned_to_user_id where owner_type is 'user'
    op.execute("""
        UPDATE cases 
        SET assigned_to_user_id = owner_id
        WHERE owner_type = 'user' 
          AND owner_id IS NOT NULL
    """)
