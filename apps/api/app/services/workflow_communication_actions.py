"""Workflow communication queuing; delivery services retain final admission."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobType, OwnerType
from app.db.models import (
    Donor,
    EmailTemplate,
    FormSubmission,
    IntakeLead,
    MessageTemplate,
    MessagingContact,
    Organization,
    PipelineStage,
    Queue,
    Surrogate,
    User,
)
from app.schemas.workflow import is_subject_email_recipient
from app.services import job_service, notification_service

DONOR_LEAD_KINDS = frozenset({"egg_donor", "sperm_donor"})


def send_email(
    db: Session,
    action: dict,
    entity: Surrogate | Donor | FormSubmission | IntakeLead,
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
    if is_subject_email_recipient(recipients):
        # An unlinked submission or lead has no record contact to email yet.
        if not isinstance(entity, (FormSubmission, IntakeLead)) and entity.email:
            recipient_emails = [entity.email]
    else:
        recipient_emails = _resolve_staff_email_recipients(
            db,
            entity,
            action,
            workflow_creator_user_id=workflow_creator_user_id,
        )

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
    variables = resolve_email_variables(db, entity)

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
                "subject_type": _email_subject_type(entity),
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


def _email_subject_type(entity: Surrogate | Donor | FormSubmission | IntakeLead) -> str:
    if isinstance(entity, Donor):
        return entity.pipeline_entity_type
    if isinstance(entity, FormSubmission):
        return "form_submission"
    if isinstance(entity, IntakeLead):
        return "intake_lead"
    return "surrogate"


def _is_donor_context(entity: Surrogate | Donor | FormSubmission | IntakeLead) -> bool:
    if isinstance(entity, Donor):
        return True
    if isinstance(entity, FormSubmission):
        return entity.lead_kind in DONOR_LEAD_KINDS
    if isinstance(entity, IntakeLead):
        return entity.lead_type in DONOR_LEAD_KINDS
    return False


def _resolve_staff_email_recipients(
    db: Session,
    entity: Surrogate | Donor | FormSubmission | IntakeLead,
    action: dict,
    *,
    workflow_creator_user_id: UUID | None,
) -> list[str]:
    """Resolve staff recipients through current org membership.

    Donor-context emails reach only members who can view donors. Custom addresses are
    configured explicitly on the workflow and are sent as given.
    """
    from app.db.enums import Role
    from app.db.models import Membership, QueueMember
    from app.services import task_service

    org_id = entity.organization_id
    recipients = action.get("recipients")
    query = (
        db.query(User.email, Membership.user_id, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
    )

    if recipients == "custom":
        emails = action.get("recipient_emails") or []
        return [email for email in emails if isinstance(email, str) and email]

    queue_id: UUID | None = None
    recipient_ids: list[UUID] | None = None
    if recipients == "owner":
        owner_type = getattr(entity, "owner_type", None)
        owner_id = getattr(entity, "owner_id", None)
        if owner_type == OwnerType.QUEUE.value and owner_id:
            queue_id = owner_id
        elif owner_type == OwnerType.USER.value and owner_id:
            recipient_ids = [owner_id]
        else:
            return []
    elif recipients == "creator":
        creator_id = getattr(entity, "created_by_user_id", None)
        # Surrogates keep their historical creator-only rule.
        if creator_id is None and not isinstance(entity, Surrogate):
            creator_id = workflow_creator_user_id
        recipient_ids = [creator_id] if creator_id else []
    elif recipients == "queue":
        try:
            queue_id = UUID(str(action.get("recipient_queue_id")))
        except ValueError:
            return []
    elif recipients == "role":
        role = action.get("recipient_role")
        if role not in {item.value for item in Role}:
            return []
        query = query.filter(Membership.role == role)
    elif recipients == "all_admins":
        query = query.filter(Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]))
    elif isinstance(recipients, list):
        try:
            recipient_ids = [UUID(str(recipient_id)) for recipient_id in recipients]
        except ValueError:
            return []
    else:
        return []

    if queue_id is not None:
        member_ids = (
            db.query(QueueMember.user_id)
            .join(Queue, Queue.id == QueueMember.queue_id)
            .filter(
                Queue.id == queue_id,
                Queue.organization_id == org_id,
                Queue.is_active.is_(True),
            )
        )
        query = query.filter(Membership.user_id.in_(member_ids.scalar_subquery()))
    if recipient_ids is not None:
        if not recipient_ids:
            return []
        query = query.filter(Membership.user_id.in_(set(recipient_ids)))

    donor_context = _is_donor_context(entity)
    return [
        email
        for email, user_id, role in query.all()
        if email
        and (not donor_context or task_service.user_can_view_donors(db, org_id, user_id, role=role))
    ]


def send_message(
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
        variables = resolve_email_variables(db, entity)
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
    except messaging_delivery_service.MessagingRouteNotReady as exc:
        return {
            "success": False,
            "error": str(exc),
            "skipped": True,
        }
    return {
        "success": True,
        "queued": True,
        "delivery_id": str(delivery.id),
        "description": "Queued consent-gated message",
    }


def send_notification(
    db: Session,
    action: dict,
    entity: Any,
    *,
    dedupe_key: str | None = None,
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
            target = (
                db.query(Surrogate)
                .filter(
                    Surrogate.id == surrogate_id,
                    Surrogate.organization_id == entity.organization_id,
                )
                .first()
            )
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
        notification = notification_service.create_notification(
            db=db,
            org_id=target.organization_id,
            user_id=user_id,
            type=NotificationType.WORKFLOW_NOTIFICATION,
            title=title,
            body=body if body else None,
            entity_type=target_entity_type,
            entity_id=getattr(target, "id", None),
            dedupe_key=dedupe_key,
            dedupe_window_hours=None,
        )
        if notification:
            created_count += 1

    return {
        "success": True,
        "recipients_count": created_count,
        "description": f"Sent notification to {created_count} user(s)",
    }


def send_zapier_conversion_event(
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
            "error": "Failed to enqueue conversion event for " + ", ".join(failed_transports) + ".",
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


def resolve_email_variables(
    db: Session, subject: Surrogate | Donor | FormSubmission | IntakeLead
) -> dict:
    """Resolve allowlisted email variables from the workflow subject."""
    from app.services import email_service

    if isinstance(subject, Donor):
        variables = email_service.build_donor_template_variables(db, subject)
    elif isinstance(subject, Surrogate):
        variables = email_service.build_surrogate_template_variables(db, subject)
    else:
        variables = _intake_email_variables(db, subject)
    variables["record_link"] = _record_link(db, subject)
    return variables


def _record_path(subject: Surrogate | Donor | FormSubmission | IntakeLead) -> str:
    if isinstance(subject, Surrogate):
        return f"/surrogates/{subject.id}"
    if isinstance(subject, Donor):
        return f"/donors/{subject.id}"
    if subject.form_id:
        return f"/automation/form-submissions?form={subject.form_id}"
    return "/automation/form-submissions"


def _record_link(db: Session, subject: Surrogate | Donor | FormSubmission | IntakeLead) -> str:
    from app.services import org_service

    org = db.query(Organization).filter(Organization.id == subject.organization_id).first()
    base_url = org_service.get_org_portal_base_url(org) if org else ""
    return f"{base_url}{_record_path(subject)}" if base_url else ""


def _intake_email_variables(db: Session, subject: FormSubmission | IntakeLead) -> dict:
    """Variables for a submission or intake lead that is not yet a surrogate or donor."""
    from app.db.models import Form
    from app.services import form_intake_service

    org = db.query(Organization).filter(Organization.id == subject.organization_id).first()
    form = (
        db.query(Form)
        .filter(Form.id == subject.form_id, Form.organization_id == subject.organization_id)
        .first()
        if subject.form_id
        else None
    )
    contact: dict = {}
    if isinstance(subject, IntakeLead):
        contact = {"full_name": subject.full_name, "email": subject.email, "phone": subject.phone}
        submitted_at = subject.created_at
    else:
        submitted_at = subject.submitted_at
        lead = (
            db.query(IntakeLead)
            .filter(
                IntakeLead.id == subject.intake_lead_id,
                IntakeLead.organization_id == subject.organization_id,
            )
            .first()
            if subject.intake_lead_id
            else None
        )
        if lead is not None:
            contact = {"full_name": lead.full_name, "email": lead.email, "phone": lead.phone}
        else:
            try:
                contact = form_intake_service.extract_submission_identity(
                    subject, form_purpose=form.purpose if form else None
                )
            except ValueError:
                contact = {}
    return {
        "full_name": contact.get("full_name") or "",
        "email": contact.get("email") or "",
        "phone": contact.get("phone") or "",
        "org_name": org.name if org else "",
        "form_name": form.name if form else "",
        "submitted_at": submitted_at.strftime("%Y-%m-%d %H:%M UTC") if submitted_at else "",
    }
