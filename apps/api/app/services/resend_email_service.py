"""Resend Email Service.

Sends campaign emails via Resend API with idempotency, retry logic, and suppression checking.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.db.models import CampaignRecipient, ResendSettings
from app.services import resend_settings_service
from app.services.campaign_service import is_email_suppressed
from app.services.http_service import DEFAULT_RETRY_STATUSES, request_with_retries

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

    text = re.sub(r"<(script|style)[^>]*>.*?</\\1>", "", content, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return html_module.unescape(text)


async def send_campaign_email(
    db: Session,
    org_id: UUID,
    recipient: CampaignRecipient,
    subject: str,
    body: str,
    settings: ResendSettings,
    unsubscribe_url: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a campaign email via Resend API.

    Args:
        db: Database session
        org_id: Organization ID
        recipient: CampaignRecipient record
        subject: Email subject
        body: Email body (HTML)
        settings: ResendSettings with API key and sender info

    Returns:
        (success, error_message)
    """
    # 1. Check suppression
    if is_email_suppressed(db, org_id, recipient.recipient_email):
        recipient.status = "skipped"
        recipient.skip_reason = "suppressed"
        db.commit()
        logger.info("Email suppressed for recipient %s", recipient.id)
        return False, "Email suppressed"

    # 2. Decrypt API key and build sender info
    try:
        api_key = resend_settings_service.decrypt_api_key(settings.api_key_encrypted)
    except Exception:
        recipient.status = "failed"
        recipient.error = "Failed to decrypt API key"
        db.commit()
        return False, "Failed to decrypt API key"

    from_address = (
        f"{settings.from_name} <{settings.from_email}>"
        if settings.from_name
        else settings.from_email
    )

    # 3. Build payload
    payload: dict[str, object] = {
        "from": from_address,
        "to": [recipient.recipient_email],
        "subject": subject,
        "html": body,
    }

    # Add plain text version for deliverability
    text = _html_to_text(body)
    if text:
        payload["text"] = text

    # Add reply-to if configured
    if settings.reply_to_email:
        payload["reply_to"] = settings.reply_to_email
    if unsubscribe_url:
        payload["headers"] = {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    # 4. Build headers with idempotency key
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Use recipient ID as idempotency key (stable across retries)
    idempotency_key = f"campaign-recipient/{recipient.id}"
    headers["Idempotency-Key"] = idempotency_key

    # 5. Send with retry
    try:
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
    except httpx.TimeoutException:
        recipient.status = "failed"
        recipient.error = "Connection timeout"
        db.commit()
        logger.warning("Resend timeout for recipient %s", recipient.id)
        return False, "Connection timeout"
    except Exception as e:
        recipient.status = "failed"
        recipient.error = f"Connection error: {e.__class__.__name__}"
        db.commit()
        logger.exception("Resend connection error for recipient %s", recipient.id)
        return False, recipient.error

    # 6. Process response
    now = datetime.now(timezone.utc)

    if 200 <= response.status_code < 300:
        data = response.json()
        message_id = data.get("id")

        recipient.status = "sent"
        recipient.sent_at = now
        recipient.external_message_id = message_id
        db.commit()

        logger.info("Email sent to recipient %s, message_id=%s", recipient.id, message_id)
        return True, None

    # Handle 409 as duplicate (idempotency conflict = already sent)
    if response.status_code == 409:
        message_id = None
        try:
            data = response.json()
            if isinstance(data, dict):
                mid = data.get("id")
                if isinstance(mid, str) and mid:
                    message_id = mid
        except Exception:
            pass

        # Already sent, mark as success
        recipient.status = "sent"
        recipient.sent_at = now
        recipient.external_message_id = message_id
        db.commit()

        logger.info("Email already sent (409) for recipient %s", recipient.id)
        return True, None

    # Handle non-retryable errors
    error_detail = None
    try:
        data = response.json()
        if isinstance(data, dict):
            error_detail = data.get("message") or data.get("error")
    except Exception:
        pass

    error_msg = f"Resend API error: {response.status_code}"
    if error_detail:
        error_msg = f"{error_msg} ({error_detail})"

    recipient.status = "failed"
    recipient.error = error_msg
    db.commit()

    logger.warning("Resend error for recipient %s: %s", recipient.id, error_msg)
    return False, error_msg


async def send_email_direct(
    api_key: str,
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str | None = None,
    reply_to: str | None = None,
    idempotency_key: str | None = None,
    unsubscribe_url: str | None = None,
) -> tuple[bool, str | None, str | None]:
    """
    Send an email directly via Resend (no campaign context).

    Args:
        api_key: Resend API key (decrypted)
        to_email: Recipient email
        subject: Email subject
        body: Email body (HTML)
        from_email: Sender email
        from_name: Sender name (optional)
        reply_to: Reply-to email (optional)
        idempotency_key: Idempotency key (optional)

    Returns:
        (success, error_message, message_id)
    """
    from_address = f"{from_name} <{from_email}>" if from_name else from_email

    payload: dict[str, object] = {
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": body,
    }

    text = _html_to_text(body)
    if text:
        payload["text"] = text

    if reply_to:
        payload["reply_to"] = reply_to
    if unsubscribe_url:
        payload["headers"] = {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
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
    except httpx.TimeoutException:
        return False, "Connection timeout", None
    except Exception as e:
        logger.exception("Resend connection error")
        return False, f"Connection error: {e.__class__.__name__}", None

    if 200 <= response.status_code < 300:
        data = response.json()
        message_id = data.get("id")
        return True, None, message_id

    if response.status_code == 409:
        # Idempotency conflict = already sent
        message_id = None
        try:
            data = response.json()
            if isinstance(data, dict):
                mid = data.get("id")
                if isinstance(mid, str) and mid:
                    message_id = mid
        except Exception:
            pass
        return True, None, message_id

    # Error
    error_detail = None
    try:
        data = response.json()
        if isinstance(data, dict):
            error_detail = data.get("message") or data.get("error")
    except Exception:
        pass

    error_msg = f"Resend API error: {response.status_code}"
    if error_detail:
        error_msg = f"{error_msg} ({error_detail})"

    return False, error_msg, None
