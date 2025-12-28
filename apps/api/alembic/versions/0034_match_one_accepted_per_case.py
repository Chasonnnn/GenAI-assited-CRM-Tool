"""Add partial unique index for one accepted match per case.

Revision ID: 0034_match_one_accepted_per_case
Revises: 0033_add_matches
Create Date: 2025-12-19

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0034_match_one_accepted_per_case"
down_revision = "0033_add_matches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index: only one accepted match per (org, case)
    # This prevents race conditions allowing multiple accepts
    op.execute("""
        CREATE UNIQUE INDEX uq_one_accepted_match_per_case
        ON matches (organization_id, case_id)
        WHERE status = 'accepted'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_one_accepted_match_per_case")
