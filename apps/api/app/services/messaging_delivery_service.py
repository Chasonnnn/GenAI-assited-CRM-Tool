"""Consent-gated materialization and fenced claiming for Twilio messages."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.messaging import (
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
)
from app.db.models.messaging_delivery import (
    MessageDelivery,
    MessageDeliveryAttempt,
    MessageMediaAsset,
    MessageMediaLink,
    MessageReconciliationCase,
    MessageWebhookEvent,
    MessagingConversation,
    MessagingMessage,
)
from app.services import twilio_settings_service

_PROVIDER_STATUS_RANK = {
    "accepted": 10,
    "scheduled": 10,
    "queued": 20,
    "sending": 30,
    "sent": 40,
    "failed": 50,
    "undelivered": 50,
    "canceled": 50,
    "delivered": 60,
    "read": 70,
}


class MessagingIdempotencyConflict(ValueError):
    """An idempotency key was reused for a different immutable payload."""


class MessagingConsentBlocked(ValueError):
    """The contact is not currently eligible for the selected purpose."""


class MessagingEnrollmentRequired(ValueError):
    """The first message in a consent epoch must confirm enrollment."""


class MessagingMediaBlocked(ValueError):
    """An outbound media asset is unsafe or unavailable."""


class MessagingLeaseLost(RuntimeError):
    """A stale delivery worker attempted to mutate a newer lease generation."""


@dataclass(frozen=True, slots=True)
class ConsentRecheckResult:
    allowed: bool
    reason: str | None


def _should_advance_provider_status(current: str | None, incoming: str) -> bool:
    if current is None:
        return True
    return _PROVIDER_STATUS_RANK.get(incoming, 0) >= _PROVIDER_STATUS_RANK.get(current, 0)


def _status_delivery_and_message(
    db: Session,
    *,
    organization_id: UUID,
    route_id: UUID,
    provider_message_sid: str,
) -> tuple[MessageDelivery | None, MessagingMessage | None]:
    delivery = db.scalar(
        select(MessageDelivery)
        .where(
            MessageDelivery.organization_id == organization_id,
            MessageDelivery.route_id == route_id,
            MessageDelivery.provider_message_sid == provider_message_sid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if delivery is None:
        return None, None
    message = db.scalar(
        select(MessagingMessage)
        .where(
            MessagingMessage.id == delivery.message_id,
            MessagingMessage.organization_id == organization_id,
            MessagingMessage.route_id == route_id,
            MessagingMessage.provider_message_sid == provider_message_sid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return delivery, message


def ensure_orphan_status_case(
    db: Session,
    *,
    event: MessageWebhookEvent,
) -> MessageReconciliationCase:
    """Keep one operator-visible case for an accepted but unlinked status event."""
    db.flush()
    existing = db.scalar(
        select(MessageReconciliationCase)
        .where(
            MessageReconciliationCase.organization_id == event.organization_id,
            MessageReconciliationCase.webhook_event_id == event.id,
            MessageReconciliationCase.case_type == "orphan_webhook",
        )
        .with_for_update()
    )
    if existing is not None:
        return existing
    case = MessageReconciliationCase(
        organization_id=event.organization_id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="status_message_not_found",
        webhook_event_id=event.id,
    )
    db.add(case)
    db.flush()
    return case


def _resolve_orphan_status_cases(
    db: Session,
    *,
    event: MessageWebhookEvent,
    delivery: MessageDelivery,
    resolved_at: datetime,
) -> None:
    cases = list(
        db.scalars(
            select(MessageReconciliationCase)
            .where(
                MessageReconciliationCase.organization_id == event.organization_id,
                MessageReconciliationCase.webhook_event_id == event.id,
                MessageReconciliationCase.case_type == "orphan_webhook",
            )
            .with_for_update()
        )
    )
    for case in cases:
        if case.delivery_id not in {None, delivery.id}:
            continue
        case.delivery_id = delivery.id
        if case.status != "resolved":
            case.status = "resolved"
            case.resolved_at = resolved_at
            case.resolution_code = "status_callback_replayed"
            case.version += 1


def _apply_status_event(
    db: Session,
    *,
    event: MessageWebhookEvent,
    delivery: MessageDelivery,
    message: MessagingMessage,
    processed_at: datetime,
) -> None:
    status = event.provider_status or ""
    if _should_advance_provider_status(message.provider_status, status):
        message.provider_status = status
        if status in {"delivered", "read"}:
            delivery.status = "delivered"
            delivery.completed_at = processed_at
            from app.services import campaign_service

            campaign_service.project_campaign_message_delivery(
                db,
                organization_id=event.organization_id,
                message_delivery_id=delivery.id,
                status="delivered",
                provider_message_id=event.provider_message_sid,
                occurred_at=event.received_at,
                commit=False,
            )
        elif status in {"failed", "undelivered", "canceled"}:
            delivery.status = "failed"
            delivery.completed_at = processed_at
            delivery.last_error_type = f"twilio_{status}"
            delivery.last_error = "Twilio reported a terminal delivery failure"
            from app.services import campaign_service

            campaign_service.project_campaign_message_delivery(
                db,
                organization_id=event.organization_id,
                message_delivery_id=delivery.id,
                status="failed",
                provider_message_id=event.provider_message_sid,
                error="Twilio reported a terminal delivery failure",
                occurred_at=event.received_at,
                commit=False,
            )
        else:
            delivery.status = "submitted"
        delivery.updated_at = processed_at
    event.processed_at = processed_at
    _resolve_orphan_status_cases(
        db,
        event=event,
        delivery=delivery,
        resolved_at=processed_at,
    )


def replay_pending_status_events(
    db: Session,
    *,
    organization_id: UUID,
    route_id: UUID,
    provider_message_sid: str,
) -> int:
    """Replay persisted callbacks after local SID correlation, without provider I/O."""
    # SessionLocal disables autoflush; persist the freshly accepted event or SID link
    # before resolving either side of the correlation.
    db.flush()
    delivery, message = _status_delivery_and_message(
        db,
        organization_id=organization_id,
        route_id=route_id,
        provider_message_sid=provider_message_sid,
    )
    if delivery is None or message is None:
        return 0
    events = list(
        db.scalars(
            select(MessageWebhookEvent)
            .where(
                MessageWebhookEvent.organization_id == organization_id,
                MessageWebhookEvent.route_id == route_id,
                MessageWebhookEvent.provider_message_sid == provider_message_sid,
                MessageWebhookEvent.event_type == "status",
                MessageWebhookEvent.processed_at.is_(None),
            )
            .order_by(MessageWebhookEvent.received_at, MessageWebhookEvent.id)
            .with_for_update()
        )
    )
    for event in events:
        _apply_status_event(
            db,
            event=event,
            delivery=delivery,
            message=message,
            processed_at=datetime.now(UTC),
        )
    db.flush()
    return len(events)


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _payload_fingerprint(
    *,
    contact_id: UUID,
    purpose: str,
    body: str,
    source_type: str,
    source_id: UUID | None,
    template_version_id: UUID | None,
    media_asset_ids: list[UUID],
    is_enrollment_confirmation: bool,
) -> str:
    return _fingerprint(
        {
            "contact_id": str(contact_id),
            "purpose": purpose,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "source_type": source_type,
            "source_id": str(source_id) if source_id else None,
            "template_version_id": str(template_version_id) if template_version_id else None,
            "media_asset_ids": [str(item) for item in media_asset_ids],
            "is_enrollment_confirmation": is_enrollment_confirmation,
        }
    )


def _current_consent(
    db: Session,
    *,
    organization_id: UUID,
    contact_id: UUID,
    purpose: str,
    lock: bool,
) -> tuple[MessagingConsentState | None, MessagingGlobalSuppression | None]:
    state_query = select(MessagingConsentState).where(
        MessagingConsentState.organization_id == organization_id,
        MessagingConsentState.contact_id == contact_id,
        MessagingConsentState.purpose == purpose,
    )
    suppression_query = select(MessagingGlobalSuppression).where(
        MessagingGlobalSuppression.organization_id == organization_id,
        MessagingGlobalSuppression.contact_id == contact_id,
    )
    if lock:
        state_query = state_query.with_for_update()
        suppression_query = suppression_query.with_for_update()
    return (
        db.execute(state_query).scalar_one_or_none(),
        db.execute(suppression_query).scalar_one_or_none(),
    )


def _eligibility_reason(
    state: MessagingConsentState | None,
    suppression: MessagingGlobalSuppression | None,
) -> str | None:
    if suppression is not None and suppression.active:
        return "globally_suppressed"
    if state is None or state.status == "unknown":
        return "consent_unknown"
    if state.status != "opted_in":
        return "purpose_opted_out"
    return None


def materialize_delivery(
    db: Session,
    *,
    organization_id: UUID,
    contact_id: UUID,
    purpose: str,
    body: str,
    idempotency_key: str,
    source_type: str,
    source_id: UUID | None,
    template_version_id: UUID | None,
    media_asset_ids: list[UUID],
    is_enrollment_confirmation: bool,
    run_at: datetime | None = None,
) -> MessageDelivery:
    """Create one immutable message and outbox row after a local eligibility check."""
    if purpose not in {"operational", "promotional"}:
        raise ValueError("Unsupported messaging purpose")
    body = body.strip()
    if not body and not media_asset_ids:
        raise ValueError("A message body or media asset is required")
    if not idempotency_key.strip():
        raise ValueError("An idempotency key is required")

    fingerprint = _payload_fingerprint(
        contact_id=contact_id,
        purpose=purpose,
        body=body,
        source_type=source_type,
        source_id=source_id,
        template_version_id=template_version_id,
        media_asset_ids=media_asset_ids,
        is_enrollment_confirmation=is_enrollment_confirmation,
    )
    existing = db.execute(
        select(MessageDelivery).where(
            MessageDelivery.organization_id == organization_id,
            MessageDelivery.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_fingerprint != fingerprint:
            raise MessagingIdempotencyConflict(
                "Messaging idempotency key was reused with a different payload"
            )
        return existing

    contact = db.execute(
        select(MessagingContact).where(
            MessagingContact.id == contact_id,
            MessagingContact.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if contact is None:
        raise LookupError("Messaging contact not found")

    state, suppression = _current_consent(
        db,
        organization_id=organization_id,
        contact_id=contact_id,
        purpose=purpose,
        lock=True,
    )
    reason = _eligibility_reason(state, suppression)
    if reason:
        raise MessagingConsentBlocked(reason)
    assert state is not None

    prior_confirmation = db.execute(
        select(MessageDelivery.id).where(
            MessageDelivery.organization_id == organization_id,
            MessageDelivery.contact_id == contact_id,
            MessageDelivery.purpose == purpose,
            MessageDelivery.consent_evidence_id == state.latest_evidence_id,
            MessageDelivery.is_enrollment_confirmation.is_(True),
            MessageDelivery.status.notin_(("failed", "cancelled")),
        )
    ).scalar_one_or_none()
    if prior_confirmation is None and not is_enrollment_confirmation:
        raise MessagingEnrollmentRequired(
            "The first message in this consent epoch must be an enrollment confirmation"
        )

    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    route = next((item for item in settings.routes if item.purpose == purpose), None)
    if route is None:
        raise RuntimeError("Purpose-bound Twilio route is missing")

    assets: list[MessageMediaAsset] = []
    if media_asset_ids:
        assets = list(
            db.execute(
                select(MessageMediaAsset).where(
                    MessageMediaAsset.organization_id == organization_id,
                    MessageMediaAsset.id.in_(media_asset_ids),
                )
            ).scalars()
        )
        assets_by_id = {asset.id: asset for asset in assets}
        if set(assets_by_id) != set(media_asset_ids):
            raise MessagingMediaBlocked("One or more media assets are unavailable")
        for asset in assets:
            if asset.scan_status != "clean":
                raise MessagingMediaBlocked("Outbound media must pass malware scanning")
            if asset.content_classification == "phi" and not settings.phi_enabled:
                raise MessagingMediaBlocked("PHI-classified media is blocked")

    conversation = db.execute(
        select(MessagingConversation).where(
            MessagingConversation.organization_id == organization_id,
            MessagingConversation.contact_id == contact_id,
            MessagingConversation.route_id == route.id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        conversation = MessagingConversation(
            organization_id=organization_id,
            contact_id=contact_id,
            route_id=route.id,
        )
        db.add(conversation)
        db.flush()

    sender_hash = (
        route.sender_phone_hash
        or hashlib.sha256(f"unconfigured-route:{route.id}".encode()).hexdigest()
    )
    sender_last4 = route.sender_phone_last4 or "0000"
    message = MessagingMessage(
        organization_id=organization_id,
        conversation_id=conversation.id,
        contact_id=contact_id,
        route_id=route.id,
        purpose=purpose,
        direction="outbound",
        body=body,
        from_phone_hash=sender_hash,
        from_phone_last4=sender_last4,
        to_phone_hash=contact.phone_hash,
        to_phone_last4=contact.phone_last4,
    )
    db.add(message)
    db.flush()

    for position, asset_id in enumerate(media_asset_ids):
        db.add(
            MessageMediaLink(
                organization_id=organization_id,
                message_id=message.id,
                media_asset_id=asset_id,
                position=position,
            )
        )

    delivery = MessageDelivery(
        organization_id=organization_id,
        message_id=message.id,
        contact_id=contact_id,
        route_id=route.id,
        purpose=purpose,
        template_version_id=template_version_id,
        consent_evidence_id=state.latest_evidence_id,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        payload_fingerprint=fingerprint,
        is_enrollment_confirmation=is_enrollment_confirmation,
        run_at=run_at or datetime.now(UTC),
    )
    db.add(delivery)
    conversation.last_message_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.execute(
            select(MessageDelivery).where(
                MessageDelivery.organization_id == organization_id,
                MessageDelivery.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if concurrent is not None and concurrent.payload_fingerprint == fingerprint:
            return concurrent
        raise MessagingIdempotencyConflict(
            "Messaging idempotency key was reused with a different payload"
        ) from None
    db.refresh(delivery)
    return delivery


def _cancel_delivery(delivery: MessageDelivery, reason: str) -> None:
    delivery.status = "cancelled"
    delivery.last_error_type = "consent_block"
    delivery.last_error = reason
    delivery.completed_at = datetime.now(UTC)
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    delivery.updated_at = datetime.now(UTC)


def recheck_before_provider_io(
    db: Session,
    *,
    organization_id: UUID,
    delivery_id: UUID,
    lease_token: UUID | None = None,
    lease_generation: int | None = None,
) -> ConsentRecheckResult:
    """Atomically recheck local consent immediately before the network boundary."""
    delivery = db.execute(
        select(MessageDelivery)
        .where(
            MessageDelivery.id == delivery_id,
            MessageDelivery.organization_id == organization_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if delivery is None:
        raise LookupError("Message delivery not found")
    if lease_token is not None and (
        delivery.lease_token != lease_token or delivery.lease_generation != lease_generation
    ):
        raise MessagingLeaseLost("Messaging delivery lease is no longer current")

    state, suppression = _current_consent(
        db,
        organization_id=organization_id,
        contact_id=delivery.contact_id,
        purpose=delivery.purpose,
        lock=True,
    )
    reason = _eligibility_reason(state, suppression)
    if reason is not None:
        _cancel_delivery(delivery, reason)
        db.commit()
        return ConsentRecheckResult(allowed=False, reason=reason)
    assert state is not None
    if state.latest_evidence_id != delivery.consent_evidence_id:
        _cancel_delivery(delivery, "consent_epoch_changed")
        db.commit()
        return ConsentRecheckResult(allowed=False, reason="consent_epoch_changed")
    return ConsentRecheckResult(allowed=True, reason=None)


def claim_due_deliveries(
    db: Session,
    *,
    worker_id: str,
    limit: int = 25,
    lease_for: timedelta = timedelta(minutes=2),
) -> list[MessageDelivery]:
    """Claim due rows with SKIP LOCKED and a monotonic fencing generation."""
    now = datetime.now(UTC)
    db.execute(
        update(MessageDelivery)
        .where(
            MessageDelivery.status.in_(("pending", "retry_scheduled")),
            MessageDelivery.run_at <= now,
            MessageDelivery.attempt_count >= MessageDelivery.max_attempts,
        )
        .values(
            status="failed",
            last_error_type="max_attempts_exhausted",
            last_error="Maximum delivery attempts exhausted",
            completed_at=now,
            lease_token=None,
            lease_owner=None,
            lease_expires_at=None,
            updated_at=now,
        )
    )
    query = (
        select(MessageDelivery)
        .where(
            MessageDelivery.status.in_(("pending", "retry_scheduled")),
            MessageDelivery.run_at <= now,
            MessageDelivery.attempt_count < MessageDelivery.max_attempts,
        )
        .order_by(MessageDelivery.run_at, MessageDelivery.id)
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = list(db.execute(query).scalars())
    for delivery in rows:
        delivery.status = "leased"
        delivery.lease_token = uuid.uuid4()
        delivery.lease_owner = worker_id[:255]
        delivery.lease_expires_at = now + lease_for
        delivery.lease_generation += 1
        delivery.attempt_count += 1
        delivery.updated_at = now
        db.add(
            MessageDeliveryAttempt(
                organization_id=delivery.organization_id,
                delivery_id=delivery.id,
                attempt_number=delivery.attempt_count,
                lease_token=delivery.lease_token,
                lease_generation=delivery.lease_generation,
                started_at=now,
            )
        )
    db.commit()
    return rows


def mark_ambiguous_delivery(
    db: Session,
    *,
    delivery_id: UUID,
    organization_id: UUID,
    lease_token: UUID,
    lease_generation: int,
) -> MessageReconciliationCase:
    """Fence an ambiguous provider result and prevent automatic resend."""
    delivery = db.execute(
        select(MessageDelivery)
        .where(
            MessageDelivery.id == delivery_id,
            MessageDelivery.organization_id == organization_id,
        )
        .with_for_update()
    ).scalar_one()
    if delivery.lease_token != lease_token or delivery.lease_generation != lease_generation:
        raise MessagingLeaseLost("Messaging delivery lease is no longer current")
    delivery.status = "reconciliation_required"
    delivery.last_error_type = "ambiguous_provider_outcome"
    delivery.last_error = "Provider acceptance could not be determined"
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    delivery.updated_at = datetime.now(UTC)
    attempt = db.execute(
        select(MessageDeliveryAttempt).where(
            MessageDeliveryAttempt.delivery_id == delivery.id,
            MessageDeliveryAttempt.attempt_number == delivery.attempt_count,
        )
    ).scalar_one()
    attempt.outcome = "ambiguous"
    attempt.completed_at = datetime.now(UTC)
    case = MessageReconciliationCase(
        organization_id=organization_id,
        case_type="ambiguous_delivery",
        status="action_required",
        reason_code="provider_acceptance_unknown",
        delivery_id=delivery.id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def recover_expired_delivery_leases(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Quarantine expired provider-call leases instead of blindly resending."""
    now = now or datetime.now(UTC)
    query = (
        select(MessageDelivery)
        .where(
            MessageDelivery.status == "leased",
            MessageDelivery.lease_expires_at <= now,
        )
        .order_by(MessageDelivery.lease_expires_at, MessageDelivery.id)
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = list(db.execute(query).scalars())
    if not rows:
        return 0

    delivery_ids = [d.id for d in rows]
    attempts = (
        db.execute(
            select(MessageDeliveryAttempt).where(
                MessageDeliveryAttempt.delivery_id.in_(delivery_ids)
            )
        )
        .scalars()
        .all()
    )
    attempts_by_delivery = {(a.delivery_id, a.attempt_number): a for a in attempts}

    cases = db.execute(
        select(MessageReconciliationCase.id, MessageReconciliationCase.delivery_id).where(
            MessageReconciliationCase.delivery_id.in_(delivery_ids)
        )
    ).all()
    cases_by_delivery = {c.delivery_id: c.id for c in cases}

    for delivery in rows:
        attempt = attempts_by_delivery.get((delivery.id, delivery.attempt_count))
        if attempt is not None and attempt.outcome == "in_progress":
            attempt.outcome = "lease_expired"
            attempt.error_type = "delivery_lease_expired"
            attempt.error_message = "Provider acceptance could not be determined"
            attempt.completed_at = now
        delivery.status = "reconciliation_required"
        delivery.last_error_type = "delivery_lease_expired"
        delivery.last_error = "Provider acceptance could not be determined"
        delivery.lease_token = None
        delivery.lease_owner = None
        delivery.lease_expires_at = None
        delivery.updated_at = now
        if delivery.id not in cases_by_delivery:
            db.add(
                MessageReconciliationCase(
                    organization_id=delivery.organization_id,
                    case_type="ambiguous_delivery",
                    status="action_required",
                    reason_code="delivery_lease_expired",
                    delivery_id=delivery.id,
                )
            )
    db.commit()
    return len(rows)
