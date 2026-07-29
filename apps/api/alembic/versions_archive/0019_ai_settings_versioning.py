"""Add current_version to ai_settings

Revision ID: 0019_ai_settings_versioning
Revises: 0018_email_templates_versioning
Create Date: 2025-12-17

Adds version control to AI settings.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_ai_settings_versioning"
down_revision: str | Sequence[str] | None = "0018_email_templates_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add current_version column to ai_settings."""
    op.add_column(
        "ai_settings",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Remove current_version from ai_settings."""
    op.drop_column("ai_settings", "current_version")
