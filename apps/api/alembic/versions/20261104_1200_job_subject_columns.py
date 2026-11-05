"""Promote the workflow email subject out of jobs.payload.

Revision ID: 20261104_1200_job_subject_columns
Revises: 20261103_1200_email_content_ticket_header
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "20261104_1200_job_subject_columns"
down_revision = "20261103_1200_email_content_ticket_header"
branch_labels = None
depends_on = None

# Payloads store str(uuid); only that exact form matched the old text comparison.
CANONICAL_UUID = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def _subject_type(row: str) -> str:
    return f"CASE WHEN {row}.job_type = 'workflow_email' THEN {row}.payload ->> 'subject_type' END"


def _subject_id(row: str) -> str:
    return (
        f"CASE WHEN {row}.job_type = 'workflow_email' "
        f"AND {row}.payload ->> 'subject_id' ~ '{CANONICAL_UUID}' "
        f"THEN CAST({row}.payload ->> 'subject_id' AS uuid) END"
    )


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    # Nullable without a default: a catalog-only change, no table rewrite.
    op.add_column("jobs", sa.Column("subject_type", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("subject_id", UUID(as_uuid=True), nullable=True))
    # The trigger also covers jobs that pre-release workers enqueue during a rollout.
    op.execute(
        f"""
        CREATE FUNCTION jobs_subject_from_payload() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.subject_type := {_subject_type("NEW")};
            NEW.subject_id := {_subject_id("NEW")};
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER jobs_subject_from_payload BEFORE INSERT OR UPDATE OF payload, job_type "
        "ON jobs FOR EACH ROW EXECUTE FUNCTION jobs_subject_from_payload()"
    )
    op.execute(
        f"""
        UPDATE jobs SET subject_type = {_subject_type("jobs")}, subject_id = {_subject_id("jobs")}
        WHERE job_type = 'workflow_email'
        """
    )
    op.create_index(
        "idx_jobs_subject",
        "jobs",
        ["organization_id", "subject_type", "subject_id"],
        postgresql_where=sa.text("subject_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_index("idx_jobs_subject", table_name="jobs")
    op.execute("DROP TRIGGER jobs_subject_from_payload ON jobs")
    op.execute("DROP FUNCTION jobs_subject_from_payload()")
    op.drop_column("jobs", "subject_id")
    op.drop_column("jobs", "subject_type")
