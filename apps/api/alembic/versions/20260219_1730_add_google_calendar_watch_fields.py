"""Add Google Calendar push-channel metadata to user integrations.

Revision ID: 20260219_1730
Revises: 20260219_1400
Create Date: 2026-02-19 17:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260219_1730"
down_revision: str | Sequence[str] | None = "20260219_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_integrations",
        sa.Column("google_calendar_channel_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_integrations",
        sa.Column("google_calendar_resource_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_integrations",
        sa.Column("google_calendar_channel_token_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "user_integrations",
        sa.Column("google_calendar_watch_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_user_integrations_google_calendar_watch_lookup",
        "user_integrations",
        ["integration_type", "google_calendar_channel_id", "google_calendar_resource_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_integrations_google_calendar_watch_lookup",
        table_name="user_integrations",
    )
    op.drop_column("user_integrations", "google_calendar_watch_expires_at")
    op.drop_column("user_integrations", "google_calendar_channel_token_encrypted")
    op.drop_column("user_integrations", "google_calendar_resource_id")
    op.drop_column("user_integrations", "google_calendar_channel_id")
