"""Email-related job handlers."""

from __future__ import annotations

import logging
import os
from uuid import UUID

from app.db.models import EmailLog
from app.jobs.utils import mask_email
from app.services import email_service

logger = logging.getLogger(__name__)

# Email sending configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@example.com")


async def send_email_async(email_log: EmailLog, db=None) -> str:
    """
    Send an email using the appropriate provider.

    For campaign emails: uses the org's configured provider (Resend/Gmail).
    For other emails: uses the global RESEND_API_KEY if available.
    """
    # Check if this is a campaign email and get the provider
    campaign_provider = None
    campaign_run = None
    include_unsubscribed = False
    if db:
        from app.db.models import CampaignRecipient, CampaignRun, Campaign

        # Find linked campaign recipient
        campaign_recipient = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.external_message_id == str(email_log.id))
            .first()
        )
        if campaign_recipient:
            campaign_run = (
                db.query(CampaignRun).filter(CampaignRun.id == campaign_recipient.run_id).first()
            )
            if campaign_run:
                campaign_provider = campaign_run.email_provider
                campaign = (
                    db.query(Campaign).filter(Campaign.id == campaign_run.campaign_id).first()
                )
                include_unsubscribed = bool(
                    getattr(campaign, "include_unsubscribed", False) if campaign else False
                )

    # Global suppression check (best-effort)
    if db:
        try:
            if email_service.is_email_suppressed(
                db,
                email_log.organization_id,
                email_log.recipient_email,
                ignore_opt_out=include_unsubscribed,
            ):
                logger.info(
                    "Email suppressed for email_log=%s recipient=%s",
                    email_log.id,
                    mask_email(email_log.recipient_email),
                )
                return "skipped"
        except Exception as exc:
            logger.warning("Suppression check failed: %s", exc)

    # Use org-level provider for campaigns
    if campaign_provider and db:
        await _send_via_org_provider(db, email_log, campaign_provider, campaign_run.organization_id)
        return "sent"

    # Fallback to global RESEND_API_KEY for non-campaign emails
    if not RESEND_API_KEY:
        logger.info("[DRY RUN] Email send skipped for email_log=%s", email_log.id)
        return "sent"

    try:
        from app.services import resend_email_service, unsubscribe_service, org_service

        portal_base_url = None
        if db:
            org = org_service.get_org_by_id(db, email_log.organization_id)
            portal_base_url = org_service.get_org_portal_base_url(org)

        unsubscribe_url = unsubscribe_service.build_list_unsubscribe_url(
            org_id=email_log.organization_id,
            email=email_log.recipient_email,
            base_url=portal_base_url,
        )

        success, error, message_id = await resend_email_service.send_email_direct(
            api_key=RESEND_API_KEY,
            to_email=email_log.recipient_email,
            subject=email_log.subject,
            body=email_log.body,
            from_email=EMAIL_FROM,
            idempotency_key=f"email-log/{email_log.id}",
            unsubscribe_url=unsubscribe_url,
        )
        if not success:
            raise Exception(f"Resend send failed: {error}")

        if db:
            email_log.external_id = message_id
            email_log.resend_status = "sent"
            db.commit()

        logger.info(
            "Email sent for email_log=%s recipient=%s message_id=%s",
            email_log.id,
            mask_email(email_log.recipient_email),
            message_id,
        )
        return "sent"
    except Exception as e:
        logger.error(
            "Email send failed for email_log=%s error_class=%s",
            email_log.id,
            e.__class__.__name__,
        )
        raise


