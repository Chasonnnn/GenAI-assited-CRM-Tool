"""Add Zoom and Google Meet integration fields.

Adds:
- google_meet_url, meeting_started_at, meeting_ended_at to appointments
- zoom_webhook_events table for webhook deduplication

Revision ID: 20260116_1500
Revises: 20260116_1400
Create Date: 2026-01-16 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "20260116_1500"
down_revision: Union[str, None] = "20260116_1400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new fields to appointments table
    op.add_column(
        "appointments",
        sa.Column("google_meet_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("meeting_started_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("meeting_ended_at", TIMESTAMP(timezone=True), nullable=True),
    )

    # Create zoom_webhook_events table for deduplication
    op.create_table(
        "zoom_webhook_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "provider_event_id",
            sa.String(length=255),
            nullable=False,
            unique=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("zoom_meeting_id", sa.String(length=100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "processed_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Create indexes for zoom_webhook_events
    op.create_index(
        "ix_zoom_webhook_events_zoom_meeting_id",
        "zoom_webhook_events",
        ["zoom_meeting_id"],
    )
    op.create_index(
        "ix_zoom_webhook_events_processed_at",
        "zoom_webhook_events",
        ["processed_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_zoom_webhook_events_processed_at", table_name="zoom_webhook_events")
    op.drop_index("ix_zoom_webhook_events_zoom_meeting_id", table_name="zoom_webhook_events")

    # Drop zoom_webhook_events table
    op.drop_table("zoom_webhook_events")

    # Remove new columns from appointments
    op.drop_column("appointments", "meeting_ended_at")
    op.drop_column("appointments", "meeting_started_at")
    op.drop_column("appointments", "google_meet_url")
