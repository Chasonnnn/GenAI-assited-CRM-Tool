"""The fixed-trigger subject repair moves and disables only mismatched workflows."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20260928_1200_ip_stage_permission"
REVISION = "20260928_1300_workflow_fixed_trigger_subjects"
SEEDED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _insert_workflow(
    connection, *, org_id: UUID, subject_type: str, trigger_type: str, enabled: bool = True
) -> UUID:
    workflow_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO automation_workflows (
                id, organization_id, name, icon, schema_version, subject_type,
                trigger_type, trigger_config, conditions, condition_logic, actions,
                is_enabled, run_count, updated_at
            ) VALUES (
                :id, :org_id, :name, 'workflow', 1, :subject_type,
                :trigger_type, '{}'::jsonb, '[]'::jsonb, 'AND', '[]'::jsonb,
                :enabled, 0, :seeded_at
            )
            """
        ),
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": f"{subject_type} {trigger_type} {workflow_id.hex[:6]}",
            "subject_type": subject_type,
            "trigger_type": trigger_type,
            "enabled": enabled,
            "seeded_at": SEEDED_AT,
        },
    )
    return workflow_id


def _insert_template(
    connection,
    *,
    subject_type: str | None,
    trigger_type: str,
    draft_subject_type: str | None,
    draft_trigger_type: str,
) -> UUID:
    template_id = uuid4()
    draft_config = {
        "name": "Draft",
        "trigger_type": draft_trigger_type,
        "subject_type": draft_subject_type,
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [],
    }
    connection.execute(
        text(
            """
            INSERT INTO workflow_templates (
                id, name, icon, category, subject_type, trigger_type, trigger_config,
                conditions, condition_logic, actions, draft_config, is_global, usage_count
            ) VALUES (
                :id, :name, 'template', 'general', :subject_type, :trigger_type, '{}'::jsonb,
                '[]'::jsonb, 'AND', '[]'::jsonb, CAST(:draft_config AS jsonb), TRUE, 0
            )
            """
        ),
        {
            "id": template_id,
            "name": f"Template {template_id.hex[:6]}",
            "subject_type": subject_type,
            "trigger_type": trigger_type,
            "draft_config": json.dumps(draft_config),
        },
    )
    return template_id


def test_upgrade_repairs_and_disables_mismatched_fixed_trigger_workflows(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            org_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Fixed Subject Org", "slug": f"fixed-{org_id.hex[:8]}"},
            )
            workflows = {
                "form_mismatch": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="surrogate",
                    trigger_type="form_submitted",
                ),
                "match_mismatch": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="surrogate",
                    trigger_type="match_cancelled",
                ),
                "appointment_cross": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="match",
                    trigger_type="appointment_scheduled",
                ),
                "stale_fixed_subject": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="form_submission",
                    trigger_type="status_changed",
                ),
                "form_correct": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="form_submission",
                    trigger_type="form_submitted",
                ),
                "surrogate_correct": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="surrogate",
                    trigger_type="status_changed",
                ),
                "donor_untouched": _insert_workflow(
                    connection,
                    org_id=org_id,
                    subject_type="egg_donor",
                    trigger_type="donor_created",
                ),
            }
            templates = {
                "declined_mismatch": _insert_template(
                    connection,
                    subject_type="surrogate",
                    trigger_type="match_declined",
                    draft_subject_type="surrogate",
                    draft_trigger_type="match_cancelled",
                ),
                "stale_template": _insert_template(
                    connection,
                    subject_type="appointment",
                    trigger_type="note_added",
                    draft_subject_type="intake_lead",
                    draft_trigger_type="task_due",
                ),
                "donor_repair_required": _insert_template(
                    connection,
                    subject_type=None,
                    trigger_type="donor_created",
                    draft_subject_type=None,
                    draft_trigger_type="donor_created",
                ),
                "template_correct": _insert_template(
                    connection,
                    subject_type="intake_lead",
                    trigger_type="intake_lead_created",
                    draft_subject_type="form_submission",
                    draft_trigger_type="form_submitted",
                ),
            }

            command.upgrade(config, REVISION)

            rows = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, subject_type, is_enabled, updated_at "
                        "FROM automation_workflows WHERE id = ANY(:ids)"
                    ),
                    {"ids": list(workflows.values())},
                )
            }
            expected = {
                "form_mismatch": ("form_submission", False),
                "match_mismatch": ("match", False),
                "appointment_cross": ("appointment", False),
                "stale_fixed_subject": ("surrogate", False),
                "form_correct": ("form_submission", True),
                "surrogate_correct": ("surrogate", True),
                "donor_untouched": ("egg_donor", True),
            }
            for key, (subject_type, enabled) in expected.items():
                row = rows[workflows[key]]
                assert (row.subject_type, row.is_enabled) == (subject_type, enabled), key
            assert rows[workflows["form_mismatch"]].updated_at > SEEDED_AT
            assert rows[workflows["form_correct"]].updated_at == SEEDED_AT

            template_rows = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, subject_type, draft_config "
                        "FROM workflow_templates WHERE id = ANY(:ids)"
                    ),
                    {"ids": list(templates.values())},
                )
            }
            declined = template_rows[templates["declined_mismatch"]]
            assert declined.subject_type == "match"
            assert declined.draft_config["subject_type"] == "match"
            stale = template_rows[templates["stale_template"]]
            assert stale.subject_type == "surrogate"
            assert stale.draft_config["subject_type"] == "surrogate"
            donor = template_rows[templates["donor_repair_required"]]
            assert donor.subject_type is None
            assert donor.draft_config["subject_type"] is None
            correct = template_rows[templates["template_correct"]]
            assert correct.subject_type == "intake_lead"
            assert correct.draft_config["subject_type"] == "form_submission"
        finally:
            transaction.rollback()
