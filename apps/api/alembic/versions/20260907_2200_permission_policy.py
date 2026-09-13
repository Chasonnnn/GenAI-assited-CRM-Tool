"""Add explicit organization permission-policy activation state.

Revision ID: 20260907_2200_perm_policy
Revises: 20260907_1200
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260907_2200_perm_policy"
down_revision = "20260907_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_permission_policies",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "configuration_revision", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version IN (1, 2)", name="ck_permission_policy_version"),
        sa.CheckConstraint("configuration_revision > 0", name="ck_permission_policy_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("LOCK TABLE organizations, organization_permission_policies IN EXCLUSIVE MODE")
    )
    if conn.execute(
        sa.text("SELECT 1 FROM organization_permission_policies WHERE version=2 LIMIT 1")
    ).scalar():
        raise RuntimeError(
            "Active permission policies require a reviewed rollback before schema downgrade"
        )
    op.drop_table("organization_permission_policies")
