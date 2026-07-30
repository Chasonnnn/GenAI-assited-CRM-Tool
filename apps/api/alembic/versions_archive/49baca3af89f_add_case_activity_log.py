"""add_case_activity_log

Revision ID: 49baca3af89f
Revises: 0b97aee1ec96
Create Date: 2025-12-15 09:52:53.431809

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49baca3af89f"
down_revision: str | Sequence[str] | None = "0b97aee1ec96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create case_activity_log table for comprehensive case history tracking."""
    op.create_table(
        "case_activity_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("activity_type", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_case_activity_case_time",
        "case_activity_log",
        ["case_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop case_activity_log table."""
    op.drop_index("idx_case_activity_case_time", table_name="case_activity_log")
    op.drop_table("case_activity_log")
