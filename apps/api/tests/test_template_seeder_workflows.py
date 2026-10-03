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
