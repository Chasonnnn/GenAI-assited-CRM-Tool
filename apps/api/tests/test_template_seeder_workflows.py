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
