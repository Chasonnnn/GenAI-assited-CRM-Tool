"""Email-related job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

from app.db.models import EmailLog
from app.jobs.utils import mask_email
from app.services import email_service

logger = logging.getLogger(__name__)

DIRECT_RESEND_NOT_CONFIGURED_ERROR = "Org Resend is not configured for direct email sending."


async def send_email_async(email_log: EmailLog, db=None) -> str:
    """Migrate a legacy SEND_EMAIL record into the durable Resend outbox."""
    if db is None:
        raise Exception(DIRECT_RESEND_NOT_CONFIGURED_ERROR)

    campaign_provider = None
    include_unsubscribed = False
    from app.db.models import Campaign, CampaignRecipient, CampaignRun

    campaign_recipient = (
        db.query(CampaignRecipient)
        .join(CampaignRun, CampaignRun.id == CampaignRecipient.run_id)
        .filter(
            CampaignRun.organization_id == email_log.organization_id,
            CampaignRecipient.email_log_id == email_log.id,
        )
        .first()
    )
    if campaign_recipient:
        campaign_run = (
            db.query(CampaignRun).filter(CampaignRun.id == campaign_recipient.run_id).first()
        )
        if campaign_run:
            campaign_provider = campaign_run.email_provider
            campaign = db.query(Campaign).filter(Campaign.id == campaign_run.campaign_id).first()
            include_unsubscribed = bool(
                getattr(campaign, "include_unsubscribed", False) if campaign else False
            )

    if campaign_provider and campaign_provider != "resend":
        raise Exception(
            "Campaign emails must use Resend. "
            "Set Email provider to Resend in Settings → Integrations → Email Configuration."
        )

    attachments = email_service.list_email_log_attachments(
        db=db,
        org_id=email_log.organization_id,
        email_log_id=email_log.id,
    )
    actor_user_id = email_service._resolve_sender_user_id_from_job(db, email_log)
    migrated_log, delivery = email_service.send_email(
        db=db,
        org_id=email_log.organization_id,
        template_id=email_log.template_id,
        recipient_email=email_log.recipient_email,
        subject=email_log.subject,
        body=email_log.body,
        surrogate_id=email_log.surrogate_id,
        attachments=attachments,
        sender_user_id=actor_user_id,
        ignore_opt_out=include_unsubscribed,
        idempotency_key=f"legacy-email-log/{email_log.id}",
        source_type="legacy_email_log",
        source_id=email_log.id,
        purpose="campaign" if campaign_recipient else "transactional",
        commit=True,
    )
    if delivery is None:
        return "skipped"
    logger.info(
        "Legacy email_log=%s migrated to durable email_log=%s",
        email_log.id,
        migrated_log.id,
    )
    return "queued"


async def process_send_email(db, job) -> None:
    """Process SEND_EMAIL job."""
    payload = job.payload or {}
    email_log_id = payload.get("email_log_id")
    if not email_log_id:
        raise Exception("Missing email_log_id in job payload")

    email_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.id == UUID(email_log_id),
            EmailLog.organization_id == job.organization_id,
        )
        .first()
    )
    if not email_log:
        raise Exception(f"EmailLog {email_log_id} not found")

    result = await send_email_async(email_log, db=db)
    if result == "skipped":
        email_service.mark_email_skipped(db, email_log, "suppressed")
    else:
        email_log.status = "skipped"
        email_log.error = "migrated_to_durable_outbox"
        db.commit()


async def process_workflow_email(db, job) -> None:
    """
    Process a WORKFLOW_EMAIL job - send email triggered by workflow action.

    Uses the centralized email provider resolver based on workflow scope:
    - Personal workflows: Send via user's connected Gmail
    - Org workflows: Send via org's Resend only

    NO FALLBACK: If the configured provider is not available, the job fails
    with an explicit error message.

    Payload:
        - template_id: UUID of email template
        - surrogate_id: UUID of case (for variable resolution)
        - recipient_email: Target email address
        - variables: Dict of resolved template variables
        - workflow_scope: 'org' or 'personal'
        - workflow_owner_id: Owner user ID (for personal workflows)
    """
    from app.db.models import EmailLog, EmailTemplate
    from app.services import gmail_service
    from app.services.workflow_email_provider import (
        EmailProviderError,
        resolve_workflow_email_provider,
    )

    template_id = job.payload.get("template_id")
    surrogate_id = job.payload.get("surrogate_id")
    recipient_email = job.payload.get("recipient_email")
    variables = job.payload.get("variables", {})
    workflow_scope = job.payload.get("workflow_scope", "org")
    workflow_owner_id = job.payload.get("workflow_owner_id")
    template_snapshot_payload = job.payload.get("email_template_snapshot")

    if not template_id or not recipient_email:
        raise Exception("Missing template_id or recipient_email in workflow email job")

    from app.services.email_template_snapshot import (
        EmailTemplateSnapshot,
        build_snapshot,
        parse_snapshot,
    )

    resolved_template_id = UUID(str(template_id))
    log_template_id: UUID | None = None
    legacy_template: EmailTemplate | None = None
    if template_snapshot_payload is None:
        # Compatibility for jobs queued before immutable snapshots were added.
        template = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.id == resolved_template_id,
                EmailTemplate.organization_id == job.organization_id,
            )
            .first()
        )
        if not template:
            raise Exception(f"Email template {template_id} not found")
        legacy_template = template

        template_snapshot = EmailTemplateSnapshot(
            organization_id=job.organization_id,
            template_id=template.id,
            template_version=template.current_version,
            subject=template.subject,
            body=template.body,
            from_email=template.from_email,
            scope=template.scope,
            owner_user_id=template.owner_user_id,
            system_key=template.system_key,
        )
        persisted_template_snapshot = build_snapshot(
            template,
            effective_from_email=template.from_email,
            include_scope=True,
        )
        log_template_id = template.id
    else:
        template_snapshot = parse_snapshot(template_snapshot_payload, require_scope=True)
        persisted_template_snapshot = dict(template_snapshot_payload)
        # Preserve the relational link while the template still exists without
        # consulting its mutable content. The snapshot remains the sole source
        # for the queued subject, body, sender, scope, and version.
        log_template_id = (
            db.query(EmailTemplate.id)
            .filter(
                EmailTemplate.id == resolved_template_id,
                EmailTemplate.organization_id == job.organization_id,
            )
            .scalar()
        )

    from app.services import system_email_template_service

    if (
        template_snapshot.system_key
        and template_snapshot.system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
    ):
        raise Exception(
            f"Platform system template '{template_snapshot.system_key}' cannot be used in workflow "
            "emails. Use the platform/system endpoint instead."
        )

    if (
        template_snapshot.organization_id != job.organization_id
        or template_snapshot.template_id != resolved_template_id
    ):
        raise Exception("Workflow email template snapshot does not match job scope")
    if workflow_scope == "org":
        if template_snapshot.scope != "org" or template_snapshot.owner_user_id is not None:
            raise Exception("Workflow email template snapshot does not match workflow scope")
    elif workflow_scope == "personal":
        if not workflow_owner_id:
            raise Exception("Personal workflow missing owner")
        resolved_workflow_owner_id = UUID(str(workflow_owner_id))
        if template_snapshot.scope == "personal":
            if template_snapshot.owner_user_id != resolved_workflow_owner_id:
                raise Exception("Workflow email template snapshot does not match workflow owner")
        elif template_snapshot.scope != "org" or template_snapshot.owner_user_id is not None:
            raise Exception("Workflow email template snapshot does not match workflow scope")
    else:
        raise Exception("Workflow email template snapshot does not match workflow scope")

    # Resolve subject and body with variables (escaped)
    from app.services import email_composition_service

    cleaned_body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
        template_snapshot.body
    )
    subject, body = email_service.render_template(
        template_snapshot.subject, cleaned_body_template, variables
    )

    from app.services import org_service

    org = org_service.get_org_by_id(db, job.organization_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    body = email_composition_service.compose_template_email_html(
        db=db,
        org_id=job.organization_id,
        recipient_email=recipient_email,
        rendered_body_html=body,
        scope="personal" if workflow_scope == "personal" else "org",
        sender_user_id=UUID(workflow_owner_id)
        if workflow_scope == "personal" and workflow_owner_id
        else None,
        portal_base_url=portal_base_url,
    )

    actor_user_id = UUID(workflow_owner_id) if workflow_owner_id else None
    resolved_surrogate_id = UUID(surrogate_id) if surrogate_id else None
    idempotency_key = f"workflow-email/{job.id}"

    def upsert_terminal_email_log(
        *,
        occurrence_key: str,
        status: str,
        error_message: str,
        purpose: str,
    ) -> None:
        from sqlalchemy.dialects.postgresql import insert

        statement = (
            insert(EmailLog)
            .values(
                organization_id=job.organization_id,
                job_id=job.id,
                template_id=log_template_id,
                email_template_snapshot=persisted_template_snapshot,
                surrogate_id=resolved_surrogate_id,
                actor_user_id=actor_user_id,
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                status=status,
                error=error_message[:500],
                source_type="workflow_job",
                source_id=job.id,
                idempotency_key=occurrence_key,
                purpose=purpose,
            )
            .on_conflict_do_update(
                index_elements=[EmailLog.organization_id, EmailLog.idempotency_key],
                index_where=EmailLog.idempotency_key.is_not(None),
                set_={
                    "status": status,
                    "error": error_message[:500],
                    "subject": subject,
                    "body": body,
                    "template_id": log_template_id,
                    "email_template_snapshot": persisted_template_snapshot,
                    "surrogate_id": resolved_surrogate_id,
                    "actor_user_id": actor_user_id,
                },
            )
        )
        db.execute(statement)
        db.commit()

    def record_configuration_failure(error_message: str) -> None:
        upsert_terminal_email_log(
            occurrence_key=f"workflow-email-config/{job.id}",
            status="failed",
            error_message=error_message,
            purpose="configuration_diagnostic",
        )

    if workflow_scope == "personal" and email_service.is_email_suppressed(
        db,
        job.organization_id,
        recipient_email,
    ):
        upsert_terminal_email_log(
            occurrence_key=idempotency_key,
            status="skipped",
            error_message="suppressed",
            purpose="transactional",
        )
        logger.info(
            "Workflow email suppressed for org=%s recipient=%s",
            job.organization_id,
            mask_email(recipient_email),
        )
        return

    # Resolve email provider based on workflow scope (NO FALLBACK)
    try:
        provider, config = resolve_workflow_email_provider(
            db=db,
            scope=workflow_scope,
            org_id=job.organization_id,
            owner_user_id=actor_user_id,
        )
    except EmailProviderError as e:
        record_configuration_failure(str(e))
        raise Exception(str(e))

    if workflow_scope == "org" and provider != "resend":
        error_message = (
            "Org workflows must use Resend. "
            "Set Email provider to Resend in Settings → Integrations → Email Configuration."
        )
        record_configuration_failure(error_message)
        raise Exception(error_message)

    if provider == "user_gmail" and template_snapshot_payload is not None:
        pinned_sender = (template_snapshot.from_email or "").strip()
        current_sender = str(config.get("email") or "").strip()
        if (
            not pinned_sender
            or not current_sender
            or pinned_sender.casefold() != current_sender.casefold()
        ):
            raise Exception(
                "Workflow Gmail sender changed after this email was queued. "
                "Queue a new workflow email before sending."
            )

    if template_snapshot_payload is None and legacy_template is not None:
        from dataclasses import replace

        from app.services.email_template_snapshot import format_from_address

        if provider == "resend":
            effective_from_email = format_from_address(
                template_snapshot.from_email or config.get("from_email"),
                config.get("from_name"),
            )
        else:
            effective_from_email = (config.get("email") or "").strip() or None
        template_snapshot = replace(
            template_snapshot,
            from_email=effective_from_email,
        )
        persisted_template_snapshot = build_snapshot(
            legacy_template,
            effective_from_email=effective_from_email,
            include_scope=True,
        )

    from app.services import unsubscribe_service

    headers = unsubscribe_service.build_list_unsubscribe_headers(
        db,
        org_id=job.organization_id,
        email=recipient_email,
        base_url=portal_base_url,
    )

    if provider == "resend":
        from app.services.email_content import html_to_text
        from app.services.email_delivery_service import (
            DeliveryRoute,
            EmailSource,
            RenderedEmail,
            queue_rendered_email,
        )

        configured_from = (template_snapshot.from_email or config["from_email"]).strip()
        from_address = configured_from
        queued = queue_rendered_email(
            db,
            organization_id=job.organization_id,
            route=DeliveryRoute.ORGANIZATION_RESEND,
            provider_account_id=f"organization:{job.organization_id}",
            rendered_email=RenderedEmail(
                recipient_email=recipient_email,
                subject=subject,
                html=body,
                text=html_to_text(body),
                from_email=from_address,
                reply_to_email=config.get("reply_to"),
                headers=headers,
                safe_tags=({"name": "message_kind", "value": "workflow"},),
            ),
            idempotency_key=idempotency_key,
            source=EmailSource(
                source_type="workflow_job",
                source_id=job.id,
                template_id=log_template_id,
                email_template_snapshot=persisted_template_snapshot,
                surrogate_id=resolved_surrogate_id,
                actor_user_id=actor_user_id,
                job_id=job.id,
                purpose="transactional",
            ),
            commit=False,
        )
        db.commit()
        db.refresh(queued.email_log)
        if queued.delivery is not None:
            db.refresh(queued.delivery)

        if queued.delivery is None:
            logger.info(
                "Workflow email suppressed for org=%s recipient=%s",
                job.organization_id,
                mask_email(recipient_email),
            )
            return

        logger.info(
            "Workflow email queued via Resend for case=%s recipient=%s email_log=%s",
            surrogate_id,
            mask_email(recipient_email),
            queued.email_log.id,
        )
        return

    if provider != "user_gmail":
        error_message = f"Unknown email provider: {provider}"
        record_configuration_failure(error_message)
        raise Exception(error_message)

    email_log = EmailLog(
        organization_id=job.organization_id,
        job_id=job.id,
        template_id=log_template_id,
        email_template_snapshot=persisted_template_snapshot,
        surrogate_id=resolved_surrogate_id,
        actor_user_id=actor_user_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        from_email=template_snapshot.from_email,
        status="pending",
        provider="gmail",
        source_type="workflow_job",
        source_id=job.id,
        idempotency_key=idempotency_key,
    )
    db.add(email_log)
    db.commit()

    try:
        result = await gmail_service.send_email(
            db=db,
            user_id=str(config["user_id"]),
            to=recipient_email,
            subject=subject,
            body=body,
            html=True,
            headers=headers,
        )
        if not result.get("success"):
            raise Exception(f"Gmail send failed: {result.get('error')}")
        email_log.external_id = result.get("message_id")
        email_service.mark_email_sent(db, email_log)
        email_service.log_surrogate_email_send_success(
            db=db,
            org_id=email_log.organization_id,
            surrogate_id=email_log.surrogate_id,
            email_log_id=email_log.id,
            subject=email_log.subject,
            provider="gmail",
            template_id=template_snapshot.template_id,
            actor_user_id=actor_user_id,
        )

        logger.info(
            "Workflow email sent via Gmail for case=%s recipient=%s",
            surrogate_id,
            mask_email(recipient_email),
        )

    except Exception as e:
        email_log.status = "failed"
        email_log.error = str(e)[:500]
        db.commit()
        raise
