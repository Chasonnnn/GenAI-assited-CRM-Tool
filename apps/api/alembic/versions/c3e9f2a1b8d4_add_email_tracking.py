"""Add email tracking fields and CampaignTrackingEvent table

Revision ID: c3e9f2a1b8d4
Revises: b2a7e1c9f4d0
Create Date: 2024-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3e9f2a1b8d4'
down_revision = 'b2a7e1c9f4d0'
branch_labels = None
depends_on = None


def upgrade():
    # Add tracking fields to campaign_runs
    op.add_column('campaign_runs', sa.Column('opened_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('campaign_runs', sa.Column('clicked_count', sa.Integer(), server_default='0', nullable=False))
    
    # Add tracking fields to campaign_recipients
    op.add_column('campaign_recipients', sa.Column('tracking_token', sa.String(64), nullable=True))
    op.add_column('campaign_recipients', sa.Column('opened_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('campaign_recipients', sa.Column('open_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('campaign_recipients', sa.Column('clicked_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('campaign_recipients', sa.Column('click_count', sa.Integer(), server_default='0', nullable=False))
    
    # Add unique index for tracking_token
    op.create_index('idx_campaign_recipients_tracking_token', 'campaign_recipients', ['tracking_token'], unique=True)
    
    # Create campaign_tracking_events table
    op.create_table(
        'campaign_tracking_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('recipient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(10), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['recipient_id'], ['campaign_recipients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tracking_events_recipient', 'campaign_tracking_events', ['recipient_id'])
    op.create_index('idx_tracking_events_type', 'campaign_tracking_events', ['event_type'])


def downgrade():
    # Drop campaign_tracking_events table
    op.drop_index('idx_tracking_events_type', table_name='campaign_tracking_events')
    op.drop_index('idx_tracking_events_recipient', table_name='campaign_tracking_events')
    op.drop_table('campaign_tracking_events')
    
    # Remove tracking fields from campaign_recipients
    op.drop_index('idx_campaign_recipients_tracking_token', table_name='campaign_recipients')
    op.drop_column('campaign_recipients', 'click_count')
    op.drop_column('campaign_recipients', 'clicked_at')
    op.drop_column('campaign_recipients', 'open_count')
    op.drop_column('campaign_recipients', 'opened_at')
    op.drop_column('campaign_recipients', 'tracking_token')
    
    # Remove tracking fields from campaign_runs
    op.drop_column('campaign_runs', 'clicked_count')
    op.drop_column('campaign_runs', 'opened_count')
