from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import event

from app.db.enums import (
    OwnerType,
    TaskStatus,
    TaskType,
    WorkflowEventSource,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)
from app.db.models import AutomationWorkflow, Organization, Task, WorkflowExecution
from app.services import workflow_service


@contextmanager
def _collect_selects(db):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        if statement.lstrip().lower().startswith("select"):
            statements.append(" ".join(statement.split()))

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)


def _add_workflow(
    db,
    *,
    org_id,
    user_id,
    name: str,
    trigger_type: WorkflowTriggerType,
    is_enabled: bool,
    scope: str = "org",
    owner_user_id=None,
) -> AutomationWorkflow:
    workflow = AutomationWorkflow(
        id=uuid4(),
        organization_id=org_id,
        name=name,
        trigger_type=trigger_type.value,
        trigger_config={},
        conditions=[],
        actions=[{"action_type": "add_note", "content": "note"}],
        is_enabled=is_enabled,
        scope=scope,
        owner_user_id=owner_user_id,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(workflow)
    return workflow


def _add_execution(
    db,
    *,
    org_id,
    workflow_id,
    status: WorkflowExecutionStatus,
    executed_at: datetime,
    duration_ms: int | None,
) -> None:
    db.add(
        WorkflowExecution(
            id=uuid4(),
            organization_id=org_id,
            workflow_id=workflow_id,
            event_id=uuid4(),
            depth=0,
            event_source=WorkflowEventSource.USER.value,
            entity_type="surrogate",
            entity_id=uuid4(),
            trigger_event={},
            dedupe_key=None,
            matched_conditions=status != WorkflowExecutionStatus.SKIPPED,
            actions_executed=[{"success": status == WorkflowExecutionStatus.SUCCESS.value}],
            status=status.value,
            duration_ms=duration_ms,
            executed_at=executed_at,
        )
    )


def _add_approval_task(
    db,
    *,
    org_id,
    user_id,
    title: str,
    status: TaskStatus,
    created_at: datetime,
    updated_at: datetime,
    completed_at: datetime | None = None,
) -> None:
    db.add(
        Task(
            id=uuid4(),
            organization_id=org_id,
            surrogate_id=None,
            intended_parent_id=None,
            created_by_user_id=user_id,
            owner_type=OwnerType.USER.value,
            owner_id=user_id,
            title=title,
            description=None,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            status=status.value,
            created_at=created_at,
            updated_at=updated_at,
            completed_at=completed_at,
        )
    )


def test_get_workflow_stats_uses_four_selects_and_preserves_counts(db, test_org, test_user):
    now = datetime.now(timezone.utc)
    other_org = Organization(
        id=uuid4(),
        name="Other Workflow Stats Org",
        slug=f"other-workflow-stats-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)

    wf_status = _add_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Status Enabled",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        is_enabled=True,
    )
    wf_created = _add_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Created Disabled",
        trigger_type=WorkflowTriggerType.SURROGATE_CREATED,
        is_enabled=False,
    )
    _add_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Personal Enabled",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        is_enabled=True,
        scope="personal",
        owner_user_id=test_user.id,
    )
    other_workflow = _add_workflow(
        db,
        org_id=other_org.id,
        user_id=test_user.id,
        name="Other Org Workflow",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        is_enabled=True,
    )
    db.flush()

    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=wf_status.id,
        status=WorkflowExecutionStatus.SUCCESS,
        executed_at=now - timedelta(hours=1),
        duration_ms=100,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=wf_status.id,
        status=WorkflowExecutionStatus.FAILED,
        executed_at=now - timedelta(hours=2),
        duration_ms=300,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=wf_created.id,
        status=WorkflowExecutionStatus.SKIPPED,
        executed_at=now - timedelta(hours=3),
        duration_ms=None,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=wf_created.id,
        status=WorkflowExecutionStatus.SUCCESS,
        executed_at=now - timedelta(days=2),
        duration_ms=900,
    )
    _add_execution(
        db,
        org_id=other_org.id,
        workflow_id=other_workflow.id,
        status=WorkflowExecutionStatus.SUCCESS,
        executed_at=now - timedelta(hours=1),
        duration_ms=50,
    )

    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="Pending approval",
        status=TaskStatus.PENDING,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="In progress approval",
        status=TaskStatus.IN_PROGRESS,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )
    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="Completed approval",
        status=TaskStatus.COMPLETED,
        created_at=now - timedelta(hours=4),
        updated_at=now - timedelta(hours=1),
        completed_at=now - timedelta(hours=2),
    )
    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="Denied approval",
        status=TaskStatus.DENIED,
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=1),
    )
    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="Expired approval",
        status=TaskStatus.EXPIRED,
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=1),
    )
    _add_approval_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        title="Old completed approval",
        status=TaskStatus.COMPLETED,
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=3, hours=-2),
    )
    _add_approval_task(
        db,
        org_id=other_org.id,
        user_id=test_user.id,
        title="Other org pending approval",
        status=TaskStatus.PENDING,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    db.flush()

    with _collect_selects(db) as selects:
        stats = workflow_service.get_workflow_stats(db, test_org.id)

    assert len(selects) == 4
    assert stats.total_workflows == 3
    assert stats.enabled_workflows == 2
    assert stats.org_workflows == 2
    assert stats.personal_workflows == 1
    assert stats.by_trigger_type == {
        WorkflowTriggerType.STATUS_CHANGED.value: 2,
        WorkflowTriggerType.SURROGATE_CREATED.value: 1,
    }
    assert stats.total_executions_24h == 3
    assert stats.success_rate_24h == 33.3
    assert stats.pending_approvals == 2
    assert stats.approvals_resolved_24h == 3
    assert stats.approval_rate_24h == 33.3
    assert stats.denial_rate_24h == 33.3
    assert stats.expiry_rate_24h == 33.3
    assert stats.avg_approval_latency_hours == 2.0


def test_get_execution_stats_uses_one_select_and_preserves_counts(db, test_org, test_user):
    now = datetime.now(timezone.utc)
    other_org = Organization(
        id=uuid4(),
        name="Other Execution Stats Org",
        slug=f"other-execution-stats-{uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    workflow = _add_workflow(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Execution Stats Workflow",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        is_enabled=True,
    )
    other_workflow = _add_workflow(
        db,
        org_id=other_org.id,
        user_id=test_user.id,
        name="Other Execution Stats Workflow",
        trigger_type=WorkflowTriggerType.STATUS_CHANGED,
        is_enabled=True,
    )
    db.flush()

    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.SUCCESS,
        executed_at=now - timedelta(hours=1),
        duration_ms=100,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.FAILED,
        executed_at=now - timedelta(hours=2),
        duration_ms=300,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.SKIPPED,
        executed_at=now - timedelta(hours=3),
        duration_ms=None,
    )
    _add_execution(
        db,
        org_id=test_org.id,
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.SUCCESS,
        executed_at=now - timedelta(days=2),
        duration_ms=900,
    )
    _add_execution(
        db,
        org_id=other_org.id,
        workflow_id=other_workflow.id,
        status=WorkflowExecutionStatus.FAILED,
        executed_at=now - timedelta(hours=1),
        duration_ms=10,
    )
    db.flush()

    with _collect_selects(db) as selects:
        stats = workflow_service.get_execution_stats(db, test_org.id)

    assert len(selects) == 1
    assert stats == {
        "total_24h": 3,
        "failed_24h": 1,
        "success_rate": 33.3,
        "avg_duration_ms": 200,
    }
