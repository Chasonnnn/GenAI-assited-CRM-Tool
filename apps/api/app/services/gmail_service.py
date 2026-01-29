"""Gmail sending service.

Uses Gmail API to send emails via user's connected account.
"""

import base64
import logging
import uuid
from uuid import UUID
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import EmailStatus
from app.db.models import EmailLog
from app.services import oauth_service
from app.services.http_service import DEFAULT_RETRY_STATUSES, request_with_retries
from app.types import JsonObject

logger = logging.getLogger(__name__)

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_MAX_ATTEMPTS = 3
GMAIL_RETRY_BASE_DELAY = 0.5
GMAIL_RETRY_MAX_DELAY = 4.0


def _result_from_log(log: EmailLog) -> JsonObject:
    success = log.status == EmailStatus.SENT.value
    return {
        "success": success,
        "message_id": log.external_id,
        "email_log_id": log.id,
        "error": None if success else (log.error or "Email send failed"),
    }


async def send_email(
    db: Session,
    user_id: str,
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    headers: dict[str, str] | None = None,
) -> JsonObject:
    """Send an email via Gmail API.

    Args:
        db: Database session
        user_id: UUID of the user (as string)
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text or HTML)
        html: If True, body is HTML

    Returns:
        {"success": True, "message_id": "..."} or {"success": False, "error": "..."}
    """
    # Get access token
    access_token = await oauth_service.get_access_token_async(db, uuid.UUID(user_id), "gmail")
    if not access_token:
        return {"success": False, "error": "Gmail not connected"}

    # Get sender email
    integration = oauth_service.get_user_integration(db, uuid.UUID(user_id), "gmail")
    sender_email = integration.account_email if integration else "me"

    try:
        # Build email message
        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(body, "html"))
        else:
            msg = MIMEText(body)

        msg["To"] = to
        msg["From"] = sender_email
        msg["Subject"] = subject
        if headers:
            for key, value in headers.items():
                if key and value:
                    msg[key] = value

        # Encode message
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        # Send via Gmail API (with retries)
        async with httpx.AsyncClient() as client:

            async def request_fn():
                return await client.post(
                    GMAIL_SEND_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"raw": raw},
                    timeout=30.0,
                )

            response = await request_with_retries(
                request_fn,
                max_attempts=GMAIL_MAX_ATTEMPTS,
                base_delay=GMAIL_RETRY_BASE_DELAY,
                max_delay=GMAIL_RETRY_MAX_DELAY,
            )

        if response.status_code == 401:
            return {
                "success": False,
                "error": "Gmail token expired. Please reconnect.",
            }

        if response.status_code in DEFAULT_RETRY_STATUSES:
            return {
                "success": False,
                "error": f"Gmail API error: {response.status_code}",
            }

        response.raise_for_status()
        data = response.json()

        return {
            "success": True,
            "message_id": data.get("id"),
            "thread_id": data.get("threadId"),
        }
    except httpx.RequestError as e:
        logger.error("Gmail API request failed: %s", e)
        return {"success": False, "error": "Gmail API request failed"}
    except httpx.HTTPStatusError as e:
        logger.error("Gmail API error: status=%s", e.response.status_code)
        return {"success": False, "error": f"Gmail API error: {e.response.status_code}"}
    except Exception as e:
        logger.exception("Gmail send error")
        return {"success": False, "error": str(e)}


async def send_email_logged(
    db: Session,
    org_id: uuid.UUID,
    user_id: str,
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    template_id: uuid.UUID | None = None,
    surrogate_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    headers: dict[str, str] | None = None,
) -> JsonObject:
    """Send a Gmail email with EmailLog tracking + idempotency."""
    from app.services import email_service, unsubscribe_service

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
            return _result_from_log(existing)

    if email_service.is_email_suppressed(db, org_id, to):
        email_log = EmailLog(
            organization_id=org_id,
            template_id=template_id,
            surrogate_id=surrogate_id,
            recipient_email=to,
            subject=subject,
            body=body,
            status=EmailStatus.SKIPPED.value,
            error="suppressed",
            idempotency_key=idempotency_key,
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        return {
            "success": False,
            "error": "Email suppressed",
            "email_log_id": email_log.id,
        }

    email_log = EmailLog(
        organization_id=org_id,
        template_id=template_id,
        surrogate_id=surrogate_id,
        recipient_email=to,
        subject=subject,
        body=body,
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
            return _result_from_log(existing)
        raise
    db.refresh(email_log)

    if headers is None:
        headers = unsubscribe_service.build_list_unsubscribe_headers(org_id=org_id, email=to)

    result = await send_email(
        db=db,
        user_id=user_id,
        to=to,
        subject=subject,
        body=body,
        html=html,
        headers=headers,
    )

    if result.get("success"):
        email_log.status = EmailStatus.SENT.value
        email_log.external_id = result.get("message_id")
        email_log.sent_at = datetime.now(timezone.utc)
        email_log.error = None
    else:
        email_log.status = EmailStatus.FAILED.value
        email_log.error = result.get("error")

    db.commit()
    return {
        **result,
        "email_log_id": email_log.id,
    }


class GmailEmailSender:
    key = "gmail"

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    async def send_email_logged(
        self,
        *,
        db: Session,
        org_id: uuid.UUID,
        to_email: str,
        subject: str,
        html: str,
        text: str | None = None,
        from_email: str | None = None,
        template_id: uuid.UUID | None = None,
        surrogate_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> JsonObject:
        _ = text
        _ = from_email
        return await send_email_logged(
            db=db,
            org_id=org_id,
            user_id=str(self.user_id),
            to=to_email,
            subject=subject,
            body=html,
            html=True,
            template_id=template_id,
            surrogate_id=surrogate_id,
            idempotency_key=idempotency_key,
        )
