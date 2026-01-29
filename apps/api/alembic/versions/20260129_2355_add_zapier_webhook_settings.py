"""Add zapier_webhook_settings table.

Revision ID: 20260129_2355
Revises: 20260129_2300
Create Date: 2026-01-29 23:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260129_2355"
down_revision: Union[str, Sequence[str], None] = "20260129_2300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zapier_webhook_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "webhook_id",
            sa.String(36),
            server_default=sa.text("gen_random_uuid()::text"),
            nullable=False,
        ),
        sa.Column("webhook_secret_encrypted", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_index(
        "idx_zapier_webhook_settings_webhook_id",
        "zapier_webhook_settings",
        ["webhook_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_zapier_webhook_settings_webhook_id",
        table_name="zapier_webhook_settings",
    )
    op.drop_table("zapier_webhook_settings")
