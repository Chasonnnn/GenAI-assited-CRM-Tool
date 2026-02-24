"""add important notification settings

Revision ID: 20260224_1835
Revises: 20260224_1710
Create Date: 2026-02-24 18:35:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260224_1835"
down_revision: str | Sequence[str] | None = "20260224_1710"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("user_notification_settings", "status_change_decisions"):
        op.add_column(
            "user_notification_settings",
            sa.Column(
                "status_change_decisions",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )
    if not _has_column("user_notification_settings", "approval_timeouts"):
        op.add_column(
            "user_notification_settings",
            sa.Column(
                "approval_timeouts",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )
    if not _has_column("user_notification_settings", "security_alerts"):
        op.add_column(
            "user_notification_settings",
            sa.Column(
                "security_alerts",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    if _has_column("user_notification_settings", "security_alerts"):
        op.drop_column("user_notification_settings", "security_alerts")
    if _has_column("user_notification_settings", "approval_timeouts"):
        op.drop_column("user_notification_settings", "approval_timeouts")
    if _has_column("user_notification_settings", "status_change_decisions"):
        op.drop_column("user_notification_settings", "status_change_decisions")
