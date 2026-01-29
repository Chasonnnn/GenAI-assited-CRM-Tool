"""Workflow-related job handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_workflow_sweep(db, job) -> None:
    """
    Process a WORKFLOW_SWEEP job - daily sweep for scheduled and inactivity workflows.

    Payload:
        - org_id: Organization to sweep (optional, sweeps all if not provided)
        - sweep_type: 'scheduled', 'inactivity', 'task_due', 'task_overdue', or 'all'
    """
    from app.services import workflow_triggers
    from app.db.models import Organization

    sweep_type = job.payload.get("sweep_type", "all")
    org_id = job.payload.get("org_id")

    if org_id:
        orgs = [db.query(Organization).filter(Organization.id == UUID(org_id)).first()]
        orgs = [o for o in orgs if o]
    else:
        orgs = db.query(Organization).all()

    logger.info("Starting workflow sweep: type=%s, orgs=%s", sweep_type, len(orgs))

    for org in orgs:
        try:
            if sweep_type in ("all", "scheduled"):
                workflow_triggers.trigger_scheduled_workflows(db, org.id)

            if sweep_type in ("all", "inactivity"):
                workflow_triggers.trigger_inactivity_workflows(db, org.id)

            if sweep_type in ("all", "task_due"):
                workflow_triggers.trigger_task_due_sweep(db, org.id)

            if sweep_type in ("all", "task_overdue"):
                workflow_triggers.trigger_task_overdue_sweep(db, org.id)

            db.commit()
            logger.info("Workflow sweep complete for org %s", org.id)
        except Exception as e:
            logger.error("Workflow sweep failed for org %s: %s", org.id, e)
            db.rollback()

    logger.info("Workflow sweep finished for %s organizations", len(orgs))


async def process_workflow_approval_expiry(db, job) -> None:
    """
    Sweep for expired workflow approval tasks and mark them as expired.

    This job should be scheduled to run every 5 minutes.
    """
    from app.services import task_service
    from app.db.models import Task
    from app.db.enums import TaskType, TaskStatus

    logger.info("Starting workflow approval expiry sweep for org %s", job.organization_id)

    now = datetime.now(timezone.utc)

    # Find overdue approval tasks
    overdue_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == job.organization_id,
            Task.task_type == TaskType.WORKFLOW_APPROVAL.value,
            Task.status.in_([TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]),
            Task.due_at < now,
        )
        .with_for_update(skip_locked=True)
        .all()
    )

    expired_count = 0
    for task in overdue_tasks:
        try:
            task_service.expire_approval_task(db, task)
            expired_count += 1
            logger.info("Expired workflow approval task %s", task.id)
        except Exception as e:
            logger.error("Failed to expire task %s: %s", task.id, e)

    logger.info("Workflow approval expiry sweep complete: %s expired", expired_count)


async def process_workflow_resume(db, job) -> None:
    """
    Resume a paused workflow after approval resolution.

    Payload:
        - execution_id: UUID of the workflow execution
        - task_id: UUID of the resolved approval task
    """
    from app.db.models import WorkflowExecution, Task, AutomationWorkflow, WorkflowResumeJob
    from app.db.enums import WorkflowExecutionStatus, TaskStatus
    from app.services.workflow_engine import WorkflowEngine

    payload = job.payload or {}
    execution_id = payload.get("execution_id")
    task_id = payload.get("task_id")
    idempotency_key = payload.get("idempotency_key")

    if not execution_id or not task_id:
        raise Exception("Missing execution_id or task_id in workflow resume job")

    # Check idempotency
    if idempotency_key:
        existing = (
            db.query(WorkflowResumeJob)
            .filter(WorkflowResumeJob.idempotency_key == idempotency_key)
            .first()
        )
        if existing and existing.processed_at is not None:
            logger.info("Workflow resume job already processed: %s", idempotency_key)
            return

    # Get task and execution
    task = db.query(Task).filter(Task.id == UUID(task_id)).first()
    if not task:
        raise Exception(f"Task {task_id} not found")

    execution = (
        db.query(WorkflowExecution).filter(WorkflowExecution.id == UUID(execution_id)).first()
    )
    if not execution:
        raise Exception(f"Execution {execution_id} not found")

    # Check execution is paused on this task
    if execution.status != WorkflowExecutionStatus.PAUSED.value:
        logger.info("Execution %s not paused, skipping resume", execution_id)
        return

    if str(execution.paused_task_id) != str(task_id):
        logger.warning(
            "Execution %s not waiting on task %s, waiting on %s",
            execution_id,
            task_id,
            execution.paused_task_id,
        )
        return

    # Get workflow
    workflow = (
        db.query(AutomationWorkflow).filter(AutomationWorkflow.id == execution.workflow_id).first()
    )
    if not workflow:
        raise Exception(f"Workflow {execution.workflow_id} not found")

    # Handle based on task status
    if task.status == TaskStatus.COMPLETED.value:
        # APPROVED: Execute the action and continue workflow
        logger.info("Resuming approved workflow execution %s", execution_id)

        engine = WorkflowEngine()
        engine.continue_execution(
            db=db,
            execution_id=execution.id,
            task=task,
            decision="approve",
        )

    elif task.status == TaskStatus.DENIED.value:
        # DENIED: Cancel workflow
        logger.info("Workflow execution %s denied", execution_id)
        execution.paused_at_action_index = None
        execution.paused_task_id = None
        execution.status = WorkflowExecutionStatus.CANCELED.value
        execution.error_message = task.workflow_denial_reason or "Approval denied by case owner"

        # Record the skipped action
        action_results = list(execution.actions_executed or [])
        action_results.append(
            {
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "denied",
            }
        )
        execution.actions_executed = action_results

    elif task.status == TaskStatus.EXPIRED.value:
        # EXPIRED: Mark workflow expired
        logger.info("Workflow execution %s expired", execution_id)
        execution.paused_at_action_index = None
        execution.paused_task_id = None
        execution.status = WorkflowExecutionStatus.EXPIRED.value
        execution.error_message = "Approval timed out"

        action_results = list(execution.actions_executed or [])
        action_results.append(
            {
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "expired",
            }
        )
        execution.actions_executed = action_results

    else:
        logger.warning("Unexpected task status for resume: %s", task.status)
        return

    # Mark idempotency record as processed
    if idempotency_key:
        resume_job = (
            db.query(WorkflowResumeJob)
            .filter(WorkflowResumeJob.idempotency_key == idempotency_key)
            .first()
        )
        if resume_job:
            resume_job.processed_at = datetime.now(timezone.utc)

    db.commit()
    logger.info("Workflow resume complete for execution %s", execution_id)
