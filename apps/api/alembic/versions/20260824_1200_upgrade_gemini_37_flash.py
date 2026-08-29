"""Upgrade Google AI settings to Gemini 3.7 Flash.

Revision ID: 20260824_1200
Revises: 20260824_1150
Create Date: 2026-08-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260824_1200"
down_revision: str | Sequence[str] | None = "20260824_1150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
        """
    )
    op.execute(
        """
        UPDATE ai_settings
        SET vertex_location = 'us'
        WHERE (provider = 'vertex_wif'
               AND (vertex_location IS NULL OR vertex_location NOT IN ('global', 'us', 'eu')))
           OR (provider = 'vertex_api_key'
               AND vertex_location IS NOT NULL
               AND vertex_location NOT IN ('global', 'us', 'eu'))
        """
    )


def downgrade() -> None:
    op.alter_column(
        "ai_settings",
        "model",
        server_default=sa.text("'gemini-3-flash-preview'"),
        existing_type=sa.String(length=50),
        existing_nullable=True,
    )
    op.execute(
        """
        UPDATE ai_settings
        SET model = 'gemini-3-flash-preview'
        WHERE provider IN ('gemini', 'vertex_wif', 'vertex_api_key')
          AND model = 'gemini-3.7-flash'
        """
    )
