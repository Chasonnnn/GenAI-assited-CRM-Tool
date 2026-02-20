"""Email sender interface + selection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.gmail_service import GmailEmailSender
from app.services.platform_email_service import PlatformEmailSender


class EmailSender(Protocol):
    key: str

    async def send_email_logged(
        self,
        *,
        db: Session,
        org_id: UUID,
        to_email: str,
        subject: str,
        html: str,
        text: str | None = None,
        from_email: str | None = None,
        template_id: UUID | None = None,
        surrogate_id: UUID | None = None,
        idempotency_key: str | None = None,
        attachments: list[dict[str, object]] | None = None,
    ):
        """Send and log an email with provider-specific tracking."""


@dataclass(frozen=True)
class SenderSelection:
    sender: EmailSender | None
    integration_key: str | None
    error: str | None


def select_sender(*, prefer_platform: bool, sender_user_id: UUID | None) -> SenderSelection:
    """
    Select the sender to use based on platform configuration and fallback user.

    prefer_platform: If True, chooses platform sender when configured.
    sender_user_id: User ID to fall back to Gmail when platform sender unavailable.
    """
    platform_sender = PlatformEmailSender()
    if prefer_platform and platform_sender.is_configured():
        return SenderSelection(
            sender=platform_sender,
            integration_key=platform_sender.key,
            error=None,
        )

    if not sender_user_id:
        return SenderSelection(
            sender=None,
            integration_key=None,
            error="No inviter to send from",
        )

    gmail_sender = GmailEmailSender(sender_user_id)
    return SenderSelection(
        sender=gmail_sender,
        integration_key=gmail_sender.key,
        error=None,
    )
