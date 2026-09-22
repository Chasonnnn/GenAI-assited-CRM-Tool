"""Add donor stage delivery settings and durable Zapier event links.

Revision ID: 20260920_0200_donor_zapier_reporting
Revises: 20260920_0100_workflow_template_subject_type
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260920_0200_donor_zapier_reporting"
down_revision = "20260920_0100_workflow_template_subject_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "zapier_webhook_settings",
        sa.Column(
            "donor_outbound_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "zapier_webhook_settings",
        sa.Column("donor_outbound_event_mapping", postgresql.JSONB(), nullable=True),
    )

    op.add_column(
        "zapier_outbound_events",
        sa.Column("donor_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("donor_status_history_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("donor_type", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("attribution_source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("first_party_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "zapier_outbound_events",
        sa.Column("config_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_zapier_outbound_events_donor_id",
        "zapier_outbound_events",
        "donors",
        ["donor_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_zapier_outbound_events_donor_history_id",
        "zapier_outbound_events",
        "donor_status_history",
        ["donor_status_history_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_zapier_outbound_events_pipeline_id",
        "zapier_outbound_events",
        "pipelines",
        ["pipeline_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_zapier_outbound_events_stage_id",
        "zapier_outbound_events",
        "pipeline_stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_zapier_outbound_events_first_party_submission_id",
        "zapier_outbound_events",
        "form_submissions",
        ["first_party_submission_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_zapier_outbound_events_donor_type",
        "zapier_outbound_events",
        "donor_type IS NULL OR donor_type IN ('egg', 'sperm')",
    )
    op.create_index(
        "uq_zapier_outbound_events_donor_history",
        "zapier_outbound_events",
        ["donor_status_history_id"],
        unique=True,
        postgresql_where=sa.text("donor_status_history_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_zapier_outbound_events_donor_history",
        table_name="zapier_outbound_events",
    )
    op.drop_constraint(
        "ck_zapier_outbound_events_donor_type",
        "zapier_outbound_events",
        type_="check",
    )
    op.drop_constraint(
        "fk_zapier_outbound_events_first_party_submission_id",
        "zapier_outbound_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_zapier_outbound_events_stage_id",
        "zapier_outbound_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_zapier_outbound_events_pipeline_id",
        "zapier_outbound_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_zapier_outbound_events_donor_history_id",
        "zapier_outbound_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_zapier_outbound_events_donor_id",
        "zapier_outbound_events",
        type_="foreignkey",
    )
    for column_name in (
        "config_fingerprint",
        "first_party_submission_id",
        "attribution_source",
        "stage_id",
        "pipeline_id",
        "donor_type",
        "donor_status_history_id",
        "donor_id",
    ):
        op.drop_column("zapier_outbound_events", column_name)
    op.drop_column("zapier_webhook_settings", "donor_outbound_event_mapping")
    op.drop_column("zapier_webhook_settings", "donor_outbound_enabled")
