"""Retired routing payloads may remain in history or arrive from older releases."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID
from app.db.enums import AuditEventType, TaskStatus, TaskType, WorkflowExecutionStatus
from app.db.models import Task, WorkflowExecution
from app.services import audit_service

RETIRED_ROUTING_ACTIONS = frozenset({"auto_match_submission", "create_intake_lead"})
GENERATED_ROUTING_PREFIX = "shared_intake_routing:"
logger = logging.getLogger(__name__)


def has_retired_routing_actions(actions: list[dict] | None) -> bool:
    return any(a.get("action_type") in RETIRED_ROUTING_ACTIONS for a in actions or [])


def strip_retired_routing_actions(actions: list[dict] | None) -> list[dict]:
    return [a for a in actions or [] if a.get("action_type") not in RETIRED_ROUTING_ACTIONS]


def retired_action_skip(action: dict) -> dict | None:
    if action.get("action_type") not in RETIRED_ROUTING_ACTIONS:
        return None
    return {
        "action_type": action["action_type"],
        "success": True,
        "skipped": True,
        "description": "Skipped retired routing action",
    }


def cancel_paused_routing_execution(db: Session, execution: WorkflowExecution) -> None:
    """Caller locks the execution and owns the cancellation/audit transaction."""
    if execution.status != WorkflowExecutionStatus.PAUSED.value:
        return
    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == execution.organization_id,
            Task.workflow_execution_id == execution.id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
        )
        .order_by(Task.id)
        .with_for_update()
        .all()
    )
    now = datetime.now(UTC)
    for task in tasks:
        task.status = TaskStatus.COMPLETED.value
        task.is_completed = True
        task.completed_at = now
        task.completed_by_user_id = SYSTEM_USER_ID
        task.updated_at = now
        audit_service.log_event(
            db,
            execution.organization_id,
            AuditEventType.TASK_COMPLETED,
            actor_user_id=SYSTEM_USER_ID,
            target_type="task",
            target_id=task.id,
            details={"action": "retire_workflow_routing", "execution_id": str(execution.id)},
        )
        db.flush()
    execution.status = WorkflowExecutionStatus.CANCELED.value
    execution.paused_task_id = None
    execution.paused_at_action_index = None
    execution.error_message = "Workflow routing retired"
    logger.warning(
        "Canceled retired routing execution: workflow_id=%s organization_id=%s execution_id=%s",
        execution.workflow_id,
        execution.organization_id,
        execution.id,
    )
