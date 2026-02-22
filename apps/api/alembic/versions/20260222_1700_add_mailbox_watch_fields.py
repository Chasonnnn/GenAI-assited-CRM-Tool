"""Add Gmail watch metadata fields to mailboxes.

Revision ID: 20260222_1700
Revises: 20260222_1200
Create Date: 2026-02-22 17:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_1700"
down_revision: Union[str, Sequence[str], None] = "20260222_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mailboxes",
        sa.Column("gmail_watch_expiration_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column("gmail_watch_last_renewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column("gmail_watch_topic_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "mailboxes",
        sa.Column("gmail_watch_last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mailboxes", "gmail_watch_last_error")
    op.drop_column("mailboxes", "gmail_watch_topic_name")
    op.drop_column("mailboxes", "gmail_watch_last_renewed_at")
    op.drop_column("mailboxes", "gmail_watch_expiration_at")
