"""add_email_template_from_email

Revision ID: 20260125_1915
Revises: 20260123_2355
Create Date: 2026-01-24 19:46:01.056297

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260125_1915"
down_revision: str | Sequence[str] | None = "20260123_2355"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "email_templates",
        sa.Column("from_email", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("email_templates", "from_email")
