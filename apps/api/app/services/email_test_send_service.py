"""Email template test-send helpers.

Shared between:
- Org/personal email templates (main app)
- Platform template studio email templates (ops console)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.enums import EmailStatus
from app.db.models import EmailLog, Organization
from app.services import gmail_service, media_service


VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def extract_variables(subject: str, body: str) -> set[str]:
    """Extract template variables from subject + body."""
    combined = f"{subject or ''}\n{body or ''}"
    return {match.group(1) for match in VARIABLE_PATTERN.finditer(combined)}


def build_sample_variables(
    db: Session,
    *,
    org_id: UUID,
    to_email: str,
    actor_display_name: str | None,
) -> dict[str, str]:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_name = org.name if org else ""
    org_logo_url = (
        media_service.get_signed_media_url(org.signature_logo_url) if org else None
    ) or ""

    unsubscribe_url = ""
    form_link = ""
    appointment_link = ""
    appointment_manage_url = ""
    appointment_reschedule_url = ""
    appointment_cancel_url = ""
    if (to_email or "").strip():
        from app.services import unsubscribe_service, org_service

        portal_base_url = org_service.get_org_portal_base_url(org)

        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            org_id=org_id,
            email=to_email,
            base_url=portal_base_url,
        )
        form_link = (
            f"{portal_base_url}/intake/EXAMPLE_SLUG" if portal_base_url else "/intake/EXAMPLE_SLUG"
        )
        appointment_link = (
            f"{portal_base_url}/book/EXAMPLE_APPOINTMENT_SLUG"
            if portal_base_url
            else "/book/EXAMPLE_APPOINTMENT_SLUG"
        )
        appointment_manage_url = (
            f"{portal_base_url}/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN"
            if portal_base_url
            else "/book/self-service/EXAMPLE_ORG/manage/EXAMPLE_TOKEN"
        )
        appointment_reschedule_url = (
            f"{portal_base_url}/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN"
            if portal_base_url
            else "/book/self-service/EXAMPLE_ORG/reschedule/EXAMPLE_TOKEN"
        )
        appointment_cancel_url = (
            f"{portal_base_url}/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN"
            if portal_base_url
            else "/book/self-service/EXAMPLE_ORG/cancel/EXAMPLE_TOKEN"
        )

    return {
        # Recipient
        "first_name": "Jordan",
        "full_name": "Jordan Smith",
        "email": to_email,
        "phone": "(555) 555-5555",
        # Case
        "surrogate_number": "S10001",
        "intended_parent_number": "I10001",
        "status_label": "Pre-Qualified",
        "state": "CA",
        "owner_name": actor_display_name or "Case Manager",
        "form_link": form_link,
        "appointment_link": appointment_link,
        "appointment_manage_url": appointment_manage_url,
        "appointment_reschedule_url": appointment_reschedule_url,
        "appointment_cancel_url": appointment_cancel_url,
        # Organization
        "org_name": org_name,
        "org_logo_url": org_logo_url,
        # Appointment
        "appointment_date": "2026-01-01",
        "appointment_time": "09:00",
        "appointment_location": "Zoom",
        # Compliance
        "unsubscribe_url": unsubscribe_url,
    }


def apply_unknown_variable_fallbacks(
    *,
    variables_used: set[str],
    variables: dict[str, str],
) -> dict[str, str]:
    for var in variables_used:
        if var not in variables:
            variables[var] = f"TEST_{var.upper()}"
    return variables


@dataclass(frozen=True)
class _SendResult:
    success: bool
    queued: bool
    provider_used: str | None
    email_log_id: UUID | None
    message_id: str | None
    error: str | None

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "queued": self.queued,
            "provider_used": self.provider_used,
            "email_log_id": self.email_log_id,
            "message_id": self.message_id,
            "error": self.error,
        }


def _result_from_log(*, provider_used: str, log: EmailLog) -> _SendResult:
    queued = log.status == EmailStatus.PENDING.value and log.delivery is not None
    success = log.status == EmailStatus.SENT.value or queued
    return _SendResult(
        success=success,
        queued=queued,
        provider_used=provider_used,
        email_log_id=log.id,
        message_id=log.external_id,
        error=None if success else (log.error or "Email send failed"),
    )


async def send_resend_logged(
    *,
    db: Session,
    org_id: UUID,
    to_email: str,
    subject: str,
    html: str,
    from_email: str,
    from_name: str | None,
    reply_to: str | None,
    template_id: UUID | None,
    idempotency_key: str | None,
    ignore_opt_out: bool = False,
) -> dict:
    from app.services import unsubscribe_service, org_service
    from app.services.email_content import html_to_text
    from app.services.email_delivery_service import (
        DeliveryRoute,
        EmailSource,
        RenderedEmail,
        queue_rendered_email,
    )
    from app.db.enums import EmailSuppressionPolicy

    org = org_service.get_org_by_id(db, org_id)
    headers = unsubscribe_service.build_list_unsubscribe_headers(
        org_id=org_id,
        email=to_email,
        base_url=org_service.get_org_portal_base_url(org),
    )
    resolved_from = (
        f"{from_name} <{from_email}>" if from_name and "<" not in from_email else from_email
    )
    queued = queue_rendered_email(
        db,
        organization_id=org_id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{org_id}",
        rendered_email=RenderedEmail(
            recipient_email=to_email,
            subject=subject,
            html=html,
            text=html_to_text(html),
            from_email=resolved_from,
            reply_to_email=reply_to,
            headers=headers,
            safe_tags=({"name": "message_kind", "value": "template_test"},),
        ),
        idempotency_key=idempotency_key or f"template-test/{uuid4()}",
        source=EmailSource(
            source_type="template_test_send",
            source_id=template_id,
            template_id=template_id,
            purpose="transactional",
            suppression_policy=(
                EmailSuppressionPolicy.ALLOW_OPT_OUT
                if ignore_opt_out
                else EmailSuppressionPolicy.ENFORCE_ALL
            ),
        ),
        commit=True,
    )
    if queued.email_log.status == EmailStatus.SKIPPED.value:
        return _SendResult(
            success=False,
            queued=False,
            provider_used="resend",
            email_log_id=queued.email_log.id,
            message_id=None,
            error="Email suppressed",
        ).as_dict()
    return _result_from_log(provider_used="resend", log=queued.email_log).as_dict()


async def send_gmail_logged(
    *,
    db: Session,
    org_id: UUID,
    sender_user_id: UUID,
    to_email: str,
    subject: str,
    html: str,
    template_id: UUID | None,
    idempotency_key: str | None,
    ignore_opt_out: bool = False,
) -> dict:
    result = await gmail_service.send_email_logged(
        db=db,
        org_id=org_id,
        user_id=str(sender_user_id),
        to=to_email,
        subject=subject,
        body=html,
        html=True,
        template_id=template_id,
        idempotency_key=idempotency_key,
        ignore_opt_out=ignore_opt_out,
    )
    return _SendResult(
        success=bool(result.get("success")),
        queued=False,
        provider_used="gmail",
        email_log_id=result.get("email_log_id"),
        message_id=result.get("message_id"),
        error=result.get("error"),
    ).as_dict()


async def send_test_via_org_provider(
    *,
    db: Session,
    org_id: UUID,
    to_email: str,
    subject: str,
    html: str,
    template_id: UUID | None,
    idempotency_key: str | None,
    template_from_email: str | None = None,
    ignore_opt_out: bool = False,
) -> dict:
    from app.services.workflow_email_provider import (
        EmailProviderError,
        resolve_workflow_email_provider,
    )

    try:
        provider, config = resolve_workflow_email_provider(
            db=db, scope="org", org_id=org_id, owner_user_id=None
        )
    except EmailProviderError as exc:
        return _SendResult(
            success=False,
            queued=False,
            provider_used=None,
            email_log_id=None,
            message_id=None,
            error=str(exc),
        ).as_dict()

    if provider == "resend":
        resolved_from = (template_from_email or "").strip() or config["from_email"]
        return await send_resend_logged(
            db=db,
            org_id=org_id,
            to_email=to_email,
            subject=subject,
            html=html,
            from_email=resolved_from,
            from_name=config.get("from_name"),
            reply_to=config.get("reply_to"),
            template_id=template_id,
            idempotency_key=idempotency_key,
            ignore_opt_out=ignore_opt_out,
        )

    if provider == "org_gmail":
        return await send_gmail_logged(
            db=db,
            org_id=org_id,
            sender_user_id=config["sender_user_id"],
            to_email=to_email,
            subject=subject,
            html=html,
            template_id=template_id,
            idempotency_key=idempotency_key,
            ignore_opt_out=ignore_opt_out,
        )

    return _SendResult(
        success=False,
        queued=False,
        provider_used=None,
        email_log_id=None,
        message_id=None,
        error=f"Unknown email provider: {provider}",
    ).as_dict()


async def send_test_via_user_gmail(
    *,
    db: Session,
    org_id: UUID,
    sender_user_id: UUID,
    to_email: str,
    subject: str,
    html: str,
    template_id: UUID | None,
    idempotency_key: str | None,
    ignore_opt_out: bool = False,
) -> dict:
    return await send_gmail_logged(
        db=db,
        org_id=org_id,
        sender_user_id=sender_user_id,
        to_email=to_email,
        subject=subject,
        html=html,
        template_id=template_id,
        idempotency_key=idempotency_key,
        ignore_opt_out=ignore_opt_out,
    )
