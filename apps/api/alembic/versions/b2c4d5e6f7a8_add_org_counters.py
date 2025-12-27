"""Add org_counters table for atomic sequence generation.

Revision ID: b2c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2025-12-27

Provides atomic counter generation for case numbers without race conditions.
Uses INSERT...ON CONFLICT for atomic increment.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'  # MFA fields migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create org_counters table for atomic sequence generation
    op.create_table(
        'org_counters',
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('counter_type', sa.String(50), nullable=False),
        sa.Column('current_value', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('organization_id', 'counter_type'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    
    # Seed existing organizations with their current max case numbers
    op.execute("""
        INSERT INTO org_counters (organization_id, counter_type, current_value)
        SELECT
            organization_id,
            'case_number',
            COALESCE(
                MAX(
                    CASE
                        WHEN case_number ~ '^[0-9]+$' THEN CAST(case_number AS INTEGER)
                        ELSE NULL
                    END
                ),
                0
            )
        FROM cases
        GROUP BY organization_id
    """)


def downgrade() -> None:
    op.drop_table('org_counters')
