"""Add support session constraints and operational indexes.

Revision ID: 20260123_2355
Revises: 20260123_0900
Create Date: 2026-01-23 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260123_2355"
down_revision: Union[str, None] = "20260123_0900"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_support_sessions_expires_after_created",
        "support_sessions",
        "expires_at > created_at",
    )

    op.create_index(
        "idx_support_sessions_actor_active",
        "support_sessions",
        ["actor_user_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_index(
        "idx_org_subscriptions_period_end_active",
        "organization_subscriptions",
        ["current_period_end"],
        postgresql_where=sa.text("status IN ('active', 'trial', 'past_due')"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_org_subscriptions_period_end_active",
        table_name="organization_subscriptions",
    )
    op.drop_index("idx_support_sessions_actor_active", table_name="support_sessions")
    op.drop_constraint(
        "ck_support_sessions_expires_after_created",
        "support_sessions",
        type_="check",
    )
