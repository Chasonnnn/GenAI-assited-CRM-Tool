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
    OwnerType,
    TaskStatus,
    TaskType,
    WorkflowActionType,
)
from app.db.models import (
    Appointment,
    Attachment,
    AutomationWorkflow,
    Donor,
    EntityNote,
    FormSubmission,
    IntakeLead,
    Match,
    Organization,
    Surrogate,
    Task,
    User,
    WorkflowExecution,
)
from app.schemas.workflow import is_subject_email_recipient
from app.services import (
    notification_service,
    workflow_communication_actions,
    workflow_intake_actions,
    workflow_record_actions,
    workflow_task_actions,
)
from app.services.workflow_action_preview import build_action_preview, render_action_payload
from app.utils.business_hours import calculate_approval_due_date

logger = logging.getLogger(__name__)

TriggerCallback = Callable[..., list[WorkflowExecution]]


class WorkflowDomainAdapter(Protocol):
    def get_entity(self, db: Session, entity_type: str, entity_id: UUID) -> Any: ...

    def resolve_donor_subject(
        self, db: Session, org_id: UUID, subject_type: str, subject_id: UUID | None
    ) -> Donor | None: ...

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
        execution_permissions: frozenset[str] | None = None,
        appointment_record_type: str | None = None,
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
    INTAKE_LEAD_ONLY_ACTIONS = {WorkflowActionType.PROMOTE_INTAKE_LEAD.value}
    DONOR_COMPATIBLE_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.ASSIGN_DONOR.value,
        WorkflowActionType.SEND_NOTIFICATION.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }
    # Record actions an intake workflow runs against the donor its source is linked to.
    INTAKE_DONOR_RECORD_ACTIONS = SURROGATE_ONLY_ACTIONS | {
        WorkflowActionType.SEND_NOTIFICATION.value,
    }
    # Actions an appointment workflow runs against the surrogate or donor the appointment
    # is linked to. Notifications stay on the appointment so unlinked bookings reach staff.
    APPOINTMENT_RECORD_ACTIONS = {
        WorkflowActionType.SEND_EMAIL.value,
        WorkflowActionType.SEND_MESSAGE.value,
        WorkflowActionType.CREATE_TASK.value,
        WorkflowActionType.UPDATE_FIELD.value,
        WorkflowActionType.ADD_NOTE.value,
    }

    def _appointment_record(
        self, db: Session, appointment: Appointment, record_type: str
    ) -> Surrogate | Donor | None:
        """Return the appointment's linked record of the workflow's record type."""
        if record_type in {"egg_donor", "sperm_donor"}:
            return self.resolve_donor_subject(
                db, appointment.organization_id, record_type, appointment.donor_id
            )
        if appointment.surrogate_id is None:
            return None
        return (
            db.query(Surrogate)
            .filter(
                Surrogate.id == appointment.surrogate_id,
                Surrogate.organization_id == appointment.organization_id,
            )
            .first()
        )

    def _notification_occurrence_key(
        self,
        db: Session,
        org_id: UUID,
        execution_id: UUID | None,
        action_index: int | None,
    ) -> str | None:
        """Key one notification action across an execution and its manual retries."""
        if execution_id is None or action_index is None:
            return None
        trigger_event = (
            db.query(WorkflowExecution.trigger_event)
            .filter(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.organization_id == org_id,
            )
            .scalar()
        ) or {}
        root_id = trigger_event.get("retry_root_execution_id") or str(execution_id)
        return f"workflow-notification:{root_id}:{action_index}"

    def _intake_donor_link(self, entity_type: str, entity: Any) -> tuple[str, UUID | None] | None:
        """Return (donor subject, linked donor id) for donor-kind intake sources."""
        if entity_type == "form_submission" and isinstance(entity, FormSubmission):
            kind, donor_id = entity.lead_kind, entity.donor_id
        elif entity_type == "intake_lead" and isinstance(entity, IntakeLead):
            kind, donor_id = entity.lead_type, entity.promoted_donor_id
        else:
            return None
        if kind not in {"egg_donor", "sperm_donor"}:
            return None
        return kind, donor_id

    def intake_linked_stage_id(self, db: Session, entity: Any) -> UUID | None:
        """Return the current stage of the record an intake source is linked to.

        A donor link counts only for the source's donor subtype; links outside the
        source organization are ignored.
        """
        if isinstance(entity, FormSubmission):
            kind, surrogate_id, donor_id = entity.lead_kind, entity.surrogate_id, entity.donor_id
        elif isinstance(entity, IntakeLead):
            kind = entity.lead_type
            surrogate_id, donor_id = entity.promoted_surrogate_id, entity.promoted_donor_id
        else:
            return None
        if kind in {"egg_donor", "sperm_donor"}:
            if donor_id is None:
                return None
            return (
                db.query(Donor.stage_id)
                .filter(
                    Donor.id == donor_id,
                    Donor.organization_id == entity.organization_id,
                    Donor.donor_type == kind.removesuffix("_donor"),
                )
                .scalar()
            )
        if surrogate_id is None:
            return None
        return (
            db.query(Surrogate.stage_id)
            .filter(
                Surrogate.id == surrogate_id,
                Surrogate.organization_id == entity.organization_id,
            )
            .scalar()
        )

    def resolve_donor_subject(
        self, db: Session, org_id: UUID, subject_type: str, subject_id: UUID | None
    ) -> Donor | None:
        """Reload an active donor within the workflow's exact tenant and subtype."""
        if subject_type not in {"egg_donor", "sperm_donor"} or subject_id is None:
            return None
        return (
            db.query(Donor)
            .filter(
                Donor.id == subject_id,
                Donor.organization_id == org_id,
                Donor.donor_type == subject_type.removesuffix("_donor"),
                Donor.is_archived.is_(False),
            )
            .populate_existing()
            .first()
        )

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
            donor = self.resolve_donor_subject(
                db, execution.organization_id, execution.subject_type, execution.subject_id
            )
            if donor is None:
                return None

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
            form_submission_id=entity.id if isinstance(entity, FormSubmission) else None,
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
        execution_permissions: frozenset[str] | None = None,
        appointment_record_type: str | None = None,
    ) -> dict:
        """Execute a single action."""
        action_type = action.get("action_type")
        action_entity = entity
        from app.services import permission_policy_service
        from app.services.workflow_execution_authority import enabled

        if workflow_execution_id:
            permission_policy_service.lock_configuration(db, entity.organization_id)
        v2_authority = bool(workflow_execution_id) and enabled(db, entity.organization_id)
        workflow_actor_id = (
            (workflow_owner_id if workflow_scope == "personal" else SYSTEM_USER_ID)
            if v2_authority
            else (workflow_owner_id or workflow_creator_user_id)
        )

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
            action_entity = self.resolve_donor_subject(
                db, entity.organization_id, subject_type, subject_id
            )
            if action_entity is None:
                return _with_action_type(
                    {"success": False, "error": "Donor subject not found", "skipped": True}
                )

        if (
            entity_type == "appointment"
            and isinstance(entity, Appointment)
            and action_type in self.APPOINTMENT_RECORD_ACTIONS
        ):
            record_type = appointment_record_type or "surrogate"
            action_entity = self._appointment_record(db, entity, record_type)
            if action_entity is None:
                label = record_type.replace("_", " ")
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"Appointment is not linked to {'an' if label[0] == 'e' else 'a'} {label}",
                        "skipped": True,
                    }
                )
            if (
                isinstance(action_entity, Donor)
                and action_type not in self.DONOR_COMPATIBLE_ACTIONS
            ):
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"Action '{action_type}' does not support donor subjects",
                        "skipped": True,
                    }
                )

        # Staff emails and notifications about an unlinked submission or lead run on that
        # record itself; record actions need the surrogate or donor it became.
        staff_alert_on_intake = entity_type in {"form_submission", "intake_lead"} and (
            action_type == WorkflowActionType.SEND_NOTIFICATION.value
            or (
                action_type == WorkflowActionType.SEND_EMAIL.value
                and not is_subject_email_recipient(action.get("recipients"))
            )
        )
        intake_donor_link = (
            self._intake_donor_link(entity_type, entity)
            if action_type in self.INTAKE_DONOR_RECORD_ACTIONS
            else None
        )
        if (
            entity_type == "form_submission"
            and isinstance(entity, FormSubmission)
            and not staff_alert_on_intake
            and (
                (intake_donor_link is not None and intake_donor_link[1] is None)
                or (
                    entity.lead_kind not in {"egg_donor", "sperm_donor"}
                    and action_type
                    in self.SURROGATE_ONLY_ACTIONS | {WorkflowActionType.SEND_MESSAGE.value}
                    and entity.surrogate_id is None
                )
            )
        ):
            return _with_action_type(
                {
                    "success": True,
                    "skipped": True,
                    "description": "Skipped record action: submission has no linked record",
                }
            )

        if intake_donor_link is not None:
            donor_subject_type, linked_donor_id = intake_donor_link
            entity_label = entity_type.replace("_", " ")
            if linked_donor_id is None and not staff_alert_on_intake:
                return _with_action_type(
                    {
                        "success": False,
                        "error": f"{entity_label.title()} is not linked to a donor",
                        "skipped": True,
                    }
                )
            if linked_donor_id is not None:
                if action_type not in self.DONOR_COMPATIBLE_ACTIONS:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"Action '{action_type}' does not support donor subjects",
                            "skipped": True,
                        }
                    )
                action_entity = self.resolve_donor_subject(
                    db, entity.organization_id, donor_subject_type, linked_donor_id
                )
                if action_entity is None:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"Donor not found for {entity_label}",
                            "skipped": True,
                        }
                    )

        # Validate entity type for Surrogate-only actions; map tasks, submissions and
        # promoted intake leads to their surrogate when possible.
        if action_type in self.SURROGATE_ONLY_ACTIONS and not isinstance(
            action_entity, (Donor, Surrogate)
        ):
            if entity_type in {"task", "form_submission", "intake_lead"}:
                surrogate_id = getattr(
                    entity,
                    "promoted_surrogate_id" if entity_type == "intake_lead" else "surrogate_id",
                    None,
                )
                if not surrogate_id and not staff_alert_on_intake:
                    return _with_action_type(
                        {
                            "success": False,
                            "error": f"{entity_type.replace('_', ' ').title()} is not linked to a surrogate",
                            "skipped": True,
                        }
                    )
                if surrogate_id:
                    action_entity = (
                        db.query(Surrogate)
                        .filter(
                            Surrogate.id == surrogate_id,
                            Surrogate.organization_id == entity.organization_id,
                        )
                        .first()
                    )
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
                isinstance(entity, IntakeLead) and entity.lead_type in {"egg_donor", "sperm_donor"}
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
            elif entity_type not in {"surrogate", "intake_lead"} and not isinstance(
                action_entity, Surrogate
            ):
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

        try:
            if action_type == WorkflowActionType.SEND_EMAIL.value:
                result = workflow_communication_actions.send_email(
                    db=db,
                    action=action,
                    entity=action_entity,
                    event_id=event_id,
                    workflow_scope=workflow_scope,
                    workflow_owner_id=workflow_owner_id,
                    workflow_creator_user_id=workflow_creator_user_id,
                    workflow_execution_id=workflow_execution_id,
                    appointment=entity if isinstance(entity, Appointment) else None,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_MESSAGE.value:
                result = workflow_communication_actions.send_message(
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
                result = workflow_task_actions.create_task(
                    db,
                    action,
                    action_entity,
                    workflow_actor_id=workflow_actor_id,
                    use_workflow_actor=v2_authority,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ASSIGN_SURROGATE.value:
                result = workflow_record_actions.assign_surrogate(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ASSIGN_DONOR.value:
                result = workflow_record_actions.assign_donor(
                    db, action, action_entity, event_id, depth, trigger_callback
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_NOTIFICATION.value:
                result = workflow_communication_actions.send_notification(
                    db,
                    action,
                    action_entity,
                    dedupe_key=self._notification_occurrence_key(
                        db, entity.organization_id, workflow_execution_id, workflow_action_index
                    ),
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.SEND_ZAPIER_CONVERSION_EVENT.value:
                result = workflow_communication_actions.send_zapier_conversion_event(
                    db, action_entity
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.UPDATE_FIELD.value:
                result = workflow_record_actions.update_field(
                    db,
                    action,
                    action_entity,
                    event_id,
                    depth,
                    trigger_callback,
                    workflow_actor_id=workflow_actor_id,
                    execution_permissions=execution_permissions,
                    v2_authority=v2_authority,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.ADD_NOTE.value:
                result = workflow_record_actions.add_note(
                    db,
                    action,
                    action_entity,
                    workflow_actor_id=workflow_actor_id,
                    use_workflow_actor=v2_authority,
                )
                return _with_action_type(result)

            if action_type == WorkflowActionType.PROMOTE_INTAKE_LEAD.value:
                promote_action = action
                if isinstance(entity, IntakeLead) and entity.lead_type in {
                    "egg_donor",
                    "sperm_donor",
                }:
                    # Priority and owner assignment are surrogate-only promotion options.
                    promote_action = {
                        key: value
                        for key, value in action.items()
                        if key not in {"is_priority", "assign_to_user"}
                    }
                result = workflow_intake_actions.promote_intake_lead(db, promote_action, entity)
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
