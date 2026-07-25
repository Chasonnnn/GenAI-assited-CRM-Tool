"""Expand jobs with rolling-compatible claim metadata.

Revision ID: 20260725_1800
Revises: 20260701_1025
Create Date: 2026-07-25 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260725_1800"
down_revision = "20260701_1025"
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
        "idx_jobs_stale_claims",
        "jobs",
        ["claimed_at", "id"],
        postgresql_where=sa.text("status = 'running' AND claimed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_jobs_stale_claims",
        table_name="jobs",
        if_exists=True,
    )
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_claim_pair")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS claimed_at")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS claim_token")
