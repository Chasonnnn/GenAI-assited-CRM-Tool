"""Add hashed opaque unsubscribe tokens.

Revision ID: 20260803_0100
Revises: 20260725_0290
Create Date: 2026-08-03 01:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260803_0100"
down_revision = "20260725_0290"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "unsubscribe_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_unsubscribe_tokens_token_hash"),
    )
    op.create_index(
        "idx_unsubscribe_tokens_org_email",
        "unsubscribe_tokens",
        ["organization_id", "email"],
    )
    op.create_index(
        "idx_unsubscribe_tokens_expires_at",
        "unsubscribe_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("idx_unsubscribe_tokens_expires_at", table_name="unsubscribe_tokens")
    op.drop_index("idx_unsubscribe_tokens_org_email", table_name="unsubscribe_tokens")
    op.drop_table("unsubscribe_tokens")
