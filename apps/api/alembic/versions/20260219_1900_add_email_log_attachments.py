"""Add email_log_attachments join table.

Revision ID: 20260219_1900
Revises: 20260219_1730
Create Date: 2026-02-19 19:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260219_1900"
down_revision: Union[str, Sequence[str], None] = "20260219_1730"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_log_attachments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "email_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attachment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attachments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "email_log_id",
            "attachment_id",
            name="uq_email_log_attachments_unique_link",
        ),
    )
    op.create_index(
        "idx_email_log_attachments_org",
        "email_log_attachments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "idx_email_log_attachments_email_log",
        "email_log_attachments",
        ["email_log_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_email_log_attachments_email_log", table_name="email_log_attachments")
    op.drop_index("idx_email_log_attachments_org", table_name="email_log_attachments")
    op.drop_table("email_log_attachments")
