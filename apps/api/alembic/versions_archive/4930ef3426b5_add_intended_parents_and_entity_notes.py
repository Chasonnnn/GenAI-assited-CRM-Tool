"""add_intended_parents_and_entity_notes

Revision ID: 4930ef3426b5
Revises: 07883c4d40ee
Create Date: 2025-12-14 16:03:36.509774

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4930ef3426b5"
down_revision: Union[str, Sequence[str], None] = "07883c4d40ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add intended_parents, intended_parent_status_history, and entity_notes tables."""
    # Create entity_notes table (polymorphic notes for any entity)
    op.create_table(
        "entity_notes",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_entity_notes_lookup",
        "entity_notes",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_entity_notes_org",
        "entity_notes",
        ["organization_id", "created_at"],
        unique=False,
    )

    # Create intended_parents table
    op.create_table(
        "intended_parents",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("budget", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes_internal", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'new'"),
            nullable=False,
        ),
        sa.Column("assigned_to_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "is_archived", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_activity",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ip_org_created",
        "intended_parents",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_ip_org_status",
        "intended_parents",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_ip_email_active",
        "intended_parents",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_archived = false"),
    )

    # Create intended_parent_status_history table
    op.create_table(
        "intended_parent_status_history",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("intended_parent_id", sa.UUID(), nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["intended_parent_id"], ["intended_parents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ip_history_ip",
        "intended_parent_status_history",
        ["intended_parent_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove intended_parents, intended_parent_status_history, and entity_notes tables."""
    op.drop_index("idx_ip_history_ip", table_name="intended_parent_status_history")
    op.drop_table("intended_parent_status_history")
    op.drop_index(
        "uq_ip_email_active",
        table_name="intended_parents",
        postgresql_where=sa.text("is_archived = false"),
    )
    op.drop_index("idx_ip_org_status", table_name="intended_parents")
    op.drop_index("idx_ip_org_created", table_name="intended_parents")
    op.drop_table("intended_parents")
    op.drop_index("idx_entity_notes_org", table_name="entity_notes")
    op.drop_index("idx_entity_notes_lookup", table_name="entity_notes")
    op.drop_table("entity_notes")
