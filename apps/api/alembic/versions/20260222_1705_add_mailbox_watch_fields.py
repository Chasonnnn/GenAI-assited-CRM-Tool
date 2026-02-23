"""Add Gmail watch metadata fields to mailboxes.

Revision ID: 20260222_1705
Revises: 20260222_1700
Create Date: 2026-02-22 17:05:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260222_1705"
down_revision: Union[str, Sequence[str], None] = "20260222_1700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("mailboxes", "gmail_watch_expiration_at"):
        op.add_column(
            "mailboxes",
            sa.Column("gmail_watch_expiration_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("mailboxes", "gmail_watch_last_renewed_at"):
        op.add_column(
            "mailboxes",
            sa.Column("gmail_watch_last_renewed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column("mailboxes", "gmail_watch_topic_name"):
        op.add_column(
            "mailboxes",
            sa.Column("gmail_watch_topic_name", sa.Text(), nullable=True),
        )
    if not _has_column("mailboxes", "gmail_watch_last_error"):
        op.add_column(
            "mailboxes",
            sa.Column("gmail_watch_last_error", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("mailboxes", "gmail_watch_last_error"):
        op.drop_column("mailboxes", "gmail_watch_last_error")
    if _has_column("mailboxes", "gmail_watch_topic_name"):
        op.drop_column("mailboxes", "gmail_watch_topic_name")
    if _has_column("mailboxes", "gmail_watch_last_renewed_at"):
        op.drop_column("mailboxes", "gmail_watch_last_renewed_at")
    if _has_column("mailboxes", "gmail_watch_expiration_at"):
        op.drop_column("mailboxes", "gmail_watch_expiration_at")
