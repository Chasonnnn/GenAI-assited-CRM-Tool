from datetime import date, datetime

from app.db.enums import WorkflowTriggerType
from app.db.models import AutomationWorkflow
from app.services import task_service, workflow_triggers


def test_trigger_task_due_sweep_uses_task_service_window_query(db, test_org, monkeypatch):
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Task Due Sweep",
        trigger_type=WorkflowTriggerType.TASK_DUE.value,
        trigger_config={"hours_before": 24},
        is_enabled=True,
    )
    db.add(workflow)
    db.commit()

    called: dict[str, object] = {}

    def fake_iter(db_arg, org_id, window_start, window_end, batch_size=1000):
        called["args"] = (org_id, window_start, window_end, batch_size)
        return iter([])

    monkeypatch.setattr(task_service, "iter_tasks_due_in_window", fake_iter, raising=False)

    workflow_triggers.trigger_task_due_sweep(db, test_org.id)

    assert "args" in called
    assert called["args"][0] == test_org.id
    assert isinstance(called["args"][1], datetime)
    assert isinstance(called["args"][2], datetime)


def test_trigger_task_overdue_sweep_uses_task_service_query(db, test_org, monkeypatch):
    called: dict[str, object] = {}

    def fake_iter(db_arg, org_id, today, batch_size=1000):
        called["args"] = (org_id, today, batch_size)
        return iter([])

    monkeypatch.setattr(task_service, "iter_overdue_tasks", fake_iter, raising=False)

    workflow_triggers.trigger_task_overdue_sweep(db, test_org.id)

    assert "args" in called
    assert called["args"][0] == test_org.id
    assert isinstance(called["args"][1], date)
