"""Add workflow approval notification preference.

Revision ID: c5f4e3d2b1a0
Revises: 0afc5c98c589
Create Date: 2026-01-05
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5f4e3d2b1a0"
down_revision = "0afc5c98c589"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "workflow_approvals",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_notification_settings", "workflow_approvals")
