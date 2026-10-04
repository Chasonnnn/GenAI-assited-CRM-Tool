"""Store the React Email editor document next to email template bodies.

``body`` stays the HTML that every send, snapshot, and campaign reads. The new
``body_design`` columns hold the editor document (ADR 0006). Existing rows keep
NULL and open in the editor as one Custom HTML node, so no body is rewritten.

Revision ID: 20261004_1200_email_template_body_design
Revises: 20261004_1000_drop_flat_medical_columns
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261004_1200_email_template_body_design"
down_revision = "20261004_1000_drop_flat_medical_columns"
branch_labels = None
depends_on = None

DESIGN_COLUMNS = (
    ("email_templates", "body_design", "ck_email_templates_body_design_object"),
    ("email_template_drafts", "body_design", "ck_email_template_drafts_body_design_object"),
    (
        "platform_email_templates",
        "body_design",
        "ck_platform_email_templates_body_design_object",
    ),
    (
        "platform_email_templates",
        "published_body_design",
        "ck_platform_email_templates_published_body_design_object",
    ),
    (
        "platform_system_email_templates",
        "body_design",
        "ck_platform_system_email_templates_body_design_object",
    ),
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table, column, constraint in DESIGN_COLUMNS:
        op.add_column(table, sa.Column(column, postgresql.JSONB(), nullable=True))
        op.create_check_constraint(
            constraint,
            table,
            f"{column} IS NULL OR jsonb_typeof({column}) = 'object'",
        )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table, column, constraint in reversed(DESIGN_COLUMNS):
        op.drop_constraint(constraint, table, type_="check")
        op.drop_column(table, column)
