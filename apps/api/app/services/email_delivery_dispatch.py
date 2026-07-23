"""Dispatch leased email outbox rows through their recorded Resend account.

Database transactions are intentionally closed before provider I/O. The claim's
fencing token is re-checked when the result is projected, so a stale worker
cannot overwrite a newer attempt.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, ContextManager

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import (
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderScope,
    EmailSuppressionPolicy,
)
from app.db.models import EmailDelivery, ResendSettings
from app.services import (
    email_provider_admission_service,
    email_service,
    resend_settings_service,
    resend_transport,
)
from app.services.email_delivery_service import (
    DeliveryClaim,
    DeliveryLeaseLost,
    claim_due_deliveries,
    record_delivery_cancelled,
    record_delivery_failure,
    record_delivery_reconciliation_required,
    record_delivery_suppressed,
    record_delivery_success,
    stored_request_fingerprint_matches,
)

logger = logging.getLogger(__name__)
MAX_DELIVERY_BATCH_SIZE = 10
MIN_DELIVERY_LEASE_SECONDS = 90
MIN_PROVIDER_IO_WINDOW_SECONDS = 75


@dataclass(frozen=True, slots=True)
class PreparedDelivery:
    """Provider request copied out of the database before network I/O."""

    api_key: str
    payload: dict[str, object]
    idempotency_key: str
    provider: str
    provider_account_id: str
    provider_credential_fingerprint: str
    lease_expires_at: datetime
    idempotency_expires_at: datetime


@dataclass(frozen=True, slots=True)
class DeliveryBatchSummary:
    """Bounded batch outcome for worker observability."""

    claimed: int = 0
    sent: int = 0
    retry_scheduled: int = 0
    failed: int = 0
    cancelled: int = 0
    lease_lost: int = 0
    unexpected_errors: int = 0


class DeliveryConfigurationError(RuntimeError):
    """A leased delivery cannot resolve its recorded credential identity."""


class DeliveryPayloadError(RuntimeError):
    """Stored provider payload or attachment content cannot be prepared safely."""


class DeliveryCredentialChanged(RuntimeError):
    """A retry resolved a different credential than the first provider attempt."""


class RecipientSuppressed(RuntimeError):
    """A suppression was added after the message entered the outbox."""


class DeliveryNoLongerEligible(RuntimeError):
    """The source operation was cancelled after this message was queued."""

    def __init__(self, reason_type: str, reason_message: str):
        super().__init__(reason_message)
        self.reason_type = reason_type
        self.reason_message = reason_message


def _raise_if_source_ineligible(db: Session, delivery: EmailDelivery) -> None:
    email_log = delivery.email_log
    if email_log.source_type == "campaign_recipient":
        if email_log.source_id is None:
            raise DeliveryConfigurationError("Campaign recipient delivery source is missing")
        from app.services import campaign_service

        if not campaign_service.is_campaign_recipient_delivery_eligible(
            db,
            delivery.organization_id,
            email_log.source_id,
        ):
            raise DeliveryNoLongerEligible(
                "campaign_ineligible",
                "campaign_ineligible",
            )
    elif email_log.source_type == "org_invite":
        if email_log.source_id is None:
            raise DeliveryConfigurationError("Invite delivery source is missing")
        from app.services import invite_service

        if not invite_service.is_invite_delivery_eligible(
            db,
            delivery.organization_id,
            email_log.source_id,
            email_log.idempotency_key,
        ):
            raise DeliveryNoLongerEligible(
                "invite_ineligible",
                "invite_ineligible",
            )
    elif email_log.source_type == "appointment_email":
        if email_log.source_id is None:
            raise DeliveryConfigurationError("Appointment email delivery source is missing")
        from app.services import appointment_email_service

        if not appointment_email_service.is_appointment_email_delivery_eligible(
            db,
            delivery.organization_id,
            email_log.source_id,
        ):
            raise DeliveryNoLongerEligible(
                "appointment_ineligible",
                "appointment_ineligible",
            )


def _resolve_api_key(db: Session, delivery: EmailDelivery) -> str:
    scope = delivery.provider_scope
    account_id = delivery.provider_account_id

    if scope == EmailProviderScope.PLATFORM.value:
        if account_id != "platform:default":
            raise DeliveryConfigurationError("Platform provider account identity is invalid")
        api_key = settings.PLATFORM_RESEND_API_KEY.get_secret_value()
        if not api_key:
            raise DeliveryConfigurationError("Platform Resend sender is not configured")
        return api_key

    if scope == EmailProviderScope.ORGANIZATION.value:
        expected_account_id = f"organization:{delivery.organization_id}"
        if account_id != expected_account_id:
            raise DeliveryConfigurationError("Organization provider account identity is invalid")
        resend_settings = (
            db.query(ResendSettings)
            .filter(ResendSettings.organization_id == delivery.organization_id)
            .one_or_none()
        )
        if not resend_settings_service.is_resend_sender_configured(resend_settings):
            raise DeliveryConfigurationError("Organization Resend sender is not configured")
        try:
            return resend_settings_service.decrypt_api_key(resend_settings.api_key_encrypted)
        except Exception as exc:
            raise DeliveryConfigurationError(
                "Organization Resend credentials are unavailable"
            ) from exc

    raise DeliveryConfigurationError("Email provider scope is not supported")


def _provider_attachments(
    db: Session,
    *,
    organization_id,
    email_log_id,
) -> list[dict[str, object]]:
    try:
        attachments = email_service.load_email_log_provider_attachments(
            db,
            organization_id,
            email_log_id,
        )
        return [
            {
                "filename": attachment["filename"],
                "content": base64.b64encode(attachment["content_bytes"]).decode("ascii"),
                "content_type": attachment["content_type"],
            }
            for attachment in attachments
        ]
    except Exception as exc:
        logger.error(
            "Stored email attachments could not be prepared",
            extra={"error_type": type(exc).__name__},
        )
        raise DeliveryPayloadError("Stored email attachments could not be prepared") from None


def _prepare_delivery(db: Session, claim: DeliveryClaim) -> PreparedDelivery:
    delivery = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.id == claim.delivery_id,
            EmailDelivery.organization_id == claim.organization_id,
        )
        .one_or_none()
    )
    if (
        delivery is None
        or delivery.status != EmailDeliveryStatus.LEASED.value
        or delivery.lease_token != claim.lease_token
    ):
        raise DeliveryLeaseLost("delivery lease is no longer owned by this worker")
    if delivery.lease_expires_at is None or delivery.lease_expires_at <= datetime.now(timezone.utc):
        raise DeliveryLeaseLost("delivery lease has expired")
    if delivery.provider != EmailProvider.RESEND.value:
        raise DeliveryConfigurationError("Email provider is not supported")

    api_key = _resolve_api_key(db, delivery)
    credential_fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    if delivery.provider_credential_fingerprint is None:
        delivery.provider_credential_fingerprint = credential_fingerprint
        db.flush()
    elif delivery.provider_credential_fingerprint != credential_fingerprint:
        raise DeliveryCredentialChanged("Provider credential changed after delivery attempts began")
    email_log = delivery.email_log
    if (
        email_log.provider != delivery.provider
        or email_log.provider_scope != delivery.provider_scope
        or email_log.provider_account_id != delivery.provider_account_id
        or email_log.idempotency_key != delivery.idempotency_key
    ):
        raise DeliveryConfigurationError("Stored email delivery identity is inconsistent")
    if not email_log.from_email:
        raise DeliveryConfigurationError("Stored email sender is missing")
    if not stored_request_fingerprint_matches(delivery):
        raise DeliveryPayloadError("Stored email payload fingerprint does not match")

    try:
        payload: dict[str, object] = {
            "from": email_log.from_email,
            "to": [email_log.recipient_email],
            "subject": email_log.subject,
            "html": email_log.body,
        }
        if email_log.text_body:
            payload["text"] = email_log.text_body
        if email_log.reply_to_email:
            payload["reply_to"] = email_log.reply_to_email
        if email_log.headers:
            payload["headers"] = dict(email_log.headers)
        if email_log.safe_tags:
            payload["tags"] = [dict(tag) for tag in email_log.safe_tags]
    except (TypeError, ValueError) as exc:
        logger.error(
            "Stored email payload is invalid",
            extra={"error_type": type(exc).__name__},
        )
        raise DeliveryPayloadError("Stored email payload could not be prepared") from None

    attachments = _provider_attachments(
        db,
        organization_id=delivery.organization_id,
        email_log_id=email_log.id,
    )
    if attachments:
        payload["attachments"] = attachments

    if email_service.is_email_suppressed(
        db,
        delivery.organization_id,
        email_log.recipient_email,
        ignore_opt_out=(email_log.suppression_policy == EmailSuppressionPolicy.ALLOW_OPT_OUT.value),
    ):
        raise RecipientSuppressed
    _raise_if_source_ineligible(db, delivery)
    return PreparedDelivery(
        api_key=api_key,
        payload=payload,
        idempotency_key=delivery.idempotency_key,
        provider=delivery.provider,
        provider_account_id=delivery.provider_account_id,
        provider_credential_fingerprint=credential_fingerprint,
        lease_expires_at=delivery.lease_expires_at,
        idempotency_expires_at=delivery.idempotency_expires_at,
    )


def _revalidate_delivery_for_send(db: Session, claim: DeliveryClaim) -> None:
    """Recheck mutable delivery policy immediately before provider I/O."""
    delivery = (
        db.query(EmailDelivery)
        .populate_existing()
        .filter(
            EmailDelivery.id == claim.delivery_id,
            EmailDelivery.organization_id == claim.organization_id,
        )
        .one_or_none()
    )
    if (
        delivery is None
        or delivery.status != EmailDeliveryStatus.LEASED.value
        or delivery.lease_token != claim.lease_token
    ):
        raise DeliveryLeaseLost("delivery lease is no longer owned by this worker")
    if delivery.lease_expires_at is None or delivery.lease_expires_at <= datetime.now(timezone.utc):
        raise DeliveryLeaseLost("delivery lease has expired")

    email_log = delivery.email_log
    if email_service.is_email_suppressed(
        db,
        delivery.organization_id,
        email_log.recipient_email,
        ignore_opt_out=(email_log.suppression_policy == EmailSuppressionPolicy.ALLOW_OPT_OUT.value),
    ):
        raise RecipientSuppressed
    _raise_if_source_ineligible(db, delivery)


async def dispatch_claim(
    db: Session,
    *,
    claim: DeliveryClaim,
    sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> EmailDelivery:
    """Dispatch one leased delivery and durably record its fenced outcome."""
    try:
        prepared = _prepare_delivery(db, claim)
    except DeliveryLeaseLost:
        db.commit()
        raise
    except RecipientSuppressed:
        db.commit()
        return record_delivery_suppressed(db, claim=claim)
    except DeliveryNoLongerEligible as exc:
        db.commit()
        return record_delivery_cancelled(
            db,
            claim=claim,
            reason_type=exc.reason_type,
            reason_message=exc.reason_message,
        )
    except DeliveryCredentialChanged as exc:
        db.commit()
        return record_delivery_reconciliation_required(
            db,
            claim=claim,
            error_type="provider_credential_changed",
            error_message=str(exc),
        )
    except DeliveryConfigurationError as exc:
        db.commit()
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=False,
            error_type="configuration_error",
            error_message=str(exc),
        )
    except DeliveryPayloadError as exc:
        db.commit()
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=False,
            error_type="payload_error",
            error_message=str(exc),
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "Email delivery preparation failed",
            extra={
                "delivery_id": str(claim.delivery_id),
                "error_type": type(exc).__name__,
            },
        )
        raise

    # Release the read transaction before provider I/O.
    db.commit()
    try:
        reservation = email_provider_admission_service.reserve_provider_request_slot(
            db,
            provider=prepared.provider,
            # Exact shared credentials use one admission lane across organizations.
            # Distinct keys from the same Resend team still require an explicit
            # shared account identity because the send API exposes no team ID.
            provider_account_id=(f"credential:{prepared.provider_credential_fingerprint}"),
            requests_per_second=settings.RESEND_PROVIDER_REQUESTS_PER_SECOND,
        )
    except Exception as exc:
        logger.error(
            "Email provider admission reservation failed",
            extra={
                "delivery_id": str(claim.delivery_id),
                "error_type": type(exc).__name__,
            },
        )
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=True,
            error_type="provider_admission_unavailable",
            error_message="Provider admission is temporarily unavailable",
        )

    admitted_at = datetime.now(timezone.utc)
    wait_seconds = max(0.0, (reservation.send_at - admitted_at).total_seconds())
    provider_window = timedelta(seconds=MIN_PROVIDER_IO_WINDOW_SECONDS)
    if reservation.send_at + provider_window > prepared.lease_expires_at:
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=True,
            error_type="provider_admission_deferred",
            error_message="Provider admission exceeded the active delivery lease",
            retry_after=timedelta(seconds=max(1, int(wait_seconds) + 1)),
        )
    if wait_seconds:
        await sleeper(wait_seconds)

    if datetime.now(timezone.utc) + provider_window > prepared.lease_expires_at:
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=True,
            error_type="provider_admission_deferred",
            error_message="Delivery lease is too short for provider I/O",
            retry_after=timedelta(seconds=1),
        )
    if datetime.now(timezone.utc) >= prepared.idempotency_expires_at:
        return record_delivery_reconciliation_required(
            db,
            claim=claim,
            error_type="idempotency_window_expired",
            error_message=(
                "Provider idempotency window expired; operator reconciliation is required"
            ),
        )

    try:
        _revalidate_delivery_for_send(db, claim)
    except RecipientSuppressed:
        db.commit()
        return record_delivery_suppressed(db, claim=claim)
    except DeliveryNoLongerEligible as exc:
        db.commit()
        return record_delivery_cancelled(
            db,
            claim=claim,
            reason_type=exc.reason_type,
            reason_message=exc.reason_message,
        )
    except Exception:
        db.rollback()
        raise
    db.commit()

    try:
        result = await resend_transport.send_email(
            api_key=prepared.api_key,
            payload=prepared.payload,
            idempotency_key=prepared.idempotency_key,
        )
    except Exception as exc:
        logger.error(
            "Resend transport raised unexpectedly",
            extra={
                "delivery_id": str(claim.delivery_id),
                "error_type": type(exc).__name__,
            },
        )
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=True,
            error_type="network_error",
            error_message="Provider transport failed",
            provider_outcome_unknown=True,
        )

    if result.ambiguous and not result.retryable:
        return record_delivery_reconciliation_required(
            db,
            claim=claim,
            error_type=result.error_type or "ambiguous_provider_response",
            error_message=result.error or "Provider acceptance could not be confirmed",
            provider_http_status=result.status_code,
        )

    if result.ambiguous:
        return record_delivery_failure(
            db,
            claim=claim,
            retryable=True,
            error_type=result.error_type or "ambiguous_provider_response",
            error_message=result.error or "Provider acceptance could not be confirmed",
            provider_http_status=result.status_code,
            retry_after=(
                timedelta(seconds=result.retry_after_seconds)
                if result.retry_after_seconds is not None
                else None
            ),
            provider_outcome_unknown=True,
        )

    if result.success and result.message_id:
        return record_delivery_success(
            db,
            claim=claim,
            provider_message_id=result.message_id,
        )

    return record_delivery_failure(
        db,
        claim=claim,
        retryable=result.retryable,
        error_type=result.error_type,
        error_message=result.error or "Provider rejected email",
        provider_http_status=result.status_code,
        retry_after=(
            timedelta(seconds=result.retry_after_seconds)
            if result.retry_after_seconds is not None
            else None
        ),
    )


async def dispatch_due_delivery_batch(
    *,
    session_factory: Callable[[], ContextManager[Session]],
    worker_id: str,
    limit: int = 5,
    lease_for: timedelta = timedelta(minutes=2),
) -> DeliveryBatchSummary:
    """Claim a bounded batch, then dispatch every lease concurrently.

    Each provider call receives its own database session. `dispatch_claim`
    closes its read transaction before network I/O and the batch does not claim
    more work until all current leases have resolved.
    """
    if limit < 1 or limit > MAX_DELIVERY_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_DELIVERY_BATCH_SIZE}")
    if lease_for < timedelta(seconds=MIN_DELIVERY_LEASE_SECONDS):
        raise ValueError(f"lease_for must be at least {MIN_DELIVERY_LEASE_SECONDS} seconds")

    with session_factory() as claim_db:
        claims = claim_due_deliveries(
            claim_db,
            worker_id=worker_id,
            lease_for=lease_for,
            limit=limit,
        )
    if not claims:
        return DeliveryBatchSummary()

    async def dispatch_one(claim: DeliveryClaim):
        with session_factory() as delivery_db:
            return await dispatch_claim(delivery_db, claim=claim)

    results = await asyncio.gather(
        *(dispatch_one(claim) for claim in claims),
        return_exceptions=True,
    )
    counts = {
        EmailDeliveryStatus.SENT.value: 0,
        EmailDeliveryStatus.RETRY_SCHEDULED.value: 0,
        EmailDeliveryStatus.FAILED.value: 0,
        EmailDeliveryStatus.CANCELLED.value: 0,
    }
    lease_lost = 0
    unexpected_errors = 0
    for claim, result in zip(claims, results, strict=True):
        if isinstance(result, DeliveryLeaseLost):
            lease_lost += 1
            logger.warning(
                "Email delivery lease was lost before projection",
                extra={"delivery_id": str(claim.delivery_id)},
            )
            continue
        if isinstance(result, BaseException):
            unexpected_errors += 1
            logger.error(
                "Email delivery dispatch failed unexpectedly",
                extra={
                    "delivery_id": str(claim.delivery_id),
                    "error_type": type(result).__name__,
                },
            )
            continue
        counts[result.status] = counts.get(result.status, 0) + 1

    return DeliveryBatchSummary(
        claimed=len(claims),
        sent=counts[EmailDeliveryStatus.SENT.value],
        retry_scheduled=counts[EmailDeliveryStatus.RETRY_SCHEDULED.value],
        failed=counts[EmailDeliveryStatus.FAILED.value],
        cancelled=counts[EmailDeliveryStatus.CANCELLED.value],
        lease_lost=lease_lost,
        unexpected_errors=unexpected_errors,
    )
