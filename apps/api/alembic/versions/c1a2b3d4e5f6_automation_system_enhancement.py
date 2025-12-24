"""Automation system enhancement

Add fields for:
- Email templates: is_system_template, system_key, category
- Workflows: recurrence settings, system workflow fields, first-run review
- New tables: campaigns, campaign_runs, campaign_recipients, email_suppressions

Revision ID: c1a2b3d4e5f6
Revises: 866add7e8baa
Create Date: 2024-12-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = '32f6855c0777'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Clean up any legacy partial indexes that may exist from previous migrations
    # ==========================================================================
    op.execute("DROP INDEX IF EXISTS uq_email_template_system_key")
    op.execute("DROP INDEX IF EXISTS uq_workflow_system_key")
    
    # ==========================================================================
    # Email Templates: Add system template fields
    # ==========================================================================
    op.add_column('email_templates', sa.Column(
        'is_system_template',
        sa.Boolean(),
        server_default=sa.text('FALSE'),
        nullable=False
    ))
    op.add_column('email_templates', sa.Column(
        'system_key',
        sa.String(100),
        nullable=True
    ))
    op.add_column('email_templates', sa.Column(
        'category',
        sa.String(50),
        nullable=True
    ))
    

    
    # ==========================================================================
    # Automation Workflows: Add recurrence and system fields
    # ==========================================================================
    op.add_column('automation_workflows', sa.Column(
        'recurrence_mode',
        sa.String(20),
        server_default=sa.text("'one_time'"),
        nullable=False
    ))
    op.add_column('automation_workflows', sa.Column(
        'recurrence_interval_hours',
        sa.Integer(),
        nullable=True
    ))
    op.add_column('automation_workflows', sa.Column(
        'recurrence_stop_on_status',
        sa.String(50),
        nullable=True
    ))
    op.add_column('automation_workflows', sa.Column(
        'is_system_workflow',
        sa.Boolean(),
        server_default=sa.text('FALSE'),
        nullable=False
    ))
    op.add_column('automation_workflows', sa.Column(
        'system_key',
        sa.String(100),
        nullable=True
    ))
    op.add_column('automation_workflows', sa.Column(
        'requires_review',
        sa.Boolean(),
        server_default=sa.text('FALSE'),
        nullable=False
    ))
    op.add_column('automation_workflows', sa.Column(
        'reviewed_at',
        sa.TIMESTAMP(timezone=True),
        nullable=True
    ))
    op.add_column('automation_workflows', sa.Column(
        'reviewed_by_user_id',
        sa.UUID(),
        nullable=True
    ))
    
    # FK for reviewed_by_user_id
    op.create_foreign_key(
        'fk_workflow_reviewed_by',
        'automation_workflows',
        'users',
        ['reviewed_by_user_id'],
        ['id'],
        ondelete='SET NULL'
    )
    

    
    # ==========================================================================
    # Campaigns Table
    # ==========================================================================
    op.create_table(
        'campaigns',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('email_template_id', sa.UUID(), sa.ForeignKey('email_templates.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('recipient_type', sa.String(30), nullable=False),
        sa.Column('filter_criteria', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    op.create_unique_constraint('uq_campaign_name', 'campaigns', ['organization_id', 'name'])
    op.create_index('idx_campaigns_org_status', 'campaigns', ['organization_id', 'status'])
    op.create_index('idx_campaigns_org_created', 'campaigns', ['organization_id', 'created_at'])
    
    # ==========================================================================
    # Campaign Runs Table
    # ==========================================================================
    op.create_table(
        'campaign_runs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('campaign_id', sa.UUID(), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), server_default=sa.text("'running'"), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('sent_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('failed_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('skipped_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    
    op.create_index('idx_campaign_runs_campaign', 'campaign_runs', ['campaign_id', 'started_at'])
    op.create_index('idx_campaign_runs_org', 'campaign_runs', ['organization_id', 'started_at'])
    
    # ==========================================================================
    # Campaign Recipients Table
    # ==========================================================================
    op.create_table(
        'campaign_recipients',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('run_id', sa.UUID(), sa.ForeignKey('campaign_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('recipient_email', postgresql.CITEXT(), nullable=False),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('skip_reason', sa.String(100), nullable=True),
        sa.Column('sent_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('external_message_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    op.create_index('idx_campaign_recipients_run', 'campaign_recipients', ['run_id'])
    op.create_index('idx_campaign_recipients_entity', 'campaign_recipients', ['entity_type', 'entity_id'])
    op.create_unique_constraint('uq_campaign_recipient', 'campaign_recipients', ['run_id', 'entity_type', 'entity_id'])
    
    # ==========================================================================
    # Email Suppressions Table
    # ==========================================================================
    op.create_table(
        'email_suppressions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('reason', sa.String(30), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=True),
        sa.Column('source_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    op.create_unique_constraint('uq_email_suppression', 'email_suppressions', ['organization_id', 'email'])
    op.create_index('idx_email_suppressions_org', 'email_suppressions', ['organization_id'])
    op.create_index('idx_email_suppressions_email', 'email_suppressions', ['email'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('campaign_recipients')
    op.drop_table('campaign_runs')
    op.drop_table('campaigns')
    op.drop_table('email_suppressions')
    
    # Drop workflow additions
    op.drop_constraint('fk_workflow_reviewed_by', 'automation_workflows', type_='foreignkey')

    op.drop_column('automation_workflows', 'reviewed_by_user_id')
    op.drop_column('automation_workflows', 'reviewed_at')
    op.drop_column('automation_workflows', 'requires_review')
    op.drop_column('automation_workflows', 'system_key')
    op.drop_column('automation_workflows', 'is_system_workflow')
    op.drop_column('automation_workflows', 'recurrence_stop_on_status')
    op.drop_column('automation_workflows', 'recurrence_interval_hours')
    op.drop_column('automation_workflows', 'recurrence_mode')
    
    # Drop email template additions

    op.drop_column('email_templates', 'category')
    op.drop_column('email_templates', 'system_key')
    op.drop_column('email_templates', 'is_system_template')
