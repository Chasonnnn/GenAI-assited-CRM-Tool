"""Interpret existing form, intake, and pipeline stage timestamps as UTC.

Revision ID: 20261003_1800_timezone_aware_form_timestamps
Revises: 20261003_1700_medical_records
"""

from alembic import op

revision = "20261003_1800_timezone_aware_form_timestamps"
down_revision = "20261003_1700_medical_records"
branch_labels = None
depends_on = None

# Frozen column inventory; do not import application metadata in migrations.
COLUMNS = {
    "consent_records": ("accepted_at",),
    "embed_sessions": ("expires_at", "consumed_at", "created_at"),
    "form_field_mappings": ("created_at",),
    "form_intake_drafts": ("started_at", "created_at", "updated_at"),
    "form_intake_links": ("expires_at", "created_at", "updated_at"),
    "form_logos": ("created_at",),
    "form_submission_drafts": ("started_at", "created_at", "updated_at"),
    "form_submission_files": ("deleted_at", "created_at"),
    "form_submission_match_candidates": ("created_at",),
    "form_submissions": ("matched_at", "submitted_at", "reviewed_at", "applied_at", "created_at"),
    "forms": ("created_at", "updated_at"),
    "intake_leads": ("created_at", "updated_at", "promoted_at"),
    "lead_attribution": ("created_at",),
    "pipeline_stages": ("deleted_at", "created_at", "updated_at"),
    "published_intake_versions": ("published_at",),
    "tracking_event_logs": ("created_at",),
}


def _convert(target_type: str) -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '120s'")
    # Stored values are UTC wall-clock. With the session zone at UTC, a plain cast keeps them
    # and Postgres changes only metadata; a USING expression would rewrite every table.
    op.execute("SET LOCAL TimeZone = 'UTC'")
    for table, columns in COLUMNS.items():
        # One ALTER per table rebuilds each table's indexes once.
        changes = ", ".join(f"ALTER COLUMN {column} TYPE {target_type}" for column in columns)
        op.execute(f"ALTER TABLE {table} {changes}")


def upgrade() -> None:
    _convert("timestamp with time zone")


def downgrade() -> None:
    _convert("timestamp without time zone")
