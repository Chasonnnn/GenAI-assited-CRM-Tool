"""Index stale Resend reconciliation claims.

Revision ID: 20260723_0230
Revises: 20260723_0220
Create Date: 2026-07-23 18:35:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260723_0230"
down_revision = "20260723_0220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Release A owns the rolling-compatible nullable claim columns. This
    # unpublished Resend revision only adds its workload-specific lookup index.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_index(
        "idx_jobs_stale_resend_reconciliation",
        "jobs",
        ["claimed_at", "id"],
        postgresql_where=sa.text("status = 'running' AND job_type = 'resend_event_reconcile'"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_jobs_stale_resend_reconciliation",
        table_name="jobs",
    )
