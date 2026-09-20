"""Add independently authenticated ops CLI tokens.

Revision ID: 20260919_0100_ops_cli_tokens
Revises: 20260914_1200_donor_profile
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260919_0100_ops_cli_tokens"
down_revision = "20260914_1200_donor_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    op.create_table(
        "ops_cli_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ops_cli_tokens_user_id", "ops_cli_tokens", ["user_id"])
    op.create_index("ix_ops_cli_tokens_token_hash", "ops_cli_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ops_cli_tokens_token_hash", table_name="ops_cli_tokens")
    op.drop_index("ix_ops_cli_tokens_user_id", table_name="ops_cli_tokens")
    op.drop_table("ops_cli_tokens")
