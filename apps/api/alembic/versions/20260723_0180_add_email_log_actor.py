"""Preserve the user who initiated a durable email.

Revision ID: 20260723_0180
Revises: 20260723_0170
Create Date: 2026-07-23 03:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260723_0180"
down_revision = "20260723_0170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_logs",
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_email_logs_actor_user",
        "email_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_email_logs_actor_user",
        "email_logs",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_email_logs_actor_user", table_name="email_logs")
    op.drop_constraint(
        "fk_email_logs_actor_user",
        "email_logs",
        type_="foreignkey",
    )
    op.drop_column("email_logs", "actor_user_id")
