"""Add permission system tables.

Revision ID: 0040_permission_system
Revises: 0039_invite_enhancements
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0040_permission_system"
down_revision = "0039_invite_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Role default permissions table
    op.create_table(
        "role_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.Column("is_granted", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "role",
            "permission",
            name="uq_role_permissions_org_role_perm",
        ),
    )
    op.create_index(
        "idx_role_permissions_org_role", "role_permissions", ["organization_id", "role"]
    )

    # 2. User permission overrides table
    op.create_table(
        "user_permission_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission", sa.String(100), nullable=False),
        sa.Column("override_type", sa.String(10), nullable=False),  # 'grant' or 'revoke'
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "permission",
            name="uq_user_overrides_org_user_perm",
        ),
        sa.CheckConstraint("override_type IN ('grant', 'revoke')", name="ck_override_type_valid"),
    )
    op.create_index(
        "idx_user_overrides_org_user",
        "user_permission_overrides",
        ["organization_id", "user_id"],
    )

    # 3. Add last_login_at to users
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_index("idx_user_overrides_org_user", table_name="user_permission_overrides")
    op.drop_table("user_permission_overrides")
    op.drop_index("idx_role_permissions_org_role", table_name="role_permissions")
    op.drop_table("role_permissions")
