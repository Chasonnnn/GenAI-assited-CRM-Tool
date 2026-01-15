"""Add pipelines table

Revision ID: 0016_add_pipelines
Revises: 0015_add_case_imports
Create Date: 2025-12-17

Org-configurable pipelines for case status display customization (v1: display-only).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0016_add_pipelines"
down_revision: Union[str, Sequence[str], None] = "0015_add_case_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pipelines table."""
    op.create_table(
        "pipelines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), server_default="Default", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("stages", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("idx_pipelines_org", "pipelines", ["organization_id"])


def downgrade() -> None:
    """Drop pipelines table."""
    op.drop_index("idx_pipelines_org", "pipelines")
    op.drop_table("pipelines")
