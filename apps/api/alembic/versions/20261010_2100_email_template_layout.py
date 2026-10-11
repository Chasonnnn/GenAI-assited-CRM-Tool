"""Store the email layout (plain, card, letterhead) on templates and drafts.

NULL means the default for the template scope: org templates send in a card,
personal templates in plain. Existing rows keep NULL, so no row is rewritten.

Revision ID: 20261010_2100_email_template_layout
Revises: 20261007_2000_messaging_test_phones
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261010_2100_email_template_layout"
down_revision = "20261007_2000_messaging_test_phones"
branch_labels = None
depends_on = None

LAYOUT_COLUMNS = (
    ("email_templates", "ck_email_templates_layout_object"),
    ("email_template_drafts", "ck_email_template_drafts_layout_object"),
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table, constraint in LAYOUT_COLUMNS:
        op.add_column(table, sa.Column("layout", postgresql.JSONB(), nullable=True))
        op.create_check_constraint(
            constraint,
            table,
            "layout IS NULL OR jsonb_typeof(layout) = 'object'",
        )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table, constraint in reversed(LAYOUT_COLUMNS):
        op.drop_constraint(constraint, table, type_="check")
        op.drop_column(table, "layout")
