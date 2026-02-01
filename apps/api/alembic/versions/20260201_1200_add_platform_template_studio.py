"""Add platform template studio tables and workflow template publish controls.

Revision ID: 20260201_1200
Revises: 20260131_2355
Create Date: 2026-02-01 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260201_1200"
down_revision: Union[str, Sequence[str], None] = "20260131_2355"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_email_templates",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("from_email", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("published_name", sa.String(length=120), nullable=True),
        sa.Column("published_subject", sa.String(length=200), nullable=True),
        sa.Column("published_body", sa.Text(), nullable=True),
        sa.Column("published_from_email", sa.String(length=200), nullable=True),
        sa.Column("published_category", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("published_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_published_globally",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    )
    op.create_index(
        "idx_platform_email_templates_status",
        "platform_email_templates",
        ["status"],
    )
    op.create_table(
        "platform_email_template_targets",
        sa.Column(
            "template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("platform_email_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_platform_email_template_targets_org",
        "platform_email_template_targets",
        ["organization_id"],
    )

    op.create_table(
        "platform_form_templates",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("settings_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("published_name", sa.String(length=150), nullable=True),
        sa.Column("published_description", sa.Text(), nullable=True),
        sa.Column("published_schema_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("published_settings_json", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("published_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_published_globally",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    )
    op.create_index(
        "idx_platform_form_templates_status",
        "platform_form_templates",
        ["status"],
    )
    op.create_table(
        "platform_form_template_targets",
        sa.Column(
            "template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("platform_form_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_platform_form_template_targets_org",
        "platform_form_template_targets",
        ["organization_id"],
    )

    op.add_column(
        "workflow_templates",
        sa.Column("draft_config", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "workflow_templates",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'published'"),
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_templates",
        sa.Column(
            "published_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_templates",
        sa.Column(
            "is_published_globally",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_templates",
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_table(
        "workflow_template_targets",
        sa.Column(
            "template_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_workflow_template_targets_org",
        "workflow_template_targets",
        ["organization_id"],
    )

    op.execute("UPDATE workflow_templates SET is_published_globally = TRUE WHERE is_global = TRUE")
    op.execute("UPDATE workflow_templates SET published_at = updated_at WHERE published_at IS NULL")


def downgrade() -> None:
    op.drop_index("idx_workflow_template_targets_org", table_name="workflow_template_targets")
    op.drop_table("workflow_template_targets")
    op.drop_column("workflow_templates", "published_at")
    op.drop_column("workflow_templates", "is_published_globally")
    op.drop_column("workflow_templates", "published_version")
    op.drop_column("workflow_templates", "status")
    op.drop_column("workflow_templates", "draft_config")

    op.drop_index(
        "idx_platform_form_template_targets_org", table_name="platform_form_template_targets"
    )
    op.drop_table("platform_form_template_targets")
    op.drop_index("idx_platform_form_templates_status", table_name="platform_form_templates")
    op.drop_table("platform_form_templates")

    op.drop_index(
        "idx_platform_email_template_targets_org", table_name="platform_email_template_targets"
    )
    op.drop_table("platform_email_template_targets")
    op.drop_index("idx_platform_email_templates_status", table_name="platform_email_templates")
    op.drop_table("platform_email_templates")
