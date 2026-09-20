"""Add one-time OPS browser login grants.

Revision ID: 20260919_0300_ops_cli_login
Revises: 20260919_0200_template_cli_identity
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260919_0300_ops_cli_login"
down_revision = "20260919_0200_template_cli_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.create_table(
        "ops_cli_logins",
        sa.Column("device_hash", sa.String(64), primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=True),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ops_cli_logins_expires_at", "ops_cli_logins", ["expires_at"])


def downgrade() -> None:
    op.drop_table("ops_cli_logins")
