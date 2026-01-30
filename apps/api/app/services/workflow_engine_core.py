"""Workflow engine core - executes workflows with loop protection and action handling."""

import logging
import time
import uuid as uuid_module
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AutomationWorkflow, WorkflowExecution, User
from app.db.enums import (
    OwnerType,
    TaskStatus,
    WorkflowConditionOperator,
    WorkflowEventSource,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)
from app.services import workflow_service
from app.services.workflow_engine_adapters import WorkflowDomainAdapter

logger = logging.getLogger(__name__)

# Maximum recursion depth for workflow-triggered events
MAX_DEPTH = 3


class WorkflowEngineCore:
    """
    Core workflow execution engine.

    Handles trigger evaluation, condition matching, and action execution
    with loop protection and full audit logging.
    """

    def __init__(self, adapter: WorkflowDomainAdapter) -> None:
        self.adapter = adapter

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
        entity_owner_id: UUID | None = None,
    ) -> list[WorkflowExecution]:
        """
        Trigger workflows for an event.

        Args:
            entity_owner_id: The owner_id of the entity when owner_type='user'.
                Used to match personal workflows.

        Returns list of execution records created.
        """
        # Loop protection
        if depth >= MAX_DEPTH:
            logger.warning(f"Max workflow depth ({MAX_DEPTH}) reached for event {event_id}")
            return []

        # Ignore workflow-triggered events at depth > 1
        if source == WorkflowEventSource.WORKFLOW and depth > 1:
            logger.debug(f"Ignoring nested workflow-triggered event at depth {depth}")
            return []

        event_id = event_id or uuid_module.uuid4()
        executions = []

        # Find matching enabled workflows
        workflows = self._find_matching_workflows(
            db, org_id, trigger_type, event_data, entity_owner_id
        )

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
        entity_owner_id: UUID | None = None,
    ) -> list[AutomationWorkflow]:
        """
        Find enabled workflows that match the trigger.

        Scope filtering:
        - Org workflows: always included
        - Personal workflows: only if entity_owner_id matches workflow owner
        """
        from sqlalchemy import and_, or_

        # Build scope filter
        scope_filter = or_(
            AutomationWorkflow.scope == "org",
            and_(
                AutomationWorkflow.scope == "personal",
                AutomationWorkflow.owner_user_id == entity_owner_id,
            ),
        )

        workflows = (
            db.query(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == org_id,
                AutomationWorkflow.trigger_type == trigger_type.value,
                AutomationWorkflow.is_enabled.is_(True),
                scope_filter,
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
            to_status = config.get("to_status")
            from_status = config.get("from_status")

            if to_stage_id and str(event_data.get("new_stage_id")) != str(to_stage_id):
                return False
            if from_stage_id and str(event_data.get("old_stage_id")) != str(from_stage_id):
                return False
            if to_status and str(event_data.get("new_status")) != str(to_status):
                return False
            if from_status and str(event_data.get("old_status")) != str(from_status):
                return False
            return True

        if trigger_type == WorkflowTriggerType.SURROGATE_ASSIGNED:
            to_user_id = config.get("to_user_id")
            if to_user_id and str(event_data.get("new_owner_id")) != str(to_user_id):
                return False
            return True

        if trigger_type == WorkflowTriggerType.SURROGATE_UPDATED:
            required_fields = set(config.get("fields", []))
            changed_fields = set(event_data.get("changed_fields", []))
            return bool(required_fields & changed_fields)

        # For surrogate_created, task_due, task_overdue, scheduled, inactivity
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
        entity = self.adapter.get_entity(db, entity_type, entity_id)
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
            user_opted_out = workflow_service.is_user_opted_out(db, entity.owner_id, workflow.id)

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
        # FAIL FAST: Workflows require user-owned surrogates at trigger time
        # (after conditions match to avoid false failures)
        # =====================================================================
        has_approval_actions = any(action.get("requires_approval") for action in workflow.actions)
        surrogate = self.adapter.get_related_surrogate(db, entity_type, entity)
        surrogate_owner = None

        if surrogate:
            # Validate surrogate has a user owner (not queue/null)
            if surrogate.owner_type != OwnerType.USER.value or not surrogate.owner_id:
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
                    error_message="Workflow requires surrogate owner to be a user",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                db.add(execution)
                db.commit()
                return execution

            # Verify owner exists
            surrogate_owner = db.query(User).filter(User.id == surrogate.owner_id).first()
            if not surrogate_owner:
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
                    error_message="Workflow requires surrogate owner but owner not found",
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
                error_message="Workflow requires approval but entity has no related surrogate",
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
                # Get the surrogate for approval task
                # Create approval task and pause execution
                task = self.adapter.create_approval_task(
                    db=db,
                    workflow=workflow,
                    execution=execution,
                    action=action,
                    action_index=idx,
                    entity=entity,
                    surrogate=surrogate,
                    owner=surrogate_owner,
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
                        "action_type": action.get("action_type"),
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
            result = self.adapter.execute_action(
                db=db,
                action=action,
                entity=entity,
                entity_type=entity_type,
                event_id=event_id,
                depth=depth,
                workflow_scope=workflow.scope,
                workflow_owner_id=workflow.owner_user_id,
                trigger_callback=self.trigger,
            )
            action_results.append(result)
            if not result.get("success"):
                all_success = False

        # Update workflow stats
        workflow.run_count += 1
        workflow.last_run_at = datetime.now(timezone.utc)
        workflow.last_error = (
            None if all_success else (action_results[-1].get("error") if action_results else None)
        )

        # Update execution record
        execution.actions_executed = action_results
        execution.status = (
            WorkflowExecutionStatus.SUCCESS.value
            if all_success
            else WorkflowExecutionStatus.PARTIAL.value
        )
        execution.error_message = (
            None if all_success else (action_results[-1].get("error") if action_results else None)
        )
        execution.duration_ms = int((time.time() - start_time) * 1000)
        db.commit()

        return execution

    def continue_execution(
        self,
        db: Session,
        execution_id: UUID,
        task: Any,
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

        workflow = (
            db.query(AutomationWorkflow)
            .filter(AutomationWorkflow.id == execution.workflow_id)
            .first()
        )

        if not workflow:
            logger.error(f"Workflow {execution.workflow_id} not found for resume")
            return

        # Get entity
        entity = self.adapter.get_entity(db, execution.entity_type, execution.entity_id)
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
                action_results.append(
                    {
                        "success": False,
                        "action_type": task.workflow_action_type,
                        "error": "No action payload",
                    }
                )
                execution.actions_executed = action_results
                execution.status = WorkflowExecutionStatus.FAILED.value
                db.commit()
                return

            # Execute the approved action
            result = self.adapter.execute_action(
                db=db,
                action=action,
                entity=entity,
                entity_type=execution.entity_type,
                event_id=execution.event_id,
                depth=execution.depth,
                workflow_scope=workflow.scope,
                workflow_owner_id=workflow.owner_user_id,
                trigger_callback=self.trigger,
            )
            action_results.append(result)

            # Continue with remaining actions
            remaining_actions = workflow.actions[action_index + 1 :]
            for idx, next_action in enumerate(remaining_actions):
                actual_idx = action_index + 1 + idx

                if next_action.get("requires_approval"):
                    # Need another approval - pause again
                    surrogate = self.adapter.get_related_surrogate(
                        db, execution.entity_type, entity
                    )
                    owner = (
                        db.query(User).filter(User.id == surrogate.owner_id).first()
                        if surrogate
                        else None
                    )

                    if not surrogate or not owner:
                        action_results.append(
                            {
                                "success": False,
                                "action_type": next_action.get("action_type"),
                                "error": "Surrogate or owner not found for approval",
                            }
                        )
                        execution.actions_executed = action_results
                        execution.status = WorkflowExecutionStatus.FAILED.value
                        execution.error_message = "Workflow requires surrogate owner to be a user"
                        db.commit()
                        return

                    new_task = self.adapter.create_approval_task(
                        db=db,
                        workflow=workflow,
                        execution=execution,
                        action=next_action,
                        action_index=actual_idx,
                        entity=entity,
                        surrogate=surrogate,
                        owner=owner,
                        triggered_by_user_id=task.workflow_triggered_by_user_id,
                    )

                    if new_task:
                        execution.status = WorkflowExecutionStatus.PAUSED.value
                        execution.paused_at_action_index = actual_idx
                        execution.paused_task_id = new_task.id
                        execution.actions_executed = action_results
                        db.commit()
                        logger.info(f"Workflow {workflow.id} paused again at action {actual_idx}")
                        return

                # Execute non-approval action
                result = self.adapter.execute_action(
                    db=db,
                    action=next_action,
                    entity=entity,
                    entity_type=execution.entity_type,
                    event_id=execution.event_id,
                    depth=execution.depth,
                    workflow_scope=workflow.scope,
                    workflow_owner_id=workflow.owner_user_id,
                    trigger_callback=self.trigger,
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
            action_results.append(
                {
                    "success": False,
                    "action_type": task.workflow_action_type,
                    "skipped": True,
                    "reason": "denied",
                }
            )
            execution.status = WorkflowExecutionStatus.CANCELED.value
            execution.error_message = (
                f"Approval denied: {task.workflow_denial_reason or 'No reason given'}"
            )
            execution.actions_executed = action_results
            db.commit()

        elif task.status == TaskStatus.EXPIRED.value:
            # EXPIRED: Mark execution as expired
            action_results.append(
                {
                    "success": False,
                    "action_type": task.workflow_action_type,
                    "skipped": True,
                    "reason": "expired",
                }
            )
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
            db.query(WorkflowExecution).filter(WorkflowExecution.dedupe_key == dedupe_key).first()
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

        def _normalize_list_value(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return [str(value).strip()] if str(value).strip() else []

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
            values = _normalize_list_value(condition_value)
            if not values:
                return False
            return str(entity_value) in values

        if operator == WorkflowConditionOperator.NOT_IN.value:
            values = _normalize_list_value(condition_value)
            if not values:
                return True
            return str(entity_value) not in values

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
