"""Workflow engine - executes workflows with loop protection and action handling."""

import logging
import time
import uuid as uuid_module
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AutomationWorkflow,
    WorkflowExecution,
    Case,
    Task,
    User,
    Organization,
    EntityNote,
    Match,
    Appointment,
    Attachment,
)
from app.db.enums import (
    WorkflowTriggerType,
    WorkflowActionType,
    WorkflowExecutionStatus,
    WorkflowEventSource,
    WorkflowConditionOperator,
    JobType,
    EntityType,
    OwnerType,
    TaskType,
    TaskStatus,
)
from app.services import workflow_service, job_service, notification_service
from app.services.workflow_action_preview import build_action_preview, render_action_payload
from app.schemas.workflow import ALLOWED_UPDATE_FIELDS
from app.core.constants import (
    SYSTEM_USER_ID,
    WORKFLOW_APPROVAL_TIMEOUT_HOURS,
)
from app.utils.business_hours import calculate_approval_due_date


logger = logging.getLogger(__name__)

# Maximum recursion depth for workflow-triggered events
MAX_DEPTH = 3


class WorkflowEngine:
    """
    Core workflow execution engine.

    Handles trigger evaluation, condition matching, and action execution
    with loop protection and full audit logging.
    """

    def trigger(
        self,
        db: Session,
        trigger_type: WorkflowTriggerType,
        entity_type: str,
        entity_id: UUID,
        event_data: dict,
        org_id: UUID,
        event_id: UUID | None = None,
        depth: int = 0,
        source: WorkflowEventSource = WorkflowEventSource.USER,
    ) -> list[WorkflowExecution]:
        """
        Trigger workflows for an event.

        Returns list of execution records created.
        """
        # Loop protection
        if depth >= MAX_DEPTH:
            logger.warning(
                f"Max workflow depth ({MAX_DEPTH}) reached for event {event_id}"
            )
            return []

        # Ignore workflow-triggered events at depth > 1
        if source == WorkflowEventSource.WORKFLOW and depth > 1:
            logger.debug(f"Ignoring nested workflow-triggered event at depth {depth}")
            return []

        event_id = event_id or uuid_module.uuid4()
        executions = []

        # Find matching enabled workflows
        workflows = self._find_matching_workflows(db, org_id, trigger_type, event_data)

        for workflow in workflows:
            execution = self._execute_workflow(
                db=db,
                workflow=workflow,
                entity_type=entity_type,
                entity_id=entity_id,
                event_data=event_data,
                event_id=event_id,
                depth=depth,
                source=source,
            )
            if execution:
                executions.append(execution)

        return executions

    def _find_matching_workflows(
        self,
        db: Session,
        org_id: UUID,
        trigger_type: WorkflowTriggerType,
        event_data: dict,
    ) -> list[AutomationWorkflow]:
        """Find enabled workflows that match the trigger."""
        workflows = (
            db.query(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == org_id,
                AutomationWorkflow.trigger_type == trigger_type.value,
                AutomationWorkflow.is_enabled.is_(True),
            )
            .all()
        )

        matching = []
        for workflow in workflows:
            if self._trigger_matches(workflow, trigger_type, event_data):
                matching.append(workflow)

        return matching

    def _trigger_matches(
        self,
        workflow: AutomationWorkflow,
        trigger_type: WorkflowTriggerType,
        event_data: dict,
    ) -> bool:
        """Check if trigger config matches the event data."""
        config = workflow.trigger_config

        if trigger_type == WorkflowTriggerType.STATUS_CHANGED:
            to_stage_id = config.get("to_stage_id")
            from_stage_id = config.get("from_stage_id")

            if to_stage_id and str(event_data.get("new_stage_id")) != str(to_stage_id):
                return False
            if from_stage_id and str(event_data.get("old_stage_id")) != str(
                from_stage_id
            ):
                return False
            return True

        if trigger_type == WorkflowTriggerType.CASE_ASSIGNED:
            to_user_id = config.get("to_user_id")
            if to_user_id and str(event_data.get("new_owner_id")) != str(to_user_id):
                return False
            return True

        if trigger_type == WorkflowTriggerType.CASE_UPDATED:
            required_fields = set(config.get("fields", []))
            changed_fields = set(event_data.get("changed_fields", []))
            return bool(required_fields & changed_fields)

        # For case_created, task_due, task_overdue, scheduled, inactivity
        # No trigger-level filtering needed (conditions handle it)
        return True

    def _execute_workflow(
        self,
        db: Session,
        workflow: AutomationWorkflow,
        entity_type: str,
        entity_id: UUID,
        event_data: dict,
        event_id: UUID,
        depth: int,
        source: WorkflowEventSource,
    ) -> WorkflowExecution | None:
        """Execute a single workflow and log the result."""
        start_time = time.time()

        # Check dedupe for sweep-based triggers
        dedupe_key = self._get_dedupe_key(workflow, entity_id)
        if dedupe_key and self._is_duplicate(db, dedupe_key):
            return None

        # Check rate limits
        rate_limit_error = self._check_rate_limits(db, workflow, entity_id)
        if rate_limit_error:
            execution = WorkflowExecution(
                organization_id=workflow.organization_id,
                workflow_id=workflow.id,
                event_id=event_id,
                depth=depth,
                event_source=source.value,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_event=event_data,
                dedupe_key=dedupe_key,
                matched_conditions=False,
                actions_executed=[],
                status=WorkflowExecutionStatus.SKIPPED.value,
                error_message=rate_limit_error,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            db.add(execution)
            db.commit()
            logger.info(f"Workflow {workflow.id} rate limited: {rate_limit_error}")
            return execution

        # Get entity for condition evaluation
        entity = self._get_entity(db, entity_type, entity_id)
        if not entity:
            logger.warning(f"Entity {entity_type}:{entity_id} not found")
            return None

        # Evaluate conditions
        conditions_matched = self._evaluate_conditions(
            workflow.conditions,
            workflow.condition_logic,
            entity,
        )

        # Check user opt-out (for owner of entity)
        user_opted_out = False
        if hasattr(entity, "owner_id") and entity.owner_type == OwnerType.USER.value:
            user_opted_out = workflow_service.is_user_opted_out(
                db, entity.owner_id, workflow.id
            )

        if not conditions_matched or user_opted_out:
            execution = WorkflowExecution(
                organization_id=workflow.organization_id,
                workflow_id=workflow.id,
                event_id=event_id,
                depth=depth,
                event_source=source.value,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_event=event_data,
                dedupe_key=dedupe_key,
                matched_conditions=conditions_matched,
                actions_executed=[],
                status=WorkflowExecutionStatus.SKIPPED.value,
                error_message="User opted out" if user_opted_out else None,
                duration_ms=int((time.time() - start_time) * 1000),
            )
            db.add(execution)
            db.commit()
            return execution

        # =====================================================================
        # FAIL FAST: Workflows require user-owned cases at trigger time
        # (after conditions match to avoid false failures)
        # =====================================================================
        has_approval_actions = any(
            action.get("requires_approval") for action in workflow.actions
        )
        case = self._get_related_case(db, entity_type, entity)
        case_owner = None

        if case:
            # Validate case has a user owner (not queue/null)
            if case.owner_type != OwnerType.USER.value or not case.owner_id:
                execution = WorkflowExecution(
                    organization_id=workflow.organization_id,
                    workflow_id=workflow.id,
                    event_id=event_id,
                    depth=depth,
                    event_source=source.value,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    trigger_event=event_data,
                    dedupe_key=dedupe_key,
                    matched_conditions=True,
                    actions_executed=[],
                    status=WorkflowExecutionStatus.FAILED.value,
                    error_message="Workflow requires case owner to be a user",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                db.add(execution)
                db.commit()
                return execution

            # Verify owner exists
            case_owner = db.query(User).filter(User.id == case.owner_id).first()
            if not case_owner:
                execution = WorkflowExecution(
                    organization_id=workflow.organization_id,
                    workflow_id=workflow.id,
                    event_id=event_id,
                    depth=depth,
                    event_source=source.value,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    trigger_event=event_data,
                    dedupe_key=dedupe_key,
                    matched_conditions=True,
                    actions_executed=[],
                    status=WorkflowExecutionStatus.FAILED.value,
                    error_message="Workflow requires case owner but owner not found",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                db.add(execution)
                db.commit()
                return execution
        elif has_approval_actions:
            execution = WorkflowExecution(
                organization_id=workflow.organization_id,
                workflow_id=workflow.id,
                event_id=event_id,
                depth=depth,
                event_source=source.value,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_event=event_data,
                dedupe_key=dedupe_key,
                matched_conditions=True,
                actions_executed=[],
                status=WorkflowExecutionStatus.FAILED.value,
                error_message="Workflow requires approval but entity has no related case",
                duration_ms=int((time.time() - start_time) * 1000),
            )
            db.add(execution)
            db.commit()
            return execution

        # Create execution record first (needed for approval task FK)
        execution = WorkflowExecution(
            organization_id=workflow.organization_id,
            workflow_id=workflow.id,
            event_id=event_id,
            depth=depth,
            event_source=source.value,
            entity_type=entity_type,
            entity_id=entity_id,
            trigger_event=event_data,
            dedupe_key=dedupe_key,
            matched_conditions=True,
            actions_executed=[],
            status=WorkflowExecutionStatus.SUCCESS.value,  # Will update if needed
        )
        db.add(execution)
        db.flush()  # Get execution.id

        # Execute actions with approval pause support
        action_results = []
        all_success = True

        for idx, action in enumerate(workflow.actions):
            # Check if this action requires approval
            if action.get("requires_approval"):
                # Get the case for approval task
                # Create approval task and pause execution
                task = self._create_approval_task(
                    db=db,
                    workflow=workflow,
                    execution=execution,
                    action=action,
                    action_index=idx,
                    entity=entity,
                    case=case,
                    owner=case_owner,
                    triggered_by_user_id=event_data.get("triggered_by_user_id"),
                )

                if task:
                    # Pause execution
                    execution.status = WorkflowExecutionStatus.PAUSED.value
                    execution.paused_at_action_index = idx
                    execution.paused_task_id = task.id
                    execution.actions_executed = action_results
                    execution.duration_ms = int((time.time() - start_time) * 1000)
                    db.commit()

                    logger.info(
                        f"Workflow {workflow.id} paused at action {idx} for approval, task {task.id}"
                    )
                    return execution

                # Approval task could not be created
                action_results.append(
                    {
                        "success": False,
                        "error": "Failed to create approval task",
                        "skipped": True,
                    }
                )
                execution.actions_executed = action_results
                execution.status = WorkflowExecutionStatus.FAILED.value
                execution.error_message = "Failed to create approval task"
                execution.duration_ms = int((time.time() - start_time) * 1000)
                db.commit()
                return execution

            # Execute non-approval action normally
            result = self._execute_action(
                db=db,
                action=action,
                entity=entity,
                entity_type=entity_type,
                event_id=event_id,
                depth=depth,
            )
            action_results.append(result)
            if not result.get("success"):
                all_success = False

        # Update workflow stats
        workflow.run_count += 1
        workflow.last_run_at = datetime.now(timezone.utc)
        workflow.last_error = None if all_success else (
            action_results[-1].get("error") if action_results else None
        )

        # Update execution record
        execution.actions_executed = action_results
        execution.status = (
            WorkflowExecutionStatus.SUCCESS.value
            if all_success
            else WorkflowExecutionStatus.PARTIAL.value
        )
        execution.error_message = None if all_success else (
            action_results[-1].get("error") if action_results else None
        )
        execution.duration_ms = int((time.time() - start_time) * 1000)
        db.commit()

        return execution

    def _get_related_case(
        self,
        db: Session,
        entity_type: str,
        entity: Any,
    ) -> Case | None:
        """Get the case related to an entity."""
        if entity_type == "case":
            return entity
        if hasattr(entity, "case_id") and entity.case_id:
            return db.query(Case).filter(Case.id == entity.case_id).first()
        return None

    def _create_approval_task(
        self,
        db: Session,
        workflow: AutomationWorkflow,
        execution: WorkflowExecution,
        action: dict,
        action_index: int,
        entity: Any,
        case: Case,
        owner: User,
        triggered_by_user_id: UUID | None,
    ) -> Task | None:
        """
        Create an approval task for a workflow action.

        Returns the task if created or already exists (idempotency).
        """
        # Get organization for timezone fallback
        org = db.query(Organization).filter(
            Organization.id == case.organization_id
        ).first()

        # Build sanitized preview (no PII)
        preview = build_action_preview(db, action, entity)

        # Build payload snapshot (internal only, never exposed via API)
        payload = render_action_payload(action, entity)

        # Calculate due date (48 business hours)
        now = datetime.now(timezone.utc)
        due_at = calculate_approval_due_date(
            start_utc=now,
            owner=owner,
            org=org,
            timeout_hours=WORKFLOW_APPROVAL_TIMEOUT_HOURS,
        )

        task = Task(
            organization_id=execution.organization_id,
            case_id=case.id,
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            title=f"Approve: {preview}",
            description=f"Workflow '{workflow.name}' requires your approval to proceed.",
            owner_type=OwnerType.USER.value,
            owner_id=owner.id,
            status=TaskStatus.PENDING.value,
            due_at=due_at,
            created_by_user_id=SYSTEM_USER_ID,
            # Workflow-specific fields
            workflow_execution_id=execution.id,
            workflow_action_index=action_index,
            workflow_action_type=action.get("action_type"),
            workflow_action_preview=preview,
            workflow_action_payload=payload,
            workflow_triggered_by_user_id=triggered_by_user_id,
        )

        try:
            db.add(task)
            db.flush()
            logger.info(f"Created approval task {task.id} for execution {execution.id}")

            # Send notification to owner (respects user settings)
            notification_service.notify_workflow_approval_requested(
                db=db,
                task_id=task.id,
                task_title=task.title,
                org_id=case.organization_id,
                assignee_id=owner.id,
                case_number=case.case_number,
            )

            return task

        except IntegrityError:
            # Idempotency: task already exists for this execution+action
            db.rollback()
            existing = db.query(Task).filter(
                Task.workflow_execution_id == execution.id,
                Task.workflow_action_index == action_index,
            ).first()
            logger.info(
                f"Approval task already exists: {existing.id if existing else 'unknown'}"
            )
            return existing

    def continue_execution(
        self,
        db: Session,
        execution_id: UUID,
        task: Task,
        decision: str,
    ) -> None:
        """
        Continue workflow execution after approval decision.

        Called by the resume job processor after task is resolved.
        """

        # Lock execution row
        execution = (
            db.query(WorkflowExecution)
            .filter(WorkflowExecution.id == execution_id)
            .with_for_update()
            .first()
        )

        if not execution:
            logger.error(f"Execution {execution_id} not found for resume")
            return

        if execution.status != WorkflowExecutionStatus.PAUSED.value:
            logger.warning(
                f"Execution {execution_id} not paused (status={execution.status}), skipping resume"
            )
            return

        workflow = db.query(AutomationWorkflow).filter(
            AutomationWorkflow.id == execution.workflow_id
        ).first()

        if not workflow:
            logger.error(f"Workflow {execution.workflow_id} not found for resume")
            return

        # Get entity
        entity = self._get_entity(db, execution.entity_type, execution.entity_id)
        if not entity:
            logger.error(f"Entity {execution.entity_type}:{execution.entity_id} not found")
            execution.status = WorkflowExecutionStatus.FAILED.value
            execution.error_message = "Entity not found during resume"
            execution.paused_at_action_index = None
            execution.paused_task_id = None
            db.commit()
            return

        # Clear paused state
        action_index = execution.paused_at_action_index
        execution.paused_at_action_index = None
        execution.paused_task_id = None

        action_results = list(execution.actions_executed or [])

        if task.status == TaskStatus.COMPLETED.value:
            # APPROVED: Execute the action using snapshot
            action = task.workflow_action_payload
            if not action:
                logger.error(f"No action payload found for task {task.id}")
                action_results.append({
                    "success": False,
                    "action_type": task.workflow_action_type,
                    "error": "No action payload",
                })
                execution.actions_executed = action_results
                execution.status = WorkflowExecutionStatus.FAILED.value
                db.commit()
                return

            # Execute the approved action
            result = self._execute_action(
                db=db,
                action=action,
                entity=entity,
                entity_type=execution.entity_type,
                event_id=execution.event_id,
                depth=execution.depth,
            )
            action_results.append(result)

            # Continue with remaining actions
            remaining_actions = workflow.actions[action_index + 1:]
            for idx, next_action in enumerate(remaining_actions):
                actual_idx = action_index + 1 + idx

                if next_action.get("requires_approval"):
                    # Need another approval - pause again
                    case = self._get_related_case(db, execution.entity_type, entity)
                    owner = db.query(User).filter(User.id == case.owner_id).first() if case else None

                    if not case or not owner:
                        action_results.append(
                            {
                                "success": False,
                                "action_type": next_action.get("action_type"),
                                "error": "Case or owner not found for approval",
                            }
                        )
                        execution.actions_executed = action_results
                        execution.status = WorkflowExecutionStatus.FAILED.value
                        execution.error_message = "Workflow requires case owner to be a user"
                        db.commit()
                        return

                    new_task = self._create_approval_task(
                        db=db,
                        workflow=workflow,
                        execution=execution,
                        action=next_action,
                        action_index=actual_idx,
                        entity=entity,
                        case=case,
                        owner=owner,
                        triggered_by_user_id=task.workflow_triggered_by_user_id,
                    )

                    if new_task:
                        execution.status = WorkflowExecutionStatus.PAUSED.value
                        execution.paused_at_action_index = actual_idx
                        execution.paused_task_id = new_task.id
                        execution.actions_executed = action_results
                        db.commit()
                        logger.info(
                            f"Workflow {workflow.id} paused again at action {actual_idx}"
                        )
                        return

                # Execute non-approval action
                result = self._execute_action(
                    db=db,
                    action=next_action,
                    entity=entity,
                    entity_type=execution.entity_type,
                    event_id=execution.event_id,
                    depth=execution.depth,
                )
                action_results.append(result)

            # All done - determine final status
            all_success = all(r.get("success") for r in action_results)
            execution.status = (
                WorkflowExecutionStatus.SUCCESS.value
                if all_success
                else WorkflowExecutionStatus.PARTIAL.value
            )
            execution.actions_executed = action_results
            db.commit()

            # Update workflow stats
            workflow.run_count += 1
            workflow.last_run_at = datetime.now(timezone.utc)
            db.commit()

        elif task.status == TaskStatus.DENIED.value:
            # DENIED: Mark execution as canceled
            action_results.append({
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "denied",
            })
            execution.status = WorkflowExecutionStatus.CANCELED.value
            execution.error_message = f"Approval denied: {task.workflow_denial_reason or 'No reason given'}"
            execution.actions_executed = action_results
            db.commit()

        elif task.status == TaskStatus.EXPIRED.value:
            # EXPIRED: Mark execution as expired
            action_results.append({
                "success": False,
                "action_type": task.workflow_action_type,
                "skipped": True,
                "reason": "expired",
            })
            execution.status = WorkflowExecutionStatus.EXPIRED.value
            execution.error_message = "Approval timed out"
            execution.actions_executed = action_results
            db.commit()

        else:
            logger.warning(f"Unexpected task status for resume: {task.status}")
            execution.status = WorkflowExecutionStatus.FAILED.value
            execution.error_message = f"Unexpected task status: {task.status}"
            db.commit()

    def _get_dedupe_key(
        self,
        workflow: AutomationWorkflow,
        entity_id: UUID,
    ) -> str | None:
        """Generate dedupe key for sweep-based triggers."""
        trigger_type = workflow.trigger_type

        # Only dedupe for scheduled/sweep triggers
        if trigger_type in ["scheduled", "inactivity", "task_due", "task_overdue"]:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return f"{workflow.id}:{entity_id}:{trigger_type}:{today}"

        return None

    def _is_duplicate(self, db: Session, dedupe_key: str) -> bool:
        """Check if this execution would be a duplicate."""
        existing = (
            db.query(WorkflowExecution)
            .filter(WorkflowExecution.dedupe_key == dedupe_key)
            .first()
        )
        return existing is not None

    def _check_rate_limits(
        self,
        db: Session,
        workflow: AutomationWorkflow,
        entity_id: UUID,
    ) -> str | None:
        """
        Check if workflow execution would exceed rate limits.

        Returns error message if rate limited, None if OK to proceed.
        """
        from datetime import timedelta
        from sqlalchemy import func

        now = datetime.now(timezone.utc)

        # Check per-hour limit (global for this workflow)
        if workflow.rate_limit_per_hour:
            hour_ago = now - timedelta(hours=1)
            executions_this_hour = (
                db.query(func.count(WorkflowExecution.id))
                .filter(
                    WorkflowExecution.workflow_id == workflow.id,
                    WorkflowExecution.executed_at >= hour_ago,
                    WorkflowExecution.status != WorkflowExecutionStatus.SKIPPED.value,
                )
                .scalar()
                or 0
            )

            if executions_this_hour >= workflow.rate_limit_per_hour:
                return f"Rate limit exceeded: {executions_this_hour}/{workflow.rate_limit_per_hour} per hour"

        # Check per-entity-per-day limit
        if workflow.rate_limit_per_entity_per_day:
            day_ago = now - timedelta(hours=24)
            executions_for_entity = (
                db.query(func.count(WorkflowExecution.id))
                .filter(
                    WorkflowExecution.workflow_id == workflow.id,
                    WorkflowExecution.entity_id == entity_id,
                    WorkflowExecution.executed_at >= day_ago,
                    WorkflowExecution.status != WorkflowExecutionStatus.SKIPPED.value,
                )
                .scalar()
                or 0
            )

            if executions_for_entity >= workflow.rate_limit_per_entity_per_day:
                return f"Entity rate limit exceeded: {executions_for_entity}/{workflow.rate_limit_per_entity_per_day} per day for this entity"

        return None

    def _get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any:
        """Get entity by type and ID."""
        if entity_type == "case":
            return db.query(Case).filter(Case.id == entity_id).first()
        if entity_type == "task":
            return db.query(Task).filter(Task.id == entity_id).first()
        if entity_type == "match":
            return db.query(Match).filter(Match.id == entity_id).first()
        if entity_type == "appointment":
            return db.query(Appointment).filter(Appointment.id == entity_id).first()
        if entity_type == "note":
            return db.query(EntityNote).filter(EntityNote.id == entity_id).first()
        if entity_type == "document":
            return db.query(Attachment).filter(Attachment.id == entity_id).first()
        return None

    def _evaluate_conditions(
        self,
        conditions: list[dict],
        logic: str,
        entity: Any,
    ) -> bool:
        """Evaluate condition list with AND/OR logic."""
        if not conditions:
            return True

        results = []
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            entity_value = getattr(entity, field, None)
            result = self._evaluate_condition(operator, entity_value, value)
            results.append(result)

        if logic == "AND":
            return all(results)
        else:  # OR
            return any(results)

    def _evaluate_condition(
        self,
        operator: str,
        entity_value: Any,
        condition_value: Any,
    ) -> bool:
        """Evaluate a single condition."""
        if operator == WorkflowConditionOperator.EQUALS.value:
            return str(entity_value) == str(condition_value)

        if operator == WorkflowConditionOperator.NOT_EQUALS.value:
            return str(entity_value) != str(condition_value)

        if operator == WorkflowConditionOperator.CONTAINS.value:
            return condition_value in str(entity_value or "")

        if operator == WorkflowConditionOperator.NOT_CONTAINS.value:
            return condition_value not in str(entity_value or "")

        if operator == WorkflowConditionOperator.IS_EMPTY.value:
            return entity_value is None or entity_value == ""

        if operator == WorkflowConditionOperator.IS_NOT_EMPTY.value:
            return entity_value is not None and entity_value != ""

        if operator == WorkflowConditionOperator.IN.value:
            return str(entity_value) in [str(v) for v in condition_value]

        if operator == WorkflowConditionOperator.NOT_IN.value:
            return str(entity_value) not in [str(v) for v in condition_value]

        if operator == WorkflowConditionOperator.GREATER_THAN.value:
            try:
                return float(entity_value or 0) > float(condition_value)
            except (TypeError, ValueError):
                return False

        if operator == WorkflowConditionOperator.LESS_THAN.value:
            try:
                return float(entity_value or 0) < float(condition_value)
            except (TypeError, ValueError):
                return False

        return False

    # Actions that require the entity to be a Case
    CASE_ONLY_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.ASSIGN_CASE.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }

    def _execute_action(
        self,
        db: Session,
        action: dict,
        entity: Any,
        entity_type: str,
        event_id: UUID,
        depth: int,
    ) -> dict:
        """Execute a single action."""
        action_type = action.get("action_type")
        action_entity = entity

        # Validate entity type for Case-only actions, map tasks to cases when possible
        if action_type in self.CASE_ONLY_ACTIONS:
            if entity_type == "task":
                case_id = getattr(entity, "case_id", None)
                if not case_id:
                    return {
                        "success": False,
                        "error": "Task is not linked to a case",
                        "skipped": True,
                    }
                action_entity = db.query(Case).filter(Case.id == case_id).first()
                if not action_entity:
                    return {
                        "success": False,
                        "error": "Case not found for task",
                        "skipped": True,
                    }
            elif entity_type != "case":
                return {
                    "success": False,
                    "error": f"Action '{action_type}' only supports Case entities, got '{entity_type}'",
                    "skipped": True,
                }

        try:
            if action_type == WorkflowActionType.SEND_EMAIL.value:
                return self._action_send_email(db, action, action_entity, event_id)

            if action_type == WorkflowActionType.CREATE_TASK.value:
                return self._action_create_task(db, action, action_entity)

            if action_type == WorkflowActionType.ASSIGN_CASE.value:
                return self._action_assign_case(
                    db, action, action_entity, event_id, depth
                )

            if action_type == WorkflowActionType.SEND_NOTIFICATION.value:
                return self._action_send_notification(db, action, entity)

            if action_type == WorkflowActionType.UPDATE_FIELD.value:
                return self._action_update_field(
                    db, action, action_entity, event_id, depth
                )

            if action_type == WorkflowActionType.ADD_NOTE.value:
                return self._action_add_note(db, action, action_entity)

            return {"success": False, "error": f"Unknown action type: {action_type}"}

        except Exception as e:
            logger.exception(f"Action {action_type} failed: {e}")
            # Create system alert for workflow action failure
            try:
                from app.services import alert_service
                from app.db.enums import AlertType, AlertSeverity

                org_id = getattr(entity, "organization_id", None)
                if org_id:
                    alert_service.create_or_update_alert(
                        db=db,
                        org_id=org_id,
                        alert_type=AlertType.WORKFLOW_EXECUTION_FAILED,
                        severity=AlertSeverity.ERROR,
                        title=f"Workflow action '{action_type}' failed",
                        message=str(e)[:500],
                        integration_key="workflow_engine",
                        error_class=type(e).__name__,
                    )
            except Exception as alert_err:
                logger.warning(f"Failed to create workflow alert: {alert_err}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Action Executors
    # =========================================================================

    def _action_send_email(
        self,
        db: Session,
        action: dict,
        entity: Case,
        event_id: UUID,
    ) -> dict:
        """Queue an email using template."""
        template_id = action.get("template_id")

        if not entity.email:
            return {"success": False, "error": "Entity has no email address"}

        # Resolve variables
        variables = self._resolve_email_variables(db, entity)

        # Queue job instead of sending inline
        job = job_service.schedule_job(
            db=db,
            org_id=entity.organization_id,
            job_type=JobType.WORKFLOW_EMAIL,
            payload={
                "template_id": str(template_id),
                "recipient_email": entity.email,
                "variables": variables,
                "case_id": str(entity.id),
                "event_id": str(event_id),
            },
        )

        return {
            "success": True,
            "queued": True,
            "job_id": str(job.id),
            "description": f"Queued email to {entity.email}",
        }

    def _action_create_task(
        self,
        db: Session,
        action: dict,
        entity: Case,
    ) -> dict:
        """Create a task on the case."""
        from app.services import task_service
        from datetime import timedelta
        from app.schemas.task import TaskCreate
        from app.db.enums import TaskType

        title = action.get("title", "Follow up")
        description = action.get("description")
        due_days = action.get("due_days", 1)
        assignee = action.get("assignee", "owner")

        # Determine assignee
        owner_type = OwnerType.USER.value
        owner_id = None
        if assignee == "owner":
            owner_type = entity.owner_type
            owner_id = entity.owner_id
        elif assignee == "creator":
            owner_type = OwnerType.USER.value
            owner_id = entity.created_by_user_id
        elif isinstance(assignee, str) and assignee.startswith(
            ("admin", "owner", "creator")
        ):
            owner_type = entity.owner_type
            owner_id = entity.owner_id
        else:
            owner_type = OwnerType.USER.value
            owner_id = UUID(assignee) if assignee else None

        due_date = datetime.now(timezone.utc) + timedelta(days=due_days)

        actor_user_id = entity.created_by_user_id
        if not actor_user_id and entity.owner_type == OwnerType.USER.value:
            actor_user_id = entity.owner_id
        if not actor_user_id:
            return {
                "success": False,
                "error": "No actor user available for task creation",
            }

        task_data = TaskCreate(
            title=title,
            description=description,
            task_type=TaskType.FOLLOW_UP,
            case_id=entity.id,
            owner_type=owner_type,
            owner_id=owner_id,
            due_date=due_date.date(),
        )
        task = task_service.create_task(
            db=db,
            org_id=entity.organization_id,
            user_id=actor_user_id,
            data=task_data,
        )

        return {
            "success": True,
            "task_id": str(task.id),
            "description": f"Created task: {title}",
        }

    def _action_assign_case(
        self,
        db: Session,
        action: dict,
        entity: Case,
        event_id: UUID,
        depth: int,
    ) -> dict:
        """Assign case to user or queue."""
        owner_type = action.get("owner_type")
        owner_id = action.get("owner_id")

        old_owner_type = entity.owner_type
        old_owner_id = entity.owner_id

        entity.owner_type = owner_type
        entity.owner_id = UUID(owner_id) if isinstance(owner_id, str) else owner_id
        entity.updated_at = datetime.now(timezone.utc)

        db.commit()

        # Trigger case_assigned workflow (with increased depth to prevent loops)
        self.trigger(
            db=db,
            trigger_type=WorkflowTriggerType.CASE_ASSIGNED,
            entity_type="case",
            entity_id=entity.id,
            event_data={
                "old_owner_type": old_owner_type,
                "old_owner_id": str(old_owner_id) if old_owner_id else None,
                "new_owner_type": owner_type,
                "new_owner_id": str(owner_id),
            },
            org_id=entity.organization_id,
            event_id=event_id,
            depth=depth + 1,
            source=WorkflowEventSource.WORKFLOW,
        )

        return {
            "success": True,
            "description": f"Assigned case to {owner_type}:{owner_id}",
        }

    def _action_send_notification(
        self,
        db: Session,
        action: dict,
        entity: Case,
    ) -> dict:
        """Send in-app notification."""
        from app.db.enums import NotificationType

        title = action.get("title", "Workflow Notification")
        body = action.get("body", "")
        recipients = action.get("recipients", "owner")

        # Determine recipient user IDs
        user_ids = []
        if recipients == "owner" and entity.owner_type == OwnerType.USER.value:
            user_ids = [entity.owner_id]
        elif recipients == "creator":
            user_ids = [entity.created_by_user_id] if entity.created_by_user_id else []
        elif recipients == "all_admins":
            from app.db.models import Membership
            from app.db.enums import Role

            memberships = (
                db.query(Membership)
                .filter(
                    Membership.organization_id == entity.organization_id,
                    Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]),
                )
                .all()
            )
            user_ids = [m.user_id for m in memberships]
        elif isinstance(recipients, list):
            user_ids = [UUID(r) if isinstance(r, str) else r for r in recipients]

        # Create notifications
        for user_id in user_ids:
            notification_service.create_notification(
                db=db,
                org_id=entity.organization_id,
                user_id=user_id,
                type=NotificationType.CASE_STATUS_CHANGED,  # Generic type
                title=title,
                body=body if body else None,
                entity_type="case",
                entity_id=entity.id,
            )

        return {
            "success": True,
            "recipients_count": len(user_ids),
            "description": f"Sent notification to {len(user_ids)} user(s)",
        }

    def _action_update_field(
        self,
        db: Session,
        action: dict,
        entity: Case,
        event_id: UUID,
        depth: int,
    ) -> dict:
        """Update a case field."""
        field = action.get("field")
        value = action.get("value")

        if field not in ALLOWED_UPDATE_FIELDS:
            return {"success": False, "error": f"Field {field} not allowed for update"}

        old_value = getattr(entity, field, None)

        if field == "stage_id":
            from app.services import pipeline_service
            from app.db.models import CaseStatusHistory

            new_stage_id = UUID(value) if isinstance(value, str) else value
            if new_stage_id == entity.stage_id:
                return {"success": True, "description": "Stage unchanged"}

            stage = pipeline_service.get_stage_by_id(db, new_stage_id)
            current_stage = (
                pipeline_service.get_stage_by_id(db, entity.stage_id)
                if entity.stage_id
                else None
            )
            case_pipeline_id = current_stage.pipeline_id if current_stage else None
            if not case_pipeline_id:
                case_pipeline_id = pipeline_service.get_or_create_default_pipeline(
                    db,
                    entity.organization_id,
                ).id
            if (
                not stage
                or not stage.is_active
                or stage.pipeline_id != case_pipeline_id
            ):
                return {"success": False, "error": "Invalid stage for case pipeline"}

            old_stage_id = entity.stage_id
            old_label = entity.status_label
            old_stage = (
                pipeline_service.get_stage_by_id(db, old_stage_id)
                if old_stage_id
                else None
            )
            old_slug = old_stage.slug if old_stage else None
            entity.stage_id = stage.id
            entity.status_label = stage.label
            entity.updated_at = datetime.now(timezone.utc)

            history = CaseStatusHistory(
                case_id=entity.id,
                organization_id=entity.organization_id,
                from_stage_id=old_stage_id,
                to_stage_id=stage.id,
                from_label_snapshot=old_label,
                to_label_snapshot=stage.label,
                changed_by_user_id=None,
                reason="Workflow update",
            )
            db.add(history)
            db.commit()

            # Trigger status_changed workflow with loop protection
            self.trigger(
                db=db,
                trigger_type=WorkflowTriggerType.STATUS_CHANGED,
                entity_type="case",
                entity_id=entity.id,
                event_data={
                    "case_id": str(entity.id),
                    "old_stage_id": str(old_stage_id) if old_stage_id else None,
                    "new_stage_id": str(stage.id),
                    "old_status": old_slug,
                    "new_status": stage.slug,
                },
                org_id=entity.organization_id,
                event_id=event_id,
                depth=depth + 1,
                source=WorkflowEventSource.WORKFLOW,
            )
        else:
            setattr(entity, field, value)
            entity.updated_at = datetime.now(timezone.utc)
            db.commit()

        # Trigger case_updated workflow
        self.trigger(
            db=db,
            trigger_type=WorkflowTriggerType.CASE_UPDATED,
            entity_type="case",
            entity_id=entity.id,
            event_data={
                "changed_fields": [field],
                "old_values": {
                    field: str(old_value) if old_value is not None else None
                },
                "new_values": {field: str(value)},
            },
            org_id=entity.organization_id,
            event_id=event_id,
            depth=depth + 1,
            source=WorkflowEventSource.WORKFLOW,
        )

        return {
            "success": True,
            "description": f"Updated {field} to {value}",
        }

    def _action_add_note(
        self,
        db: Session,
        action: dict,
        entity: Case,
    ) -> dict:
        """Add a note to the case."""
        content = action.get("content", "")

        # Determine author (prefer owner, fall back to creator)
        author_id = None
        if entity.owner_type == OwnerType.USER.value and entity.owner_id:
            author_id = entity.owner_id
        elif entity.created_by_user_id:
            author_id = entity.created_by_user_id

        if not author_id:
            return {
                "success": False,
                "error": "No user available to author note",
            }

        note = EntityNote(
            organization_id=entity.organization_id,
            entity_type=EntityType.CASE.value,
            entity_id=entity.id,
            content=content,
            author_id=author_id,
        )
        db.add(note)
        db.commit()

        return {
            "success": True,
            "note_id": str(note.id),
            "description": f"Added note: {content[:50]}...",
        }

    def _resolve_email_variables(self, db: Session, case: Case) -> dict:
        """Resolve email template variables from case context."""
        from app.services import email_service

        return email_service.build_case_template_variables(db, case)


# Singleton instance
engine = WorkflowEngine()