async def _send_via_org_provider(db, email_log: EmailLog, provider: str, org_id) -> None:
    """Send email using org-level provider configuration."""
    from app.services import resend_settings_service, gmail_service, org_service

    org = org_service.get_org_by_id(db, org_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    if provider == "resend":
        settings = resend_settings_service.get_resend_settings(db, org_id)
        if not settings or not settings.api_key_encrypted:
            raise Exception("Resend not configured for organization")

        api_key = resend_settings_service.decrypt_api_key(settings.api_key_encrypted)

        from app.services import resend_email_service
        from app.services import unsubscribe_service

        unsubscribe_url = unsubscribe_service.build_list_unsubscribe_url(
            org_id=org_id,
            email=email_log.recipient_email,
            base_url=portal_base_url,
        )

        success, error, message_id = await resend_email_service.send_email_direct(
            api_key=api_key,
            to_email=email_log.recipient_email,
            subject=email_log.subject,
            body=email_log.body,
            from_email=settings.from_email,
            from_name=settings.from_name,
            reply_to=settings.reply_to_email,
            idempotency_key=f"email-log/{email_log.id}",
            unsubscribe_url=unsubscribe_url,
        )

        if success:
            email_log.external_id = message_id
            email_log.resend_status = "sent"
            logger.info(
                "Email sent via org Resend for email_log=%s message_id=%s",
                email_log.id,
                message_id,
            )
        else:
            raise Exception(f"Resend send failed: {error}")

    elif provider == "gmail":
        settings = resend_settings_service.get_resend_settings(db, org_id)
        if not settings or not settings.default_sender_user_id:
            raise Exception("Gmail sender not configured for organization")

        from app.services import unsubscribe_service

        headers = unsubscribe_service.build_list_unsubscribe_headers(
            org_id=org_id,
            email=email_log.recipient_email,
            base_url=portal_base_url,
        )

        result = await gmail_service.send_email(
            db=db,
            user_id=str(settings.default_sender_user_id),
            to=email_log.recipient_email,
            subject=email_log.subject,
            body=email_log.body,
            html=True,
            headers=headers,
        )

        if result.get("success"):
            email_log.external_id = result.get("message_id")
            logger.info(
                "Email sent via Gmail for email_log=%s message_id=%s",
                email_log.id,
                result.get("message_id"),
            )
        else:
            raise Exception(f"Gmail send failed: {result.get('error')}")

    else:
        raise Exception(f"Unknown email provider: {provider}")


async def process_send_email(db, job) -> None:
    """Process SEND_EMAIL job."""
    email_log_id = job.payload.get("email_log_id")
    if not email_log_id:
        raise Exception("Missing email_log_id in job payload")

    email_log = db.query(EmailLog).filter(EmailLog.id == UUID(email_log_id)).first()
    if not email_log:
        raise Exception(f"EmailLog {email_log_id} not found")

    result = await send_email_async(email_log, db=db)
    if result == "skipped":
        email_service.mark_email_skipped(db, email_log, "suppressed")
    else:
        email_service.mark_email_sent(db, email_log)


async def process_workflow_email(db, job) -> None:
    """
    Process a WORKFLOW_EMAIL job - send email triggered by workflow action.

    Uses the centralized email provider resolver based on workflow scope:
    - Personal workflows: Send via user's connected Gmail
    - Org workflows: Send via org's Resend or org's default Gmail sender

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
    from app.services import gmail_service, resend_settings_service
    from app.services.workflow_email_provider import (
        resolve_workflow_email_provider,
        EmailProviderError,
    )
    from app.services import resend_email_service

    template_id = job.payload.get("template_id")
    surrogate_id = job.payload.get("surrogate_id")
    recipient_email = job.payload.get("recipient_email")
    variables = job.payload.get("variables", {})
    workflow_scope = job.payload.get("workflow_scope", "org")
    workflow_owner_id = job.payload.get("workflow_owner_id")

    if not template_id or not recipient_email:
        raise Exception("Missing template_id or recipient_email in workflow email job")

    # Get template
    template = db.query(EmailTemplate).filter(EmailTemplate.id == UUID(template_id)).first()
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

    # Create email log
    email_log = EmailLog(
        organization_id=job.organization_id,
        job_id=job.id,
        template_id=template.id,
        surrogate_id=UUID(surrogate_id) if surrogate_id else None,
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        status="pending",
    )
    db.add(email_log)
    db.commit()

    # Suppression check (global)
    if email_service.is_email_suppressed(db, job.organization_id, recipient_email):
        email_service.mark_email_skipped(db, email_log, "suppressed")
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
            owner_user_id=UUID(workflow_owner_id) if workflow_owner_id else None,
        )
    except EmailProviderError as e:
        # Fail explicitly with clear error
        email_log.status = "failed"
        email_log.error = str(e)
        db.commit()
        raise Exception(str(e))

    # Send via resolved provider
    try:
        from app.services import unsubscribe_service, org_service

        org = org_service.get_org_by_id(db, job.organization_id)
        portal_base_url = org_service.get_org_portal_base_url(org)

        headers = unsubscribe_service.build_list_unsubscribe_headers(
            org_id=job.organization_id,
            email=recipient_email,
            base_url=portal_base_url,
        )

        if provider == "user_gmail":
            # Personal workflow: send via user's Gmail
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

        elif provider == "org_gmail":
            # Org workflow via org's default Gmail sender
            result = await gmail_service.send_email(
                db=db,
                user_id=str(config["sender_user_id"]),
                to=recipient_email,
                subject=subject,
                body=body,
                html=True,
                headers=headers,
            )
            if not result.get("success"):
                raise Exception(f"Gmail send failed: {result.get('error')}")
            email_log.external_id = result.get("message_id")

        elif provider == "resend":
            # Org workflow via Resend
            # For org workflows, use template from_email if set, otherwise org default
            from_email = template.from_email or config["from_email"]

            api_key = resend_settings_service.decrypt_api_key(config["api_key_encrypted"])
            unsubscribe_url = unsubscribe_service.build_list_unsubscribe_url(
                org_id=job.organization_id,
                email=recipient_email,
                base_url=portal_base_url,
            )
            success, error, message_id = await resend_email_service.send_email_direct(
                api_key=api_key,
                to_email=recipient_email,
                subject=subject,
                body=body,
                from_email=from_email,
                from_name=config.get("from_name"),
                reply_to=config.get("reply_to"),
                idempotency_key=f"workflow-email/{email_log.id}",
                unsubscribe_url=unsubscribe_url,
            )
            if not success:
                raise Exception(f"Resend send failed: {error}")
            email_log.external_id = message_id

        else:
            raise Exception(f"Unknown email provider: {provider}")

        # Mark as sent
        email_service.mark_email_sent(db, email_log)

        logger.info(
            "Workflow email sent via %s for case=%s recipient=%s",
            provider,
            surrogate_id,
            mask_email(recipient_email),
        )

    except Exception as e:
        email_log.status = "failed"
        email_log.error = str(e)[:500]
        db.commit()
        raise
