"""Add Meta integration tables and fields.

Revision ID: 0006_meta_integration
Revises: 07e0a3628b1b
Create Date: 2025-12-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0006_meta_integration'
down_revision: Union[str, None] = '07e0a3628b1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # meta_page_mappings table
    # ==========================================================================
    op.create_table(
        'meta_page_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_id', sa.String(100), nullable=False),
        sa.Column('page_name', sa.String(255), nullable=True),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('page_id', name='uq_meta_page_id'),
    )
    op.create_index('idx_meta_page_org', 'meta_page_mappings', ['organization_id'])

    # ==========================================================================
    # Add idempotency_key to jobs table
    # ==========================================================================
    op.add_column('jobs', sa.Column('idempotency_key', sa.String(255), nullable=True))
    op.create_index(
        'uq_job_idempotency',
        'jobs',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL')
    )

    # ==========================================================================
    # Add status and fetch_error to meta_leads table
    # ==========================================================================
    op.add_column('meta_leads', sa.Column('status', sa.String(20), server_default=sa.text("'received'"), nullable=False))
    op.add_column('meta_leads', sa.Column('fetch_error', sa.Text(), nullable=True))
    op.create_index('idx_meta_leads_status', 'meta_leads', ['organization_id', 'status'])

    # ==========================================================================
    # Add campaign tracking to cases (for filtering by ad/form)
    # ==========================================================================
    op.add_column('cases', sa.Column('meta_ad_id', sa.String(100), nullable=True))
    op.add_column('cases', sa.Column('meta_form_id', sa.String(100), nullable=True))
    op.create_index('idx_cases_meta_ad', 'cases', ['organization_id', 'meta_ad_id'], postgresql_where=sa.text('meta_ad_id IS NOT NULL'))
    op.create_index('idx_cases_meta_form', 'cases', ['organization_id', 'meta_form_id'], postgresql_where=sa.text('meta_form_id IS NOT NULL'))


def downgrade() -> None:
    # cases campaign columns
    op.drop_index('idx_cases_meta_form', table_name='cases')
    op.drop_index('idx_cases_meta_ad', table_name='cases')
    op.drop_column('cases', 'meta_form_id')
    op.drop_column('cases', 'meta_ad_id')

    # meta_leads columns
    op.drop_index('idx_meta_leads_status', table_name='meta_leads')
    op.drop_column('meta_leads', 'fetch_error')
    op.drop_column('meta_leads', 'status')

    # jobs idempotency_key
    op.drop_index('uq_job_idempotency', table_name='jobs')
    op.drop_column('jobs', 'idempotency_key')

    # meta_page_mappings table
    op.drop_index('idx_meta_page_org', table_name='meta_page_mappings')
    op.drop_table('meta_page_mappings')
