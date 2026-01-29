"""Add outbound Zapier webhook settings fields.

Revision ID: 20260130_0010
Revises: 20260129_2355
Create Date: 2026-01-30 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260130_0010"
down_revision: Union[str, Sequence[str], None] = "20260129_2355"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "zapier_webhook_settings",
        sa.Column("outbound_webhook_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "zapier_webhook_settings",
        sa.Column("outbound_webhook_secret_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "zapier_webhook_settings",
        sa.Column(
            "outbound_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "zapier_webhook_settings",
        sa.Column(
            "outbound_send_hashed_pii",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "zapier_webhook_settings",
        sa.Column("outbound_event_mapping", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("zapier_webhook_settings", "outbound_event_mapping")
    op.drop_column("zapier_webhook_settings", "outbound_send_hashed_pii")
    op.drop_column("zapier_webhook_settings", "outbound_enabled")
    op.drop_column("zapier_webhook_settings", "outbound_webhook_secret_encrypted")
    op.drop_column("zapier_webhook_settings", "outbound_webhook_url")
