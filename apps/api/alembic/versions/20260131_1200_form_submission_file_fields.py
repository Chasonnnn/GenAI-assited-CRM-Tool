"""Add form submission mapping snapshots and file field keys.

Revision ID: 20260131_1200
Revises: 20260131_0100
Create Date: 2026-01-31 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260131_1200"
down_revision: Union[str, Sequence[str], None] = "20260131_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "form_submissions",
        sa.Column("mapping_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "form_submission_files",
        sa.Column("field_key", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "form_submission_files",
        sa.Column("deleted_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_form_submission_files_deleted_by",
        "form_submission_files",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_form_submission_files_deleted_by",
        "form_submission_files",
        type_="foreignkey",
    )
    op.drop_column("form_submission_files", "deleted_by_user_id")
    op.drop_column("form_submission_files", "field_key")
    op.drop_column("form_submissions", "mapping_snapshot")
