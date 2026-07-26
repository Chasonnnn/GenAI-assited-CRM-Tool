def test_outbound_readiness_events_are_supported_and_sanitized():
    from app.services.resend_event_contract import (
        RESEND_DELIVERY_EVENT_TYPES,
        RESEND_ENGAGEMENT_EVENT_TYPES,
        RESEND_OUTBOUND_READINESS_EVENT_TYPES,
        RESEND_RECONCILABLE_EVENT_TYPES,
        RESEND_SANITIZED_WEBHOOK_EVENT_TYPES,
    )

    delivery_events = frozenset(
        {
            "email.sent",
            "email.delivery_delayed",
            "email.delivered",
            "email.failed",
            "email.suppressed",
            "email.bounced",
            "email.complained",
        }
    )
    engagement_events = frozenset({"email.opened", "email.clicked"})
    outbound_readiness_events = delivery_events | engagement_events

    assert delivery_events <= RESEND_DELIVERY_EVENT_TYPES
    assert RESEND_ENGAGEMENT_EVENT_TYPES == engagement_events
    assert RESEND_OUTBOUND_READINESS_EVENT_TYPES == outbound_readiness_events
    assert outbound_readiness_events <= RESEND_RECONCILABLE_EVENT_TYPES
    assert outbound_readiness_events <= RESEND_SANITIZED_WEBHOOK_EVENT_TYPES
    assert "email.scheduled" not in RESEND_OUTBOUND_READINESS_EVENT_TYPES
    assert "email.received" not in RESEND_OUTBOUND_READINESS_EVENT_TYPES
