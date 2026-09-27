"""Upgrade Google AI settings to Gemini 3.8 Flash.

Revision ID: 20260907_1200
Revises: 20260905_1600_record_integrations
"""

import sqlalchemy as sa

from alembic import op

revision = "20260907_1200"
down_revision = "20260905_1600_record_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "ai_settings",
        "model",
        server_default=sa.text("'gemini-3.8-flash'"),
        existing_type=sa.String(length=50),
        existing_nullable=True,
    )
    op.execute(
        """
        UPDATE ai_settings
        SET model = 'gemini-3.8-flash'
        WHERE provider IN ('gemini', 'vertex_wif', 'vertex_api_key')
        """
    )


def downgrade() -> None:
    op.alter_column(
        "ai_settings",
        "model",
        server_default=sa.text("'gemini-3.7-flash'"),
        existing_type=sa.String(length=50),
        existing_nullable=True,
    )
    op.execute(
        """
        UPDATE ai_settings
        SET model = 'gemini-3.7-flash'
        WHERE provider IN ('gemini', 'vertex_wif', 'vertex_api_key')
          AND model = 'gemini-3.8-flash'
        """
    )
