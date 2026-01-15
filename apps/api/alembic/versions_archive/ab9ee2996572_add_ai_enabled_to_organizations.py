"""add_ai_enabled_to_organizations

Revision ID: ab9ee2996572
Revises: 0011_ai_privacy_settings
Create Date: 2025-12-16 21:37:38.461035

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab9ee2996572"
down_revision: Union[str, Sequence[str], None] = "0011_ai_privacy_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_enabled column to organizations table."""
    op.add_column(
        "organizations",
        sa.Column("ai_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    """Remove ai_enabled column from organizations table."""
    op.drop_column("organizations", "ai_enabled")
