"""Add org-level hidden list for platform form templates.

Revision ID: 20260213_0900
Revises: 20260209_1200
Create Date: 2026-02-13 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260213_0900"
down_revision: Union[str, Sequence[str], None] = "20260209_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_form_template_hidden_orgs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hidden_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["platform_form_templates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hidden_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "organization_id",
            name="uq_platform_form_template_hidden_org",
        ),
    )
    op.create_index(
        "idx_platform_form_template_hidden_org_org",
        "platform_form_template_hidden_orgs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "idx_platform_form_template_hidden_org_template",
        "platform_form_template_hidden_orgs",
        ["template_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_platform_form_template_hidden_org_template",
        table_name="platform_form_template_hidden_orgs",
    )
    op.drop_index(
        "idx_platform_form_template_hidden_org_org",
        table_name="platform_form_template_hidden_orgs",
    )
    op.drop_table("platform_form_template_hidden_orgs")
