"""Email template test-send helpers.

Shared between:
- Org/personal email templates (main app)
- Platform template studio email templates (ops console)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import EmailStatus
from app.db.models import EmailLog, Organization
from app.services import email_service, gmail_service, media_service, resend_email_service
from app.services import resend_settings_service


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
    if (to_email or "").strip():
        from app.services import unsubscribe_service

        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(org_id=org_id, email=to_email)

    return {
        # Recipient
        "first_name": "Jordan",
        "full_name": "Jordan Smith",
        "email": to_email,
        "phone": "(555) 555-5555",
        # Case
        "surrogate_number": "S10001",
        "intended_parent_number": "I10001",
        "status_label": "Qualified",
        "state": "CA",
        "owner_name": actor_display_name or "Case Manager",
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
    provider_used: str | None
    email_log_id: UUID | None
    message_id: str | None
    error: str | None

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "provider_used": self.provider_used,
            "email_log_id": self.email_log_id,
            "message_id": self.message_id,
            "error": self.error,
        }


def _result_from_log(*, provider_used: str, log: EmailLog) -> _SendResult:
    success = log.status == EmailStatus.SENT.value
    return _SendResult(
        success=success,
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
    api_key_encrypted: str,
    from_email: str,
    from_name: str | None,
    reply_to: str | None,
    template_id: UUID | None,
    idempotency_key: str | None,
) -> dict:
    if idempotency_key:
        existing = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == org_id,
                EmailLog.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return _result_from_log(provider_used="resend", log=existing).as_dict()

    if email_service.is_email_suppressed(db, org_id, to_email):
        email_log = EmailLog(
            organization_id=org_id,
            template_id=template_id,
            surrogate_id=None,
            recipient_email=to_email,
            subject=subject,
            body=html,
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
            idempotency_key=idempotency_key,
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        return _SendResult(
            success=False,
            provider_used="resend",
            email_log_id=email_log.id,
            message_id=None,
            error="Email suppressed",
        ).as_dict()

    email_log = EmailLog(
        organization_id=org_id,
        template_id=template_id,
        surrogate_id=None,
        recipient_email=to_email,
        subject=subject,
        body=html,
        status=EmailStatus.PENDING.value,
        idempotency_key=idempotency_key,
    )
    db.add(email_log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == org_id,
                EmailLog.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return _result_from_log(provider_used="resend", log=existing).as_dict()
        raise

    db.refresh(email_log)

    from app.services import unsubscribe_service

    api_key = resend_settings_service.decrypt_api_key(api_key_encrypted)
    unsubscribe_url = unsubscribe_service.build_unsubscribe_url(org_id=org_id, email=to_email)

    try:
        success, error, message_id = await resend_email_service.send_email_direct(
            api_key=api_key,
            to_email=to_email,
            subject=subject,
            body=html,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            idempotency_key=idempotency_key,
            unsubscribe_url=unsubscribe_url,
        )
    except Exception as exc:
        email_log.status = EmailStatus.FAILED.value
        email_log.error = f"Resend send failed: {exc.__class__.__name__}"
        db.commit()
        return _SendResult(
            success=False,
            provider_used="resend",
            email_log_id=email_log.id,
            message_id=None,
            error=email_log.error,
        ).as_dict()

    now = datetime.now(timezone.utc)
    if success:
        email_log.status = EmailStatus.SENT.value
        email_log.external_id = message_id
        email_log.resend_status = "sent"
        email_log.sent_at = now
        email_log.error = None
    else:
        email_log.status = EmailStatus.FAILED.value
        email_log.error = (error or "Send failed")[:500]
    db.commit()

    return _SendResult(
        success=bool(success),
        provider_used="resend",
        email_log_id=email_log.id,
        message_id=message_id,
        error=None if success else email_log.error,
    ).as_dict()


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
    )
    return _SendResult(
        success=bool(result.get("success")),
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
            api_key_encrypted=config["api_key_encrypted"],
            from_email=resolved_from,
            from_name=config.get("from_name"),
            reply_to=config.get("reply_to"),
            template_id=template_id,
            idempotency_key=idempotency_key,
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
        )

    return _SendResult(
        success=False,
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
    )
