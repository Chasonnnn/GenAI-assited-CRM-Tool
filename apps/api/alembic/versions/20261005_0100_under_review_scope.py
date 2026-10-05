"""Add an explicit surrogate visibility boundary at Under Review.

Revision ID: 20261005_0100_under_review_scope
Revises: 20261004_1300_organization_logo
"""

import sqlalchemy as sa

from alembic import op

revision = "20261005_0100_under_review_scope"
down_revision = "20261004_1300_organization_logo"
branch_labels = None
depends_on = None

_TABLES = (
    ("role_record_scopes", "ck_role_scope_phase"),
    ("user_record_scope_additions", "ck_user_scope_phase"),
)
_APPROVAL_PHASES = "phase IN ('all', 'pre_approval', 'post_approval')"


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for table, constraint in _TABLES:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            _APPROVAL_PHASES + " OR (phase = 'under_review_onward' AND module = 'surrogates')",
        )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("LOCK TABLE role_record_scopes, user_record_scope_additions IN EXCLUSIVE MODE")
    connection = op.get_bind()
    for table, _ in _TABLES:
        if connection.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE phase = 'under_review_onward' LIMIT 1")
        ).scalar():
            raise RuntimeError("Under Review scopes require a reviewed rollback before downgrade")
    for table, constraint in _TABLES:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(constraint, table, _APPROVAL_PHASES)
