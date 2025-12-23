"""add_case_id_and_ip_id_to_appointments

Revision ID: b0c7fdaa4a94
Revises: f0db6749d310
Create Date: 2025-12-23 16:12:38.793837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b0c7fdaa4a94'
down_revision: Union[str, Sequence[str], None] = 'f0db6749d310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add case_id and intended_parent_id to appointments for match-scoped filtering."""
    # Add columns
    op.add_column('appointments', sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('appointments', sa.Column('intended_parent_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Add foreign keys
    op.create_foreign_key(
        'fk_appointments_case_id', 'appointments', 'cases',
        ['case_id'], ['id'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_appointments_intended_parent_id', 'appointments', 'intended_parents',
        ['intended_parent_id'], ['id'], ondelete='SET NULL'
    )
    
    # Add indexes
    op.create_index('idx_appointments_case', 'appointments', ['case_id'])
    op.create_index('idx_appointments_ip', 'appointments', ['intended_parent_id'])


def downgrade() -> None:
    """Remove case_id and intended_parent_id from appointments."""
    op.drop_index('idx_appointments_ip', table_name='appointments')
    op.drop_index('idx_appointments_case', table_name='appointments')
    op.drop_constraint('fk_appointments_intended_parent_id', 'appointments', type_='foreignkey')
    op.drop_constraint('fk_appointments_case_id', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'intended_parent_id')
    op.drop_column('appointments', 'case_id')
