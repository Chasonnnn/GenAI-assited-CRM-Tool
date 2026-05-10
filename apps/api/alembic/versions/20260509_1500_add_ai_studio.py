"""add ai studio settings and drafts

Revision ID: 20260509_1500
Revises: 20260509_0915
Create Date: 2026-05-09 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260509_1500"
down_revision: str | Sequence[str] | None = "20260509_0915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("ai_studio_settings"):
        op.create_table(
            "ai_studio_settings",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True),
            sa.Column("agents_md", sa.Text(), server_default=sa.text("''"), nullable=False),
            sa.Column("skills_md", sa.Text(), server_default=sa.text("''"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id"),
        )

    if not _has_table("ai_studio_drafts"):
        op.create_table(
            "ai_studio_drafts",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=20), server_default=sa.text("'preview'"), nullable=False),
            sa.Column("platform", sa.String(length=30), nullable=False),
            sa.Column("format", sa.String(length=30), nullable=False),
            sa.Column("tone", sa.String(length=30), nullable=False),
            sa.Column("audience", sa.String(length=200), server_default=sa.text("''"), nullable=False),
            sa.Column("brief", sa.Text(), nullable=False),
            sa.Column("caption", sa.Text(), nullable=False),
            sa.Column(
                "hashtags",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
            sa.Column("image_prompt", sa.Text(), nullable=False),
            sa.Column("image_storage_key", sa.String(length=512), nullable=True),
            sa.Column("image_mime_type", sa.String(length=100), nullable=True),
            sa.Column("image_size_bytes", sa.Integer(), nullable=True),
            sa.Column("image_revised_prompt", sa.Text(), nullable=True),
            sa.Column("reasoning_model", sa.String(length=50), server_default=sa.text("'gpt-5.5'"), nullable=False),
            sa.Column("image_model", sa.String(length=50), server_default=sa.text("'gpt-image-2'"), nullable=False),
            sa.Column(
                "generation_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_ai_studio_drafts_org_created",
            "ai_studio_drafts",
            ["organization_id", "created_at"],
        )
        op.create_index(
            "ix_ai_studio_drafts_org_status_created",
            "ai_studio_drafts",
            ["organization_id", "status", "created_at"],
        )


def downgrade() -> None:
    if _has_table("ai_studio_drafts"):
        op.drop_index("ix_ai_studio_drafts_org_status_created", table_name="ai_studio_drafts")
        op.drop_index("ix_ai_studio_drafts_org_created", table_name="ai_studio_drafts")
        op.drop_table("ai_studio_drafts")
    if _has_table("ai_studio_settings"):
        op.drop_table("ai_studio_settings")
