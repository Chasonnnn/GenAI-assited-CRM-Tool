"""Add owner model to tasks table.

Revision ID: 0029_task_owner_model
Revises: 0028_remove_assigned_to_user_id
Create Date: 2024-12-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "0029_task_owner_model"
down_revision: Union[str, None] = "0028_remove_assigned_to_user_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add owner_type and owner_id to tasks table.

    This matches the Case model ownership pattern, allowing tasks
    to be assigned to either users or queues.
    """
    # Add new columns (nullable initially for migration)
    op.add_column("tasks", sa.Column("owner_type", sa.String(10), nullable=True))
    op.add_column("tasks", sa.Column("owner_id", UUID(as_uuid=True), nullable=True))

    # Migrate existing assigned_to_user_id data
    op.execute("""
        UPDATE tasks 
        SET owner_type = 'user', 
            owner_id = assigned_to_user_id
        WHERE assigned_to_user_id IS NOT NULL
    """)

    # For tasks without assignment, default to created_by_user_id
    op.execute("""
        UPDATE tasks 
        SET owner_type = 'user', 
            owner_id = created_by_user_id
        WHERE owner_id IS NULL
    """)

    # Make columns NOT NULL now that all rows have values
    op.alter_column("tasks", "owner_type", nullable=False)
    op.alter_column("tasks", "owner_id", nullable=False)

    # Create index for owner-based queries
    op.create_index(
        "idx_tasks_org_owner",
        "tasks",
        ["organization_id", "owner_type", "owner_id", "is_completed"],
    )

    # Drop old index and constraint
    op.drop_index("idx_tasks_org_assigned", table_name="tasks")
    op.drop_constraint("tasks_assigned_to_user_id_fkey", "tasks", type_="foreignkey")

    # Drop legacy column
    op.drop_column("tasks", "assigned_to_user_id")


def downgrade() -> None:
    """Re-add legacy assigned_to_user_id column."""
    # Re-add the column
    op.add_column(
        "tasks", sa.Column("assigned_to_user_id", UUID(as_uuid=True), nullable=True)
    )

    # Re-add foreign key
    op.create_foreign_key(
        "tasks_assigned_to_user_id_fkey",
        "tasks",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Re-create old index
    op.create_index(
        "idx_tasks_org_assigned",
        "tasks",
        ["organization_id", "assigned_to_user_id", "is_completed"],
    )

    # Migrate owner_id back to assigned_to_user_id where owner_type is 'user'
    op.execute("""
        UPDATE tasks 
        SET assigned_to_user_id = owner_id
        WHERE owner_type = 'user' 
          AND owner_id IS NOT NULL
    """)

    # Drop new columns
    op.drop_index("idx_tasks_org_owner", table_name="tasks")
    op.drop_column("tasks", "owner_id")
    op.drop_column("tasks", "owner_type")
