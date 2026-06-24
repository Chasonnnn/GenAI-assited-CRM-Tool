"""public intake hardening

Revision ID: 20260624_1130
Revises: 20260615_0945
Create Date: 2026-06-24 11:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260624_1130"
down_revision = "20260615_0945"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "form_submissions",
        sa.Column("full_name_normalized", sa.String(length=255), nullable=True),
    )
    op.add_column("form_submissions", sa.Column("date_of_birth", sa.Text(), nullable=True))
    op.add_column(
        "form_submissions", sa.Column("date_of_birth_hash", sa.String(length=64), nullable=True)
    )
    op.add_column("form_submissions", sa.Column("email_hash", sa.String(length=64), nullable=True))
    op.add_column("form_submissions", sa.Column("phone_hash", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE form_submissions AS fs
        SET
            full_name_normalized = il.full_name_normalized,
            date_of_birth = il.date_of_birth,
            email_hash = il.email_hash,
            phone_hash = il.phone_hash
        FROM intake_leads AS il
        WHERE
            fs.intake_lead_id = il.id
            AND fs.organization_id = il.organization_id
        """
    )
    op.execute(
        """
        UPDATE form_submissions AS fs
        SET full_name_normalized = lower(regexp_replace(trim(fs.answers_json ->> 'full_name'), '\\s+', ' ', 'g'))
        WHERE
            fs.full_name_normalized IS NULL
            AND fs.answers_json ? 'full_name'
            AND trim(fs.answers_json ->> 'full_name') <> ''
        """
    )

    op.create_index(
        "idx_form_submission_duplicate_email",
        "form_submissions",
        ["organization_id", "form_id", "full_name_normalized", "date_of_birth_hash", "email_hash"],
        unique=False,
        postgresql_where=sa.text("email_hash IS NOT NULL"),
    )
    op.create_index(
        "idx_form_submission_duplicate_phone",
        "form_submissions",
        ["organization_id", "form_id", "full_name_normalized", "date_of_birth_hash", "phone_hash"],
        unique=False,
        postgresql_where=sa.text("phone_hash IS NOT NULL"),
    )

    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("form_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("intake_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("provider_response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "meta_crm_dataset_events",
        sa.Column("provider_error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "idx_meta_crm_dataset_events_submission",
        "meta_crm_dataset_events",
        ["organization_id", "form_submission_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_meta_crm_dataset_events_intake_lead",
        "meta_crm_dataset_events",
        ["organization_id", "intake_lead_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "uq_workflow_execution_dedupe_key",
        "workflow_executions",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_workflow_execution_dedupe_key", table_name="workflow_executions")

    op.drop_index("idx_meta_crm_dataset_events_intake_lead", table_name="meta_crm_dataset_events")
    op.drop_index("idx_meta_crm_dataset_events_submission", table_name="meta_crm_dataset_events")
    op.drop_column("meta_crm_dataset_events", "provider_error_json")
    op.drop_column("meta_crm_dataset_events", "provider_response_json")
    op.drop_column("meta_crm_dataset_events", "provider_response_id")
    op.drop_column("meta_crm_dataset_events", "provider_status_code")
    op.drop_column("meta_crm_dataset_events", "intake_lead_id")
    op.drop_column("meta_crm_dataset_events", "form_submission_id")

    op.drop_index("idx_form_submission_duplicate_phone", table_name="form_submissions")
    op.drop_index("idx_form_submission_duplicate_email", table_name="form_submissions")
    op.drop_column("form_submissions", "phone_hash")
    op.drop_column("form_submissions", "email_hash")
    op.drop_column("form_submissions", "date_of_birth_hash")
    op.drop_column("form_submissions", "date_of_birth")
    op.drop_column("form_submissions", "full_name_normalized")
