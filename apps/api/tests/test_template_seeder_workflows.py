from __future__ import annotations

from app.db.models import AutomationWorkflow
from app.services.template_seeder import seed_system_workflows


def test_seed_system_workflows_includes_zapier_meta_conversion_sync(db, test_org, test_user):
    created_count = seed_system_workflows(db, test_org.id, test_user.id)
    assert created_count > 0

    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key == "zapier_meta_conversion_sync",
        )
        .first()
    )
    assert workflow is not None
    assert workflow.trigger_type == "status_changed"
    assert workflow.trigger_config == {}
    assert workflow.is_enabled is False
    assert workflow.requires_review is True
    assert workflow.actions
    assert workflow.actions[0]["action_type"] == "send_zapier_conversion_event"

    created_again = seed_system_workflows(db, test_org.id, test_user.id)
    assert created_again == 0


def _stage_scoped_system_keys() -> set[str]:
    from app.services.template_seeder import SYSTEM_WORKFLOWS

    return {
        workflow["system_key"]
        for workflow in SYSTEM_WORKFLOWS
        if workflow.get("trigger_type") == "status_changed"
        and (
            workflow.get("trigger_config", {}).get("to_stage_slug")
            or workflow.get("trigger_config", {}).get("from_stage_slug")
        )
    }


def test_seed_system_workflows_binds_stage_scoped_triggers_to_stages(db, test_org, test_user):
    seed_system_workflows(db, test_org.id, test_user.id)

    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key.in_(_stage_scoped_system_keys()),
        )
        .all()
    )
    assert {workflow.system_key for workflow in workflows} == _stage_scoped_system_keys()
    for workflow in workflows:
        assert workflow.trigger_config.get("to_stage_id")
        assert workflow.trigger_config.get("to_stage_key")
        assert "to_stage_slug" not in workflow.trigger_config


def test_seed_system_workflows_skips_stage_trigger_when_stage_is_missing(
    db, test_org, test_user, monkeypatch
):
    from app.services import pipeline_service

    original_resolve_stage = pipeline_service.resolve_stage

    def resolve_without_lost(db_session, pipeline_id, ref):
        if ref == "lost":
            return None
        return original_resolve_stage(db_session, pipeline_id, ref)

    monkeypatch.setattr(pipeline_service, "resolve_stage", resolve_without_lost)

    seed_system_workflows(db, test_org.id, test_user.id)

    seeded_keys = {
        row[0]
        for row in db.query(AutomationWorkflow.system_key)
        .filter(AutomationWorkflow.organization_id == test_org.id)
        .all()
    }
    # An unresolved stage must not widen the trigger to every stage change.
    assert "lead_marked_lost" not in seeded_keys
    assert "application_followup" in seeded_keys

    monkeypatch.setattr(pipeline_service, "resolve_stage", original_resolve_stage)
    assert seed_system_workflows(db, test_org.id, test_user.id) == 1
    assert (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.system_key == "lead_marked_lost",
        )
        .one()
        .trigger_config.get("to_stage_key")
        == "lost"
    )


def test_every_seeded_system_workflow_passes_workflow_validation(db, test_org, test_user):
    from app.db.enums import WorkflowTriggerType
    from app.schemas.workflow import Condition
    from app.services import workflow_service
    from app.services.template_seeder import seed_system_templates
    from app.services.workflow_definition_rules import validate_trigger_config

    seed_system_templates(db, test_org.id)
    seed_system_workflows(db, test_org.id, test_user.id)
    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == test_org.id,
            AutomationWorkflow.is_system_workflow.is_(True),
        )
        .all()
    )
    assert workflows

    options = workflow_service.get_workflow_options(db, test_org.id, workflow_scope="org")
    invalid: dict[str, str] = {}
    for workflow in workflows:
        trigger_type = WorkflowTriggerType(workflow.trigger_type)
        try:
            workflow_service._validate_subject_trigger(workflow.subject_type, trigger_type)
            allowed_actions = set(options.action_types_by_trigger[trigger_type.value])
            for action in workflow.actions:
                if action["action_type"] not in allowed_actions:
                    raise ValueError(f"{action['action_type']} is not offered for this trigger")
            validate_trigger_config(trigger_type, workflow.trigger_config)
            for condition in workflow.conditions:
                Condition.model_validate(condition)
            workflow_service._validate_trigger_conditions(
                trigger_type, workflow.subject_type, workflow.conditions
            )
            for action in workflow.actions:
                workflow_service._validate_action_config(
                    db,
                    test_org.id,
                    dict(action),
                    workflow_scope="org",
                    trigger_type=trigger_type,
                    subject_type=workflow.subject_type,
                )
        except ValueError as exc:
            invalid[workflow.system_key] = str(exc)
    assert invalid == {}
