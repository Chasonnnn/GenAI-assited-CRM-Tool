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
