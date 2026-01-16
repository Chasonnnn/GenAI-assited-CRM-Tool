"""Add backdated status change support for intended parents.

Revision ID: 20260115_1700
Revises: 20260115_1600
Create Date: 2026-01-15 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260115_1700"
down_revision: Union[str, None] = "20260115_1600"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intended_parent_status_history",
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("is_undo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_ip_status_history_approved_by",
        "intended_parent_status_history",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ip_status_history_request",
        "intended_parent_status_history",
        "status_change_requests",
        ["request_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE intended_parent_status_history
        SET effective_at = changed_at,
            recorded_at = changed_at
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ip_status_history_request", "intended_parent_status_history", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_ip_status_history_approved_by",
        "intended_parent_status_history",
        type_="foreignkey",
    )
    op.drop_column("intended_parent_status_history", "request_id")
    op.drop_column("intended_parent_status_history", "is_undo")
    op.drop_column("intended_parent_status_history", "approved_at")
    op.drop_column("intended_parent_status_history", "approved_by_user_id")
    op.drop_column("intended_parent_status_history", "requested_at")
    op.drop_column("intended_parent_status_history", "recorded_at")
    op.drop_column("intended_parent_status_history", "effective_at")
