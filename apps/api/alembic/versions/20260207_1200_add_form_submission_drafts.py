"""Add form submission drafts for server-side autosave.

Revision ID: 20260207_1200
Revises: 20260206_1300
Create Date: 2026-02-07 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260207_1200"
down_revision: Union[str, Sequence[str], None] = "20260206_1300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "form_submission_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "form_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "surrogate_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "answers_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["surrogate_id"],
            ["surrogates.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("form_id", "surrogate_id", name="uq_form_draft_surrogate"),
    )

    op.create_index("idx_form_drafts_org", "form_submission_drafts", ["organization_id"])
    op.create_index("idx_form_drafts_form", "form_submission_drafts", ["form_id"])
    op.create_index("idx_form_drafts_surrogate", "form_submission_drafts", ["surrogate_id"])


def downgrade() -> None:
    op.drop_index("idx_form_drafts_surrogate", table_name="form_submission_drafts")
    op.drop_index("idx_form_drafts_form", table_name="form_submission_drafts")
    op.drop_index("idx_form_drafts_org", table_name="form_submission_drafts")
    op.drop_table("form_submission_drafts")
