"""Add analytics cache and hot-filter indexes.

Revision ID: d3c4b5e6f7a8
Revises: c7e8f9a0b1c2
Create Date: 2025-02-20 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d3c4b5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "c7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "analytics_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_type", sa.String(length=50), nullable=False),
        sa.Column("snapshot_key", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("range_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("range_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_analytics_snapshot_key",
        "analytics_snapshots",
        ["organization_id", "snapshot_key"],
    )
    op.create_index(
        "idx_analytics_snapshot_org_type",
        "analytics_snapshots",
        ["organization_id", "snapshot_type"],
    )
    op.create_index(
        "idx_analytics_snapshot_expires",
        "analytics_snapshots",
        ["expires_at"],
    )

    op.create_index(
        "idx_cases_org_status_label",
        "cases",
        ["organization_id", "status_label"],
    )
    op.create_index(
        "idx_cases_org_updated",
        "cases",
        ["organization_id", "updated_at"],
    )

    op.create_index(
        "idx_tasks_org_status",
        "tasks",
        ["organization_id", "is_completed"],
    )
    op.create_index(
        "idx_tasks_org_created",
        "tasks",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "idx_tasks_org_updated",
        "tasks",
        ["organization_id", "updated_at"],
    )

    op.create_index(
        "idx_ip_org_updated",
        "intended_parents",
        ["organization_id", "updated_at"],
    )

    op.create_index(
        "idx_matches_org_status",
        "matches",
        ["organization_id", "status"],
    )
    op.create_index(
        "idx_matches_org_created",
        "matches",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "idx_matches_org_updated",
        "matches",
        ["organization_id", "updated_at"],
    )

    op.create_index(
        "idx_appointments_org_user",
        "appointments",
        ["organization_id", "user_id"],
    )
    op.create_index(
        "idx_appointments_org_created",
        "appointments",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "idx_appointments_org_updated",
        "appointments",
        ["organization_id", "updated_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_appointments_org_updated", table_name="appointments")
    op.drop_index("idx_appointments_org_created", table_name="appointments")
    op.drop_index("idx_appointments_org_user", table_name="appointments")

    op.drop_index("idx_matches_org_updated", table_name="matches")
    op.drop_index("idx_matches_org_created", table_name="matches")
    op.drop_index("idx_matches_org_status", table_name="matches")

    op.drop_index("idx_ip_org_updated", table_name="intended_parents")

    op.drop_index("idx_tasks_org_updated", table_name="tasks")
    op.drop_index("idx_tasks_org_created", table_name="tasks")
    op.drop_index("idx_tasks_org_status", table_name="tasks")

    op.drop_index("idx_cases_org_updated", table_name="cases")
    op.drop_index("idx_cases_org_status_label", table_name="cases")

    op.drop_index("idx_analytics_snapshot_expires", table_name="analytics_snapshots")
    op.drop_index("idx_analytics_snapshot_org_type", table_name="analytics_snapshots")
    op.drop_constraint(
        "uq_analytics_snapshot_key", "analytics_snapshots", type_="unique"
    )
    op.drop_table("analytics_snapshots")
