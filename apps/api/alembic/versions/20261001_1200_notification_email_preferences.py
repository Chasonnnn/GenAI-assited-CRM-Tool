"""Add the per-user email toggle for workflow notifications.

Existing rows get FALSE so nobody receives notification email after deploy
until they turn it on.

Revision ID: 20261001_1200_notification_email_preferences
Revises: 20260928_1340_zapier_event_effective_at
"""

import sqlalchemy as sa

from alembic import op

revision = "20261001_1200_notification_email_preferences"
down_revision = "20260928_1340_zapier_event_effective_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "email_workflow_notifications",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_column("user_notification_settings", "email_workflow_notifications")
