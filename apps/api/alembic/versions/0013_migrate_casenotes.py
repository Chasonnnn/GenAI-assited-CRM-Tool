"""Migrate CaseNote to EntityNote

Revision ID: 0013_migrate_casenotes
Revises: 0012_add_indexes
Create Date: 2025-12-17

Per "No Backward Compatibility" rule:
- Copies all case_notes into entity_notes with entity_type='case'
- Drops the case_notes table
- This is a one-way migration (no downgrade to restore old table)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013_migrate_casenotes'
down_revision: Union[str, Sequence[str], None] = '0012_add_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate case_notes to entity_notes, then drop case_notes table."""
    
    # 1. Copy all case_notes into entity_notes
    op.execute("""
        INSERT INTO entity_notes (id, organization_id, entity_type, entity_id, author_id, content, created_at)
        SELECT 
            id,
            organization_id,
            'case' AS entity_type,
            case_id AS entity_id,
            author_id,
            body AS content,
            created_at
        FROM case_notes
        ON CONFLICT (id) DO NOTHING
    """)
    
    # 2. Drop the old case_notes table
    op.drop_table('case_notes')


def downgrade() -> None:
    """Cannot restore deleted case_notes - per No Backward Compatibility rule."""
    raise NotImplementedError(
        "Downgrade not supported: case_notes data was migrated to entity_notes. "
        "Restore from backup if needed."
    )
