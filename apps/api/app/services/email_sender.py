"""Email sender interface and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.types import JsonObject
from app.services import gmail_service, platform_email_service


class EmailSender(Protocol):
    async def send_logged(
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
    ) -> JsonObject:
        """Send an email and persist EmailLog."""


@dataclass(frozen=True)
class PlatformEmailSender:
    async def send_logged(
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
    ) -> JsonObject:
        return await platform_email_service.send_logged(
            db=db,
            org_id=org_id,
            to_email=to_email,
            subject=subject,
            from_email=from_email,
            html=html,
            text=text,
            template_id=template_id,
            surrogate_id=surrogate_id,
            idempotency_key=idempotency_key,
        )


@dataclass(frozen=True)
class GmailEmailSender:
    user_id: UUID

    async def send_logged(
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
    ) -> JsonObject:
        return await gmail_service.send_logged(
            db=db,
            org_id=org_id,
            user_id=str(self.user_id),
            to_email=to_email,
            subject=subject,
            html=html,
            text=text,
            template_id=template_id,
            surrogate_id=surrogate_id,
            idempotency_key=idempotency_key,
        )


def platform_sender_configured() -> bool:
    return platform_email_service.platform_sender_configured()


def get_platform_sender() -> PlatformEmailSender:
    return PlatformEmailSender()


def get_gmail_sender(user_id: UUID) -> GmailEmailSender:
    return GmailEmailSender(user_id=user_id)
