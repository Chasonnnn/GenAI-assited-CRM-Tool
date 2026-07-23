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
    from app.db.models import EmailTemplate, EmailLog
    from app.services import gmail_service
    from app.services.workflow_email_provider import (
        resolve_workflow_email_provider,
        EmailProviderError,
    )

    template_id = job.payload.get("template_id")
    surrogate_id = job.payload.get("surrogate_id")
    recipient_email = job.payload.get("recipient_email")
    variables = job.payload.get("variables", {})
    workflow_scope = job.payload.get("workflow_scope", "org")
    workflow_owner_id = job.payload.get("workflow_owner_id")

    if not template_id or not recipient_email:
        raise Exception("Missing template_id or recipient_email in workflow email job")

    # Get template
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == UUID(template_id),
            EmailTemplate.organization_id == job.organization_id,
        )
        .first()
    )
    if not template:
        raise Exception(f"Email template {template_id} not found")

    from app.services import system_email_template_service

    if (
        template.system_key
        and template.system_key in system_email_template_service.DEFAULT_SYSTEM_TEMPLATES
    ):
        raise Exception(
            f"Platform system template '{template.system_key}' cannot be used in workflow emails. "
            "Use the platform/system endpoint instead."
        )

    # Resolve subject and body with variables (escaped)
    from app.services import email_composition_service

    cleaned_body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(
        template.body
    )
    subject, body = email_service.render_template(
        template.subject, cleaned_body_template, variables
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
                template_id=template.id,
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
                    "template_id": template.id,
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

    from app.services import unsubscribe_service

    headers = unsubscribe_service.build_list_unsubscribe_headers(
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

        configured_from = (template.from_email or config["from_email"]).strip()
        from_name = (config.get("from_name") or "").strip()
        from_address = (
            f"{from_name} <{configured_from}>"
            if from_name and "<" not in configured_from
            else configured_from
        )
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
                template_id=template.id,
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
        template_id=template.id,
        surrogate_id=resolved_surrogate_id,
        actor_user_id=actor_user_id,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
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
            template_id=email_log.template_id,
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
