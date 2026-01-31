"""Add zapier_inbound_webhooks table.

Revision ID: 20260131_2355
Revises: 20260131_2345
Create Date: 2026-01-31 23:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260131_2355"
down_revision: Union[str, Sequence[str], None] = "20260131_2345"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zapier_inbound_webhooks",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "webhook_id",
            sa.String(length=36),
            nullable=False,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_zapier_inbound_webhooks_webhook_id",
        "zapier_inbound_webhooks",
        ["webhook_id"],
        unique=True,
    )
    op.create_index(
        "idx_zapier_inbound_webhooks_org_id",
        "zapier_inbound_webhooks",
        ["organization_id"],
    )

    op.execute(
        """
        INSERT INTO zapier_inbound_webhooks
            (organization_id, webhook_id, webhook_secret_encrypted, is_active, label, created_at, updated_at)
        SELECT
            organization_id,
            webhook_id,
            webhook_secret_encrypted,
            is_active,
            'Primary',
            created_at,
            updated_at
        FROM zapier_webhook_settings
        """
    )


def downgrade() -> None:
    op.drop_index("idx_zapier_inbound_webhooks_org_id", table_name="zapier_inbound_webhooks")
    op.drop_index("idx_zapier_inbound_webhooks_webhook_id", table_name="zapier_inbound_webhooks")
    op.drop_table("zapier_inbound_webhooks")
