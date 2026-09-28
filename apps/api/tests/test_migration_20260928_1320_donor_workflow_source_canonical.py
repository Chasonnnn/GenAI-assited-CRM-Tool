"""Donor workflow source upgrade stores canonical source values in update_field actions."""

import json
from uuid import uuid4

from sqlalchemy import text

from alembic import command
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import (
    SEEDED_AT,
    _alembic_config,
)

REVISION = "20260928_1320_donor_workflow_source_canonical"
PREVIOUS = "20260928_1310_donor_source_canonical"


def _source_action(value):
    return {"action_type": "update_field", "field": "source", "value": value}


def _insert_workflow(connection, org_id, actions):
    workflow_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO automation_workflows (
                id, organization_id, name, icon, schema_version, subject_type,
                trigger_type, trigger_config, conditions, condition_logic, actions,
                is_enabled, run_count, updated_at
            ) VALUES (
                :id, :org_id, :name, 'workflow', 1, 'egg_donor',
                'donor_created', '{}'::jsonb, '[]'::jsonb, 'AND', CAST(:actions AS jsonb),
                TRUE, 0, :seeded_at
            )
            """
        ),
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": f"Donor source {workflow_id.hex[:6]}",
            "actions": json.dumps(actions),
            "seeded_at": SEEDED_AT,
        },
    )
    return workflow_id


def _insert_template(connection, actions, draft_actions):
    template_id = uuid4()
    draft_config = {
        "name": "Draft",
        "trigger_type": "donor_created",
        "subject_type": "egg_donor",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": draft_actions,
    }
    connection.execute(
        text(
            """
            INSERT INTO workflow_templates (
                id, name, icon, category, subject_type, trigger_type, trigger_config,
                conditions, condition_logic, actions, draft_config, is_global, usage_count
            ) VALUES (
                :id, :name, 'template', 'general', 'egg_donor', 'donor_created', '{}'::jsonb,
                '[]'::jsonb, 'AND', CAST(:actions AS jsonb), CAST(:draft_config AS jsonb),
                TRUE, 0
            )
            """
        ),
        {
            "id": template_id,
            "name": f"Template {template_id.hex[:6]}",
            "actions": json.dumps(actions),
            "draft_config": json.dumps(draft_config),
        },
    )
    return template_id


def test_upgrade_canonicalizes_donor_source_in_workflow_actions(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            org_id = uuid4()
            connection.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                {"id": org_id, "name": "Source Org", "slug": f"source-{org_id.hex[:8]}"},
            )
            note = {"action_type": "add_note", "content": "Facebook"}
            state = {"action_type": "update_field", "field": "state", "value": "Facebook"}
            cases = {
                "Facebook": "other",
                " Google ": "google",
                "META": "meta",
                "shared_intake": "website",
                "referral": "referral",
            }
            workflows = {
                _insert_workflow(
                    connection, org_id, [note, _source_action(source), state]
                ): expected
                for source, expected in cases.items()
            }
            untouched = _insert_workflow(connection, org_id, [note, state])
            template = _insert_template(
                connection, [_source_action("Facebook")], [note, _source_action("Website")]
            )

            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)

            rows = dict(
                connection.execute(
                    text(
                        "SELECT id, actions FROM automation_workflows "
                        "WHERE organization_id = :org_id"
                    ),
                    {"org_id": org_id},
                ).all()
            )
            for workflow_id, expected in workflows.items():
                assert rows[workflow_id] == [note, _source_action(expected), state]
            assert rows[untouched] == [note, state]
            updated = connection.execute(
                text(
                    "SELECT id FROM automation_workflows "
                    "WHERE organization_id = :org_id AND updated_at > :seeded_at"
                ),
                {"org_id": org_id, "seeded_at": SEEDED_AT},
            ).scalars()
            assert set(updated) == {
                workflow_id for workflow_id, expected in workflows.items() if expected != "referral"
            }
            template_actions, draft_config = connection.execute(
                text("SELECT actions, draft_config FROM workflow_templates WHERE id = :id"),
                {"id": template},
            ).one()
            assert template_actions == [_source_action("other")]
            assert draft_config["actions"] == [note, _source_action("website")]
        finally:
            transaction.rollback()
