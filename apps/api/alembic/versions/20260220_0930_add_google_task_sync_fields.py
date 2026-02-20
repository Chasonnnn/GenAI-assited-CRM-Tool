"""Add Google Tasks sync linkage fields to tasks.

Revision ID: 20260220_0930
Revises: 20260219_1900
Create Date: 2026-02-20 09:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260220_0930"
down_revision: Union[str, Sequence[str], None] = "20260219_1900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("google_task_id", sa.String(length=255), nullable=True))
    op.add_column("tasks", sa.Column("google_task_list_id", sa.String(length=255), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("google_task_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_tasks_google_task_lookup",
        "tasks",
        [
            "organization_id",
            "owner_type",
            "owner_id",
            "google_task_list_id",
            "google_task_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_google_task_lookup", table_name="tasks")
    op.drop_column("tasks", "google_task_updated_at")
    op.drop_column("tasks", "google_task_list_id")
    op.drop_column("tasks", "google_task_id")
