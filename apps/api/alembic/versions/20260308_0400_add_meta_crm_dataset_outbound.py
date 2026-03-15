"""add meta crm dataset outbound

Revision ID: 20260308_0400
Revises: 20260307_2000
Create Date: 2026-03-08 04:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260308_0400"
down_revision: str | Sequence[str] | None = "20260307_2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meta_crm_dataset_settings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "crm_name",
            sa.String(length=120),
            server_default=sa.text("'Surrogacy Force CRM'"),
            nullable=False,
        ),
        sa.Column(
            "send_hashed_pii",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("event_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("test_event_code", sa.String(length=120), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )

    op.create_table(
        "meta_crm_dataset_events",
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
        "idx_meta_crm_dataset_events_org_created",
        "meta_crm_dataset_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_meta_crm_dataset_events_org_status",
        "meta_crm_dataset_events",
        ["organization_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_meta_crm_dataset_events_job_id",
        "meta_crm_dataset_events",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_meta_crm_dataset_events_job_id", table_name="meta_crm_dataset_events")
    op.drop_index("idx_meta_crm_dataset_events_org_status", table_name="meta_crm_dataset_events")
    op.drop_index("idx_meta_crm_dataset_events_org_created", table_name="meta_crm_dataset_events")
    op.drop_table("meta_crm_dataset_events")
    op.drop_table("meta_crm_dataset_settings")
