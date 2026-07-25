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
    # This migration is the compatibility boundary between the legacy worker,
    # which cannot write claim metadata, and the fenced worker. Lock first so a
    # concurrent legacy claim either finishes before this check or is rejected
    # by ck_jobs_running_claimed after the transaction commits.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE jobs IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM jobs WHERE status = 'running') THEN
                RAISE EXCEPTION
                    'Cannot add job claim fencing while jobs are running; '
                    'drain the old worker before retrying';
            END IF;
        END
        $$
        """
    )
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
    op.create_check_constraint(
        "ck_jobs_running_claimed",
        "jobs",
        "status <> 'running' OR (claim_token IS NOT NULL AND claimed_at IS NOT NULL)",
    )
    op.create_index(
        "idx_jobs_stale_resend_reconciliation",
        "jobs",
        ["claimed_at", "id"],
        postgresql_where=sa.text("status = 'running' AND job_type = 'resend_event_reconcile'"),
    )
    # Cloud Build applies this schema before replacing the worker revision.
    # The running-claim constraint prevents the old revision from claiming new
    # work during that bounded cutover window.


def downgrade() -> None:
    op.drop_index(
        "idx_jobs_stale_resend_reconciliation",
        table_name="jobs",
    )
    # IF EXISTS keeps local databases created from an earlier draft of this
    # still-unreleased migration downgradeable during rollout rehearsal.
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_running_claimed")
    op.drop_constraint("ck_jobs_claim_pair", "jobs", type_="check")
    op.drop_column("jobs", "claimed_at")
    op.drop_column("jobs", "claim_token")
