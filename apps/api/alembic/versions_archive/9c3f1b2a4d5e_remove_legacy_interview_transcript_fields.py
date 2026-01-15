"""Remove legacy interview transcript HTML and anchor offsets.

Revision ID: 9c3f1b2a4d5e
Revises: 670f828cdc71
Create Date: 2026-01-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3f1b2a4d5e"
down_revision: Union[str, Sequence[str], None] = "670f828cdc71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_interview_notes_anchor_complete", "interview_notes", type_="check")
    op.drop_constraint("ck_interview_notes_anchor_range", "interview_notes", type_="check")
    op.drop_column("interview_notes", "anchor_start")
    op.drop_column("interview_notes", "anchor_end")
    op.drop_column("interview_notes", "current_anchor_start")
    op.drop_column("interview_notes", "current_anchor_end")
    op.drop_column("interview_notes", "anchor_status")
    op.drop_column("case_interviews", "transcript_html")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("case_interviews", sa.Column("transcript_html", sa.Text(), nullable=True))
    op.add_column(
        "interview_notes", sa.Column("anchor_status", sa.String(length=20), nullable=True)
    )
    op.add_column("interview_notes", sa.Column("current_anchor_end", sa.Integer(), nullable=True))
    op.add_column("interview_notes", sa.Column("current_anchor_start", sa.Integer(), nullable=True))
    op.add_column("interview_notes", sa.Column("anchor_end", sa.Integer(), nullable=True))
    op.add_column("interview_notes", sa.Column("anchor_start", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_interview_notes_anchor_range",
        "interview_notes",
        "anchor_end IS NULL OR anchor_end >= anchor_start",
    )
    op.create_check_constraint(
        "ck_interview_notes_anchor_complete",
        "interview_notes",
        "(anchor_start IS NULL AND anchor_end IS NULL) OR "
        "(anchor_start IS NOT NULL AND anchor_end IS NOT NULL AND anchor_text IS NOT NULL)",
    )
