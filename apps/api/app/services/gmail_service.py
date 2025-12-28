"""Gmail sending service.

Uses Gmail API to send emails via user's connected account.
"""

import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.services import oauth_service

logger = logging.getLogger(__name__)

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


async def send_email(
    db: Session,
    user_id: str,
    to: str,
    subject: str,
    body: str,
    html: bool = False,
) -> dict[str, Any]:
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
    import uuid

    # Get access token
    access_token = oauth_service.get_access_token(db, uuid.UUID(user_id), "gmail")
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

        # Encode message
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        # Send via Gmail API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GMAIL_SEND_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"raw": raw},
            )

            if response.status_code == 401:
                # Token expired, try to refresh
                return {
                    "success": False,
                    "error": "Gmail token expired. Please reconnect.",
                }

            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "message_id": data.get("id"),
                "thread_id": data.get("threadId"),
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail API error: {e.response.text}")
        return {"success": False, "error": f"Gmail API error: {e.response.status_code}"}
    except Exception as e:
        logger.exception(f"Gmail send error: {e}")
        return {"success": False, "error": str(e)}
