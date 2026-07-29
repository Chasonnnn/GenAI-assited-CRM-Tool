"""Add current_version to email_templates

Revision ID: 0018_email_templates_versioning
Revises: 0017_add_entity_versions
Create Date: 2025-12-17

Adds version control to email templates.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_email_templates_versioning"
down_revision: str | Sequence[str] | None = "0017_add_entity_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add current_version column to email_templates."""
    op.add_column(
        "email_templates",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Remove current_version from email_templates."""
    op.drop_column("email_templates", "current_version")
