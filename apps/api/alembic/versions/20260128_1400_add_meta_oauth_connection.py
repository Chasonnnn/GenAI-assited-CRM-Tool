"""Add Meta OAuth connection table and FK columns.

Adds:
- meta_oauth_connections table for storing OAuth tokens
- oauth_connection_id FK to meta_page_mappings and meta_ad_accounts
- is_legacy flag to meta_ad_accounts for migration tracking

Revision ID: 20260128_1400
Revises: 20260128_1030
Create Date: 2026-01-28 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "20260128_1400"
down_revision: Union[str, None] = "20260128_1030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create meta_oauth_connections table
    op.create_table(
        "meta_oauth_connections",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Meta user info
        sa.Column("meta_user_id", sa.String(100), nullable=False),
        sa.Column("meta_user_name", sa.String(255), nullable=True),
        # Token storage
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("token_expires_at", TIMESTAMP(timezone=True), nullable=True),
        # Granted scopes
        sa.Column("granted_scopes", JSONB, nullable=False),
        # Who connected
        sa.Column(
            "connected_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        # Health tracking
        sa.Column(
            "is_active",
            sa.Boolean,
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column("last_validated_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("last_error_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(50), nullable=True),
        # Future: system user support
        sa.Column(
            "connection_type",
            sa.String(20),
            server_default=sa.text("'user'"),
            nullable=False,
        ),
        # Timestamps
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Constraints
        sa.UniqueConstraint("organization_id", "meta_user_id", name="uq_meta_oauth_org_user"),
    )

    # Create index on organization_id
    op.create_index(
        "idx_meta_oauth_org",
        "meta_oauth_connections",
        ["organization_id"],
    )

    # Add oauth_connection_id FK to meta_page_mappings
    op.add_column(
        "meta_page_mappings",
        sa.Column(
            "oauth_connection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("meta_oauth_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add oauth_connection_id and is_legacy to meta_ad_accounts
    op.add_column(
        "meta_ad_accounts",
        sa.Column(
            "oauth_connection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("meta_oauth_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "meta_ad_accounts",
        sa.Column(
            "is_legacy",
            sa.Boolean,
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Mark existing ad accounts as legacy (they need OAuth reconnection)
    op.execute("UPDATE meta_ad_accounts SET is_legacy = TRUE WHERE oauth_connection_id IS NULL")


def downgrade() -> None:
    # Remove columns from meta_ad_accounts
    op.drop_column("meta_ad_accounts", "is_legacy")
    op.drop_column("meta_ad_accounts", "oauth_connection_id")

    # Remove column from meta_page_mappings
    op.drop_column("meta_page_mappings", "oauth_connection_id")

    # Drop index and table
    op.drop_index("idx_meta_oauth_org", table_name="meta_oauth_connections")
    op.drop_table("meta_oauth_connections")
