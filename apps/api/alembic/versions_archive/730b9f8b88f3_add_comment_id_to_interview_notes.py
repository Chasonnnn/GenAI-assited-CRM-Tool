"""add_comment_id_to_interview_notes

Revision ID: 730b9f8b88f3
Revises: 629a8e7a77e2
Create Date: 2026-01-05 23:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "730b9f8b88f3"
down_revision: str | Sequence[str] | None = "629a8e7a77e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add comment_id column for TipTap comment mark anchoring."""
    op.add_column("interview_notes", sa.Column("comment_id", sa.String(36), nullable=True))
    op.create_index("ix_interview_notes_comment_id", "interview_notes", ["comment_id"])


def downgrade() -> None:
    """Remove comment_id column."""
    op.drop_index("ix_interview_notes_comment_id", table_name="interview_notes")
    op.drop_column("interview_notes", "comment_id")
