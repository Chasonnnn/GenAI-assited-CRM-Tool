"""Add platform admin support: is_platform_admin flag, organization subscriptions, admin action logs.

Revision ID: 20260122_0900
Revises: 20260117_1200
Create Date: 2026-01-22 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "20260122_0900"
down_revision: Union[str, None] = "20260117_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_platform_admin to users table
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Create organization_subscriptions table
    op.create_table(
        "organization_subscriptions",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "plan_key",
            sa.String(50),
            server_default="starter",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(30),
            server_default="active",
            nullable=False,
        ),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("trial_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", name="uq_organization_subscriptions_org_id"),
        sa.CheckConstraint(
            "plan_key IN ('starter', 'professional', 'enterprise')",
            name="ck_organization_subscriptions_plan_key",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'trial', 'past_due', 'canceled')",
            name="ck_organization_subscriptions_status",
        ),
    )
    op.create_index(
        "idx_org_subscriptions_status",
        "organization_subscriptions",
        ["status"],
    )

    # Create admin_action_logs table
    op.create_table(
        "admin_action_logs",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "actor_user_id", UUID(as_uuid=True), nullable=True
        ),  # Nullable for system actions
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("ip_address_hmac", sa.String(64), nullable=True),
        sa.Column("user_agent_hmac", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["target_organization_id"], ["organizations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_admin_action_logs_created_at",
        "admin_action_logs",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_admin_action_logs_target_org",
        "admin_action_logs",
        ["target_organization_id"],
    )
    op.create_index(
        "idx_admin_action_logs_actor",
        "admin_action_logs",
        ["actor_user_id"],
    )

    # Create or replace the update_updated_at_column function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger for organization_subscriptions updated_at
    op.execute("""
        CREATE TRIGGER update_org_subscriptions_updated_at
            BEFORE UPDATE ON organization_subscriptions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    # Drop trigger
    op.execute(
        "DROP TRIGGER IF EXISTS update_org_subscriptions_updated_at ON organization_subscriptions"
    )

    # Drop admin_action_logs table
    op.drop_index("idx_admin_action_logs_actor", table_name="admin_action_logs")
    op.drop_index("idx_admin_action_logs_target_org", table_name="admin_action_logs")
    op.drop_index("idx_admin_action_logs_created_at", table_name="admin_action_logs")
    op.drop_table("admin_action_logs")

    # Drop organization_subscriptions table
    op.drop_index("idx_org_subscriptions_status", table_name="organization_subscriptions")
    op.drop_table("organization_subscriptions")

    # Remove is_platform_admin from users
    op.drop_column("users", "is_platform_admin")

    # Note: We don't drop the function as it might be used by other tables
