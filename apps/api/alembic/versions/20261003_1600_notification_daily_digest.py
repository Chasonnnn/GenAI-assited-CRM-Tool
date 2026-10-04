"""Add the per-user opt-in for the daily notification digest email.

Existing rows get FALSE so nobody receives a digest after deploy until they turn it on.

Revision ID: 20261003_1600_notification_daily_digest
Revises: 20261003_1400_migrate_form_routing
"""

import sqlalchemy as sa

from alembic import op

revision = "20261003_1600_notification_daily_digest"
down_revision = "20261003_1400_migrate_form_routing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "email_daily_digest",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.drop_column("user_notification_settings", "email_daily_digest")
