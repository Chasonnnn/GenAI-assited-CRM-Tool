"""Add shared Intended Parent and Donor activity logs.

Revision ID: 20260830_0100
Revises: 20260829_0100
Create Date: 2026-08-30 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260830_0100"
down_revision: str | Sequence[str] | None = "20260829_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "intended_parent_status_history",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("old_label_snapshot", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "intended_parent_status_history",
        sa.Column("new_label_snapshot", sa.String(length=100), nullable=True),
    )
    op.execute(
        """
        UPDATE intended_parent_status_history AS history
        SET organization_id = intended_parent.organization_id
        FROM intended_parents AS intended_parent
        WHERE intended_parent.id = history.intended_parent_id
        """
    )
    op.execute(
        """
        UPDATE intended_parent_status_history AS history
        SET old_label_snapshot = CASE
            WHEN history.old_status = 'archived' THEN 'Archived'
            ELSE stage.label
        END
        FROM pipeline_stages AS stage
        WHERE stage.id = history.old_stage_id
        """
    )
    op.execute(
        """
        UPDATE intended_parent_status_history AS history
        SET new_label_snapshot = CASE
            WHEN history.new_status = 'archived' THEN 'Archived'
            ELSE stage.label
        END
        FROM pipeline_stages AS stage
        WHERE stage.id = history.new_stage_id
        """
    )
    op.alter_column(
        "intended_parent_status_history",
        "organization_id",
        nullable=False,
    )
    op.create_foreign_key(
        "fk_ip_history_organization",
        "intended_parent_status_history",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_ip_history_org_recorded",
        "intended_parent_status_history",
        ["organization_id", "intended_parent_id", "recorded_at"],
    )

    op.create_table(
        "entity_activity_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intended_parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("donor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activity_type", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "num_nonnulls(intended_parent_id, donor_id) = 1",
            name="ck_entity_activity_exactly_one_subject",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["donor_id"],
            ["donors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["intended_parent_id"],
            ["intended_parents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_entity_activity_ip_time",
        "entity_activity_logs",
        ["organization_id", "intended_parent_id", "occurred_at", "id"],
    )
    op.create_index(
        "idx_entity_activity_donor_time",
        "entity_activity_logs",
        ["organization_id", "donor_id", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_entity_activity_donor_time", table_name="entity_activity_logs")
    op.drop_index("idx_entity_activity_ip_time", table_name="entity_activity_logs")
    op.drop_table("entity_activity_logs")
    op.drop_index(
        "idx_ip_history_org_recorded",
        table_name="intended_parent_status_history",
    )
    op.drop_constraint(
        "fk_ip_history_organization",
        "intended_parent_status_history",
        type_="foreignkey",
    )
    op.drop_column("intended_parent_status_history", "new_label_snapshot")
    op.drop_column("intended_parent_status_history", "old_label_snapshot")
    op.drop_column("intended_parent_status_history", "organization_id")
