"""Normalize AI model defaults for Gemini providers.

Revision ID: 20260131_2345
Revises: 20260131_1800
Create Date: 2026-01-31 23:45:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260131_2345"
down_revision: Union[str, Sequence[str], None] = "20260131_1800"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ai_settings
        SET provider = 'gemini',
            model = 'gemini-3-flash-preview',
            api_key_encrypted = NULL
        WHERE provider = 'openai'
        """
    )
    op.execute(
        """
        UPDATE ai_settings
        SET model = 'gemini-3-flash-preview'
        WHERE provider IN ('gemini', 'vertex_wif', 'vertex_api_key')
          AND (model IS NULL OR model NOT IN ('gemini-3-flash-preview', 'gemini-3-pro-preview'))
        """
    )


def downgrade() -> None:
    # No-op: data normalization is safe to retain across downgrades.
    pass
