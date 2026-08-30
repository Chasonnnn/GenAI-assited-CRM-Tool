"""Workflow engine adapters for domain-specific behavior."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
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
    Donor,
    EmailTemplate,
    EntityNote,
    FormSubmission,
    IntakeLead,
    Match,
    MessageTemplate,
    MessagingContact,
    Organization,
    PipelineStage,
    Surrogate,
    Task,
    User,
    WorkflowExecution,
)
from app.schemas.workflow import ALLOWED_UPDATE_FIELDS, DONOR_ALLOWED_UPDATE_FIELDS
from app.services import job_service, notification_facade
from app.services.workflow_action_preview import build_action_preview, render_action_payload
from app.utils.business_hours import calculate_approval_due_date

logger = logging.getLogger(__name__)

TriggerCallback = Callable[..., list[WorkflowExecution]]


class WorkflowDomainAdapter(Protocol):
    def get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any: ...

    def resolve_subject_context(
        self, db: Session, entity_type: str, entity_id: UUID
    ) -> tuple[str, UUID] | None: ...

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
        surrogate: Surrogate | None,
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
        workflow_creator_user_id: UUID | None = None,
        trigger_callback: TriggerCallback | None = None,
        workflow_execution_id: UUID | None = None,
        workflow_action_index: int | None = None,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> dict: ...


class DefaultWorkflowDomainAdapter:
    """Default adapter backed by current domain services and models."""

    # Actions that require the entity to be a Surrogate
    SURROGATE_ONLY_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.ASSIGN_SURROGATE.value,
        WorkflowActionType.SEND_ZAPIER_CONVERSION_EVENT.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }
    INTAKE_LEAD_ONLY_ACTIONS = {"promote_intake_lead"}
    FORM_SUBMISSION_ONLY_ACTIONS = {
        WorkflowActionType.AUTO_MATCH_SUBMISSION.value,
        WorkflowActionType.CREATE_INTAKE_LEAD.value,
    }
    DONOR_COMPATIBLE_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.ASSIGN_DONOR.value,
        WorkflowActionType.SEND_NOTIFICATION.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }

    def get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any:
        """Get entity by type and ID."""
        if entity_type == "surrogate":
            return db.query(Surrogate).filter(Surrogate.id == entity_id).first()
        if entity_type == "donor":
            return db.query(Donor).filter(Donor.id == entity_id).first()
        if entity_type == "form_submission":
            return db.query(FormSubmission).filter(FormSubmission.id == entity_id).first()
        if entity_type == "intake_lead":
            return db.query(IntakeLead).filter(IntakeLead.id == entity_id).first()
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

    def resolve_subject_context(
        self,
        db: Session,
        entity_type: str,
        entity_id: UUID,
    ) -> tuple[str, UUID] | None:
        entity = self.get_entity(db, entity_type, entity_id)
        if entity is None:
            return None
        if isinstance(entity, Donor):
            return entity.pipeline_entity_type, entity.id
        if isinstance(entity, Surrogate):
            return "surrogate", entity.id
        if entity_type in {"form_submission", "intake_lead", "match", "appointment"}:
            return entity_type, entity.id

        donor_id = getattr(entity, "donor_id", None)
        if donor_id:
            donor = (
                db.query(Donor)
                .filter(
                    Donor.id == donor_id,
                    Donor.organization_id == entity.organization_id,
                )
                .first()
            )
            if donor:
                return donor.pipeline_entity_type, donor.id

        surrogate_id = getattr(entity, "surrogate_id", None)
        if surrogate_id:
            surrogate = (
                db.query(Surrogate)
                .filter(
                    Surrogate.id == surrogate_id,
                    Surrogate.organization_id == entity.organization_id,
                )
                .first()
            )
            if surrogate:
                return "surrogate", surrogate.id

        if isinstance(entity, EntityNote):
            if entity.entity_type == "donor":
                donor = (
                    db.query(Donor)
                    .filter(
                        Donor.id == entity.entity_id,
                        Donor.organization_id == entity.organization_id,
                    )
                    .first()
                )
                if donor:
                    return donor.pipeline_entity_type, donor.id
            if entity.entity_type == "surrogate":
                return "surrogate", entity.entity_id

        if isinstance(entity, Attachment):
            donor = (
                db.query(Donor)
                .filter(
                    Donor.organization_id == entity.organization_id,
                    Donor.profile_photo_attachment_id == entity.id,
                )
                .first()
            )
            if donor:
                return donor.pipeline_entity_type, donor.id
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
        if entity_type == "intake_lead":
            promoted_surrogate_id = getattr(entity, "promoted_surrogate_id", None)
            if not promoted_surrogate_id:
                return None
            query = db.query(Surrogate).filter(Surrogate.id == promoted_surrogate_id)
            if hasattr(entity, "organization_id"):
                query = query.filter(Surrogate.organization_id == entity.organization_id)
            return query.first()
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
        surrogate: Surrogate | None,
        owner: User,
        triggered_by_user_id: UUID | None,
    ) -> Task | None:
        """
        Create an approval task for a workflow action.

        Returns the task if created or already exists (idempotency).
        """
        # Get organization for timezone fallback
        org = db.query(Organization).filter(Organization.id == execution.organization_id).first()
        donor = None
        if execution.subject_type in {"egg_donor", "sperm_donor"} and execution.subject_id:
            donor = (
                db.query(Donor)
                .filter(
                    Donor.id == execution.subject_id,
                    Donor.organization_id == execution.organization_id,
                    Donor.donor_type == execution.subject_type.removesuffix("_donor"),
                )
                .first()
            )

        # Build sanitized preview (no PII)
        preview = build_action_preview(db, action, donor or entity)

        # Build payload snapshot (internal only, never exposed via API)
        payload = render_action_payload(action, entity)

        # Calculate due date (48 business hours)
        now = datetime.now(UTC)
        due_at = calculate_approval_due_date(
            start_utc=now,
            owner=owner,
            org=org,
            timeout_hours=WORKFLOW_APPROVAL_TIMEOUT_HOURS,
        )

        task = Task(
            organization_id=execution.organization_id,
            surrogate_id=surrogate.id if surrogate and not donor else None,
            donor_id=donor.id if donor else None,
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
                org_id=execution.organization_id,
                assignee_id=owner.id,
                surrogate_number=surrogate.surrogate_number if surrogate else None,
                donor_number=donor.donor_number if donor else None,
                donor_type=donor.donor_type if donor else None,
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
        workflow_creator_user_id: UUID | None = None,
        trigger_callback: TriggerCallback | None = None,
        workflow_execution_id: UUID | None = None,
        workflow_action_index: int | None = None,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
    ) -> dict:
        """Execute a single action."""
        action_type = action.get("action_type")
        action_entity = entity

        def _with_action_type(result: dict) -> dict:
            if action_type and "action_type" not in result:
                result["action_type"] = action_type
            return result

        if subject_type in {"egg_donor", "sperm_donor"}:
            if action_type not in self.DONOR_COMPATIBLE_ACTIONS:
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"Action '{action_type}' does not support donor subjects",
                        "skipped": True,
                    }
                )
            if subject_id is None:
                return _with_action_type(
                    {"success": False, "error": "Donor subject is missing", "skipped": True}
                )
            action_entity = (
                db.query(Donor)
                .filter(
                    Donor.id == subject_id,
                    Donor.organization_id == entity.organization_id,
                    Donor.donor_type == subject_type.removesuffix("_donor"),
                )
                .first()
            )
            if action_entity is None:
                return _with_action_type(
                    {"success": False, "error": "Donor subject not found", "skipped": True}
                )

        # Validate entity type for Surrogate-only actions, map tasks to surrogates when possible
        if action_type in self.SURROGATE_ONLY_ACTIONS and not isinstance(action_entity, Donor):
            if entity_type in {"task", "form_submission"}:
                surrogate_id = getattr(entity, "surrogate_id", None)
                if not surrogate_id:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"{entity_type.replace('_', ' ').title()} is not linked to a surrogate",
                            "skipped": True,
                        }
                    )
                action_entity = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
                if not action_entity:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"Surrogate not found for {entity_type.replace('_', ' ')}",
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

        if action_type == WorkflowActionType.SEND_MESSAGE.value:
            donor_intake_entity = (
                isinstance(entity, FormSubmission)
                and entity.lead_kind in {"egg_donor", "sperm_donor"}
            ) or (
                isinstance(entity, IntakeLead)
                and entity.lead_type in {"egg_donor", "sperm_donor"}
            )
            if isinstance(action_entity, Donor) or donor_intake_entity:
                return _with_action_type(
                    {
                        "success": False,
                        "error": "Action 'send_message' does not support donor subjects",
                        "skipped": True,
                    }
                )
            if entity_type in {"task", "form_submission"}:
                surrogate_id = getattr(entity, "surrogate_id", None)
                if not surrogate_id:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"{entity_type.replace('_', ' ').title()} is not linked to a surrogate",
                            "skipped": True,
                        }
                    )
                action_entity = (
                    db.query(Surrogate)
                    .filter(
                        Surrogate.id == surrogate_id,
                        Surrogate.organization_id == entity.organization_id,
                    )
                    .first()
                )
                if action_entity is None:
                    return _with_action_type(
                        {"success": False, "error": "Message recipient not found", "skipped": True}
                    )
            elif entity_type not in {"surrogate", "intake_lead"}:
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"Action '{action_type}' does not support '{entity_type}' entities",
                        "skipped": True,
                    }
                )

        if action_type in self.INTAKE_LEAD_ONLY_ACTIONS and entity_type != "intake_lead":
            return _with_action_type(
                {
                    "success": False,
                    "error": f"Action '{action_type}' only supports intake_lead entities",
                    "skipped": True,
                }
            )

        if action_type in self.FORM_SUBMISSION_ONLY_ACTIONS and entity_type != "form_submission":
            return _with_action_type(
                {
                    "success": False,
                    "error": f"Action '{action_type}' only supports form_submission entities",
                    "skipped": True,
                }
            )

        try:
            if action_type == WorkflowActionType.SEND_EMAIL.value:
                result = self._action_send_email(
                    db=db,
                    action=action,
                    entity=action_entity,
                    event_id=event_id,
                    workflow_scope=workflow_scope,
                    workflow_owner_id=workflow_owner_id,
                    workflow_creator_user_id=workflow_creator_user_id,
                    workflow_execution_id=workflow_execution_id,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_MESSAGE.value:
                result = self._action_send_message(
                    db=db,
                    action=action,
                    entity=action_entity,
                    workflow_scope=workflow_scope,
                    workflow_execution_id=workflow_execution_id,
                    workflow_action_index=workflow_action_index,
                )
                if result.get("success") is False:
                    return result
                return _with_action_type(result)

            if action_type == WorkflowActionType.CREATE_TASK.value:
                result = self._action_create_task(
                    db,
                    action,
                    action_entity,
                    workflow_actor_id=workflow_owner_id or workflow_creator_user_id,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ASSIGN_SURROGATE.value:
                result = self._action_assign_surrogate(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ASSIGN_DONOR.value:
                result = self._action_assign_donor(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_NOTIFICATION.value:
                result = self._action_send_notification(db, action, action_entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_ZAPIER_CONVERSION_EVENT.value:
                result = self._action_send_zapier_conversion_event(db, action_entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.UPDATE_FIELD.value:
                result = self._action_update_field(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ADD_NOTE.value:
                result = self._action_add_note(
                    db,
                    action,
                    action_entity,
                    workflow_actor_id=workflow_owner_id or workflow_creator_user_id,
                )
                return _with_action_type(result)

            if action_type == "promote_intake_lead":
                result = self._action_promote_intake_lead(db, action, entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.AUTO_MATCH_SUBMISSION.value:
                result = self._action_auto_match_submission(db, entity)
                return _with_action_type(result)

            if action_type == WorkflowActionType.CREATE_INTAKE_LEAD.value:
                result = self._action_create_intake_lead(db, action, entity)
                return _with_action_type(result)

            return _with_action_type(
                {"success": False, "error": f"Unknown action type: {action_type}"}
            )

        except Exception as e:
            logger.exception(f"Action {action_type} failed: {e}")
            from app.db.enums import AlertSeverity, AlertType
            from app.services import alert_service

            org_id = getattr(entity, "organization_id", None)
            if org_id:
                alert_service.record_alert_isolated(
                    org_id=org_id,
                    alert_type=AlertType.WORKFLOW_EXECUTION_FAILED,
                    severity=AlertSeverity.ERROR,
                    title=f"Workflow action '{action_type}' failed",
                    message=str(e)[:500],
                    integration_key="workflow_engine",
                    error_class=type(e).__name__,
                )
            return _with_action_type({"success": False, "error": str(e)})

    # =========================================================================
    # Action Executors
    # =========================================================================

    def _action_send_email(
        self,
        db: Session,
        action: dict,
        entity: Surrogate | Donor,
        event_id: UUID,
        workflow_scope: str = "org",
        workflow_owner_id: UUID | None = None,
        workflow_creator_user_id: UUID | None = None,
        workflow_execution_id: UUID | None = None,
    ) -> dict:
        """Queue an email using template."""
        template_id = action.get("template_id")
        recipients = action.get("recipients", "subject")

        recipient_emails: list[str] = []
        if isinstance(recipients, str) and recipients in {
            "surrogate",
            "donor",
            "subject",
        }:
            if entity.email:
                recipient_emails = [entity.email]
        elif isinstance(entity, Donor):
            recipient_emails = self._resolve_donor_internal_email_recipients(
                db,
                entity,
                recipients,
                workflow_creator_user_id=workflow_creator_user_id,
            )
        elif recipients == "owner":
            if entity.owner_type == OwnerType.USER.value and entity.owner_id:
                owner = db.query(User).filter(User.id == entity.owner_id).first()
                if owner and owner.email:
                    recipient_emails = [owner.email]
        elif recipients == "creator":
            creator_id = getattr(entity, "created_by_user_id", None)
            if creator_id:
                creator = db.query(User).filter(User.id == creator_id).first()
                if creator and creator.email:
                    recipient_emails = [creator.email]
        elif recipients == "all_admins":
            from app.db.enums import Role
            from app.db.models import Membership

            rows = (
                db.query(User.email)
                .join(Membership, Membership.user_id == User.id)
                .filter(
                    Membership.organization_id == entity.organization_id,
                    Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]),
                    Membership.is_active.is_(True),
                    User.is_active.is_(True),
                )
                .all()
            )
            recipient_emails = [row[0] for row in rows if row and row[0]]
        elif isinstance(recipients, list):
            from app.db.models import Membership

            recipient_ids = [UUID(r) if isinstance(r, str) else r for r in recipients]
            rows = (
                db.query(User.email)
                .join(Membership, Membership.user_id == User.id)
                .filter(
                    Membership.organization_id == entity.organization_id,
                    Membership.user_id.in_(recipient_ids),
                    Membership.is_active.is_(True),
                    User.is_active.is_(True),
                )
                .all()
            )
            recipient_emails = [row[0] for row in rows if row and row[0]]

        if not recipient_emails:
            return {"success": False, "error": "No recipient emails resolved"}

        try:
            resolved_template_id = UUID(str(template_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("Email template not found") from exc
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == resolved_template_id,
                EmailTemplate.organization_id == entity.organization_id,
            )
            .with_for_update()
            .first()
        )
        if template is None or not template.is_active:
            raise ValueError("Email template not found")
        from app.services import system_email_template_service

        if (
            template.system_key
            and template.system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
        ):
            raise ValueError(
                f"Platform system template '{template.system_key}' cannot be used in workflow "
                "emails. Use the platform/system endpoint instead."
            )
        if workflow_scope == "org" and template.scope != "org":
            raise ValueError("Email template not found")
        if (
            workflow_scope == "personal"
            and template.scope == "personal"
            and template.owner_user_id != workflow_owner_id
        ):
            raise ValueError("Email template not found")

        from app.services.email_template_snapshot import (
            build_snapshot,
            format_from_address,
        )
        from app.services.workflow_email_provider import (
            EmailProviderError,
            resolve_workflow_email_provider,
        )

        try:
            provider, provider_config = resolve_workflow_email_provider(
                db=db,
                scope=workflow_scope,
                org_id=entity.organization_id,
                owner_user_id=workflow_owner_id,
            )
        except EmailProviderError as exc:
            raise ValueError(str(exc)) from exc
        if workflow_scope == "org" and provider != "resend":
            raise ValueError("Org workflows must use Resend")
        if provider == "resend":
            effective_from_email = format_from_address(
                (template.from_email or "").strip() or provider_config.get("from_email"),
                provider_config.get("from_name"),
            )
        else:
            effective_from_email = (provider_config.get("email") or "").strip() or None
        template_snapshot = build_snapshot(
            template,
            effective_from_email=effective_from_email,
            include_scope=True,
        )

        # Resolve variables
        variables = self._resolve_email_variables(db, entity)

        job_ids: list[str] = []
        for email in sorted(set(recipient_emails)):
            job = job_service.schedule_job(
                db=db,
                org_id=entity.organization_id,
                job_type=JobType.WORKFLOW_EMAIL,
                payload={
                    "template_id": str(resolved_template_id),
                    "email_template_snapshot": template_snapshot,
                    "recipient_email": email,
                    "variables": variables,
                    "surrogate_id": str(entity.id) if isinstance(entity, Surrogate) else None,
                    "subject_type": entity.pipeline_entity_type
                    if isinstance(entity, Donor)
                    else "surrogate",
                    "subject_id": str(entity.id),
                    "event_id": str(event_id),
                    "workflow_execution_id": (
                        str(workflow_execution_id) if workflow_execution_id else None
                    ),
                    # Scope info for email provider resolution
                    "workflow_scope": workflow_scope,
                    "workflow_owner_id": str(workflow_owner_id) if workflow_owner_id else None,
                },
            )
            job_ids.append(str(job.id))

        return {
            "success": True,
            "queued": True,
            "job_ids": job_ids,
            "queued_count": len(job_ids),
            "description": f"Queued {len(job_ids)} email(s)",
        }

    def _resolve_donor_internal_email_recipients(
        self,
        db: Session,
        donor: Donor,
        recipients: Any,
        *,
        workflow_creator_user_id: UUID | None,
    ) -> list[str]:
        """Resolve internal donor recipients through current org access."""
        from app.db.enums import Role
        from app.db.models import Membership
        from app.services import task_service

        recipient_ids: list[UUID] | None = None
        if recipients == "owner":
            recipient_ids = (
                [donor.owner_id]
                if donor.owner_type == OwnerType.USER.value and donor.owner_id
                else []
            )
        elif recipients == "creator":
            creator_id = getattr(donor, "created_by_user_id", None)
            recipient_ids = [creator_id or workflow_creator_user_id]
            recipient_ids = [recipient_id for recipient_id in recipient_ids if recipient_id]
        elif isinstance(recipients, list):
            try:
                recipient_ids = [
                    UUID(recipient_id) if isinstance(recipient_id, str) else recipient_id
                    for recipient_id in recipients
                ]
            except (TypeError, ValueError):
                return []
        elif recipients != "all_admins":
            return []

        query = (
            db.query(User.email, Membership.user_id, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .filter(
                Membership.organization_id == donor.organization_id,
                Membership.is_active.is_(True),
                User.is_active.is_(True),
            )
        )
        if recipients == "all_admins":
            query = query.filter(
                Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value])
            )
        else:
            if not recipient_ids:
                return []
            query = query.filter(Membership.user_id.in_(set(recipient_ids)))

        return [
            email
            for email, user_id, role in query.all()
            if email
            and task_service.user_can_view_donors(
                db,
                donor.organization_id,
                user_id,
                role=role,
            )
        ]

    def _action_send_message(
        self,
        db: Session,
        action: dict,
        entity: Surrogate | Donor | IntakeLead,
        *,
        workflow_scope: str,
        workflow_execution_id: UUID | None,
        workflow_action_index: int | None,
    ) -> dict:
        """Materialize one consent-gated message outbox occurrence."""
        if workflow_scope != "org":
            raise ValueError("send_message is only supported for org workflows")
        if workflow_execution_id is None or workflow_action_index is None:
            raise ValueError("Workflow messaging requires an execution occurrence")
        purpose = action.get("purpose")
        if purpose not in {"operational", "promotional"}:
            raise ValueError("Message purpose must be operational or promotional")
        try:
            template_id = UUID(str(action.get("message_template_version_id")))
        except (TypeError, ValueError) as exc:
            raise ValueError("Published message template not found") from exc
        template = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.id == template_id,
                MessageTemplate.organization_id == entity.organization_id,
                MessageTemplate.status == "published",
                MessageTemplate.purpose == purpose,
            )
            .first()
        )
        if template is None:
            raise ValueError("Published message template not found")

        contact = None
        if entity.phone_hash:
            contact = (
                db.query(MessagingContact)
                .filter(
                    MessagingContact.organization_id == entity.organization_id,
                    MessagingContact.phone_hash == entity.phone_hash,
                )
                .first()
            )
        if contact is None:
            return {
                "success": False,
                "error": "No consented messaging contact resolved",
                "skipped": True,
            }

        if isinstance(entity, (Surrogate, Donor)):
            variables = self._resolve_email_variables(db, entity)
        else:
            org = db.query(Organization).filter(Organization.id == entity.organization_id).first()
            variables = {
                "full_name": entity.full_name or "",
                "email": entity.email or "",
                "phone": entity.phone or "",
                "org_name": org.name if org else "",
            }
        from app.services import email_service, messaging_delivery_service

        _subject, body = email_service.render_template("", template.body, variables)
        try:
            delivery = messaging_delivery_service.materialize_delivery(
                db,
                organization_id=entity.organization_id,
                contact_id=contact.id,
                purpose=purpose,
                body=body,
                idempotency_key=(
                    f"workflow-message/{workflow_execution_id}/action/{workflow_action_index}"
                ),
                source_type="workflow_execution",
                source_id=workflow_execution_id,
                template_version_id=template.id,
                media_asset_ids=[],
                is_enrollment_confirmation=template.is_enrollment_confirmation,
            )
        return {
            "success": True,
            "queued": True,
            "delivery_id": str(delivery.id),
            "description": "Queued consent-gated message",
        }

    def _action_create_task(
        self,
        db: Session,
        action: dict,
        entity: Surrogate | Donor,
        workflow_actor_id: UUID | None = None,
    ) -> dict:
        """Create a task linked to the workflow subject."""
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
            owner_id = getattr(entity, "created_by_user_id", None) or entity.owner_id
        elif isinstance(assignee, str) and assignee.startswith(("admin", "owner", "creator")):
            owner_type = entity.owner_type
            owner_id = entity.owner_id
        else:
            owner_type = OwnerType.USER.value
            owner_id = UUID(assignee) if assignee else None

        due_date = datetime.now(UTC) + timedelta(days=due_days)

        actor_user_id = getattr(entity, "created_by_user_id", None)
        if not actor_user_id and entity.owner_type == OwnerType.USER.value:
            actor_user_id = entity.owner_id
        if not actor_user_id:
            actor_user_id = workflow_actor_id
        if not actor_user_id:
            return {"success": False, "error": "No actor user available for task creation"}

        task_data = TaskCreate(
            title=title,
            description=description,
            task_type=TaskType.FOLLOW_UP,
            surrogate_id=entity.id if isinstance(entity, Surrogate) else None,
            donor_id=entity.id if isinstance(entity, Donor) else None,
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

    def _action_assign_donor(
        self,
        db: Session,
        action: dict,
        entity: Donor,
        event_id: UUID,
        depth: int,
        trigger_callback: TriggerCallback | None,
    ) -> dict:
        """Assign a donor through the donor use-case boundary."""
        from app.schemas.donor import DonorUpdate
        from app.services import donor_service

        owner_type = action.get("owner_type")
        owner_id = action.get("owner_id")
        resolved_owner_id = UUID(owner_id) if isinstance(owner_id, str) else owner_id
        old_owner_type = entity.owner_type
        old_owner_id = entity.owner_id
        updated = donor_service.update_donor(
            db,
            entity,
            SYSTEM_USER_ID,
            DonorUpdate(owner_type=owner_type, owner_id=resolved_owner_id),
            emit_workflow_events=False,
        )

        if trigger_callback and (
            old_owner_type != updated.owner_type or old_owner_id != updated.owner_id
        ):
            trigger_callback(
                db=db,
                trigger_type=WorkflowTriggerType.DONOR_ASSIGNED,
                entity_type="donor",
                entity_id=updated.id,
                subject_type=updated.pipeline_entity_type,
                subject_id=updated.id,
                event_data={
                    "donor_id": str(updated.id),
                    "old_owner_type": old_owner_type,
                    "old_owner_id": str(old_owner_id) if old_owner_id else None,
                    "new_owner_type": updated.owner_type,
                    "new_owner_id": str(updated.owner_id) if updated.owner_id else None,
                },
                org_id=updated.organization_id,
                event_id=event_id,
                depth=depth + 1,
                source=WorkflowEventSource.WORKFLOW,
                entity_owner_id=(
                    updated.owner_id if updated.owner_type == OwnerType.USER.value else None
                ),
            )

        return {
            "success": True,
            "description": f"Assigned donor to {owner_type}:{resolved_owner_id}",
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
        entity.updated_at = datetime.now(UTC)

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
        from app.db.enums import NotificationType, Role
        from app.db.models import Membership

        title = action.get("title", "Workflow Notification")
        body = action.get("body", "")
        recipients = action.get("recipients", "owner")

        target = entity
        target_entity_type = "donor" if isinstance(entity, Donor) else "surrogate"
        if isinstance(entity, FormSubmission):
            target_entity_type = "form_submission"
        if not hasattr(entity, "owner_type"):
            surrogate_id = getattr(entity, "surrogate_id", None)
            if surrogate_id:
                target = db.query(Surrogate).filter(Surrogate.id == surrogate_id).first()
                if target:
                    target_entity_type = "surrogate"
            elif isinstance(entity, IntakeLead):
                target = entity
                target_entity_type = "intake_lead"
        if not target or not hasattr(target, "organization_id"):
            return {"success": False, "error": "No related surrogate for notification recipients"}

        # Determine recipient user IDs
        user_ids = []
        if (
            recipients == "owner"
            and hasattr(target, "owner_type")
            and target.owner_type == OwnerType.USER.value
        ):
            user_ids = [target.owner_id]
        elif recipients == "creator":
            creator_id = getattr(target, "created_by_user_id", None)
            user_ids = [creator_id] if creator_id else []
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
        created_count = 0
        for user_id in user_ids:
            notification = notification_facade.create_notification(
                db=db,
                org_id=target.organization_id,
                user_id=user_id,
                type=NotificationType.WORKFLOW_NOTIFICATION,
                title=title,
                body=body if body else None,
                entity_type=target_entity_type,
                entity_id=getattr(target, "id", None),
            )
            if notification:
                created_count += 1

        return {
            "success": True,
            "recipients_count": created_count,
            "description": f"Sent notification to {created_count} user(s)",
        }

    def _action_send_zapier_conversion_event(
        self,
        db: Session,
        entity: Surrogate,
    ) -> dict:
        """Queue conversion events for every enabled outbound transport."""
        from app.services import meta_crm_dataset_service, zapier_outbound_service

        if not entity.stage_id:
            return {
                "success": True,
                "queued": False,
                "skipped": True,
                "description": "Skipped conversion event: surrogate has no current stage.",
            }

        stage = db.query(PipelineStage).filter(PipelineStage.id == entity.stage_id).first()
        if not stage:
            return {
                "success": True,
                "queued": False,
                "skipped": True,
                "description": "Skipped conversion event: stage not found.",
            }

        effective_at = datetime.now(UTC)
        transport_results = {
            "zapier": zapier_outbound_service.enqueue_stage_event(
                db=db,
                surrogate=entity,
                stage_key=stage.stage_key,
                stage_slug=stage.slug,
                stage_id=str(stage.id),
                stage_label=stage.label,
                effective_at=effective_at,
                source="workflow",
            ),
            "meta_crm_dataset": meta_crm_dataset_service.enqueue_stage_event(
                db=db,
                surrogate=entity,
                stage_key=stage.stage_key,
                stage_slug=stage.slug,
                stage_id=str(stage.id),
                stage_label=stage.label,
                effective_at=effective_at,
                source="workflow",
            ),
        }

        queued_results = [result for result in transport_results.values() if result.get("queued")]
        if queued_results:
            event_name = str(queued_results[0].get("event_name") or "Lead")
            queued_transports = [
                name for name, result in transport_results.items() if result.get("queued")
            ]
            return {
                "success": True,
                "queued": True,
                "event_name": event_name,
                "transport_results": transport_results,
                "description": "Queued conversion event via "
                + ", ".join(queued_transports)
                + f" ('{event_name}').",
            }

        failed_transports = [
            name
            for name, result in transport_results.items()
            if result.get("reason") == "enqueue_failed"
        ]
        if failed_transports:
            return {
                "success": False,
                "queued": False,
                "transport_results": transport_results,
                "error": "Failed to enqueue conversion event for "
                + ", ".join(failed_transports)
                + ".",
            }

        reason_labels = {
            "disabled": "direct Meta CRM dataset is disabled",
            "missing_dataset_id": "direct Meta CRM dataset id is missing",
            "missing_access_token": "direct Meta CRM dataset access token is missing",
            "unmapped_stage": "stage is not mapped in outbound settings",
            "not_meta_source": "surrogate source is not Meta",
            "missing_meta_lead_fk": "surrogate is missing a linked Meta lead",
            "missing_meta_lead": "linked Meta lead record was not found",
            "missing_meta_lead_id": "linked Meta lead is missing lead id",
            "stale_meta_lead": "linked Meta lead is older than 90 days",
            "duplicate": "duplicate event already queued",
            "outbound_disabled": "Zapier outbound webhook is disabled",
            "missing_webhook_url": "Zapier outbound webhook URL is missing",
        }
        reason_text = "; ".join(
            f"{transport_name}: "
            + reason_labels.get(
                str(result.get("reason") or "not_queued"),
                str(result.get("reason") or "not_queued").replace("_", " "),
            )
            for transport_name, result in transport_results.items()
        )
        return {
            "success": True,
            "queued": False,
            "skipped": True,
            "transport_results": transport_results,
            "description": f"Skipped conversion event: {reason_text}.",
        }

    def _action_promote_intake_lead(
        self,
        db: Session,
        action: dict,
        entity: IntakeLead,
    ) -> dict:
        """Promote an intake lead into a surrogate case."""
        from app.services import form_intake_service

        source = action.get("source")
        if source is not None and not isinstance(source, str):
            source = None

        assign_to_user = action.get("assign_to_user")
        if not isinstance(assign_to_user, bool):
            assign_to_user = None

        surrogate, linked_submission_count = form_intake_service.promote_intake_lead(
            db=db,
            lead=entity,
            user_id=entity.created_by_user_id,
            source=source,
            is_priority=bool(action.get("is_priority", False)),
            assign_to_user=assign_to_user,
        )
        return {
            "success": True,
            "description": "Promoted intake lead to surrogate",
            "surrogate_id": str(surrogate.id),
            "linked_submission_count": int(linked_submission_count),
        }

    def _action_auto_match_submission(
        self,
        db: Session,
        entity: FormSubmission,
    ) -> dict:
        """Run deterministic matching for a shared form submission."""
        from app.services import form_intake_service

        submission, outcome = form_intake_service.auto_match_submission(
            db=db,
            submission=entity,
        )
        if outcome == "linked":
            return {
                "success": True,
                "description": "Matched submission to existing surrogate",
                "submission_id": str(submission.id),
                "surrogate_id": str(submission.surrogate_id) if submission.surrogate_id else None,
                "match_status": outcome,
            }
        return {
            "success": True,
            "description": "Submission requires review after auto-match",
            "submission_id": str(submission.id),
            "match_status": outcome,
        }

    def _action_create_intake_lead(
        self,
        db: Session,
        action: dict,
        entity: FormSubmission,
    ) -> dict:
        """Create an intake lead from a shared submission when no deterministic match exists."""
        from app.services import form_intake_service

        source = action.get("source")
        if source is not None and not isinstance(source, str):
            source = None

        submission, lead = form_intake_service.create_intake_lead_for_submission(
            db=db,
            submission=entity,
            user_id=None,
            source=source,
        )
        if not lead:
            return {
                "success": True,
                "description": "Skipped intake lead creation",
                "submission_id": str(submission.id),
                "match_status": submission.match_status,
            }
        return {
            "success": True,
            "description": "Created intake lead from submission",
            "submission_id": str(submission.id),
            "intake_lead_id": str(lead.id),
            "match_status": submission.match_status,
        }

    def _action_update_field(
        self,
        db: Session,
        action: dict,
        entity: Surrogate | Donor,
        event_id: UUID,
        depth: int,
        trigger_callback: TriggerCallback | None,
    ) -> dict:
        """Update an allowlisted subject field."""
        from app.db.models import SurrogateStatusHistory
        from app.services import pipeline_service

        field = action.get("field")
        value = action.get("value")

        if isinstance(entity, Donor):
            if field not in DONOR_ALLOWED_UPDATE_FIELDS:
                return {"success": False, "error": f"Field {field} not allowed for donor update"}
            from app.schemas.donor import DonorUpdate
            from app.services import donor_service

            old_value = getattr(entity, field, None)
            if field == "stage_id":
                from app.db.enums import Role

                new_stage_id = UUID(value) if isinstance(value, str) else value
                if new_stage_id == entity.stage_id:
                    return {"success": True, "description": "Stage unchanged"}
                old_stage = entity.stage
                result = donor_service.change_status(
                    db,
                    entity,
                    new_stage_id,
                    SYSTEM_USER_ID,
                    reason="Workflow update",
                    user_role=Role.DEVELOPER,
                    emit_workflow_events=False,
                )
                updated = result["donor"]
                if updated is None:
                    return {"success": False, "error": "Donor stage change was not applied"}
                if trigger_callback:
                    trigger_callback(
                        db=db,
                        trigger_type=WorkflowTriggerType.DONOR_STAGE_CHANGED,
                        entity_type="donor",
                        entity_id=updated.id,
                        subject_type=updated.pipeline_entity_type,
                        subject_id=updated.id,
                        event_data={
                            "donor_id": str(updated.id),
                            "old_stage_id": str(old_stage.id),
                            "new_stage_id": str(updated.stage.id),
                            "old_stage_key": old_stage.stage_key,
                            "new_stage_key": updated.stage.stage_key,
                            "old_status": old_stage.slug,
                            "new_status": updated.stage.slug,
                        },
                        org_id=updated.organization_id,
                        event_id=event_id,
                        depth=depth + 1,
                        source=WorkflowEventSource.WORKFLOW,
                        entity_owner_id=(
                            updated.owner_id if updated.owner_type == OwnerType.USER.value else None
                        ),
                    )
            else:
                updated = donor_service.update_donor(
                    db,
                    entity,
                    SYSTEM_USER_ID,
                    DonorUpdate(**{field: value}),
                    emit_workflow_events=False,
                )
                if trigger_callback:
                    trigger_callback(
                        db=db,
                        trigger_type=WorkflowTriggerType.DONOR_UPDATED,
                        entity_type="donor",
                        entity_id=updated.id,
                        subject_type=updated.pipeline_entity_type,
                        subject_id=updated.id,
                        event_data={
                            "donor_id": str(updated.id),
                            "changed_fields": [field],
                        },
                        org_id=updated.organization_id,
                        event_id=event_id,
                        depth=depth + 1,
                        source=WorkflowEventSource.WORKFLOW,
                        entity_owner_id=(
                            updated.owner_id if updated.owner_type == OwnerType.USER.value else None
                        ),
                    )
            return {
                "success": True,
                "description": f"Updated {field} from {old_value} to {value}",
            }

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
            old_stage_key = old_stage.stage_key if old_stage else None
            entity.stage_id = stage.id
            entity.status_label = stage.label
            entity.updated_at = datetime.now(UTC)

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
                        "old_stage_key": old_stage_key,
                        "new_stage_key": stage.stage_key,
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
            entity.updated_at = datetime.now(UTC)
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
        entity: Surrogate | Donor,
        workflow_actor_id: UUID | None = None,
    ) -> dict:
        """Add a note to a surrogate or donor subject."""
        content = action.get("content", "")

        # Determine author (prefer owner, fall back to creator)
        author_id = None
        if entity.owner_type == OwnerType.USER.value and entity.owner_id:
            author_id = entity.owner_id
        elif getattr(entity, "created_by_user_id", None):
            author_id = entity.created_by_user_id
        elif workflow_actor_id:
            author_id = workflow_actor_id

        if not author_id:
            return {
                "success": False,
                "error": "No user available to author note",
            }

        note = EntityNote(
            organization_id=entity.organization_id,
            entity_type=(
                EntityType.DONOR.value if isinstance(entity, Donor) else EntityType.SURROGATE.value
            ),
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

    def _resolve_email_variables(self, db: Session, subject: Surrogate | Donor) -> dict:
        """Resolve allowlisted email variables from the workflow subject."""
        if isinstance(subject, Donor):
            owner_name = ""
            if subject.owner_type == OwnerType.USER.value and subject.owner_id:
                owner = db.query(User).filter(User.id == subject.owner_id).first()
                owner_name = owner.display_name if owner else ""
            org = db.query(Organization).filter(Organization.id == subject.organization_id).first()
            return {
                "full_name": subject.full_name or "",
                "email": subject.email or "",
                "phone": subject.phone or "",
                "surrogate_number": "",
                "donor_number": subject.donor_number,
                "donor_type": subject.donor_type,
                "education": subject.education or "",
                "status_label": subject.status_label,
                "state": subject.state or "",
                "owner_name": owner_name,
                "org_name": org.name if org else "",
            }
        from app.services import email_service

        return email_service.build_surrogate_template_variables(db, subject)
