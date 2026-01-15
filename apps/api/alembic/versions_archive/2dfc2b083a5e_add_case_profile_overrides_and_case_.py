"""Add case_profile_overrides and case_profile_hidden_fields tables

Revision ID: 2dfc2b083a5e
Revises: c64d37e0bace
Create Date: 2026-01-01 22:21:14.247977

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2dfc2b083a5e"
down_revision: Union[str, Sequence[str], None] = "c64d37e0bace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create case_profile_overrides table
    op.create_table(
        "case_profile_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_key", sa.String(length=255), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "field_key", name="uq_case_profile_override_field"),
    )
    op.create_index("idx_profile_overrides_case", "case_profile_overrides", ["case_id"])

    # Create case_profile_states table
    op.create_table(
        "case_profile_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["base_submission_id"], ["form_submissions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", name="uq_case_profile_state_case"),
    )
    op.create_index("idx_profile_state_case", "case_profile_states", ["case_id"])

    # Create case_profile_hidden_fields table
    op.create_table(
        "case_profile_hidden_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_key", sa.String(length=255), nullable=False),
        sa.Column("hidden_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "hidden_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hidden_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "field_key", name="uq_case_profile_hidden_field"),
    )
    op.create_index("idx_profile_hidden_case", "case_profile_hidden_fields", ["case_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_profile_hidden_case", table_name="case_profile_hidden_fields")
    op.drop_table("case_profile_hidden_fields")
    op.drop_index("idx_profile_state_case", table_name="case_profile_states")
    op.drop_table("case_profile_states")
    op.drop_index("idx_profile_overrides_case", table_name="case_profile_overrides")
    op.drop_table("case_profile_overrides")
