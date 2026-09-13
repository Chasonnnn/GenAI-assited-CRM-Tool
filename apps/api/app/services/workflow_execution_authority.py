"""Authorize workflow configuration and execution separately from contributor credit."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import Role
from app.db.models import (
    AutomationWorkflow,
    Donor,
    Membership,
    PipelineStage,
    Surrogate,
    User,
    WorkflowExecution,
)
from app.schemas.auth import UserSession
from app.services import permission_policy_service, permission_service


class WorkflowAuthorityError(ValueError):
    """An actor or execution no longer has authority for the requested action."""


def enabled(db: Session, org_id: UUID) -> bool:
    return permission_policy_service.is_enabled(db, org_id)


def active_session(db: Session, org_id: UUID, user_id: UUID | None) -> UserSession | None:
    if not user_id:
        return None
    row = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .populate_existing()
        .first()
    )
    if not row:
        return None
    membership, user = row
    return UserSession(
        user_id=user.id,
        org_id=org_id,
        role=Role(membership.role),
        email=user.email,
        display_name=user.display_name,
    )


def has_permissions(db: Session, session: UserSession, keys: set[str]) -> bool:
    granted = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )
    return keys.issubset(granted)


def configuration_digest(workflow: AutomationWorkflow) -> str:
    config = {
        key: getattr(workflow, key)
        for key in (
            "organization_id",
            "scope",
            "owner_user_id",
            "subject_type",
            "trigger_type",
            "trigger_config",
            "conditions",
            "condition_logic",
            "actions",
        )
    }
    return sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def action_permissions(db: Session, workflow: AutomationWorkflow, action: dict) -> set[str]:
    from app.services.workflow_service import get_workflow_effective_subject_type

    effective_subject = get_workflow_effective_subject_type(db, workflow)
    donor = effective_subject in {"donor", "egg_donor", "sperm_donor"}
    module = "donors" if donor else "surrogates"
    keys = {f"view_{module}"}
    if workflow.subject_type == "match":
        keys.update({"view_matches", "view_intended_parents", "view_donors"})
    if workflow.subject_type == "appointment":
        keys.add("manage_appointments")
    action_type = action.get("action_type")
    if action_type == "send_email":
        keys.add("send_email")
    elif action_type == "send_message":
        keys.add("send_sms")
    elif action_type == "create_task":
        keys.add("create_tasks")
    elif action_type in {"assign_surrogate", "assign_donor"}:
        keys.add(f"assign_{module}")
    elif action_type in {"update_field", "update_status"}:
        field = action.get("field", "stage_id" if action_type == "update_status" else None)
        if field == "stage_id":
            keys.add("change_donor_status" if donor else "change_surrogate_status")
            try:
                stage_id = UUID(str(action.get("value", action.get("stage_id"))))
            except ValueError, TypeError:
                raise WorkflowAuthorityError("Workflow stage target is invalid") from None
            from app.db.models import Pipeline

            stage = (
                db.query(PipelineStage)
                .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
                .filter(
                    PipelineStage.id == stage_id,
                    Pipeline.organization_id == workflow.organization_id,
                )
                .first()
            )
            if stage is None:
                raise WorkflowAuthorityError("Workflow stage target is unavailable")
            gate = (
                db.query(PipelineStage)
                .filter(
                    PipelineStage.pipeline_id == stage.pipeline_id,
                    PipelineStage.stage_key == "approved",
                    PipelineStage.is_active.is_(True),
                )
                .first()
            )
            if (
                gate is not None
                and stage.order >= gate.order
                and stage.stage_type not in {"paused", "terminal"}
            ):
                keys.add(f"approve_{module}")
        elif field in {"owner_id", "owner_type"}:
            keys.add(f"assign_{module}")
        else:
            keys.add(f"edit_{module}")
    elif action_type == "add_note":
        keys.add("edit_donors" if donor else "edit_surrogate_notes")
    elif action_type == "send_notification":
        pass
    elif action_type == "send_zapier_conversion_event":
        keys.add("manage_integrations")
    elif action_type in {"promote_intake_lead", "auto_match_submission", "create_intake_lead"}:
        keys.update({"manage_forms", f"edit_{module}"})
    else:
        raise WorkflowAuthorityError("Workflow action is not supported")
    return keys


def authorize_configuration(db: Session, workflow: AutomationWorkflow, user_id: UUID) -> None:
    """Validate all executable action rights and freeze organization authority."""
    if not enabled(db, workflow.organization_id):
        return
    session = active_session(db, workflow.organization_id, user_id)
    keys = {"manage_automation"}
    if workflow.scope == "org":
        keys.add("manage_org_workflows")
    for action in workflow.actions:
        keys.update(action_permissions(db, workflow, action))
    if session is None or not has_permissions(db, session, keys):
        raise WorkflowAuthorityError("Missing permission for workflow configuration")
    if (
        workflow.scope == "personal"
        and workflow.owner_user_id != user_id
        and session.role not in {Role.ADMIN, Role.DEVELOPER}
    ):
        raise WorkflowAuthorityError("Personal workflow belongs to another user")
    if any(action.get("action_type") == "send_email" for action in workflow.actions):
        from app.services.workflow_email_provider import validate_email_provider

        valid, error = validate_email_provider(
            db, workflow.scope, workflow.organization_id, workflow.owner_user_id
        )
        if not valid:
            raise WorkflowAuthorityError(error)
    workflow.execution_authority = (
        {
            "version": 2,
            "organization_id": str(workflow.organization_id),
            "configuration_digest": configuration_digest(workflow),
            "permissions": sorted(keys),
            "authorized_by_user_id": str(user_id),
            "authorized_at": datetime.now(UTC).isoformat(),
        }
        if workflow.scope == "org"
        else None
    )


def execution_snapshot(db: Session, workflow: AutomationWorkflow) -> dict | None:
    if not enabled(db, workflow.organization_id):
        return None
    if workflow.scope == "personal":
        return {
            "version": 2,
            "scope": "personal",
            "workflow_id": str(workflow.id),
            "owner_user_id": str(workflow.owner_user_id),
            "organization_id": str(workflow.organization_id),
        }
    grant = workflow.execution_authority
    if (
        not grant
        or grant.get("organization_id") != str(workflow.organization_id)
        or grant.get("configuration_digest") != configuration_digest(workflow)
    ):
        raise WorkflowAuthorityError("Organization workflow requires configuration authorization")
    return {**deepcopy(grant), "scope": "org", "workflow_id": str(workflow.id)}


def personal_subject_allowed(
    db: Session, workflow: AutomationWorkflow, subject_type: str | None, subject_id: UUID | None
) -> bool:
    """Personal work can reach only currently assigned or retained collaborator records."""
    if workflow.scope == "org":
        return True
    session = active_session(db, workflow.organization_id, workflow.owner_user_id)
    if session is None or subject_id is None:
        return False
    from app.services import record_scope_service

    if subject_type == "surrogate":
        model, kind = Surrogate, "surrogate"
    elif subject_type in {"egg_donor", "sperm_donor"}:
        model, kind = Donor, "donor"
    else:
        from app.db.models import Appointment, FormSubmission, IntakeLead, IntendedParent, Match

        linked_model = {
            "appointment": Appointment,
            "match": Match,
            "form_submission": FormSubmission,
            "intake_lead": IntakeLead,
        }.get(subject_type)
        if linked_model is None:
            return False
        linked = (
            db.query(linked_model)
            .filter(
                linked_model.id == subject_id,
                linked_model.organization_id == workflow.organization_id,
            )
            .first()
        )
        if linked is None:
            return False
        donor_id = getattr(linked, "donor_id", None) or getattr(linked, "promoted_donor_id", None)
        surrogate_id = getattr(linked, "surrogate_id", None) or getattr(
            linked, "promoted_surrogate_id", None
        )
        if donor_id:
            donor = (
                db.query(Donor)
                .filter(Donor.id == donor_id, Donor.organization_id == workflow.organization_id)
                .first()
            )
            primary_allowed = donor is not None and personal_subject_allowed(
                db, workflow, donor.pipeline_entity_type, donor_id
            )
        else:
            primary_allowed = (
                personal_subject_allowed(db, workflow, "surrogate", surrogate_id)
                if surrogate_id
                else False
            )
        if not primary_allowed:
            return False
        ip_id = getattr(linked, "intended_parent_id", None)
        if ip_id:
            if not has_permissions(db, session, {"view_intended_parents"}):
                return False
            return (
                db.query(IntendedParent.id)
                .filter(
                    IntendedParent.id == ip_id,
                    IntendedParent.organization_id == workflow.organization_id,
                    record_scope_service.build_visibility_filter(
                        db, session, "intended_parent", model=IntendedParent
                    ),
                )
                .first()
                is not None
            )
        return True
    return (
        db.query(model.id)
        .filter(
            model.id == subject_id,
            model.organization_id == workflow.organization_id,
            record_scope_service.build_visibility_filter(
                db, session, kind, model=model, personal_only=True
            ),
        )
        .first()
        is not None
    )


def authorize_action(
    db: Session,
    workflow: AutomationWorkflow,
    action: dict,
    *,
    subject_type: str | None,
    subject_id: UUID | None,
    snapshot: dict | None = None,
) -> None:
    if not enabled(db, workflow.organization_id):
        return
    if not workflow.is_enabled:
        raise WorkflowAuthorityError("Workflow execution is paused")
    if snapshot and (
        snapshot.get("workflow_id") != str(workflow.id)
        or snapshot.get("organization_id") != str(workflow.organization_id)
    ):
        raise WorkflowAuthorityError("Workflow execution authority is invalid")
    required = action_permissions(db, workflow, action)
    if workflow.scope == "personal":
        session = active_session(db, workflow.organization_id, workflow.owner_user_id)
        if session is None or not has_permissions(db, session, required | {"manage_automation"}):
            raise WorkflowAuthorityError("Personal workflow owner no longer has action permission")
        if not personal_subject_allowed(db, workflow, subject_type, subject_id):
            raise WorkflowAuthorityError("Record is outside personal workflow scope")
    else:
        grant = snapshot or execution_snapshot(db, workflow)
        if (
            not grant
            or grant.get("organization_id") != str(workflow.organization_id)
            or grant.get("scope") != "org"
            or not required.issubset(set(grant.get("permissions", [])))
        ):
            raise WorkflowAuthorityError("Organization workflow action lacks authorization")


def authorize_email_job(db: Session, job) -> None:
    if not enabled(db, job.organization_id):
        return
    try:
        execution_id = UUID(str(job.payload.get("workflow_execution_id")))
    except ValueError, TypeError:
        raise WorkflowAuthorityError("Workflow email execution is unavailable") from None
    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.organization_id == job.organization_id,
        )
        .first()
    )
    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.id == execution.workflow_id,
            AutomationWorkflow.organization_id == job.organization_id,
        )
        .first()
        if execution
        else None
    )
    if (
        workflow is None
        or not execution
        or job.payload.get("workflow_scope", "org") != workflow.scope
    ):
        raise WorkflowAuthorityError("Workflow email execution is unavailable")
    if not workflow.is_enabled or execution.status in {"canceled", "expired"}:
        raise WorkflowAuthorityError("Workflow email execution is paused")
    if not _email_subject_matches(db, execution, job.payload):
        raise WorkflowAuthorityError("Workflow email subject is invalid")
    if workflow.scope == "personal" and str(job.payload.get("workflow_owner_id")) != str(
        workflow.owner_user_id
    ):
        raise WorkflowAuthorityError("Workflow email owner is invalid")
    authorize_action(
        db,
        workflow,
        {"action_type": "send_email"},
        subject_type=execution.subject_type,
        subject_id=execution.subject_id,
        snapshot=execution.authority_snapshot,
    )


def _email_subject_matches(db, execution, payload):
    if (
        str(payload.get("subject_id")) == str(execution.subject_id)
        and payload.get("subject_type") == execution.subject_type
    ):
        return True
    from app.db.models import FormSubmission, IntakeLead

    model = {"form_submission": FormSubmission, "intake_lead": IntakeLead}.get(
        execution.subject_type
    )
    if model is None:
        return False
    source = (
        db.query(model)
        .filter(
            model.id == execution.subject_id, model.organization_id == execution.organization_id
        )
        .first()
    )
    if source is None:
        return False
    donor_id = getattr(source, "donor_id", None) or getattr(source, "promoted_donor_id", None)
    surrogate_id = getattr(source, "surrogate_id", None) or getattr(
        source, "promoted_surrogate_id", None
    )
    if donor_id:
        donor = (
            db.query(Donor)
            .filter(Donor.id == donor_id, Donor.organization_id == execution.organization_id)
            .first()
        )
        return (
            donor is not None
            and str(payload.get("subject_id")) == str(donor.id)
            and payload.get("subject_type") == donor.pipeline_entity_type
        )
    return (
        surrogate_id is not None
        and str(payload.get("subject_id")) == str(surrogate_id)
        and payload.get("subject_type") == "surrogate"
        and db.query(Surrogate.id)
        .filter(
            Surrogate.id == surrogate_id, Surrogate.organization_id == execution.organization_id
        )
        .first()
        is not None
    )


def audit_configuration(db, workflow, actor_user_id, operation):
    if not enabled(db, workflow.organization_id):
        return
    from app.db.enums import AuditEventType
    from app.services import audit_service

    audit_service.log_event(
        db,
        workflow.organization_id,
        AuditEventType.WORKFLOW_CONFIG_CHANGED,
        actor_user_id=actor_user_id,
        target_type="workflow",
        target_id=workflow.id,
        details={"operation": operation, "scope": workflow.scope},
    )
    if workflow.scope == "personal" and workflow.owner_user_id != actor_user_id:
        audit_private_access(db, workflow, actor_user_id, operation)


def audit_private_access(db, workflow, actor_user_id, operation="view"):
    if (
        not enabled(db, workflow.organization_id)
        or workflow.scope != "personal"
        or workflow.owner_user_id == actor_user_id
    ):
        return
    from app.db.enums import AuditEventType
    from app.services import audit_service

    audit_service.log_event(
        db,
        workflow.organization_id,
        AuditEventType.WORKFLOW_PRIVATE_ACCESSED,
        actor_user_id=actor_user_id,
        target_type="workflow",
        target_id=workflow.id,
        details={"operation": operation},
    )


def get_policy_execution_snapshot(db: Session, org_id: UUID) -> list[dict]:
    """Inventory unreviewed org execution authority for the activation digest."""
    from sqlalchemy import String, cast, exists, or_

    from app.db.models import EmailDelivery, EmailLog, Job
    from app.db.models.messaging_delivery import MessageDelivery

    workflows = (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == org_id, AutomationWorkflow.scope == "org")
        .order_by(AutomationWorkflow.id)
        .all()
    )
    result = []
    for workflow in workflows:
        pending = (
            db.query(WorkflowExecution.id)
            .filter(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.workflow_id == workflow.id,
                WorkflowExecution.authority_snapshot.is_(None),
                or_(
                    WorkflowExecution.status == "paused",
                    exists().where(
                        MessageDelivery.organization_id == org_id,
                        MessageDelivery.source_type == "workflow_execution",
                        MessageDelivery.source_id == WorkflowExecution.id,
                        MessageDelivery.status.in_(["pending", "leased", "retry_scheduled"]),
                    ),
                    exists().where(
                        Job.organization_id == org_id,
                        Job.job_type == "workflow_email",
                        or_(
                            Job.status.in_(["pending", "running"]),
                            exists().where(
                                EmailLog.organization_id == org_id,
                                EmailLog.source_type == "workflow_job",
                                EmailLog.source_id == Job.id,
                                EmailDelivery.email_log_id == EmailLog.id,
                                EmailDelivery.organization_id == org_id,
                                EmailDelivery.status.in_(["pending", "leased", "retry_scheduled"]),
                            ),
                        ),
                        Job.payload["workflow_execution_id"].astext
                        == cast(WorkflowExecution.id, String),
                    ),
                ),
            )
            .order_by(WorkflowExecution.id)
            .all()
        )
        if (workflow.execution_authority is None and workflow.is_enabled) or pending:
            result.append(
                {
                    "item_type": "workflow",
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "is_enabled": workflow.is_enabled,
                    "configuration_digest": configuration_digest(workflow),
                    "unreviewed_execution_ids": [str(row.id) for row in pending],
                }
            )
    return result


def apply_policy_execution_resolutions(
    db: Session, org_id: UUID, actor_user_id: UUID, resolutions: list[dict]
) -> None:
    expected = {item["id"]: item for item in get_policy_execution_snapshot(db, org_id)}
    selected = {
        str(item["id"]): item["action"] for item in resolutions if item["item_type"] == "workflow"
    }
    if set(selected) != set(expected) or any(action != "pause" for action in selected.values()):
        raise WorkflowAuthorityError(
            "Every unreviewed organization workflow must be explicitly paused"
        )
    for workflow_id, item in expected.items():
        workflow = (
            db.query(AutomationWorkflow)
            .filter(
                AutomationWorkflow.id == UUID(workflow_id),
                AutomationWorkflow.organization_id == org_id,
            )
            .with_for_update()
            .one()
        )
        workflow.is_enabled = False
        workflow.updated_by_user_id = actor_user_id
        workflow.updated_at = datetime.now(UTC)
        for execution_id in item["unreviewed_execution_ids"]:
            execution = (
                db.query(WorkflowExecution)
                .filter(
                    WorkflowExecution.id == UUID(execution_id),
                    WorkflowExecution.organization_id == org_id,
                )
                .with_for_update()
                .one()
            )
            # Completed actions remain recorded; pending deliveries cannot inherit authority.
            if execution.status == "paused":
                execution.status = "canceled"
                execution.error_message = "Paused during permission policy activation"
                execution.paused_task_id = None
                execution.paused_at_action_index = None
        audit_configuration(db, workflow, actor_user_id, "pause_for_policy_activation")
    db.flush()


def authorize_message_delivery(db, delivery) -> None:
    if not enabled(db, delivery.organization_id):
        return
    from app.db.models import MessagingContact

    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.id == delivery.source_id,
            WorkflowExecution.organization_id == delivery.organization_id,
        )
        .first()
    )
    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.id == execution.workflow_id,
            AutomationWorkflow.organization_id == delivery.organization_id,
        )
        .first()
        if execution
        else None
    )
    contact = (
        db.query(MessagingContact)
        .filter(
            MessagingContact.id == delivery.contact_id,
            MessagingContact.organization_id == delivery.organization_id,
        )
        .first()
    )
    if (
        execution is None
        or workflow is None
        or contact is None
        or execution.status in {"canceled", "expired"}
    ):
        raise WorkflowAuthorityError("Workflow message execution is unavailable")
    bound = execution.subject_type == "surrogate" and execution.subject_id == contact.surrogate_id
    if execution.subject_type == "intake_lead":
        bound = execution.subject_id == contact.intake_lead_id
    if execution.subject_type == "form_submission":
        bound = _email_subject_matches(
            db, execution, {"subject_type": "surrogate", "subject_id": str(contact.surrogate_id)}
        )
    if not bound:
        raise WorkflowAuthorityError("Workflow message recipient is invalid")
    authorize_action(
        db,
        workflow,
        {"action_type": "send_message"},
        subject_type=execution.subject_type,
        subject_id=execution.subject_id,
        snapshot=execution.authority_snapshot,
    )
