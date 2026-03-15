"""add zapier outbound event monitoring

Revision ID: 20260307_2000
Revises: 20260306_1400
Create Date: 2026-03-07 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260307_2000"
down_revision: str | Sequence[str] | None = "20260306_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "zapier_outbound_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=20),
            server_default=sa.text("'automatic'"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.Column("event_id", sa.String(length=255), nullable=True),
        sa.Column("event_name", sa.String(length=120), nullable=True),
        sa.Column("lead_id", sa.String(length=120), nullable=True),
        sa.Column("stage_key", sa.String(length=80), nullable=True),
        sa.Column("stage_slug", sa.String(length=80), nullable=True),
        sa.Column("stage_label", sa.String(length=120), nullable=True),
        sa.Column("surrogate_id", sa.UUID(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_zapier_outbound_events_org_created",
        "zapier_outbound_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_zapier_outbound_events_org_status",
        "zapier_outbound_events",
        ["organization_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_zapier_outbound_events_job_id",
        "zapier_outbound_events",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_zapier_outbound_events_job_id", table_name="zapier_outbound_events")
    op.drop_index("idx_zapier_outbound_events_org_status", table_name="zapier_outbound_events")
    op.drop_index("idx_zapier_outbound_events_org_created", table_name="zapier_outbound_events")
    op.drop_table("zapier_outbound_events")
