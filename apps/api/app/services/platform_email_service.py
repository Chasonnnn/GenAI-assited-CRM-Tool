"""Platform/system email sender.

This module is intentionally scoped to *platform/system* emails (invites, etc).
It uses PLATFORM_RESEND_API_KEY and remains separate from org-level campaign,
workflow, and direct email provider settings.

We intentionally *do not* require a global From address in infra. Instead, each
system template can provide its own `from_email` (recommended). PLATFORM_EMAIL_FROM
is supported only as an optional fallback for local/dev or emergency ops.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import EmailStatus
from app.db.models import EmailLog
from app.services.email_delivery_service import (
    DeliveryRoute,
    EmailSource,
    RenderedEmail,
    queue_rendered_email,
)
from app.services.email_content import html_to_text
from app.types import JsonObject

logger = logging.getLogger(__name__)


def platform_sender_configured() -> bool:
    # Sender is considered "configured" if we have the API key; the From header is
    # expected to be provided by templates at send time (or via PLATFORM_EMAIL_FROM
    # fallback).
    return bool(settings.PLATFORM_RESEND_API_KEY.get_secret_value())


def _result_from_log(log: EmailLog) -> JsonObject:
    success = log.status == EmailStatus.SENT.value
    queued = log.status == EmailStatus.PENDING.value and log.delivery is not None
    return {
        "success": success or queued,
        "queued": queued,
        "message_id": log.external_id,
        "email_log_id": log.id,
        "error": None if success or queued else (log.error or "Email send failed"),
    }


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
    source_type: str | None = None,
    source_id: UUID | None = None,
    attachments: list[dict[str, object]] | None = None,
    commit: bool = True,
) -> JsonObject:
    """Queue a platform/system email in the leased transactional outbox."""
    from app.services import org_service, unsubscribe_service

    if not platform_sender_configured():
        return {
            "success": False,
            "queued": False,
            "error": "Platform email sender not configured (missing PLATFORM_RESEND_API_KEY)",
        }

    resolved_from = (from_email or "").strip() or (settings.PLATFORM_EMAIL_FROM or "").strip()
    if not resolved_from:
        return {
            "success": False,
            "queued": False,
            "error": "Missing From address for platform email (set template from_email in Ops)",
        }
    if attachments:
        return {
            "success": False,
            "queued": False,
            "error": "Platform queued email attachments must use persisted attachment records",
        }

    resolved_text = text if (text or "").strip() else html_to_text(html)
    organization = org_service.get_org_by_id(db, org_id)
    list_headers = unsubscribe_service.build_list_unsubscribe_headers(
        org_id=org_id,
        email=to_email,
        base_url=org_service.get_org_portal_base_url(organization),
    )
    queued = queue_rendered_email(
        db,
        organization_id=org_id,
        route=DeliveryRoute.PLATFORM_RESEND,
        provider_account_id="platform:default",
        rendered_email=RenderedEmail(
            recipient_email=to_email,
            subject=subject,
            html=html,
            text=resolved_text,
            from_email=resolved_from,
            headers=list_headers,
            safe_tags=({"name": "message_kind", "value": "platform_transactional"},),
        ),
        idempotency_key=idempotency_key or f"platform-email/{uuid4()}",
        source=EmailSource(
            source_type=source_type or ("platform_template" if template_id else "platform_email"),
            source_id=source_id if source_type else template_id,
            template_id=template_id,
            surrogate_id=surrogate_id,
            purpose="transactional",
        ),
        commit=commit,
    )
    if queued.email_log.status == EmailStatus.SKIPPED.value:
        return {
            "success": False,
            "queued": False,
            "error": "Email suppressed",
            "email_log_id": queued.email_log.id,
            "message_id": None,
        }

    return {
        "success": True,
        "queued": True,
        "message_id": None,
        "email_log_id": queued.email_log.id,
        "delivery_id": queued.delivery.id if queued.delivery else None,
        "error": None,
    }


class PlatformEmailSender:
    key = "resend"

    def is_configured(self) -> bool:
        return platform_sender_configured()

    async def send_email_logged(
        self,
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
        source_type: str | None = None,
        source_id: UUID | None = None,
        attachments: list[dict[str, object]] | None = None,
        commit: bool = True,
    ) -> JsonObject:
        return await send_email_logged(
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
            source_type=source_type,
            source_id=source_id,
            attachments=attachments,
            commit=commit,
        )
