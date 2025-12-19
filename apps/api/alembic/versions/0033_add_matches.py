"""Add matches table.

Revision ID: 0033_add_matches
Revises: 0032_add_zoom_meetings
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0033_add_matches"
down_revision = "0032_add_zoom_meetings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intended_parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("intended_parents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("compatibility_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("proposed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    
    # Unique constraint: only one match proposal per (org, case, IP) pair
    op.create_unique_constraint("uq_match_org_case_ip", "matches", ["organization_id", "case_id", "intended_parent_id"])
    
    # Indexes
    op.create_index("ix_matches_case_id", "matches", ["case_id"])
    op.create_index("ix_matches_ip_id", "matches", ["intended_parent_id"])
    op.create_index("ix_matches_status", "matches", ["status"])


def downgrade() -> None:
    op.drop_index("ix_matches_status")
    op.drop_index("ix_matches_ip_id")
    op.drop_index("ix_matches_case_id")
    op.drop_constraint("uq_match_org_case_ip", "matches")
    op.drop_table("matches")
