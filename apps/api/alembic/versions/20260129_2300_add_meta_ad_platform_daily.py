"""add_meta_ad_platform_daily

Revision ID: 20260129_2300
Revises: faed99d040d9
Create Date: 2026-01-29 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260129_2300"
down_revision: Union[str, Sequence[str], None] = "faed99d040d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "meta_ad_platform_daily",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ad_account_id", sa.UUID(), nullable=False),
        sa.Column("ad_external_id", sa.String(length=100), nullable=False),
        sa.Column("ad_name", sa.String(length=500), nullable=True),
        sa.Column("spend_date", sa.Date(), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("spend", sa.Numeric(12, 4), nullable=False),
        sa.Column("impressions", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("clicks", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("leads", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ad_account_id"], ["meta_ad_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "ad_account_id",
            "ad_external_id",
            "spend_date",
            "platform",
            name="uq_meta_ad_platform_daily",
        ),
    )
    op.create_index(
        "idx_meta_ad_platform_date",
        "meta_ad_platform_daily",
        ["organization_id", "spend_date"],
        unique=False,
    )
    op.create_index(
        "idx_meta_ad_platform_ad",
        "meta_ad_platform_daily",
        ["organization_id", "ad_external_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_meta_ad_platform_ad", table_name="meta_ad_platform_daily")
    op.drop_index("idx_meta_ad_platform_date", table_name="meta_ad_platform_daily")
    op.drop_table("meta_ad_platform_daily")
