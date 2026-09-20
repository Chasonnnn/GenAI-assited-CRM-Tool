"""Preserve workflow-template draft subjects across the subject-type migration."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "20260919_0300_ops_cli_login"
REVISION = "20260920_0100_workflow_template_subject_type"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _insert_template(
    connection,
    *,
    stored_trigger_type: str,
    draft_trigger_type: str,
    name: str,
) -> UUID:
    template_id = uuid4()
    draft_config = {
        "name": name,
        "description": None,
        "icon": "template",
        "category": "general",
        "trigger_type": draft_trigger_type,
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [],
    }
    connection.execute(
        text(
            """
            INSERT INTO workflow_templates (
                id, name, icon, category, trigger_type, trigger_config,
                conditions, condition_logic, actions, draft_config,
                is_global, usage_count
            ) VALUES (
                :id, :name, 'template', 'general', :trigger_type, '{}'::jsonb,
                '[]'::jsonb, 'AND', '[]'::jsonb, CAST(:draft_config AS jsonb),
                TRUE, 0
            )
            """
        ),
        {
            "id": template_id,
            "name": name,
            "trigger_type": stored_trigger_type,
            "draft_config": json.dumps(draft_config),
        },
    )
    return template_id


def test_workflow_template_subject_upgrade_and_downgrade_preserve_drafts(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PREVIOUS_REVISION)
            template_ids = {
                "form_draft": _insert_template(
                    connection,
                    stored_trigger_type="task_completed",
                    draft_trigger_type="form_submitted",
                    name="Legacy form draft",
                ),
                "surrogate_draft": _insert_template(
                    connection,
                    stored_trigger_type="form_submitted",
                    draft_trigger_type="task_completed",
                    name="Legacy surrogate draft",
                ),
                "donor_draft": _insert_template(
                    connection,
                    stored_trigger_type="task_completed",
                    draft_trigger_type="donor_created",
                    name="Ambiguous donor draft",
                ),
                "donor_published": _insert_template(
                    connection,
                    stored_trigger_type="donor_created",
                    draft_trigger_type="task_completed",
                    name="Ambiguous donor published template",
                ),
            }

            command.upgrade(config, REVISION)

            upgraded = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, subject_type, draft_config "
                        "FROM workflow_templates WHERE id = ANY(:ids)"
                    ),
                    {"ids": list(template_ids.values())},
                )
            }
            form_row = upgraded[template_ids["form_draft"]]
            assert form_row.subject_type == "surrogate"
            assert form_row.draft_config["subject_type"] == "form_submission"

            surrogate_row = upgraded[template_ids["surrogate_draft"]]
            assert surrogate_row.subject_type == "form_submission"
            assert surrogate_row.draft_config["subject_type"] == "surrogate"

            donor_draft_row = upgraded[template_ids["donor_draft"]]
            assert donor_draft_row.subject_type == "surrogate"
            assert "subject_type" in donor_draft_row.draft_config
            assert donor_draft_row.draft_config["subject_type"] is None

            donor_published_row = upgraded[template_ids["donor_published"]]
            assert donor_published_row.subject_type is None
            assert donor_published_row.draft_config["subject_type"] == "surrogate"

            command.downgrade(config, PREVIOUS_REVISION)

            assert "subject_type" not in {
                column["name"] for column in inspect(connection).get_columns("workflow_templates")
            }
            downgraded_drafts = connection.execute(
                text("SELECT draft_config FROM workflow_templates WHERE id = ANY(:ids)"),
                {"ids": list(template_ids.values())},
            ).scalars()
            assert all("subject_type" not in draft for draft in downgraded_drafts)
        finally:
            transaction.rollback()
