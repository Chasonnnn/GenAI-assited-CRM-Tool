"""Update AI settings defaults to Gemini.

Revision ID: 20260130_2310
Revises: 20260130_2130
Create Date: 2026-01-30 23:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260130_2310"
down_revision: str | Sequence[str] | None = "20260130_2130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ai_settings",
        "provider",
        server_default=sa.text("'gemini'"),
        existing_type=sa.String(length=20),
        existing_nullable=False,
    )
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
        SET provider = 'gemini',
            model = 'gemini-3-flash-preview',
            api_key_encrypted = NULL
        WHERE provider = 'openai'
        """
    )


def downgrade() -> None:
    op.alter_column(
        "ai_settings",
        "provider",
        server_default=sa.text("'openai'"),
        existing_type=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_settings",
        "model",
        server_default=sa.text("'gpt-4o-mini'"),
        existing_type=sa.String(length=50),
        existing_nullable=True,
    )
    op.execute(
        """
        UPDATE ai_settings
        SET provider = 'openai',
            model = 'gpt-4o-mini'
        WHERE provider = 'gemini'
          AND model = 'gemini-3-flash-preview'
          AND api_key_encrypted IS NULL
        """
    )
