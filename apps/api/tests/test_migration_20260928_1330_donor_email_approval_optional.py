"""Donor email approval upgrade clears forced approval and re-seals valid v2 grants."""

import json
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import text

from alembic import command
from app.services.workflow_execution_authority import configuration_digest
from tests.test_migration_20260928_1300_workflow_fixed_trigger_subjects import (
    SEEDED_AT,
    _alembic_config,
)

REVISION = "20260928_1330_donor_email_approval_optional"
PREVIOUS = "20260928_1320_donor_workflow_source_canonical"
WORKFLOW_COLUMNS = (
    "organization_id, scope, owner_user_id, subject_type, trigger_type, trigger_config, "
    "conditions, condition_logic, actions"
)


def _email(requires_approval=True):
    return {
        "action_type": "send_email",
        "template_id": str(uuid4()),
        "recipients": "donor",
        "requires_approval": requires_approval,
    }


TASK = {"action_type": "create_task", "title": "Call", "requires_approval": True}


def _insert_form(connection, org_id, lead_kind):
    form_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO forms (id, organization_id, name, status, lead_kind) "
            "VALUES (:id, :org_id, :name, 'published', :lead_kind)"
        ),
        {
            "id": form_id,
            "org_id": org_id,
            "name": f"Form {form_id.hex[:6]}",
            "lead_kind": lead_kind,
        },
    )
    return form_id


def _insert_workflow(
    connection, org_id, *, subject_type, trigger_type, actions, trigger_config=None
):
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
                :trigger_type, CAST(:trigger_config AS jsonb), '[]'::jsonb, 'AND',
                CAST(:actions AS jsonb), TRUE, 0, :seeded_at
            )
            """
        ),
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": f"Workflow {workflow_id.hex[:6]}",
            "subject_type": subject_type,
            "trigger_type": trigger_type,
            "trigger_config": json.dumps(trigger_config or {}),
            "actions": json.dumps(actions),
            "seeded_at": SEEDED_AT,
        },
    )
    return workflow_id


def _digest(connection, workflow_id):
    row = (
        connection.execute(
            text(f"SELECT {WORKFLOW_COLUMNS} FROM automation_workflows WHERE id = :id"),
            {"id": workflow_id},
        )
        .mappings()
        .one()
    )
    return configuration_digest(SimpleNamespace(**row))


def _set_authority(connection, workflow_id, digest):
    authority = {
        "version": 2,
        "configuration_digest": digest,
        "permissions": ["manage_automation", "send_email"],
        "authorized_by_user_id": str(uuid4()),
    }
    connection.execute(
        text(
            "UPDATE automation_workflows SET execution_authority = CAST(:authority AS jsonb) "
            "WHERE id = :id"
        ),
        {"id": workflow_id, "authority": json.dumps(authority)},
    )
    return authority


def _insert_template(connection, *, subject_type, trigger_type, actions, draft=None):
    template_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO workflow_templates (
                id, name, icon, category, subject_type, trigger_type, trigger_config,
                conditions, condition_logic, actions, draft_config, is_global, usage_count
            ) VALUES (
                :id, :name, 'template', 'general', :subject_type, :trigger_type, '{}'::jsonb,
                '[]'::jsonb, 'AND', CAST(:actions AS jsonb), CAST(:draft AS jsonb), TRUE, 0
            )
            """
        ),
        {
            "id": template_id,
            "name": f"Template {template_id.hex[:6]}",
            "subject_type": subject_type,
            "trigger_type": trigger_type,
            "actions": json.dumps(actions),
            "draft": None if draft is None else json.dumps(draft),
        },
    )
    return template_id


