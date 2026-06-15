"""add intake pool access grants

Revision ID: 20260615_0900
Revises: 20260529_2355
Create Date: 2026-06-15 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260615_0900"
down_revision: str | Sequence[str] | None = "20260529_2355"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intake_pool_access_grants",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_user_id", sa.UUID(), nullable=False),
        sa.Column("grantee_user_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "source_user_id <> grantee_user_id",
            name="ck_intake_pool_grants_no_self",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["grantee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_user_id",
            "grantee_user_id",
            name="uq_intake_pool_grants_org_source_grantee",
        ),
    )
    op.create_index(
        "idx_intake_pool_grants_org_grantee",
        "intake_pool_access_grants",
        ["organization_id", "grantee_user_id"],
        unique=False,
    )
    op.create_index(
        "idx_intake_pool_grants_org_source",
        "intake_pool_access_grants",
        ["organization_id", "source_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_intake_pool_grants_org_source",
        table_name="intake_pool_access_grants",
    )
    op.drop_index(
        "idx_intake_pool_grants_org_grantee",
        table_name="intake_pool_access_grants",
    )
    op.drop_table("intake_pool_access_grants")
