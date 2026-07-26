from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import WorkflowTriggerType
from app.db.models import AutomationWorkflow
from app.services import task_service, workflow_triggers


def test_scheduled_sweep_executes_only_the_workflow_whose_cron_matches(db, test_org, monkeypatch):
    due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Due schedule",
        trigger_type=WorkflowTriggerType.SCHEDULED.value,
        trigger_config={"cron": "due", "timezone": "UTC"},
        actions=[],
        is_enabled=True,
    )
    not_due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Not due schedule",
        trigger_type=WorkflowTriggerType.SCHEDULED.value,
        trigger_config={"cron": "not-due", "timezone": "UTC"},
        actions=[],
        is_enabled=True,
    )
    db.add_all([due, not_due])
    db.commit()

    surrogate = SimpleNamespace(
        id=uuid4(),
        owner_type="user",
        owner_id=uuid4(),
    )
    executed: list[AutomationWorkflow] = []

    monkeypatch.setattr(
        workflow_triggers,
        "_should_run_cron",
        lambda cron, _now, _tz: cron == "due",
    )
    monkeypatch.setattr(
        workflow_triggers, "_iter_surrogates", lambda *_args, **_kwargs: [surrogate]
    )
    monkeypatch.setattr(
        workflow_triggers.engine,
        "trigger",
        lambda **_kwargs: pytest.fail("a sweep must not fan out through engine.trigger"),
    )

    def fake_execute_workflow(*, workflow, **_kwargs):
        executed.append(workflow)
        return None

    monkeypatch.setattr(workflow_triggers.engine, "execute_workflow", fake_execute_workflow)

    workflow_triggers.trigger_scheduled_workflows(db, test_org.id)

    assert [workflow.id for workflow in executed] == [due.id]


def test_personal_scheduled_workflow_only_executes_for_its_owners_surrogate(
    db, test_org, test_user, monkeypatch
):
    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Personal schedule",
        trigger_type=WorkflowTriggerType.SCHEDULED.value,
        trigger_config={"cron": "due", "timezone": "UTC"},
        scope="personal",
        owner_user_id=test_user.id,
        actions=[],
        is_enabled=True,
    )
    db.add(workflow)
    db.commit()

    owned = SimpleNamespace(id=uuid4(), owner_type="user", owner_id=test_user.id)
    other = SimpleNamespace(id=uuid4(), owner_type="user", owner_id=uuid4())
    executed_entity_ids = []

    monkeypatch.setattr(workflow_triggers, "_should_run_cron", lambda *_args: True)
    monkeypatch.setattr(
        workflow_triggers,
        "_iter_surrogates",
        lambda *_args, **_kwargs: [owned, other],
    )

    def fake_execute_workflow(*, entity_id, **_kwargs):
        executed_entity_ids.append(entity_id)
        return None

    monkeypatch.setattr(workflow_triggers.engine, "execute_workflow", fake_execute_workflow)

    workflow_triggers.trigger_scheduled_workflows(db, test_org.id)

    assert executed_entity_ids == [owned.id]


def test_inactivity_sweep_executes_only_the_workflow_whose_threshold_matches(
    db, test_org, monkeypatch
):
    due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Seven day inactivity",
        trigger_type=WorkflowTriggerType.INACTIVITY.value,
        trigger_config={"days": 7},
        actions=[],
        is_enabled=True,
    )
    not_due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Thirty day inactivity",
        trigger_type=WorkflowTriggerType.INACTIVITY.value,
        trigger_config={"days": 30},
        actions=[],
        is_enabled=True,
    )
    db.add_all([due, not_due])
    db.commit()

    surrogate = SimpleNamespace(
        id=uuid4(),
        owner_type="user",
        owner_id=uuid4(),
        updated_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    executed: list[AutomationWorkflow] = []

    def fake_iter(_db, _org_id, updated_before=None, **_kwargs):
        assert updated_before is not None
        if updated_before > datetime.now(timezone.utc) - timedelta(days=20):
            return [surrogate]
        return []

    monkeypatch.setattr(workflow_triggers, "_iter_surrogates", fake_iter)
    monkeypatch.setattr(
        workflow_triggers.engine,
        "trigger",
        lambda **_kwargs: pytest.fail("an inactivity sweep must not fan out"),
    )

    def fake_execute_workflow(*, workflow, **_kwargs):
        executed.append(workflow)
        return None

    monkeypatch.setattr(workflow_triggers.engine, "execute_workflow", fake_execute_workflow)

    workflow_triggers.trigger_inactivity_workflows(db, test_org.id)

    assert [workflow.id for workflow in executed] == [due.id]


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


def test_task_due_sweep_executes_only_the_workflow_whose_window_matches(db, test_org, monkeypatch):
    due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Due in one day",
        trigger_type=WorkflowTriggerType.TASK_DUE.value,
        trigger_config={"hours_before": 24},
        actions=[],
        is_enabled=True,
    )
    not_due = AutomationWorkflow(
        organization_id=test_org.id,
        name="Due in three days",
        trigger_type=WorkflowTriggerType.TASK_DUE.value,
        trigger_config={"hours_before": 72},
        actions=[],
        is_enabled=True,
    )
    db.add_all([due, not_due])
    db.commit()

    task = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        title="Follow up",
        due_date=date.today() + timedelta(days=1),
        surrogate_id=None,
    )
    executed: list[AutomationWorkflow] = []

    def fake_iter(_db, _org_id, window_start, _window_end, **_kwargs):
        hours_until_window = (
            window_start - datetime.now(window_start.tzinfo)
        ).total_seconds() / 3600
        if hours_until_window < 48:
            return [task]
        return []

    monkeypatch.setattr(task_service, "iter_tasks_due_in_window", fake_iter)
    monkeypatch.setattr(
        workflow_triggers.engine,
        "trigger",
        lambda **_kwargs: pytest.fail("a task-due sweep must not fan out"),
    )

    def fake_execute_workflow(*, workflow, **_kwargs):
        executed.append(workflow)
        return None

    monkeypatch.setattr(workflow_triggers.engine, "execute_workflow", fake_execute_workflow)

    workflow_triggers.trigger_task_due_sweep(db, test_org.id)

    assert [workflow.id for workflow in executed] == [due.id]


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


@pytest.mark.asyncio
async def test_workflow_sweep_job_preserves_the_scheduled_evaluation_time(
    db, test_org, monkeypatch
):
    from app.jobs.handlers.workflows import process_workflow_sweep

    evaluated_at = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    job = SimpleNamespace(
        organization_id=test_org.id,
        payload={
            "org_id": str(test_org.id),
            "sweep_type": "scheduled",
            "evaluated_at": evaluated_at.isoformat(),
        },
    )
    called: dict[str, object] = {}

    def fake_trigger(_db, org_id, *, evaluated_at=None):
        called["org_id"] = org_id
        called["evaluated_at"] = evaluated_at

    monkeypatch.setattr(workflow_triggers, "trigger_scheduled_workflows", fake_trigger)

    await process_workflow_sweep(db, job)

    assert called == {"org_id": test_org.id, "evaluated_at": evaluated_at}


@pytest.mark.asyncio
async def test_workflow_sweep_job_rejects_payload_org_mismatch(db, test_org):
    from app.jobs.handlers.workflows import process_workflow_sweep

    job = SimpleNamespace(
        organization_id=test_org.id,
        payload={
            "org_id": str(uuid4()),
            "sweep_type": "task_overdue",
        },
    )

    with pytest.raises(ValueError, match="organization"):
        await process_workflow_sweep(db, job)