def _draft(subject_type, trigger_type, actions, trigger_config=None):
    return {
        "name": "Draft",
        "subject_type": subject_type,
        "trigger_type": trigger_type,
        "trigger_config": trigger_config or {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": actions,
    }


def _cleared(actions):
    return [
        {**action, "requires_approval": False} if action["action_type"] == "send_email" else action
        for action in actions
    ]


def test_upgrade_clears_forced_donor_email_approval(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            org_id = uuid4()
            other_org_id = uuid4()
            for org, slug in ((org_id, "approval"), (other_org_id, "approval-other")):
                connection.execute(
                    text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": org, "name": slug, "slug": f"{slug}-{org.hex[:8]}"},
                )
            donor_form = _insert_form(connection, org_id, "egg_donor")
            surrogate_form = _insert_form(connection, org_id, "surrogate")
            foreign_surrogate_form = _insert_form(connection, other_org_id, "surrogate")

            donor_actions = [TASK, _email()]
            flipped = {
                "donor_subject": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="egg_donor",
                    trigger_type="donor_created",
                    actions=donor_actions,
                ),
                "donor_form_intake": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="form_submission",
                    trigger_type="form_submitted",
                    trigger_config={"form_id": str(donor_form)},
                    actions=donor_actions,
                ),
                "unscoped_intake": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="intake_lead",
                    trigger_type="intake_lead_created",
                    actions=donor_actions,
                ),
                "donor_lead_type": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="intake_lead",
                    trigger_type="intake_lead_created",
                    trigger_config={"lead_type": "sperm_donor"},
                    actions=donor_actions,
                ),
                "foreign_form": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="form_submission",
                    trigger_type="form_submitted",
                    trigger_config={"form_id": str(foreign_surrogate_form)},
                    actions=donor_actions,
                ),
                "valid_grant": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="sperm_donor",
                    trigger_type="donor_created",
                    actions=donor_actions,
                ),
                "stale_grant": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="sperm_donor",
                    trigger_type="donor_updated",
                    actions=donor_actions,
                ),
            }
            surrogate_actions = [TASK, _email()]
            untouched = {
                "surrogate": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="surrogate",
                    trigger_type="surrogate_created",
                    actions=surrogate_actions,
                ),
                "surrogate_form": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="form_submission",
                    trigger_type="form_submitted",
                    trigger_config={"form_id": str(surrogate_form)},
                    actions=surrogate_actions,
                ),
                "surrogate_lead_kind": _insert_workflow(
                    connection,
                    org_id,
                    subject_type="form_submission",
                    trigger_type="form_submitted",
                    trigger_config={"lead_kind": "surrogate"},
                    actions=surrogate_actions,
                ),
            }
            valid_grant = _set_authority(
                connection, flipped["valid_grant"], _digest(connection, flipped["valid_grant"])
            )
            stale_grant = _set_authority(connection, flipped["stale_grant"], "0" * 64)

            donor_template = _insert_template(
                connection,
                subject_type="egg_donor",
                trigger_type="donor_created",
                actions=donor_actions,
                draft=_draft("egg_donor", "donor_created", donor_actions),
            )
            intake_template = _insert_template(
                connection,
                subject_type=None,
                trigger_type="form_submitted",
                actions=donor_actions,
                draft=_draft(
                    "form_submission",
                    "form_submitted",
                    surrogate_actions,
                    trigger_config={"lead_kind": "surrogate"},
                ),
            )
            surrogate_template = _insert_template(
                connection,
                subject_type="surrogate",
                trigger_type="surrogate_created",
                actions=surrogate_actions,
                draft=_draft("egg_donor", "donor_created", donor_actions),
            )

            command.upgrade(config, REVISION)
            first = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, actions, execution_authority, updated_at "
                        "FROM automation_workflows WHERE organization_id = :org_id"
                    ),
                    {"org_id": org_id},
                )
            }
            command.downgrade(config, PREVIOUS)
            command.upgrade(config, REVISION)
            rows = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, actions, execution_authority, updated_at "
                        "FROM automation_workflows WHERE organization_id = :org_id"
                    ),
                    {"org_id": org_id},
                )
            }

            for workflow_id in flipped.values():
                assert rows[workflow_id].actions == _cleared(donor_actions)
                assert rows[workflow_id].updated_at > SEEDED_AT
                assert rows[workflow_id].updated_at == first[workflow_id].updated_at
            for workflow_id in untouched.values():
                assert rows[workflow_id].actions == surrogate_actions
                assert rows[workflow_id].updated_at == SEEDED_AT
                assert rows[workflow_id].execution_authority is None

            resealed = rows[flipped["valid_grant"]].execution_authority
            assert resealed == {
                **valid_grant,
                "configuration_digest": _digest(connection, flipped["valid_grant"]),
            }
            assert resealed["configuration_digest"] != valid_grant["configuration_digest"]
            assert rows[flipped["stale_grant"]].execution_authority == stale_grant
            assert rows[flipped["donor_subject"]].execution_authority is None

            templates = {
                row.id: row
                for row in connection.execute(
                    text(
                        "SELECT id, actions, draft_config FROM workflow_templates "
                        "WHERE id = ANY(:ids)"
                    ),
                    {"ids": [donor_template, intake_template, surrogate_template]},
                )
            }
            assert templates[donor_template].actions == _cleared(donor_actions)
            assert templates[donor_template].draft_config["actions"] == _cleared(donor_actions)
            assert templates[intake_template].actions == _cleared(donor_actions)
            assert templates[intake_template].draft_config["actions"] == surrogate_actions
            assert templates[surrogate_template].actions == surrogate_actions
            assert templates[surrogate_template].draft_config["actions"] == _cleared(donor_actions)
        finally:
            transaction.rollback()
