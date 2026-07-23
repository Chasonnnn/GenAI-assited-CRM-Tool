"""Canonical lifecycle event contract for Resend email webhooks."""

from __future__ import annotations

from typing import Final


RESEND_DELIVERY_STATUS_BY_EVENT_TYPE: Final = {
    "email.scheduled": "scheduled",
    "email.sent": "sent",
    "email.delivery_delayed": "delivery_delayed",
    "email.delivered": "delivered",
    "email.failed": "failed",
    "email.suppressed": "suppressed",
    "email.bounced": "bounced",
    "email.complained": "complained",
}
RESEND_DELIVERY_EVENT_TYPES = frozenset(RESEND_DELIVERY_STATUS_BY_EVENT_TYPE)
RESEND_DELIVERY_FAILURE_EVENT_TYPES = frozenset(
    {
        "email.failed",
        "email.suppressed",
        "email.bounced",
        "email.complained",
    }
)
RESEND_ENGAGEMENT_EVENT_TYPES = frozenset({"email.opened", "email.clicked"})

# Scheduling is useful projection evidence, but is not proof that an outbound
# message progressed through Resend's delivery lifecycle.
RESEND_OUTBOUND_READINESS_EVENT_TYPES = frozenset(
    (RESEND_DELIVERY_EVENT_TYPES - {"email.scheduled"}) | RESEND_ENGAGEMENT_EVENT_TYPES
)
RESEND_RECONCILABLE_EVENT_TYPES = frozenset(
    RESEND_DELIVERY_EVENT_TYPES | RESEND_ENGAGEMENT_EVENT_TYPES
)

# Inbound receipt is safe to expose from webhook configuration, even though it
# is unrelated to outbound delivery readiness.
RESEND_SANITIZED_WEBHOOK_EVENT_TYPES = frozenset(
    RESEND_OUTBOUND_READINESS_EVENT_TYPES | {"email.received"}
)
