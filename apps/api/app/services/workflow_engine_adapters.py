"""Workflow engine adapters for domain-specific behavior."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import SYSTEM_USER_ID, WORKFLOW_APPROVAL_TIMEOUT_HOURS
from app.db.enums import (
    EntityType,
    JobType,
    OwnerType,
    TaskStatus,
    TaskType,
    WorkflowActionType,
    WorkflowEventSource,
    WorkflowTriggerType,
)
from app.db.models import (
    Appointment,
    Attachment,
    AutomationWorkflow,
    EntityNote,
    Match,
    Organization,
    Surrogate,
    Task,
    User,
    WorkflowExecution,
)
from app.schemas.workflow import ALLOWED_UPDATE_FIELDS
from app.services import job_service, notification_facade
from app.services.workflow_action_preview import build_action_preview, render_action_payload
from app.utils.business_hours import calculate_approval_due_date

logger = logging.getLogger(__name__)

TriggerCallback = Callable[..., list[WorkflowExecution]]


class WorkflowDomainAdapter(Protocol):
    def get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any: ...

    def get_related_surrogate(
        self,
        db: Session,
        entity_type: str,
        entity: Any,
    ) -> Surrogate | None: ...

    def create_approval_task(
        self,
        db: Session,
        workflow: AutomationWorkflow,
        execution: WorkflowExecution,
        action: dict,
        action_index: int,
        entity: Any,
        surrogate: Surrogate,
        owner: User,
        triggered_by_user_id: UUID | None,
    ) -> Task | None: ...

    def execute_action(
        self,
        db: Session,
        action: dict,
        entity: Any,
        entity_type: str,
        event_id: UUID,
        depth: int,
        workflow_scope: str = "org",
        workflow_owner_id: UUID | None = None,
        trigger_callback: TriggerCallback | None = None,
    ) -> dict: ...


class DefaultWorkflowDomainAdapter:
    """Default adapter backed by current domain services and models."""

    # Actions that require the entity to be a Surrogate
    SURROGATE_ONLY_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.ASSIGN_SURROGATE.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }

    def get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any:
        """Get entity by type and ID."""
        if entity_type == "surrogate":
            return db.query(Surrogate).filter(Surrogate.id == entity_id).first()
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

    def get_related_surrogate(
        self,
        db: Session,
        entity_type: str,
        entity: Any,
    ) -> Surrogate | None:
        """Get the surrogate related to an entity."""
        if entity_type == "surrogate":
            return entity
        if hasattr(entity, "surrogate_id") and entity.surrogate_id:
            query = db.query(Surrogate).filter(Surrogate.id == entity.surrogate_id)
            if hasattr(entity, "organization_id"):
                query = query.filter(Surrogate.organization_id == entity.organization_id)
            return query.first()
        return None

    def create_approval_task(
        self,
        db: Session,
        workflow: AutomationWorkflow,
        execution: WorkflowExecution,
        action: dict,
        action_index: int,
        entity: Any,
        surrogate: Surrogate,
        owner: User,
        triggered_by_user_id: UUID | None,
    ) -> Task | None:
        """
        Create an approval task for a workflow action.

        Returns the task if created or already exists (idempotency).
        """
        # Get organization for timezone fallback
        org = db.query(Organization).filter(Organization.id == surrogate.organization_id).first()

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
            surrogate_id=surrogate.id,
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
            notification_facade.notify_workflow_approval_requested(
                db=db,
                task_id=task.id,
                task_title=task.title,
                org_id=surrogate.organization_id,
                assignee_id=owner.id,
                surrogate_number=surrogate.surrogate_number,
            )

            return task

        except IntegrityError:
            # Idempotency: task already exists for this execution+action
            db.rollback()
            existing = (
                db.query(Task)
                .filter(
                    Task.workflow_execution_id == execution.id,
                    Task.workflow_action_index == action_index,
                )
                .first()
            )
            logger.info(f"Approval task already exists: {existing.id if existing else 'unknown'}")
            return existing

    def execute_action(
        self,
        db: Session,
        action: dict,
        entity: Any,
        entity_type: str,
        event_id: UUID,
        depth: int,
        workflow_scope: str = "org",
        workflow_owner_id: UUID | None = None,
        trigger_callback: TriggerCallback | None = None,
    ) -> dict:
        """Execute a single action."""
        action_type = action.get("action_type")
        action_entity = entity

        def _with_action_type(result: dict) -> dict:
            if action_type and "action_type" not in result:
                result["action_type"] = action_type
            return result

        # Validate entity type for Surrogate-only actions, map tasks to surrogates when possible
        if action_type in self.SURROGATE_ONLY_ACTIONS:
            if entity_type == "task":
                surrogate_id = getattr(entity, "surrogate_id", None)
                if not surrogate_id:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": "Task is not linked to a surrogate",
                            "skipped": True,
                        }
                    )
                action_entity = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
                if not action_entity:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": "Surrogate not found for task",
                            "skipped": True,
                        }
                    )
            elif entity_type != "surrogate":
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"Action '{action_type}' only supports Surrogate entities, got '{entity_type}'",
                        "skipped": True,
                    }
                )

        try:
            if action_type == WorkflowActionType.SEND_EMAIL.value:
                result = self._action_send_email(
                    db, action, action_entity, event_id, workflow_scope, workflow_owner_id
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.CREATE_TASK.value:
                result = self._action_create_task(db, action, action_entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.ASSIGN_SURROGATE.value:
                result = self._action_assign_surrogate(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_NOTIFICATION.value:
                result = self._action_send_notification(db, action, entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.UPDATE_FIELD.value:
                result = self._action_update_field(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ADD_NOTE.value:
                result = self._action_add_note(db, action, action_entity)
                return _with_action_type(result)

            return _with_action_type(
                {"success": False, "error": f"Unknown action type: {action_type}"}
            )

        except Exception as e:
            logger.exception(f"Action {action_type} failed: {e}")
            # Create system alert for workflow action failure
            try:
                from app.services import alert_service
                from app.db.enums import AlertSeverity, AlertType

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
            return _with_action_type({"success": False, "error": str(e)})

    # =========================================================================
    # Action Executors
    # =========================================================================

    def _action_send_email(
        self,
        db: Session,
        action: dict,
        entity: Surrogate,
        event_id: UUID,
        workflow_scope: str = "org",
        workflow_owner_id: UUID | None = None,
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
                "surrogate_id": str(entity.id),
                "event_id": str(event_id),
                # Scope info for email provider resolution
                "workflow_scope": workflow_scope,
                "workflow_owner_id": str(workflow_owner_id) if workflow_owner_id else None,
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
        entity: Surrogate,
    ) -> dict:
        """Create a task on the surrogate."""
        from datetime import timedelta

        from app.schemas.task import TaskCreate
        from app.services import task_service

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
        elif isinstance(assignee, str) and assignee.startswith(("admin", "owner", "creator")):
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
            surrogate_id=entity.id,
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

    def _action_assign_surrogate(
        self,
        db: Session,
        action: dict,
        entity: Surrogate,
        event_id: UUID,
        depth: int,
        trigger_callback: TriggerCallback | None,
    ) -> dict:
        """Assign surrogate to user or queue."""
        owner_type = action.get("owner_type")
        owner_id = action.get("owner_id")

        old_owner_type = entity.owner_type
        old_owner_id = entity.owner_id

        entity.owner_type = owner_type
        entity.owner_id = UUID(owner_id) if isinstance(owner_id, str) else owner_id
        entity.updated_at = datetime.now(timezone.utc)

        db.commit()

        # Trigger surrogate_assigned workflow (with increased depth to prevent loops)
        if trigger_callback:
            trigger_callback(
                db=db,
                trigger_type=WorkflowTriggerType.SURROGATE_ASSIGNED,
                entity_type="surrogate",
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
            "description": f"Assigned surrogate to {owner_type}:{owner_id}",
        }

    def _action_send_notification(
        self,
        db: Session,
        action: dict,
        entity: Any,
    ) -> dict:
        """Send in-app notification."""
        from app.db.enums import NotificationType
        from app.db.models import Membership
        from app.db.enums import Role

        title = action.get("title", "Workflow Notification")
        body = action.get("body", "")
        recipients = action.get("recipients", "owner")

        target = entity
        if not hasattr(entity, "owner_type"):
            surrogate_id = getattr(entity, "surrogate_id", None)
            if surrogate_id:
                target = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
        if not target or not hasattr(target, "organization_id"):
            return {"success": False, "error": "No related surrogate for notification recipients"}

        # Determine recipient user IDs
        user_ids = []
        if recipients == "owner" and target.owner_type == OwnerType.USER.value:
            user_ids = [target.owner_id]
        elif recipients == "creator":
            user_ids = [target.created_by_user_id] if target.created_by_user_id else []
        elif recipients == "all_admins":
            memberships = (
                db.query(Membership)
                .filter(
                    Membership.organization_id == target.organization_id,
                    Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]),
                    Membership.is_active.is_(True),
                )
                .all()
            )
            user_ids = [m.user_id for m in memberships]
        elif isinstance(recipients, list):
            user_ids = [UUID(r) if isinstance(r, str) else r for r in recipients]

        # Create notifications
        for user_id in user_ids:
            notification_facade.create_notification(
                db=db,
                org_id=target.organization_id,
                user_id=user_id,
                type=NotificationType.SURROGATE_STATUS_CHANGED,  # Generic type
                title=title,
                body=body if body else None,
                entity_type="surrogate",
                entity_id=target.id,
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
        entity: Surrogate,
        event_id: UUID,
        depth: int,
        trigger_callback: TriggerCallback | None,
    ) -> dict:
        """Update a surrogate field."""
        from app.db.models import SurrogateStatusHistory
        from app.services import pipeline_service

        field = action.get("field")
        value = action.get("value")

        if field not in ALLOWED_UPDATE_FIELDS:
            return {"success": False, "error": f"Field {field} not allowed for update"}

        old_value = getattr(entity, field, None)

        if field == "stage_id":
            new_stage_id = UUID(value) if isinstance(value, str) else value
            if new_stage_id == entity.stage_id:
                return {"success": True, "description": "Stage unchanged"}

            stage = pipeline_service.get_stage_by_id(db, new_stage_id)
            current_stage = (
                pipeline_service.get_stage_by_id(db, entity.stage_id) if entity.stage_id else None
            )
            surrogate_pipeline_id = current_stage.pipeline_id if current_stage else None
            if not surrogate_pipeline_id:
                surrogate_pipeline_id = pipeline_service.get_or_create_default_pipeline(
                    db,
                    entity.organization_id,
                ).id
            if not stage or not stage.is_active or stage.pipeline_id != surrogate_pipeline_id:
                return {"success": False, "error": "Invalid stage for surrogate pipeline"}

            old_stage_id = entity.stage_id
            old_label = entity.status_label
            old_stage = pipeline_service.get_stage_by_id(db, old_stage_id) if old_stage_id else None
            old_slug = old_stage.slug if old_stage else None
            entity.stage_id = stage.id
            entity.status_label = stage.label
            entity.updated_at = datetime.now(timezone.utc)

            history = SurrogateStatusHistory(
                surrogate_id=entity.id,
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
            if trigger_callback:
                trigger_callback(
                    db=db,
                    trigger_type=WorkflowTriggerType.STATUS_CHANGED,
                    entity_type="surrogate",
                    entity_id=entity.id,
                    event_data={
                        "surrogate_id": str(entity.id),
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

        # Trigger surrogate_updated workflow
        if trigger_callback:
            trigger_callback(
                db=db,
                trigger_type=WorkflowTriggerType.SURROGATE_UPDATED,
                entity_type="surrogate",
                entity_id=entity.id,
                event_data={
                    "changed_fields": [field],
                    "old_values": {field: str(old_value) if old_value is not None else None},
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
        entity: Surrogate,
    ) -> dict:
        """Add a note to the surrogate."""
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
            entity_type=EntityType.SURROGATE.value,
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

    def _resolve_email_variables(self, db: Session, surrogate: Surrogate) -> dict:
        """Resolve email template variables from surrogate context."""
        from app.services import email_service

        return email_service.build_surrogate_template_variables(db, surrogate)
