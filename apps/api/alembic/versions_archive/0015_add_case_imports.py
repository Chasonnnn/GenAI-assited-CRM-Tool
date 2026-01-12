"""Add case_imports table

Revision ID: 0015_add_case_imports
Revises: 0014_add_audit_logs
Create Date: 2025-12-17

Tracks CSV import jobs for bulk case creation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0015_add_case_imports"
down_revision: Union[str, Sequence[str], None] = "0014_add_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create case_imports table."""
    op.create_table(
        "case_imports",
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
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "idx_case_imports_org_created",
        "case_imports",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    """Drop case_imports table."""
    op.drop_index("idx_case_imports_org_created", "case_imports")
    op.drop_table("case_imports")
