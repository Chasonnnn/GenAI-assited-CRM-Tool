"""Webhook handler registry."""

from __future__ import annotations

from app.services.webhooks.base import WebhookHandler
from app.services.webhooks.meta import MetaWebhookHandler
from app.services.webhooks.resend import (
    PlatformResendWebhookHandler,
    ResendWebhookHandler,
)
from app.services.webhooks.zoom import ZoomWebhookHandler

_HANDLERS: dict[str, WebhookHandler] = {
    "meta": MetaWebhookHandler(),
    "zoom": ZoomWebhookHandler(),
    "resend": ResendWebhookHandler(),
    "resend_platform": PlatformResendWebhookHandler(),
}


def get_handler(name: str):
    handler = _HANDLERS.get(name)
    if not handler:
        raise KeyError(f"Unknown webhook handler: {name}")
    return handler
