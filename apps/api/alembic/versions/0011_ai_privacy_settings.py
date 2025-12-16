"""Add privacy settings to ai_settings

Revision ID: 0011_ai_privacy_settings
Revises: 0010_ai_assistant
Create Date: 2025-12-16

Adds:
- consent_accepted_at: When manager accepted AI data processing consent
- consent_accepted_by: Who accepted the consent
- anonymize_pii: Whether to strip PII before sending to AI provider
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '0011_ai_privacy_settings'
down_revision = '0010_ai_assistant'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add consent tracking
    op.add_column('ai_settings', sa.Column(
        'consent_accepted_at', 
        sa.DateTime(timezone=True), 
        nullable=True
    ))
    op.add_column('ai_settings', sa.Column(
        'consent_accepted_by', 
        UUID(), 
        nullable=True
    ))
    # Add anonymization toggle (defaults to True for safety)
    op.add_column('ai_settings', sa.Column(
        'anonymize_pii', 
        sa.Boolean(), 
        server_default='true',
        nullable=False
    ))


def downgrade() -> None:
    op.drop_column('ai_settings', 'anonymize_pii')
    op.drop_column('ai_settings', 'consent_accepted_by')
    op.drop_column('ai_settings', 'consent_accepted_at')
