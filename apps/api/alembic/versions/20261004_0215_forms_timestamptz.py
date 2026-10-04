"""Store form, intake, and pipeline stage timestamps with a time zone.

These columns were the only ``timestamp without time zone`` columns left. The
API serialized them without an offset, so browsers read UTC values as local
time. Every writer stores UTC (``now()`` and aware Python values under the UTC
session time zone), so the existing values convert ``AT TIME ZONE 'UTC'``.

Revision ID: 20261004_0215_forms_timestamptz
Revises: 20261003_2030_email_template_body_design
"""

from alembic import op

revision = "20261004_0215_forms_timestamptz"
down_revision = "20261003_2030_email_template_body_design"
branch_labels = None
depends_on = None

COLUMNS = {
    "consent_records": ("accepted_at",),
    "embed_sessions": ("consumed_at", "created_at", "expires_at"),
    "form_field_mappings": ("created_at",),
    "form_intake_drafts": ("created_at", "started_at", "updated_at"),
    "form_intake_links": ("created_at", "expires_at", "updated_at"),
    "form_logos": ("created_at",),
    "form_submission_drafts": ("created_at", "started_at", "updated_at"),
    "form_submission_files": ("created_at", "deleted_at"),
    "form_submission_match_candidates": ("created_at",),
    "form_submissions": (
        "applied_at",
        "created_at",
        "matched_at",
        "reviewed_at",
        "submitted_at",
    ),
    "forms": ("created_at", "updated_at"),
    "intake_leads": ("created_at", "promoted_at", "updated_at"),
    "lead_attribution": ("created_at",),
    "pipeline_stages": ("created_at", "deleted_at", "updated_at"),
    "published_intake_versions": ("published_at",),
    "tracking_event_logs": ("created_at",),
}


def _alter(target_type: str) -> None:
    for table, columns in COLUMNS.items():
        clauses = ", ".join(
            f"ALTER COLUMN {column} TYPE {target_type} USING {column} AT TIME ZONE 'UTC'"
            for column in columns
        )
        op.execute(f"ALTER TABLE {table} {clauses}")


def upgrade() -> None:
    _alter("timestamptz")


def downgrade() -> None:
    _alter("timestamp")
