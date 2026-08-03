"""Fenced, consent-checked Twilio outbox dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.core.encryption import hash_pii
from app.db.models import IntakeLead, MetaLead, Surrogate
from app.db.models.messaging import MessagingContact, TwilioRoute, TwilioSettings
from app.db.models.messaging_delivery import (
    MessageDelivery,
    MessageDeliveryAttempt,
    MessagingProviderAdmission,
)
from app.services import (
    messaging_consent_service,
    messaging_delivery_service,
    messaging_sending_hours,
    twilio_settings_service,
    twilio_transport,
)

MAX_DISPATCH_BATCH_SIZE = 25


@dataclass(frozen=True, slots=True)
class MessagingDeliveryClaim:
    organization_id: UUID
    delivery_id: UUID
    lease_token: UUID
    lease_generation: int


@dataclass(frozen=True, slots=True)
class MessagingDispatchSummary:
    claimed: int = 0
    submitted: int = 0
    retry_scheduled: int = 0
    deferred: int = 0
    failed: int = 0
    cancelled: int = 0
    reconciliation_required: int = 0
    lease_lost: int = 0
    unexpected_errors: int = 0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _require_current_lease(
    db: Session,
    *,
    organization_id: UUID,
    delivery_id: UUID,
    lease_token: UUID,
    lease_generation: int,
) -> MessageDelivery:
    delivery = db.execute(
        select(MessageDelivery)
        .where(
            MessageDelivery.id == delivery_id,
            MessageDelivery.organization_id == organization_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if delivery is None:
        raise LookupError("Messaging delivery not found")
    if (
        delivery.status != "leased"
        or delivery.lease_token != lease_token
        or delivery.lease_generation != lease_generation
    ):
        raise messaging_delivery_service.MessagingLeaseLost(
            "Messaging delivery lease is no longer current"
        )
    return delivery


def _current_attempt(db: Session, delivery: MessageDelivery) -> MessageDeliveryAttempt:
    return db.execute(
        select(MessageDeliveryAttempt).where(
            MessageDeliveryAttempt.delivery_id == delivery.id,
            MessageDeliveryAttempt.attempt_number == delivery.attempt_count,
            MessageDeliveryAttempt.lease_token == delivery.lease_token,
            MessageDeliveryAttempt.lease_generation == delivery.lease_generation,
        )
    ).scalar_one()


def _clear_lease(delivery: MessageDelivery) -> None:
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    delivery.updated_at = datetime.now(UTC)


def _project_campaign_delivery(
    db: Session,
    delivery: MessageDelivery,
    *,
    status: str,
    provider_message_id: str | None = None,
    error: str | None = None,
) -> None:
    from app.services import campaign_service

    campaign_service.project_campaign_message_delivery(
        db,
        organization_id=delivery.organization_id,
        message_delivery_id=delivery.id,
        status=status,
        provider_message_id=provider_message_id,
        error=error,
        commit=False,
    )


def _defer(
    db: Session,
    delivery: MessageDelivery,
    *,
    run_at: datetime,
    error_type: str,
    reason: str,
) -> None:
    attempt = _current_attempt(db, delivery)
    attempt.outcome = "retryable_error"
    attempt.error_type = error_type
    attempt.error_message = reason
    attempt.completed_at = datetime.now(UTC)
    delivery.status = "retry_scheduled"
    delivery.run_at = _as_utc(run_at)
    delivery.last_error_type = error_type
    delivery.last_error = reason
    _clear_lease(delivery)
    db.commit()


def _fail(
    db: Session,
    delivery: MessageDelivery,
    *,
    error_type: str,
    reason: str,
    provider_status_code: int | None = None,
) -> None:
    attempt = _current_attempt(db, delivery)
    attempt.outcome = "terminal_error"
    attempt.error_type = error_type
    attempt.error_message = reason
    attempt.provider_http_status = provider_status_code
    attempt.completed_at = datetime.now(UTC)
    delivery.status = "failed"
    delivery.last_error_type = error_type
    delivery.last_error = reason
    delivery.completed_at = datetime.now(UTC)
    _clear_lease(delivery)
    _project_campaign_delivery(db, delivery, status="failed", error=reason)
    db.commit()


def _location_from_dict(value: object) -> tuple[str | None, str | None, str | None]:
    if not isinstance(value, dict):
        return None, None, None
    state = value.get("address_state") or value.get("state")
    postal = value.get("address_postal") or value.get("postal_code") or value.get("zip")
    timezone_name = value.get("timezone") or value.get("timezone_name")
    return (
        str(state) if state else None,
        str(postal) if postal else None,
        str(timezone_name) if timezone_name else None,
    )


def _recipient_location(
    db: Session,
    contact: MessagingContact,
) -> tuple[str | None, str | None, str | None]:
    if contact.surrogate_id:
        surrogate = db.execute(
            select(Surrogate).where(
                Surrogate.id == contact.surrogate_id,
                Surrogate.organization_id == contact.organization_id,
            )
        ).scalar_one_or_none()
        if surrogate is not None:
            return (
                surrogate.address_state or surrogate.state,
                surrogate.address_postal,
                None,
            )
    if contact.intake_lead_id:
        lead = db.execute(
            select(IntakeLead).where(
                IntakeLead.id == contact.intake_lead_id,
                IntakeLead.organization_id == contact.organization_id,
            )
        ).scalar_one_or_none()
        if lead is not None:
            return _location_from_dict(lead.source_metadata)
    if contact.meta_lead_id:
        lead = db.execute(
            select(MetaLead).where(
                MetaLead.id == contact.meta_lead_id,
                MetaLead.organization_id == contact.organization_id,
            )
        ).scalar_one_or_none()
        if lead is not None:
            return _location_from_dict(lead.field_data)
    return None, None, None


def _reserve_account_slot(
    db: Session,
    *,
    account_sid: str,
    route: TwilioRoute,
    now: datetime,
) -> datetime | None:
    account_hash = hash_pii(account_sid, purpose="twilio-admission")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            postgresql_insert(MessagingProviderAdmission)
            .values(account_sid_hash=account_hash, next_slot_at=now)
            .on_conflict_do_nothing(index_elements=["account_sid_hash"])
        )
    admission = db.execute(
        select(MessagingProviderAdmission)
        .where(MessagingProviderAdmission.account_sid_hash == account_hash)
        .with_for_update()
    ).scalar_one_or_none()
    if admission is None:
        admission = MessagingProviderAdmission(
            account_sid_hash=account_hash,
            next_slot_at=now,
        )
        db.add(admission)
        db.flush()
    next_slot = _as_utc(admission.next_slot_at)
    if next_slot > now:
        return next_slot
    evidence = route.capability_evidence or {}
    raw_rate = evidence.get("messages_per_second", 1)
    try:
        messages_per_second = max(0.1, min(100.0, float(raw_rate)))
    except TypeError, ValueError:
        messages_per_second = 1.0
    admission.next_slot_at = now + timedelta(seconds=1 / messages_per_second)
    admission.updated_at = now
    return None


def _media_urls(delivery: MessageDelivery) -> list[str]:
    if not delivery.message.media_links:
        return []
    try:
        from app.services import message_content_service
    except ImportError as exc:
        raise RuntimeError("Messaging media delivery is unavailable") from exc
    return [
        message_content_service.create_short_lived_media_url(link.media_asset)
        for link in sorted(delivery.message.media_links, key=lambda item: item.position)
    ]


def dispatch_claimed_delivery(
    db: Session,
    *,
    organization_id: UUID,
    delivery_id: UUID,
    lease_token: UUID,
    lease_generation: int,
    now: datetime | None = None,
) -> str:
    """Dispatch one current lease; never retry an ambiguous provider outcome."""
    now = _as_utc(now or datetime.now(UTC))
    delivery = _require_current_lease(
        db,
        organization_id=organization_id,
        delivery_id=delivery_id,
        lease_token=lease_token,
        lease_generation=lease_generation,
    )
    contact = db.execute(
        select(MessagingContact).where(
            MessagingContact.id == delivery.contact_id,
            MessagingContact.organization_id == organization_id,
        )
    ).scalar_one()
    route = db.execute(
        select(TwilioRoute).where(
            TwilioRoute.id == delivery.route_id,
            TwilioRoute.organization_id == organization_id,
            TwilioRoute.purpose == delivery.purpose,
        )
    ).scalar_one()
    settings = db.execute(
        select(TwilioSettings).where(TwilioSettings.organization_id == organization_id)
    ).scalar_one()

    state, postal_code, known_timezone = _recipient_location(db, contact)
    timezone_evidence = messaging_sending_hours.resolve_recipient_timezone(
        phone_e164=contact.phone_e164,
        state=state,
        postal_code=postal_code,
        known_timezone=known_timezone,
    )
    if timezone_evidence.timezone_name is None:
        _defer(
            db,
            delivery,
            run_at=now + timedelta(days=1),
            error_type="recipient_location_ambiguous",
            reason="Recipient timezone requires location review",
        )
        return "deferred_location_ambiguous"
    window = messaging_sending_hours.evaluate_sending_window(
        now=now,
        timezone_name=timezone_evidence.timezone_name,
        state=state,
    )
    if not window.allowed:
        assert window.defer_until is not None
        _defer(
            db,
            delivery,
            run_at=window.defer_until,
            error_type="outside_sending_hours",
            reason=window.reason or "Outside recipient sending hours",
        )
        return "deferred_sending_hours"

    required_configuration = (
        settings.enabled,
        route.enabled,
        route.a2p_status == "approved",
        route.advanced_opt_out_status == "verified",
        bool(settings.account_sid_encrypted),
        bool(settings.api_key_sid_encrypted),
        bool(settings.api_secret_encrypted),
        bool(route.messaging_service_sid_encrypted),
        bool(route.sender_phone_encrypted),
    )
    if not all(required_configuration):
        _defer(
            db,
            delivery,
            run_at=now + timedelta(minutes=15),
            error_type="twilio_route_not_ready",
            reason="Purpose-bound Twilio route is not ready",
        )
        return "deferred_route_not_ready"

    account_sid = twilio_settings_service.decrypt_credential(settings.account_sid_encrypted)
    admission_at = _reserve_account_slot(
        db,
        account_sid=account_sid,
        route=route,
        now=now,
    )
    if admission_at is not None:
        _defer(
            db,
            delivery,
            run_at=admission_at,
            error_type="provider_admission_deferred",
            reason="Twilio account admission slot is not available",
        )
        return "deferred_admission"

    consent = messaging_delivery_service.recheck_before_provider_io(
        db,
        organization_id=organization_id,
        delivery_id=delivery.id,
        lease_token=lease_token,
        lease_generation=lease_generation,
    )
    if not consent.allowed:
        db.refresh(delivery)
        _project_campaign_delivery(
            db,
            delivery,
            status="cancelled",
            error=consent.reason,
        )
        db.commit()
        return "cancelled"

    service_sid = twilio_settings_service.decrypt_credential(route.messaging_service_sid_encrypted)
    sender = twilio_settings_service.decrypt_credential(route.sender_phone_encrypted)
    media_urls = _media_urls(delivery)
    result = twilio_transport.send_message(
        credentials=twilio_transport.TwilioCredentials(
            account_sid=account_sid,
            api_key_sid=twilio_settings_service.decrypt_credential(settings.api_key_sid_encrypted),
            api_secret=twilio_settings_service.decrypt_credential(settings.api_secret_encrypted),
        ),
        to=contact.phone_e164,
        from_=sender,
        messaging_service_sid=service_sid,
        body=delivery.message.body or None,
        status_callback=(f"{app_base_url()}/webhooks/twilio/{route.webhook_id}/status"),
        media_urls=media_urls,
    )
    if result.success:
        attempt = _current_attempt(db, delivery)
        attempt.outcome = "succeeded"
        attempt.provider_message_sid = result.message_sid
        attempt.completed_at = datetime.now(UTC)
        delivery.status = "submitted"
        delivery.provider_message_sid = result.message_sid
        delivery.message.provider_message_sid = result.message_sid
        delivery.message.provider_status = result.initial_status
        delivery.last_error_type = None
        delivery.last_error = None
        _clear_lease(delivery)
        _project_campaign_delivery(
            db,
            delivery,
            status="submitted",
            provider_message_id=result.message_sid,
        )
        db.commit()
        return "submitted"

    if result.ambiguous:
        messaging_delivery_service.mark_ambiguous_delivery(
            db,
            delivery_id=delivery.id,
            organization_id=organization_id,
            lease_token=lease_token,
            lease_generation=lease_generation,
        )
        db.refresh(delivery)
        _project_campaign_delivery(
            db,
            delivery,
            status="reconciliation_required",
            error="Provider acceptance could not be determined",
        )
        db.commit()
        return "reconciliation_required"
    if result.provider_opt_out:
        messaging_consent_service.record_global_stop(
            db,
            organization_id=organization_id,
            phone=contact.phone_e164,
            instruction_text="Provider reported messaging opt-out",
            source="twilio_21610",
            source_reference=str(delivery.id),
            occurred_at=now,
            idempotency_key=f"twilio-21610:{delivery.id}",
            evidence_metadata={"provider_error_code": 21610},
            commit=False,
        )
        _fail(
            db,
            delivery,
            error_type="twilio_provider_opt_out",
            reason="Twilio blocked the recipient as opted out",
            provider_status_code=result.provider_status_code,
        )
        return "failed"
    if result.retryable:
        retry_delay = min(300, 5 * (2 ** max(0, delivery.attempt_count - 1)))
        _defer(
            db,
            delivery,
            run_at=now + timedelta(seconds=retry_delay),
            error_type="twilio_rate_limited",
            reason="Twilio rate limited the request",
        )
        return "retry_scheduled"
    _fail(
        db,
        delivery,
        error_type=str(result.failure_reason or "twilio_rejected"),
        reason="Twilio rejected the message request",
        provider_status_code=result.provider_status_code,
    )
    return "failed"


def app_base_url() -> str:
    from app.core.config import settings

    return settings.API_BASE_URL.rstrip("/")


async def dispatch_due_delivery_batch(
    *,
    session_factory: Callable[[], AbstractContextManager[Session]],
    worker_id: str,
    limit: int = 10,
    lease_for: timedelta = timedelta(minutes=2),
) -> MessagingDispatchSummary:
    """Claim a bounded batch and run each blocking SDK call in a worker thread."""
    if limit < 1 or limit > MAX_DISPATCH_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_DISPATCH_BATCH_SIZE}")
    with session_factory() as claim_db:
        deliveries = messaging_delivery_service.claim_due_deliveries(
            claim_db,
            worker_id=worker_id,
            limit=limit,
            lease_for=lease_for,
        )
        claims = [
            MessagingDeliveryClaim(
                organization_id=delivery.organization_id,
                delivery_id=delivery.id,
                lease_token=delivery.lease_token,
                lease_generation=delivery.lease_generation,
            )
            for delivery in deliveries
            if delivery.lease_token is not None
        ]
    if not claims:
        return MessagingDispatchSummary()

    def dispatch_one(claim: MessagingDeliveryClaim) -> str:
        with session_factory() as delivery_db:
            return dispatch_claimed_delivery(
                delivery_db,
                organization_id=claim.organization_id,
                delivery_id=claim.delivery_id,
                lease_token=claim.lease_token,
                lease_generation=claim.lease_generation,
            )

    results = await asyncio.gather(
        *(asyncio.to_thread(dispatch_one, claim) for claim in claims),
        return_exceptions=True,
    )
    submitted = retry_scheduled = deferred = failed = cancelled = reconciliation = 0
    lease_lost = unexpected = 0
    for result in results:
        if isinstance(result, messaging_delivery_service.MessagingLeaseLost):
            lease_lost += 1
        elif isinstance(result, BaseException):
            unexpected += 1
        elif result == "submitted":
            submitted += 1
        elif result == "retry_scheduled":
            retry_scheduled += 1
        elif result.startswith("deferred_"):
            deferred += 1
        elif result == "failed":
            failed += 1
        elif result == "cancelled":
            cancelled += 1
        elif result == "reconciliation_required":
            reconciliation += 1
    return MessagingDispatchSummary(
        claimed=len(claims),
        submitted=submitted,
        retry_scheduled=retry_scheduled,
        deferred=deferred,
        failed=failed,
        cancelled=cancelled,
        reconciliation_required=reconciliation,
        lease_lost=lease_lost,
        unexpected_errors=unexpected,
    )
