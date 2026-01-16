"""Add backdated stage change support with dual timestamps and approval workflow.

Revision ID: 20260115_1600
Revises: 20260115_1500
Create Date: 2026-01-15 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260115_1600"
down_revision: Union[str, None] = "20260115_1500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dual timestamps to surrogate_status_history
    op.add_column(
        "surrogate_status_history",
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "surrogate_status_history",
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Audit fields for approval flow
    op.add_column(
        "surrogate_status_history",
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "surrogate_status_history",
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "surrogate_status_history",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "surrogate_status_history",
        sa.Column("is_undo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "surrogate_status_history",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Add FK for approved_by_user_id
    op.create_foreign_key(
        "fk_surrogate_status_history_approved_by",
        "surrogate_status_history",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. Backfill effective_at from changed_at for existing records
    op.execute(
        """
        UPDATE surrogate_status_history
        SET effective_at = changed_at
        WHERE effective_at IS NULL
        """
    )

    # 3. Create status_change_requests table
    op.create_table(
        "status_change_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),  # 'surrogate' or 'intended_parent'
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "target_stage_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_status", sa.String(50), nullable=True),  # For intended parents
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20), server_default="pending", nullable=False
        ),  # pending, approved, rejected, cancelled
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rejected_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancelled_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    )

    # Add FK for request_id in surrogate_status_history
    op.create_foreign_key(
        "fk_surrogate_status_history_request",
        "surrogate_status_history",
        "status_change_requests",
        ["request_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Create partial unique indexes to prevent duplicate pending requests
    # Surrogates: index on target_stage_id
    op.execute(
        """
        CREATE UNIQUE INDEX idx_pending_surrogate_requests
        ON status_change_requests (organization_id, entity_id, target_stage_id, effective_at)
        WHERE entity_type = 'surrogate' AND status = 'pending'
        """
    )

    # Intended Parents: index on target_status
    op.execute(
        """
        CREATE UNIQUE INDEX idx_pending_ip_requests
        ON status_change_requests (organization_id, entity_id, target_status, effective_at)
        WHERE entity_type = 'intended_parent' AND status = 'pending'
        """
    )

    # 5. Create index for looking up pending requests by org
    op.create_index(
        "idx_status_change_requests_org_status",
        "status_change_requests",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_status_change_requests_org_status", table_name="status_change_requests")
    op.execute("DROP INDEX IF EXISTS idx_pending_ip_requests")
    op.execute("DROP INDEX IF EXISTS idx_pending_surrogate_requests")

    # Drop FK for request_id
    op.drop_constraint(
        "fk_surrogate_status_history_request", "surrogate_status_history", type_="foreignkey"
    )

    # Drop status_change_requests table
    op.drop_table("status_change_requests")

    # Drop FK for approved_by_user_id
    op.drop_constraint(
        "fk_surrogate_status_history_approved_by", "surrogate_status_history", type_="foreignkey"
    )

    # Drop columns from surrogate_status_history
    op.drop_column("surrogate_status_history", "request_id")
    op.drop_column("surrogate_status_history", "is_undo")
    op.drop_column("surrogate_status_history", "approved_at")
    op.drop_column("surrogate_status_history", "approved_by_user_id")
    op.drop_column("surrogate_status_history", "requested_at")
    op.drop_column("surrogate_status_history", "recorded_at")
    op.drop_column("surrogate_status_history", "effective_at")
