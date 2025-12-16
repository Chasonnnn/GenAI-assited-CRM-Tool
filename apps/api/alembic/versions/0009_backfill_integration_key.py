"""Backfill integration_key to 'default' where NULL

Revision ID: 0009_backfill_integration_key
Revises: 0008_integration_health
Create Date: 2025-12-16

Ensures consistent upsert behavior by replacing NULL integration_key
with 'default' in rollup tables.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '0009_backfill_integration_key'
down_revision = '0008_integration_health'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill integration_key to 'default' where NULL
    op.execute("""
        UPDATE integration_health
        SET integration_key = 'default'
        WHERE integration_key IS NULL
    """)
    
    op.execute("""
        UPDATE integration_error_rollup
        SET integration_key = 'default'
        WHERE integration_key IS NULL
    """)
    
    # Optionally make NOT NULL with default (commented out for now in case
    # you want to keep NULL as a valid sentinel in the future)
    # op.alter_column('integration_health', 'integration_key',
    #     nullable=False, server_default='default')
    # op.alter_column('integration_error_rollup', 'integration_key',
    #     nullable=False, server_default='default')


def downgrade() -> None:
    # Can't safely downgrade - 'default' was a valid value before backfill
    pass
