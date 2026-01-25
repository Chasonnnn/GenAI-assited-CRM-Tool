"""Add support sessions for platform admin role override.

Revision ID: 20260123_0900
Revises: 20260122_0900
Create Date: 2026-01-23 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260123_0900"
down_revision: Union[str, None] = "20260122_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_VALUES = "('intake_specialist', 'case_manager', 'admin', 'developer')"
MODE_VALUES = "('write', 'read_only')"
REASON_CODES = (
    "('onboarding_setup', 'billing_help', 'data_fix', 'bug_repro', 'incident_response', 'other')"
)


def upgrade() -> None:
    op.create_table(
        "support_sessions",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role_override", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(20), server_default="write", nullable=False),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.CheckConstraint(f"role_override IN {ROLE_VALUES}", name="ck_support_sessions_role"),
        sa.CheckConstraint(f"mode IN {MODE_VALUES}", name="ck_support_sessions_mode"),
        sa.CheckConstraint(
            f"reason_code IN {REASON_CODES}", name="ck_support_sessions_reason_code"
        ),
    )
    op.create_index("idx_support_sessions_actor", "support_sessions", ["actor_user_id"])
    op.create_index("idx_support_sessions_org", "support_sessions", ["organization_id"])
    op.create_index("idx_support_sessions_expires_at", "support_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_support_sessions_expires_at", table_name="support_sessions")
    op.drop_index("idx_support_sessions_org", table_name="support_sessions")
    op.drop_index("idx_support_sessions_actor", table_name="support_sessions")
    op.drop_table("support_sessions")
