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


def test_workflow_seeding_batches_stage_reads(db, test_org, test_user, default_stage):
    from sqlalchemy import event

    reads = []

    def record_read(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "FROM pipeline_stages" in statement:
            reads.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", record_read)
    try:
        assert seed_system_workflows(db, test_org.id, test_user.id) > 0
    finally:
        event.remove(connection, "before_cursor_execute", record_read)
    assert len(reads) <= 5  # Pipeline setup plus one lookup for all workflow stage references.
    workflows = db.query(AutomationWorkflow).filter_by(organization_id=test_org.id).all()
    scoped = [row for row in workflows if row.trigger_config.get("to_stage_id")]
    assert scoped
    for row in scoped:
        assert row.trigger_config["to_stage_key"]
    assert seed_system_workflows(db, test_org.id, test_user.id) == 0


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

    original_resolve_stages_bulk = pipeline_service.resolve_stages_bulk

    def resolve_without_lost(db_session, org_id, pipeline_id, refs):
        stages = original_resolve_stages_bulk(db_session, org_id, pipeline_id, refs)
        return [None if ref == "lost" else stage for ref, stage in zip(refs, stages)]

    monkeypatch.setattr(pipeline_service, "resolve_stages_bulk", resolve_without_lost)

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

    monkeypatch.setattr(pipeline_service, "resolve_stages_bulk", original_resolve_stages_bulk)
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
