"""Stable library-template keys and workflow edit revisions.

Revision ID: 20260919_0200_template_cli_identity
Revises: 20260919_0100_ops_cli_tokens
"""

import sqlalchemy as sa

from alembic import op

revision = "20260919_0200_template_cli_identity"
down_revision = "20260919_0100_ops_cli_tokens"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    for table in ("platform_email_templates", "platform_form_templates", "workflow_templates"):
        op.add_column(table, sa.Column("external_key", sa.String(100), nullable=True))
    for table in ("platform_email_templates", "platform_form_templates"):
        op.create_unique_constraint(f"{table}_external_key_key", table, ["external_key"])
    op.add_column(
        "workflow_templates",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index(
        "uq_global_workflow_external_key",
        "workflow_templates",
        ["external_key"],
        unique=True,
        postgresql_where=sa.text("is_global AND organization_id IS NULL"),
    )


def downgrade():
    op.drop_index("uq_global_workflow_external_key", table_name="workflow_templates")
    op.drop_column("workflow_templates", "current_version")
    for table in ("platform_email_templates", "platform_form_templates"):
        op.drop_constraint(f"{table}_external_key_key", table, type_="unique")
    for table in ("platform_email_templates", "platform_form_templates", "workflow_templates"):
        op.drop_column(table, "external_key")
