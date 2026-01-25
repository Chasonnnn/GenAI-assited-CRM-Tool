"""Platform/system email sender.

This module is intentionally scoped to *platform/system* emails (invites, etc).
It uses PLATFORM_RESEND_API_KEY to avoid accidentally enabling Resend for campaign
or user-level email flows that rely on RESEND_API_KEY.

We intentionally *do not* require a global From address in infra. Instead, each
system template can provide its own `from_email` (recommended). PLATFORM_EMAIL_FROM
is supported only as an optional fallback for local/dev or emergency ops.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import EmailStatus
from app.db.models import EmailLog
from app.services.http_service import DEFAULT_RETRY_STATUSES, request_with_retries
from app.types import JsonObject

logger = logging.getLogger(__name__)

RESEND_SEND_URL = "https://api.resend.com/emails"
RESEND_MAX_ATTEMPTS = 3
RESEND_RETRY_BASE_DELAY = 0.5
RESEND_RETRY_MAX_DELAY = 4.0
RESEND_TIMEOUT_SECONDS = 20.0


def _html_to_text(content: str) -> str:
    """Convert HTML into readable text (deliverability + inbox previews).

    Keep this small and dependency-free; we don't need full fidelity, just a
    reasonable plain-text alternative.
    """
    import html as html_module
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\\1>", "", content, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return html_module.unescape(text)


def platform_sender_configured() -> bool:
    # Sender is considered "configured" if we have the API key; the From header is
    # expected to be provided by templates at send time (or via PLATFORM_EMAIL_FROM
    # fallback).
    return bool(settings.PLATFORM_RESEND_API_KEY)


def _result_from_log(log: EmailLog) -> JsonObject:
    success = log.status == EmailStatus.SENT.value
    return {
        "success": success,
        "message_id": log.external_id,
        "email_log_id": log.id,
        "error": None if success else (log.error or "Email send failed"),
    }


async def _send_resend_email(
    *,
    to_email: str,
    subject: str,
    from_email: str | None,
    html: str,
    text: str | None,
    idempotency_key: str | None,
) -> JsonObject:
    api_key = settings.PLATFORM_RESEND_API_KEY
    resolved_from = (from_email or "").strip() or (settings.PLATFORM_EMAIL_FROM or "").strip()
    if not api_key:
        return {"success": False, "error": "Platform email sender not configured (missing PLATFORM_RESEND_API_KEY)"}
    if not resolved_from:
        return {
            "success": False,
            "error": "Missing From address for platform email (set template from_email in Ops)",
        }

    payload: dict[str, object] = {
        "from": resolved_from,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    async with httpx.AsyncClient(timeout=RESEND_TIMEOUT_SECONDS) as client:

        async def request_fn() -> httpx.Response:
            return await client.post(RESEND_SEND_URL, headers=headers, json=payload)

        response = await request_with_retries(
            request_fn,
            max_attempts=RESEND_MAX_ATTEMPTS,
            base_delay=RESEND_RETRY_BASE_DELAY,
            max_delay=RESEND_RETRY_MAX_DELAY,
            retry_statuses=DEFAULT_RETRY_STATUSES,
        )

    if 200 <= response.status_code < 300:
        data = response.json()
        message_id = data.get("id")
        if isinstance(message_id, str) and message_id:
            return {"success": True, "message_id": message_id}
        return {"success": False, "error": "Resend API returned success without message id"}

    # Resend uses 409 for idempotency conflicts. If the message already exists, treat
    # the send as a success so we don't incorrectly mark EmailLog as failed.
    if response.status_code == 409:
        message_id = None
        try:
            data = response.json()
            if isinstance(data, dict):
                mid = data.get("id")
                if isinstance(mid, str) and mid:
                    message_id = mid
        except Exception:
            message_id = None

        if message_id:
            return {"success": True, "message_id": message_id}
        return {"success": True}

    # Best-effort parse of error response
    detail = None
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("message") or data.get("error")
    except Exception:
        detail = None

    if detail:
        return {"success": False, "error": f"Resend API error: {response.status_code} ({detail})"}
    return {"success": False, "error": f"Resend API error: {response.status_code}"}


async def send_email_logged(
    *,
    db: Session,
    org_id: UUID,
    to_email: str,
    subject: str,
    from_email: str | None = None,
    html: str,
    text: str | None = None,
    template_id: UUID | None = None,
    surrogate_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> JsonObject:
    """Send a platform/system email with EmailLog tracking + idempotency."""
    if idempotency_key:
        existing = (
            db.query(EmailLog)
            .filter(EmailLog.organization_id == org_id, EmailLog.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return _result_from_log(existing)

    email_log = EmailLog(
        organization_id=org_id,
        template_id=template_id,
        surrogate_id=surrogate_id,
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
            .filter(EmailLog.organization_id == org_id, EmailLog.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return _result_from_log(existing)
        raise

    db.refresh(email_log)

    resolved_text = text
    if not (resolved_text or "").strip() and html:
        resolved_text = _html_to_text(html)

    try:
        result = await _send_resend_email(
            to_email=to_email,
            subject=subject,
            from_email=from_email,
            html=html,
            text=resolved_text,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        email_log.status = EmailStatus.FAILED.value
        # Avoid leaking request payloads/PII into logs; exception type is enough
        # to debug the integration while keeping logs safe.
        email_log.error = f"Platform email send failed: {exc.__class__.__name__}"
        logger.exception("Platform email send raised for email_log=%s", email_log.id)
        db.commit()
        return {
            "success": False,
            "error": email_log.error,
            "email_log_id": email_log.id,
        }

    if result.get("success"):
        email_log.status = EmailStatus.SENT.value
        email_log.external_id = result.get("message_id")
        email_log.sent_at = datetime.now(timezone.utc)
        email_log.error = None
        logger.info("Platform email sent for email_log=%s", email_log.id)
    else:
        email_log.status = EmailStatus.FAILED.value
        email_log.error = str(result.get("error") or "Email send failed")
        logger.warning("Platform email failed for email_log=%s", email_log.id)

    db.commit()

    return {
        **result,
        "email_log_id": email_log.id,
    }
