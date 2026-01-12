"""Settings refactor: user phone/title, org social links, user sessions.

Revision ID: i1a2b3c4d5e6
Revises: h1b2c3d4e5f6
Create Date: 2026-01-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "i1a2b3c4d5e6"
down_revision = "h1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # 1. Add user phone/title fields
    # ==========================================================================
    op.add_column(
        "users",
        sa.Column("phone", sa.String(50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("title", sa.String(100), nullable=True),
    )

    # ==========================================================================
    # 2. Add organization social links and disclaimer
    # ==========================================================================
    op.add_column(
        "organizations",
        sa.Column(
            "signature_social_links",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
            comment="Array of {platform, url} objects for org social links",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "signature_disclaimer",
            sa.Text(),
            nullable=True,
            comment="Optional compliance footer for email signatures",
        ),
    )

    # ==========================================================================
    # 3. Create user_sessions table for session tracking
    # ==========================================================================
    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_token_hash",
            sa.String(64),
            nullable=False,
            unique=True,
            comment="SHA256 hash of JWT token for revocation lookup",
        ),
        sa.Column(
            "device_info",
            sa.String(500),
            nullable=True,
            comment="Parsed device name from user agent",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="IPv4 or IPv6 address",
        ),
        sa.Column(
            "user_agent",
            sa.String(500),
            nullable=True,
            comment="Raw user agent string",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    # Indexes for user_sessions
    op.create_index(
        "idx_user_sessions_user_id",
        "user_sessions",
        ["user_id"],
    )
    op.create_index(
        "idx_user_sessions_org_id",
        "user_sessions",
        ["organization_id"],
    )
    op.create_index(
        "idx_user_sessions_token_hash",
        "user_sessions",
        ["session_token_hash"],
    )
    op.create_index(
        "idx_user_sessions_expires",
        "user_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    # Drop user_sessions table
    op.drop_index("idx_user_sessions_expires", table_name="user_sessions")
    op.drop_index("idx_user_sessions_token_hash", table_name="user_sessions")
    op.drop_index("idx_user_sessions_org_id", table_name="user_sessions")
    op.drop_index("idx_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    # Remove organization columns
    op.drop_column("organizations", "signature_disclaimer")
    op.drop_column("organizations", "signature_social_links")

    # Remove user columns
    op.drop_column("users", "title")
    op.drop_column("users", "phone")
