"""Add isolated email template drafts.

Revision ID: 20260723_0280
Revises: 20260723_0270
Create Date: 2026-07-23 23:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260723_0280"
down_revision = "20260723_0270"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_template_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_templates.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("from_email", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "base_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("last_tested_revision", sa.Integer(), nullable=True),
        sa.Column("last_tested_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "scope IN ('org', 'personal')",
            name="ck_email_template_drafts_scope",
        ),
        sa.CheckConstraint(
            "(scope = 'org' AND owner_user_id IS NULL) "
            "OR (scope = 'personal' AND owner_user_id IS NOT NULL)",
            name="ck_email_template_drafts_scope_owner",
        ),
        sa.UniqueConstraint(
            "template_id",
            name="uq_email_template_drafts_template",
        ),
    )
    op.create_index(
        "idx_email_template_drafts_org_updated",
        "email_template_drafts",
        ["organization_id", "updated_at"],
    )
    op.create_index(
        "idx_email_template_drafts_owner",
        "email_template_drafts",
        ["organization_id", "owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_email_template_drafts_owner",
        table_name="email_template_drafts",
    )
    op.drop_index(
        "idx_email_template_drafts_org_updated",
        table_name="email_template_drafts",
    )
    op.drop_table("email_template_drafts")
