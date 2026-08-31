"""Add donor stage approval and undo audit metadata."""

import sqlalchemy as sa

from alembic import op


def upgrade() -> None:
    op.add_column(
        "donor_status_history",
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "donor_status_history",
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "donor_status_history",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "donor_status_history",
        sa.Column(
            "is_undo",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "donor_status_history",
        sa.Column("request_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_donor_history_approved_by_user",
        "donor_status_history",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_donor_history_status_change_request",
        "donor_status_history",
        "status_change_requests",
        ["request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_pending_donor_requests",
        "status_change_requests",
        ["organization_id", "entity_id", "target_stage_id", "effective_at"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'donor' AND status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("idx_pending_donor_requests", table_name="status_change_requests")
    op.drop_constraint(
        "fk_donor_history_status_change_request",
        "donor_status_history",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_donor_history_approved_by_user",
        "donor_status_history",
        type_="foreignkey",
    )
    op.drop_column("donor_status_history", "request_id")
    op.drop_column("donor_status_history", "is_undo")
    op.drop_column("donor_status_history", "approved_at")
    op.drop_column("donor_status_history", "approved_by_user_id")
    op.drop_column("donor_status_history", "requested_at")
