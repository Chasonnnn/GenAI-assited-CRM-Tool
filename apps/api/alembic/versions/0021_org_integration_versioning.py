"""Add current_version to organizations and user_integrations

Revision ID: 0021_org_integration_versioning
Revises: 0020_rehash_audit_v2
Create Date: 2025-12-17

Enable version control for org settings and user integrations.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0021_org_integration_versioning"
down_revision: Union[str, Sequence[str], None] = "0020_rehash_audit_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add current_version columns."""
    # Organizations
    op.add_column(
        "organizations",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )

    # User integrations
    op.add_column(
        "user_integrations",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    """Remove current_version columns."""
    op.drop_column("user_integrations", "current_version")
    op.drop_column("organizations", "current_version")
