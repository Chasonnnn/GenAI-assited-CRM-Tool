"""Support organization- and platform-scoped background jobs.

Revision ID: 20260723_0250
Revises: 20260723_0240
Create Date: 2026-07-23 20:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260723_0250"
down_revision = "20260723_0240"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "job_scope",
            sa.String(length=20),
            server_default=sa.text("'organization'"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE jobs
        SET job_scope = 'organization'
        WHERE job_scope IS NULL
        """
    )
    op.alter_column(
        "jobs",
        "job_scope",
        existing_type=sa.String(length=20),
        server_default=sa.text("'organization'"),
        nullable=False,
    )
    op.alter_column(
        "jobs",
        "organization_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_jobs_scope_organization_coherence",
        "jobs",
        "(job_scope = 'organization' AND organization_id IS NOT NULL) OR "
        "(job_scope = 'platform' AND organization_id IS NULL)",
    )


def downgrade() -> None:
    # This intentionally fails safely if platform jobs still exist. Downgrading
    # must never attach platform work to an arbitrary tenant.
    op.alter_column(
        "jobs",
        "organization_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_constraint(
        "ck_jobs_scope_organization_coherence",
        "jobs",
        type_="check",
    )
    op.drop_column("jobs", "job_scope")
