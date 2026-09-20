"""Add explicit subject_type to workflow templates.

Legacy rows are backfilled from their trigger type using the same mapping
workflow creation applies (LEGACY_TRIGGER_SUBJECT_TYPES). Donor-trigger
templates stay NULL: their exact donor subtype (egg_donor vs sperm_donor)
cannot be inferred and they must be repaired explicitly before use.

Revision ID: 20260920_0100_workflow_template_subject_type
Revises: 20260919_0300_ops_cli_login
"""

import sqlalchemy as sa

from alembic import op

revision = "20260920_0100_workflow_template_subject_type"
down_revision = "20260919_0300_ops_cli_login"
branch_labels = None
depends_on = None

# Mirrors app.services.workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES.
LEGACY_TRIGGER_SUBJECT_TYPES = {
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_rejected": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
}

DONOR_ONLY_TRIGGER_TYPES = (
    "donor_created",
    "donor_stage_changed",
    "donor_assigned",
    "donor_updated",
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.add_column(
        "workflow_templates",
        sa.Column("subject_type", sa.String(50), nullable=True),
    )
    for trigger_type, subject_type in LEGACY_TRIGGER_SUBJECT_TYPES.items():
        op.execute(
            sa.text(
                "UPDATE workflow_templates SET subject_type = :subject_type "
                "WHERE trigger_type = :trigger_type"
            ).bindparams(subject_type=subject_type, trigger_type=trigger_type)
        )
    donor_triggers = ", ".join(f"'{trigger}'" for trigger in DONOR_ONLY_TRIGGER_TYPES)
    op.execute(
        "UPDATE workflow_templates SET subject_type = 'surrogate' "
        f"WHERE subject_type IS NULL AND trigger_type NOT IN ({donor_triggers})"
    )


def downgrade() -> None:
    op.drop_column("workflow_templates", "subject_type")
