"""Add owner model to intended_parents table.

Revision ID: 0030_ip_owner_model
Revises: 0029_task_owner_model
Create Date: 2024-12-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0030_ip_owner_model"
down_revision: Union[str, None] = "0029_task_owner_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add owner_type and owner_id columns to intended_parents table.

    Migrate existing assigned_to_user_id data to owner fields.
    """
    # Add new columns
    op.add_column("intended_parents", sa.Column("owner_type", sa.String(10), nullable=True))
    op.add_column("intended_parents", sa.Column("owner_id", sa.UUID(), nullable=True))

    # Migrate existing data
    op.execute("""
        UPDATE intended_parents 
        SET owner_id = assigned_to_user_id, 
            owner_type = 'user'
        WHERE assigned_to_user_id IS NOT NULL
    """)

    # Create new index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ip_org_owner ON intended_parents (organization_id, owner_type, owner_id)"
    )

    # Drop the foreign key constraint and old column
    op.drop_constraint(
        "intended_parents_assigned_to_user_id_fkey",
        "intended_parents",
        type_="foreignkey",
    )
    op.drop_column("intended_parents", "assigned_to_user_id")


def downgrade() -> None:
    """Re-add assigned_to_user_id column."""
    # Re-add the column
    op.add_column("intended_parents", sa.Column("assigned_to_user_id", sa.UUID(), nullable=True))

    # Re-add foreign key
    op.create_foreign_key(
        "intended_parents_assigned_to_user_id_fkey",
        "intended_parents",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Migrate owner_id back to assigned_to_user_id
    op.execute("""
        UPDATE intended_parents 
        SET assigned_to_user_id = owner_id
        WHERE owner_type = 'user' 
          AND owner_id IS NOT NULL
    """)

    # Drop new index and columns
    op.execute("DROP INDEX IF EXISTS idx_ip_org_owner")
    op.drop_column("intended_parents", "owner_id")
    op.drop_column("intended_parents", "owner_type")
