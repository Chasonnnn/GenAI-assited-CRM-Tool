"""Add worker claim fencing metadata to jobs.

Revision ID: 20260723_0230
Revises: 20260723_0220
Create Date: 2026-07-23 18:35:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260723_0230"
down_revision = "20260723_0220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("claim_token", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_jobs_claim_pair",
        "jobs",
        "(claim_token IS NULL) = (claimed_at IS NULL)",
    )
    op.create_index(
        "idx_jobs_stale_resend_reconciliation",
        "jobs",
        ["claimed_at", "id"],
        postgresql_where=sa.text(
            "status = 'running' AND job_type = 'resend_event_reconcile'"
        ),
    )
    op.execute(
        """
        UPDATE jobs
        SET status = 'pending',
            run_at = now(),
            last_error = NULL
        WHERE status = 'running'
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_jobs_stale_resend_reconciliation",
        table_name="jobs",
    )
    op.drop_constraint("ck_jobs_claim_pair", "jobs", type_="check")
    op.drop_column("jobs", "claimed_at")
    op.drop_column("jobs", "claim_token")
