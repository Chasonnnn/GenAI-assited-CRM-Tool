"""Bound audit-chain tail and match-work lookups without rewriting audit records.

Revision ID: 20261012_0900_audit_work_indexes
Revises: 20261010_2100_email_template_layout
"""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0900_audit_work_indexes"
down_revision = "20261010_2100_email_template_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep both indexes atomic and bound the write-blocking migration window.
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '15s'")
    op.create_index(
        "idx_audit_chain_tail",
        "audit_logs",
        ["organization_id", sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("entry_hash IS NOT NULL"),
        postgresql_include=["entry_hash"],
    )
    op.create_index(
        "idx_audit_match_work",
        "audit_logs",
        ["organization_id", "target_id"],
        postgresql_where=sa.text(
            "target_type = 'match' AND (event_type <> 'phi_viewed' "
            "OR details ?| ARRAY['task_id', 'note_id', 'attachment_id'])"
        ),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_index("idx_audit_match_work", table_name="audit_logs")
    op.drop_index("idx_audit_chain_tail", table_name="audit_logs")
