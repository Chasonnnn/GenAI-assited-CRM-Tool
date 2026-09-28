"""Repair workflows whose subject does not match their fixed-subject trigger.

The workflow builder saved form, intake lead, match and appointment workflows
with the builder's record type (usually 'surrogate'). The engine matches on
subject_type, so these rows never ran. Rows are moved to the trigger's subject
and disabled so they cannot start running without an explicit re-enable.
Workflows left on a fixed subject after their trigger changed return to
'surrogate' and are disabled the same way. Donor subjects are not touched.
Templates get the same subject repair (the 20260920 backfill mapped the
retired match_rejected trigger instead of match_declined / match_cancelled).

Downgrade is a no-op: the previous subjects were invalid and never executed.

Revision ID: 20260928_1300_workflow_fixed_trigger_subjects
Revises: 20260928_1200_ip_stage_permission
"""

import sqlalchemy as sa

from alembic import op

revision = "20260928_1300_workflow_fixed_trigger_subjects"
down_revision = "20260928_1200_ip_stage_permission"
branch_labels = None
depends_on = None

# Mirrors app.services.workflow_service.LEGACY_TRIGGER_SUBJECT_TYPES.
FIXED_TRIGGER_SUBJECT_TYPES = {
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_declined": "match",
    "match_cancelled": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
}
FIXED_SUBJECT_TYPES = tuple(sorted(set(FIXED_TRIGGER_SUBJECT_TYPES.values())))
FIXED_TRIGGER_TYPES = tuple(sorted(FIXED_TRIGGER_SUBJECT_TYPES))
DONOR_SUBJECT_TYPES = ("egg_donor", "sperm_donor")


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    for trigger_type, subject_type in FIXED_TRIGGER_SUBJECT_TYPES.items():
        op.execute(
            sa.text(
                "UPDATE automation_workflows "
                "SET subject_type = :subject_type, is_enabled = FALSE, updated_at = now() "
                "WHERE trigger_type = :trigger_type "
                "AND subject_type <> :subject_type "
                "AND subject_type NOT IN :donor_subjects"
            ).bindparams(
                sa.bindparam("donor_subjects", expanding=True, value=DONOR_SUBJECT_TYPES),
                subject_type=subject_type,
                trigger_type=trigger_type,
            )
        )
    op.execute(
        sa.text(
            "UPDATE automation_workflows "
            "SET subject_type = 'surrogate', is_enabled = FALSE, updated_at = now() "
            "WHERE subject_type IN :fixed_subjects "
            "AND trigger_type NOT IN :fixed_triggers"
        ).bindparams(
            sa.bindparam("fixed_subjects", expanding=True, value=FIXED_SUBJECT_TYPES),
            sa.bindparam("fixed_triggers", expanding=True, value=FIXED_TRIGGER_TYPES),
        )
    )

    for trigger_type, subject_type in FIXED_TRIGGER_SUBJECT_TYPES.items():
        op.execute(
            sa.text(
                "UPDATE workflow_templates SET subject_type = :subject_type "
                "WHERE trigger_type = :trigger_type "
                "AND subject_type IS NOT NULL "
                "AND subject_type <> :subject_type "
                "AND subject_type NOT IN :donor_subjects"
            ).bindparams(
                sa.bindparam("donor_subjects", expanding=True, value=DONOR_SUBJECT_TYPES),
                subject_type=subject_type,
                trigger_type=trigger_type,
            )
        )
        op.execute(
            sa.text(
                "UPDATE workflow_templates "
                "SET draft_config = draft_config || "
                "jsonb_build_object('subject_type', CAST(:subject_type AS text)) "
                "WHERE draft_config IS NOT NULL "
                "AND draft_config->>'trigger_type' = :trigger_type "
                "AND draft_config->>'subject_type' IS NOT NULL "
                "AND draft_config->>'subject_type' <> :subject_type "
                "AND draft_config->>'subject_type' NOT IN :donor_subjects"
            ).bindparams(
                sa.bindparam("donor_subjects", expanding=True, value=DONOR_SUBJECT_TYPES),
                subject_type=subject_type,
                trigger_type=trigger_type,
            )
        )
    op.execute(
        sa.text(
            "UPDATE workflow_templates SET subject_type = 'surrogate' "
            "WHERE subject_type IN :fixed_subjects "
            "AND trigger_type NOT IN :fixed_triggers"
        ).bindparams(
            sa.bindparam("fixed_subjects", expanding=True, value=FIXED_SUBJECT_TYPES),
            sa.bindparam("fixed_triggers", expanding=True, value=FIXED_TRIGGER_TYPES),
        )
    )
    op.execute(
        sa.text(
            "UPDATE workflow_templates "
            "SET draft_config = draft_config || jsonb_build_object('subject_type', 'surrogate') "
            "WHERE draft_config IS NOT NULL "
            "AND draft_config->>'subject_type' IN :fixed_subjects "
            "AND draft_config->>'trigger_type' NOT IN :fixed_triggers"
        ).bindparams(
            sa.bindparam("fixed_subjects", expanding=True, value=FIXED_SUBJECT_TYPES),
            sa.bindparam("fixed_triggers", expanding=True, value=FIXED_TRIGGER_TYPES),
        )
    )


def downgrade() -> None:
    pass
