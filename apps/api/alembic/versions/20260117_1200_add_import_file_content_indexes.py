"""Add import file content and org-scoped indexes.

Revision ID: 20260117_1200
Revises: 20260117_1045
Create Date: 2026-01-17 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260117_1200"
down_revision = "20260117_1045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "surrogate_imports",
        sa.Column("file_content", sa.LargeBinary(), nullable=True),
    )
    op.create_index(
        "idx_surrogate_history_org_changed",
        "surrogate_status_history",
        ["organization_id", "changed_at"],
    )
    op.create_index(
        "idx_surrogate_history_org_stage_changed",
        "surrogate_status_history",
        ["organization_id", "to_stage_id", "changed_at"],
    )
    op.create_index(
        "idx_surrogate_activity_org_time",
        "surrogate_activity_log",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_surrogate_activity_org_time",
        table_name="surrogate_activity_log",
    )
    op.drop_index(
        "idx_surrogate_history_org_stage_changed",
        table_name="surrogate_status_history",
    )
    op.drop_index(
        "idx_surrogate_history_org_changed",
        table_name="surrogate_status_history",
    )
    op.drop_column("surrogate_imports", "file_content")
