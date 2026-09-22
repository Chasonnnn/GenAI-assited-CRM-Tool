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
    Surrogate,
    User,
)
from app.services import job_service, notification_service


def send_email(
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
        recipient_emails = _resolve_donor_internal_email_recipients(
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
            [donor.owner_id] if donor.owner_type == OwnerType.USER.value and donor.owner_id else []
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
        except TypeError, ValueError:
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
        query = query.filter(Membership.role.in_([Role.ADMIN.value, Role.DEVELOPER.value]))
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


def resolve_email_variables(db: Session, subject: Surrogate | Donor) -> dict:
    """Resolve allowlisted email variables from the workflow subject."""
    from app.services import email_service

    if isinstance(subject, Donor):
        return email_service.build_donor_template_variables(db, subject)

    return email_service.build_surrogate_template_variables(db, subject)
