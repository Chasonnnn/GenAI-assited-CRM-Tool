"""Add per-type client message settings to appointment types.

client_messages holds {message: {"enabled": bool, "template_id": uuid | null}} for
request_received, confirmed, reminder, rescheduled, and cancelled. A missing message is
enabled with the org default template.

Types with reminder_hours_before = 0 (the old "no reminder" value) get the reminder
disabled and 24 hours stored, so hours stay a timing setting and the switch owns on/off.

Revision ID: 20261003_1300_appointment_type_client_messages
Revises: 20261003_1200_repair_seeded_system_workflows
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20261003_1300_appointment_type_client_messages"
down_revision = "20261003_1200_repair_seeded_system_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointment_types",
        sa.Column(
            "client_messages",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE appointment_types
        SET client_messages = '{"reminder": {"enabled": false, "template_id": null}}'::jsonb,
            reminder_hours_before = 24
        WHERE reminder_hours_before <= 0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE appointment_types
        SET reminder_hours_before = 0
        WHERE client_messages -> 'reminder' ->> 'enabled' = 'false'
        """
    )
    op.drop_column("appointment_types", "client_messages")
