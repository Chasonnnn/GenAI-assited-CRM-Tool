"""Transactional creation and delivery primitives for outbound email."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping, Sequence
from uuid import UUID, uuid4

from sqlalchemy import and_, case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import (
    EmailDeliveryAttemptOutcome,
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderScope,
    EmailSuppressionPolicy,
    EmailStatus,
)
from app.db.models import (
    AppointmentEmailLog,
    Attachment,
    EmailDelivery,
    EmailDeliveryAttempt,
    EmailLog,
    EmailLogAttachment,
)
from app.services.resend_tags import (
    merge_resend_correlation_tags,
    validate_resend_tags,
)


class DeliveryRoute(str, Enum):
    """Supported durable delivery routes."""

    PLATFORM_RESEND = "platform_resend"
    ORGANIZATION_RESEND = "organization_resend"


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """Exact provider-facing email content captured before queueing."""

    recipient_email: str
    subject: str
    html: str
    text: str | None
    from_email: str
    reply_to_email: str | None = None
    headers: Mapping[str, str] | None = None
    safe_tags: tuple[Mapping[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class EmailSource:
    """Application object that caused an email to be queued."""

    source_type: str
    source_id: UUID | None = None
    template_id: UUID | None = None
    surrogate_id: UUID | None = None
    actor_user_id: UUID | None = None
    job_id: UUID | None = None
    purpose: str = "transactional"
    suppression_policy: EmailSuppressionPolicy = EmailSuppressionPolicy.ENFORCE_ALL


@dataclass(frozen=True, slots=True)
class QueuedEmail:
    """Result of an idempotent queue operation."""

    email_log: EmailLog
    delivery: EmailDelivery | None
    created: bool


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    """Fenced lease handed to one delivery worker."""

    delivery_id: UUID
    organization_id: UUID
    email_log_id: UUID
    lease_token: UUID
    lease_owner: str
    attempt_number: int
    lease_expires_at: datetime


class EmailDeliveryConflict(ValueError):
    """An idempotency key was reused with different immutable content."""


class DeliveryLeaseLost(RuntimeError):
    """A stale worker attempted to mutate a delivery after its lease changed."""


RESEND_IDEMPOTENCY_WINDOW = timedelta(hours=24)
_RECONCILIATION_ERROR = "Provider idempotency window expired; operator reconciliation is required"
_PROVIDER_OUTCOME_UNKNOWN_ERROR = (
    "Provider outcome remains unknown after the final safe retry; "
    "operator reconciliation is required"
)
_LEASE_EXPIRED_RECONCILIATION_ERROR = (
    "Delivery lease expired after the final attempt; provider outcome is unknown "
    "and operator reconciliation is required"
)
_UNSUBSCRIBE_TOKEN_RE = re.compile(r"(?<=/email/unsubscribe/)[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_RESEND_STATUS_RANK = {
    "scheduled": 5,
    "sent": 10,
    "delivery_delayed": 20,
    "delivered": 30,
    "failed": 40,
    "suppressed": 50,
    "bounced": 60,
    "complained": 70,
}


def _mark_reconciliation_required(
    db: Session,
    delivery: EmailDelivery,
    *,
    completed_at: datetime,
    error_type: str = "idempotency_window_expired",
    error_message: str = _RECONCILIATION_ERROR,
) -> None:
    """Stop automatic sends when provider acceptance cannot be resolved safely."""
    delivery.status = EmailDeliveryStatus.RECONCILIATION_REQUIRED.value
    delivery.completed_at = completed_at
    delivery.last_error_type = error_type
    delivery.last_error = error_message
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    delivery.email_log.status = EmailStatus.PENDING.value
    delivery.email_log.error = error_message
    from app.services import email_reconciliation_service

    email_reconciliation_service.ensure_unknown_delivery_case(
        db,
        delivery=delivery,
        error_type=error_type,
        detected_at=completed_at,
    )


def _assert_provider_message_identity(
    delivery: EmailDelivery,
    provider_message_id: str,
) -> None:
    """Reject divergent provider identities before mutating a fenced delivery."""
    for current_provider_message_id in (
        delivery.provider_message_id,
        delivery.email_log.external_id,
    ):
        if current_provider_message_id not in {None, provider_message_id}:
            raise EmailDeliveryConflict(
                "provider message id conflicts with the verified delivery identity"
            )


def _merge_provider_acceptance(
    email_log: EmailLog,
    *,
    provider_message_id: str,
    accepted_at: datetime,
) -> bool:
    """Merge provider acceptance without regressing later webhook evidence."""
    current_rank = _RESEND_STATUS_RANK.get(email_log.resend_status or "", 0)
    acceptance_rank = _RESEND_STATUS_RANK["sent"]
    email_log.external_id = provider_message_id
    email_log.sent_at = (
        accepted_at
        if email_log.sent_at is None or accepted_at < email_log.sent_at
        else email_log.sent_at
    )
    if current_rank > acceptance_rank:
        return False

    email_log.status = EmailStatus.SENT.value
    email_log.error = None
    if current_rank < acceptance_rank or email_log.resend_status_at is None:
        email_log.resend_status = "sent"
        email_log.resend_status_at = accepted_at
    return True


def _resolve_verified_provider_acceptance(
    db: Session,
    *,
    delivery: EmailDelivery,
    resolved_at: datetime,
    project_source: bool,
) -> bool:
    """Make signed provider identity authoritative over local retry outcomes."""
    provider_message_id = delivery.provider_message_id
    if provider_message_id is None:
        return False

    _assert_provider_message_identity(delivery, provider_message_id)
    delivery.status = EmailDeliveryStatus.SENT.value
    delivery.completed_at = resolved_at
    delivery.last_error_type = None
    delivery.last_error = None
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None

    email_log = delivery.email_log
    acceptance_is_canonical = _merge_provider_acceptance(
        email_log,
        provider_message_id=provider_message_id,
        accepted_at=email_log.resend_status_at or resolved_at,
    )
    if project_source and acceptance_is_canonical:
        _project_source_delivery(
            db,
            email_log=email_log,
            status=EmailStatus.SENT.value,
            provider_message_id=provider_message_id,
            occurred_at=resolved_at,
        )
    return True


def resolve_reconciliation_by_operator(
    db: Session,
    *,
    delivery: EmailDelivery,
    outcome: str,
    provider_message_id: str | None,
    resolved_at: datetime,
) -> None:
    """Project explicit operator evidence without making a provider request."""
    if delivery.status != EmailDeliveryStatus.RECONCILIATION_REQUIRED.value:
        raise EmailDeliveryConflict("delivery is no longer awaiting reconciliation")

    if outcome == "confirm_sent":
        normalized_provider_message_id = (provider_message_id or "").strip()
        if not normalized_provider_message_id:
            raise EmailDeliveryConflict(
                "provider_message_id is required when confirming provider acceptance"
            )
        _assert_provider_message_identity(delivery, normalized_provider_message_id)
        delivery.provider_message_id = normalized_provider_message_id
        if not _resolve_verified_provider_acceptance(
            db,
            delivery=delivery,
            resolved_at=resolved_at,
            project_source=True,
        ):
            raise EmailDeliveryConflict("provider acceptance could not be projected")
        return

    if outcome != "confirm_not_sent":
        raise EmailDeliveryConflict("unsupported operator reconciliation outcome")
    if provider_message_id is not None and provider_message_id.strip():
        raise EmailDeliveryConflict(
            "provider_message_id is not allowed when confirming no provider acceptance"
        )

    email_log = delivery.email_log
    if (
        delivery.provider_message_id is not None
        or email_log.external_id is not None
        or email_log.resend_status is not None
        or email_log.resend_status_at is not None
    ):
        raise EmailDeliveryConflict(
            "verified provider evidence conflicts with a not-sent resolution"
        )

    controlled_error = "Operator confirmed provider did not accept this delivery"
    delivery.status = EmailDeliveryStatus.FAILED.value
    delivery.completed_at = resolved_at
    delivery.last_error_type = "operator_confirmed_not_sent"
    delivery.last_error = controlled_error
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    email_log.status = EmailStatus.FAILED.value
    email_log.error = controlled_error
    _project_source_delivery(
        db,
        email_log=email_log,
        status=EmailStatus.FAILED.value,
        error=controlled_error,
        occurred_at=resolved_at,
    )


def lock_delivery_for_verified_webhook(
    db: Session,
    *,
    organization_id: UUID,
    email_log_id: UUID,
) -> EmailDelivery | None:
    """Lock the tenant-scoped outbox row before a signed webhook binds identity."""
    query = select(EmailDelivery).where(
        EmailDelivery.organization_id == organization_id,
        EmailDelivery.email_log_id == email_log_id,
    )
    bind = db.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        query = query.with_for_update()
    return db.execute(query).scalar_one_or_none()


def merge_verified_webhook_identity(
    *,
    delivery: EmailDelivery | None,
    email_log: EmailLog,
    provider_message_id: str,
    event_created_at: datetime,
) -> None:
    """Bind signed provider identity and resolve delivery states safe from retries."""
    normalized_provider_message_id = provider_message_id.strip()
    if not normalized_provider_message_id:
        raise ValueError("provider_message_id is required")
    if delivery is not None:
        if (
            delivery.organization_id != email_log.organization_id
            or delivery.email_log_id != email_log.id
        ):
            raise EmailDeliveryConflict("provider message id target is outside the delivery tenant")
        _assert_provider_message_identity(delivery, normalized_provider_message_id)
        delivery.provider_message_id = normalized_provider_message_id
        if delivery.status in {
            EmailDeliveryStatus.PENDING.value,
            EmailDeliveryStatus.RETRY_SCHEDULED.value,
            EmailDeliveryStatus.FAILED.value,
            EmailDeliveryStatus.RECONCILIATION_REQUIRED.value,
        }:
            delivery.status = EmailDeliveryStatus.SENT.value
            delivery.completed_at = event_created_at
            delivery.last_error_type = None
            delivery.last_error = None
            delivery.lease_token = None
            delivery.lease_owner = None
            delivery.lease_expires_at = None
    elif email_log.external_id not in {None, normalized_provider_message_id}:
        raise EmailDeliveryConflict(
            "provider message id conflicts with the verified email identity"
        )

    email_log.external_id = normalized_provider_message_id
    current_rank = _RESEND_STATUS_RANK.get(email_log.resend_status or "", 0)
    if current_rank <= _RESEND_STATUS_RANK["sent"]:
        email_log.status = EmailStatus.SENT.value
        email_log.error = None
        email_log.sent_at = (
            event_created_at
            if email_log.sent_at is None or event_created_at < email_log.sent_at
            else email_log.sent_at
        )


def _route_scope(route: DeliveryRoute) -> EmailProviderScope:
    if route is DeliveryRoute.PLATFORM_RESEND:
        return EmailProviderScope.PLATFORM
    return EmailProviderScope.ORGANIZATION


def _canonical_payload(
    *,
    route: DeliveryRoute,
    provider_account_id: str,
    rendered_email: RenderedEmail,
    source: EmailSource,
    attachment_manifest: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    return {
        "route": route.value,
        "provider_account_id": provider_account_id,
        "recipient_email": rendered_email.recipient_email.strip().lower(),
        "subject": rendered_email.subject,
        "html": rendered_email.html,
        "text": rendered_email.text,
        "from_email": rendered_email.from_email,
        "reply_to_email": rendered_email.reply_to_email,
        "headers": dict(rendered_email.headers or {}),
        "safe_tags": [dict(tag) for tag in rendered_email.safe_tags],
        "attachment_manifest": [dict(item) for item in attachment_manifest],
        "source_type": source.source_type,
        "source_id": str(source.source_id) if source.source_id else None,
        "template_id": str(source.template_id) if source.template_id else None,
        "surrogate_id": str(source.surrogate_id) if source.surrogate_id else None,
        "actor_user_id": str(source.actor_user_id) if source.actor_user_id else None,
        "job_id": str(source.job_id) if source.job_id else None,
        "purpose": source.purpose,
        "suppression_policy": source.suppression_policy.value,
    }


def _capture_attachment_manifest(
    db: Session,
    *,
    organization_id: UUID,
    attachments: Sequence[Attachment],
) -> tuple[list[Attachment], list[dict[str, object]]]:
    """Lock current attachment metadata and preserve caller-selected order."""
    ordered_ids = list(dict.fromkeys(attachment.id for attachment in attachments))
    if not ordered_ids:
        return [], []

    query = (
        select(Attachment)
        .where(
            Attachment.organization_id == organization_id,
            Attachment.id.in_(ordered_ids),
        )
        .execution_options(populate_existing=True)
    )
    bind = db.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        query = query.with_for_update()
    current_by_id = {attachment.id: attachment for attachment in db.execute(query).scalars()}
    if set(current_by_id) != set(ordered_ids):
        raise ValueError("One or more email attachments are unavailable")

    ordered: list[Attachment] = []
    manifest: list[dict[str, object]] = []
    for attachment_id in ordered_ids:
        attachment = current_by_id[attachment_id]
        if (
            attachment.deleted_at is not None
            or attachment.quarantined
            or attachment.scan_status != "clean"
        ):
            raise ValueError("One or more email attachments are unavailable")
        if attachment.file_size < 0 or not re.fullmatch(
            r"[0-9a-fA-F]{64}", attachment.checksum_sha256 or ""
        ):
            raise ValueError("One or more email attachments have invalid integrity metadata")
        ordered.append(attachment)
        manifest.append(
            {
                "attachment_id": str(attachment.id),
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size_bytes": int(attachment.file_size),
                "sha256": attachment.checksum_sha256.lower(),
            }
        )
    return ordered, manifest


def _fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_volatile_unsubscribe_tokens(value: object) -> object:
    """Ignore token timestamps when comparing retries of one logical email."""
    if isinstance(value, str):
        return _UNSUBSCRIBE_TOKEN_RE.sub("{unsubscribe-token}", value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_volatile_unsubscribe_tokens(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_volatile_unsubscribe_tokens(item) for item in value]
    return value


def stored_request_fingerprint_matches(delivery: EmailDelivery) -> bool:
    """Verify the persisted provider request still matches its immutable digest."""
    email_log = delivery.email_log
    try:
        if delivery.provider_scope == EmailProviderScope.PLATFORM.value:
            route = DeliveryRoute.PLATFORM_RESEND
        elif delivery.provider_scope == EmailProviderScope.ORGANIZATION.value:
            route = DeliveryRoute.ORGANIZATION_RESEND
        else:
            return False
        if not email_log.source_type or not email_log.from_email:
            return False
        payload = _canonical_payload(
            route=route,
            provider_account_id=delivery.provider_account_id,
            rendered_email=RenderedEmail(
                recipient_email=email_log.recipient_email,
                subject=email_log.subject,
                html=email_log.body,
                text=email_log.text_body,
                from_email=email_log.from_email,
                reply_to_email=email_log.reply_to_email,
                headers=email_log.headers,
                safe_tags=tuple(email_log.safe_tags),
            ),
            source=EmailSource(
                source_type=email_log.source_type,
                source_id=email_log.source_id,
                template_id=email_log.template_id,
                surrogate_id=email_log.surrogate_id,
                actor_user_id=email_log.actor_user_id,
                job_id=email_log.job_id,
                purpose=email_log.purpose or "transactional",
                suppression_policy=EmailSuppressionPolicy(email_log.suppression_policy),
            ),
            attachment_manifest=email_log.attachment_manifest,
        )
    except (TypeError, ValueError):
        return False
    return _fingerprint(payload) == delivery.request_fingerprint


def _validate_queue_input(
    *,
    provider_account_id: str,
    idempotency_key: str,
    rendered_email: RenderedEmail,
    source: EmailSource,
) -> None:
    if not provider_account_id.strip():
        raise ValueError("provider_account_id is required")
    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    if len(idempotency_key) > 256:
        raise ValueError("idempotency_key must be 256 characters or fewer")
    if not rendered_email.recipient_email.strip():
        raise ValueError("recipient_email is required")
    if not rendered_email.subject.strip():
        raise ValueError("subject is required")
    if not rendered_email.html.strip():
        raise ValueError("html is required")
    if not rendered_email.from_email.strip():
        raise ValueError("from_email is required")
    if not source.source_type.strip():
        raise ValueError("source_type is required")
    validate_resend_tags(rendered_email.safe_tags)


def _existing_queue_result(
    *,
    organization_id: UUID,
    provider_account_id: str,
    content_fingerprint: str,
    email_log: EmailLog,
) -> QueuedEmail:
    if (
        email_log.organization_id != organization_id
        or email_log.provider != EmailProvider.RESEND.value
        or email_log.provider_account_id != provider_account_id
        or email_log.content_fingerprint != content_fingerprint
    ):
        raise EmailDeliveryConflict("idempotency key is already bound to a different email payload")
    return QueuedEmail(
        email_log=email_log,
        delivery=email_log.delivery,
        created=False,
    )


def queue_rendered_email(
    db: Session,
    *,
    organization_id: UUID,
    route: DeliveryRoute,
    provider_account_id: str,
    rendered_email: RenderedEmail,
    idempotency_key: str,
    source: EmailSource,
    attachments: Sequence[Attachment] = (),
    schedule_at: datetime | None = None,
    max_attempts: int = 5,
    commit: bool = False,
) -> QueuedEmail:
    """Persist one immutable message and its delivery in the caller transaction."""
    _validate_queue_input(
        provider_account_id=provider_account_id,
        idempotency_key=idempotency_key,
        rendered_email=rendered_email,
        source=source,
    )
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    ordered_attachments, attachment_manifest = _capture_attachment_manifest(
        db,
        organization_id=organization_id,
        attachments=attachments,
    )
    canonical_payload = _canonical_payload(
        route=route,
        provider_account_id=provider_account_id,
        rendered_email=rendered_email,
        source=source,
        attachment_manifest=attachment_manifest,
    )
    logical_payload = _normalize_volatile_unsubscribe_tokens(canonical_payload)
    if not isinstance(logical_payload, Mapping):
        raise TypeError("canonical email payload must be a mapping")
    content_fingerprint = _fingerprint(logical_payload)

    existing_log = (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == organization_id,
            EmailLog.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing_log is not None:
        return _existing_queue_result(
            organization_id=organization_id,
            provider_account_id=provider_account_id,
            content_fingerprint=content_fingerprint,
            email_log=existing_log,
        )

    existing = (
        db.query(EmailDelivery)
        .filter(
            EmailDelivery.provider == EmailProvider.RESEND.value,
            EmailDelivery.provider_account_id == provider_account_id,
            EmailDelivery.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing is not None:
        if (
            existing.organization_id != organization_id
            or existing.email_log.content_fingerprint != content_fingerprint
        ):
            raise EmailDeliveryConflict(
                "idempotency key is already bound to a different email payload"
            )
        return QueuedEmail(
            email_log=existing.email_log,
            delivery=existing,
            created=False,
        )

    provider_scope = _route_scope(route)
    from app.services import email_service

    is_suppressed = email_service.is_email_suppressed(
        db,
        organization_id,
        rendered_email.recipient_email,
        ignore_opt_out=(source.suppression_policy is EmailSuppressionPolicy.ALLOW_OPT_OUT),
    )
    email_log_id = uuid4()
    provider_tags = merge_resend_correlation_tags(
        rendered_email.safe_tags,
        organization_id=organization_id,
        email_log_id=email_log_id,
    )
    provider_payload = _canonical_payload(
        route=route,
        provider_account_id=provider_account_id,
        rendered_email=replace(rendered_email, safe_tags=provider_tags),
        source=source,
        attachment_manifest=attachment_manifest,
    )
    request_fingerprint = _fingerprint(provider_payload)
    email_log = EmailLog(
        id=email_log_id,
        organization_id=organization_id,
        template_id=source.template_id,
        surrogate_id=source.surrogate_id,
        actor_user_id=source.actor_user_id,
        job_id=source.job_id,
        recipient_email=rendered_email.recipient_email.strip().lower(),
        subject=rendered_email.subject,
        body=rendered_email.html,
        text_body=rendered_email.text,
        from_email=rendered_email.from_email,
        reply_to_email=rendered_email.reply_to_email,
        headers=dict(rendered_email.headers or {}),
        safe_tags=[dict(tag) for tag in provider_tags],
        attachment_manifest=attachment_manifest,
        content_fingerprint=content_fingerprint,
        purpose=source.purpose,
        suppression_policy=source.suppression_policy.value,
        source_type=source.source_type,
        source_id=source.source_id,
        provider=EmailProvider.RESEND.value,
        provider_scope=provider_scope.value,
        provider_account_id=provider_account_id,
        idempotency_key=idempotency_key,
        status=EmailStatus.SKIPPED.value if is_suppressed else EmailStatus.PENDING.value,
        error="suppressed" if is_suppressed else None,
    )
    delivery: EmailDelivery | None = None
    try:
        with db.begin_nested():
            db.add(email_log)
            db.flush()

            for attachment in ordered_attachments:
                email_log.attachment_links.append(
                    EmailLogAttachment(
                        organization_id=organization_id,
                        attachment_id=attachment.id,
                    )
                )
            if ordered_attachments:
                db.flush()

            if not is_suppressed:
                delivery = EmailDelivery(
                    organization_id=organization_id,
                    email_log_id=email_log.id,
                    provider=EmailProvider.RESEND.value,
                    provider_scope=provider_scope.value,
                    provider_account_id=provider_account_id,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                    status=EmailDeliveryStatus.PENDING.value,
                    run_at=schedule_at or datetime.now(timezone.utc),
                    max_attempts=max_attempts,
                )
                db.add(delivery)
                db.flush()
    except IntegrityError:
        db.expire_all()
        concurrent_log = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == organization_id,
                EmailLog.idempotency_key == idempotency_key,
            )
            .first()
        )
        if concurrent_log is None:
            raise
        result = _existing_queue_result(
            organization_id=organization_id,
            provider_account_id=provider_account_id,
            content_fingerprint=content_fingerprint,
            email_log=concurrent_log,
        )
        if commit:
            db.commit()
        return result

    if commit:
        db.commit()
        db.refresh(email_log)
        if delivery is not None:
            db.refresh(delivery)

    return QueuedEmail(email_log=email_log, delivery=delivery, created=True)


def _locked_appointment_email_projection_target(
    db: Session,
    *,
    email_log: EmailLog,
) -> AppointmentEmailLog | None:
    if email_log.source_type != "appointment_email":
        return None

    query = select(AppointmentEmailLog).where(
        AppointmentEmailLog.organization_id == email_log.organization_id,
        AppointmentEmailLog.id == email_log.source_id,
        AppointmentEmailLog.email_log_id == email_log.id,
    )
    bind = db.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        query = query.with_for_update()
    appointment_log = db.execute(query).scalar_one_or_none()
    if appointment_log is None:
        raise RuntimeError("Appointment email projection target is missing")
    return appointment_log


def _project_appointment_email_delivery(
    db: Session,
    *,
    email_log: EmailLog,
    status: str,
    provider_message_id: str | None = None,
    error: str | None = None,
    occurred_at: datetime,
) -> bool:
    """Project a canonical delivery outcome onto its appointment audit row."""
    appointment_log = _locked_appointment_email_projection_target(
        db,
        email_log=email_log,
    )
    if appointment_log is None:
        return False

    appointment_log.status = status
    appointment_log.external_message_id = (
        provider_message_id if status == EmailStatus.SENT.value else None
    )
    appointment_log.sent_at = occurred_at if status == EmailStatus.SENT.value else None
    appointment_log.error = error
    return True


def project_appointment_email_canonical_state(
    db: Session,
    *,
    email_log: EmailLog,
) -> bool:
    """Mirror a webhook-updated canonical message onto appointment history."""
    appointment_log = _locked_appointment_email_projection_target(
        db,
        email_log=email_log,
    )
    if appointment_log is None:
        return False

    appointment_log.status = email_log.status
    appointment_log.external_message_id = email_log.external_id
    appointment_log.sent_at = email_log.sent_at
    appointment_log.error = email_log.error
    return True


def claim_due_deliveries(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    lease_for: timedelta,
    limit: int = 10,
) -> list[DeliveryClaim]:
    """Claim due or expired deliveries and durably commit their fencing leases."""
    if not worker_id.strip():
        raise ValueError("worker_id is required")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if lease_for.total_seconds() <= 0:
        raise ValueError("lease_for must be positive")

    claimed_at = now or datetime.now(timezone.utc)
    eligible = or_(
        and_(
            EmailDelivery.status.in_(
                (
                    EmailDeliveryStatus.PENDING.value,
                    EmailDeliveryStatus.RETRY_SCHEDULED.value,
                )
            ),
            EmailDelivery.run_at <= claimed_at,
        ),
        and_(
            EmailDelivery.status == EmailDeliveryStatus.LEASED.value,
            EmailDelivery.lease_expires_at.is_not(None),
            EmailDelivery.lease_expires_at <= claimed_at,
        ),
    )
    bulk_priority = case(
        (EmailLog.purpose.in_(("campaign", "marketing")), 1),
        else_=0,
    )
    query = (
        select(EmailDelivery)
        .join(EmailLog, EmailLog.id == EmailDelivery.email_log_id)
        .where(eligible)
        .order_by(bulk_priority, EmailDelivery.run_at, EmailDelivery.id)
        .limit(limit)
    )
    bind = db.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    deliveries = list(db.execute(query).scalars())
    if not deliveries:
        db.commit()
        return []

    claims: list[DeliveryClaim] = []
    lease_expires_at = claimed_at + lease_for
    for delivery in deliveries:
        stale_attempt = None
        if delivery.status == EmailDeliveryStatus.LEASED.value:
            stale_attempt = (
                db.query(EmailDeliveryAttempt)
                .filter(
                    EmailDeliveryAttempt.delivery_id == delivery.id,
                    EmailDeliveryAttempt.lease_token == delivery.lease_token,
                    EmailDeliveryAttempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
                )
                .one_or_none()
            )
            if delivery.provider_message_id is not None:
                if stale_attempt is not None:
                    stale_attempt.outcome = EmailDeliveryAttemptOutcome.LEASE_EXPIRED.value
                    stale_attempt.completed_at = claimed_at
                _resolve_verified_provider_acceptance(
                    db,
                    delivery=delivery,
                    resolved_at=claimed_at,
                    project_source=False,
                )
                continue

        if (
            delivery.idempotency_expires_at is not None
            and delivery.idempotency_expires_at <= claimed_at
        ):
            if stale_attempt is not None:
                stale_attempt.outcome = EmailDeliveryAttemptOutcome.LEASE_EXPIRED.value
                stale_attempt.completed_at = claimed_at
            _mark_reconciliation_required(db, delivery, completed_at=claimed_at)
            _project_appointment_email_delivery(
                db,
                email_log=delivery.email_log,
                status=EmailStatus.PENDING.value,
                error=delivery.last_error,
                occurred_at=claimed_at,
            )
            continue

        if delivery.status == EmailDeliveryStatus.LEASED.value:
            if stale_attempt is not None:
                stale_attempt.outcome = EmailDeliveryAttemptOutcome.LEASE_EXPIRED.value
                stale_attempt.completed_at = claimed_at
            if delivery.attempt_count >= delivery.max_attempts:
                _mark_reconciliation_required(
                    db,
                    delivery,
                    completed_at=claimed_at,
                    error_type="lease_expired",
                    error_message=_LEASE_EXPIRED_RECONCILIATION_ERROR,
                )
                _project_appointment_email_delivery(
                    db,
                    email_log=delivery.email_log,
                    status=EmailStatus.PENDING.value,
                    error=_LEASE_EXPIRED_RECONCILIATION_ERROR,
                    occurred_at=claimed_at,
                )
                continue

        lease_token = uuid4()
        attempt_number = delivery.attempt_count + 1
        delivery.status = EmailDeliveryStatus.LEASED.value
        delivery.attempt_count = attempt_number
        delivery.lease_token = lease_token
        delivery.lease_owner = worker_id
        delivery.lease_expires_at = lease_expires_at
        delivery.first_attempt_at = delivery.first_attempt_at or claimed_at
        delivery.last_attempt_at = claimed_at
        delivery.idempotency_expires_at = (
            delivery.idempotency_expires_at or claimed_at + RESEND_IDEMPOTENCY_WINDOW
        )

        db.add(
            EmailDeliveryAttempt(
                organization_id=delivery.organization_id,
                delivery_id=delivery.id,
                attempt_number=attempt_number,
                lease_token=lease_token,
                started_at=claimed_at,
                outcome=EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
            )
        )
        claims.append(
            DeliveryClaim(
                delivery_id=delivery.id,
                organization_id=delivery.organization_id,
                email_log_id=delivery.email_log_id,
                lease_token=lease_token,
                lease_owner=worker_id,
                attempt_number=attempt_number,
                lease_expires_at=lease_expires_at,
            )
        )

    db.commit()
    return claims


def _locked_delivery_for_claim(
    db: Session,
    claim: DeliveryClaim,
) -> EmailDelivery:
    query = select(EmailDelivery).where(
        EmailDelivery.id == claim.delivery_id,
        EmailDelivery.organization_id == claim.organization_id,
    )
    bind = db.get_bind()
    if getattr(bind, "dialect", None) and bind.dialect.name == "postgresql":
        query = query.with_for_update()
    delivery = db.execute(query).scalar_one_or_none()
    if (
        delivery is None
        or delivery.status != EmailDeliveryStatus.LEASED.value
        or delivery.lease_token != claim.lease_token
    ):
        raise DeliveryLeaseLost("delivery lease is no longer owned by this worker")
    return delivery


def _prelock_campaign_source_for_claim(
    db: Session,
    claim: DeliveryClaim,
) -> None:
    """Honor the run -> campaign -> delivery lock order for campaign sends."""
    from app.services import campaign_service

    campaign_service.lock_campaign_run_for_email_log(
        db,
        organization_id=claim.organization_id,
        email_log_id=claim.email_log_id,
    )


def _project_source_delivery(
    db: Session,
    *,
    email_log: EmailLog,
    status: str,
    provider_message_id: str | None = None,
    error: str | None = None,
    occurred_at: datetime,
) -> None:
    _project_appointment_email_delivery(
        db,
        email_log=email_log,
        status=status,
        provider_message_id=provider_message_id,
        error=error,
        occurred_at=occurred_at,
    )

    if email_log.source_type == "campaign_recipient":
        from app.services import campaign_service

        projected = campaign_service.project_campaign_recipient_delivery(
            db,
            organization_id=email_log.organization_id,
            email_log_id=email_log.id,
            status=status,
            provider_message_id=provider_message_id,
            error=error,
            occurred_at=occurred_at,
            commit=False,
        )
        if not projected:
            raise RuntimeError("Campaign recipient projection target is missing")

    if status == EmailStatus.SENT.value and email_log.surrogate_id is not None:
        from app.services import email_service

        email_service.log_surrogate_email_send_success(
            db=db,
            org_id=email_log.organization_id,
            surrogate_id=email_log.surrogate_id,
            email_log_id=email_log.id,
            subject=email_log.subject,
            provider=EmailProvider.RESEND.value,
            template_id=email_log.template_id,
            actor_user_id=email_log.actor_user_id,
            attachments=email_service.list_email_log_attachments(
                db=db,
                org_id=email_log.organization_id,
                email_log_id=email_log.id,
            ),
            commit=False,
        )


def record_delivery_success(
    db: Session,
    *,
    claim: DeliveryClaim,
    provider_message_id: str,
    now: datetime | None = None,
) -> EmailDelivery:
    """Atomically project provider acceptance through the current fencing token."""
    if not provider_message_id.strip():
        raise ValueError("provider_message_id is required")
    completed_at = now or datetime.now(timezone.utc)
    _prelock_campaign_source_for_claim(db, claim)
    delivery = _locked_delivery_for_claim(db, claim)
    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(
            EmailDeliveryAttempt.delivery_id == delivery.id,
            EmailDeliveryAttempt.lease_token == claim.lease_token,
            EmailDeliveryAttempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
        )
        .one_or_none()
    )
    if attempt is None:
        raise DeliveryLeaseLost("delivery attempt is no longer active")

    _assert_provider_message_identity(delivery, provider_message_id)
    attempt.outcome = EmailDeliveryAttemptOutcome.SUCCEEDED.value
    attempt.completed_at = completed_at
    attempt.provider_message_id = provider_message_id

    delivery.status = EmailDeliveryStatus.SENT.value
    delivery.provider_message_id = provider_message_id
    delivery.completed_at = completed_at
    delivery.last_error_type = None
    delivery.last_error = None
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None

    email_log = delivery.email_log
    acceptance_is_canonical = _merge_provider_acceptance(
        email_log,
        provider_message_id=provider_message_id,
        accepted_at=completed_at,
    )
    if acceptance_is_canonical:
        _project_source_delivery(
            db,
            email_log=email_log,
            status=EmailStatus.SENT.value,
            provider_message_id=provider_message_id,
            occurred_at=completed_at,
        )
    db.commit()
    db.refresh(delivery)
    return delivery


def record_delivery_cancelled(
    db: Session,
    *,
    claim: DeliveryClaim,
    reason_type: str,
    reason_message: str,
    now: datetime | None = None,
) -> EmailDelivery:
    """Atomically cancel an active delivery through its fencing token."""
    safe_reason_type = _safe_error(reason_type, limit=100)
    safe_reason_message = _safe_error(reason_message, limit=1000)
    if not safe_reason_type or not safe_reason_message:
        raise ValueError("cancellation reason is required")
    completed_at = now or datetime.now(timezone.utc)
    _prelock_campaign_source_for_claim(db, claim)
    delivery = _locked_delivery_for_claim(db, claim)
    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(
            EmailDeliveryAttempt.delivery_id == delivery.id,
            EmailDeliveryAttempt.lease_token == claim.lease_token,
            EmailDeliveryAttempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
        )
        .one_or_none()
    )
    if attempt is None:
        raise DeliveryLeaseLost("delivery attempt is no longer active")

    attempt.outcome = EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    attempt.completed_at = completed_at
    attempt.error_type = safe_reason_type
    attempt.error_message = safe_reason_message

    delivery.status = EmailDeliveryStatus.CANCELLED.value
    delivery.completed_at = completed_at
    delivery.last_error_type = safe_reason_type
    delivery.last_error = safe_reason_message
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None

    email_log = delivery.email_log
    email_log.status = EmailStatus.SKIPPED.value
    email_log.error = safe_reason_message

    _project_source_delivery(
        db,
        email_log=email_log,
        status=EmailStatus.SKIPPED.value,
        error=safe_reason_message,
        occurred_at=completed_at,
    )
    db.commit()
    db.refresh(delivery)
    return delivery


def record_delivery_suppressed(
    db: Session,
    *,
    claim: DeliveryClaim,
    now: datetime | None = None,
) -> EmailDelivery:
    """Cancel an active delivery when suppression is discovered before send."""
    return record_delivery_cancelled(
        db,
        claim=claim,
        reason_type="suppressed",
        reason_message="suppressed",
        now=now,
    )


def renew_delivery_lease(
    db: Session,
    *,
    claim: DeliveryClaim,
    lease_for: timedelta,
    now: datetime | None = None,
) -> DeliveryClaim:
    """Extend an active lease without changing its fencing token."""
    if lease_for.total_seconds() <= 0:
        raise ValueError("lease_for must be positive")
    renewed_at = now or datetime.now(timezone.utc)
    delivery = _locked_delivery_for_claim(db, claim)
    if delivery.lease_expires_at is None or delivery.lease_expires_at <= renewed_at:
        raise DeliveryLeaseLost("delivery lease has already expired")

    lease_expires_at = renewed_at + lease_for
    delivery.lease_expires_at = lease_expires_at
    db.commit()
    return replace(claim, lease_expires_at=lease_expires_at)


_EMAIL_IN_DIAGNOSTIC = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_IN_DIAGNOSTIC = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"
)


def _safe_error(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    redacted = _EMAIL_IN_DIAGNOSTIC.sub("[redacted-email]", value)
    redacted = _PHONE_IN_DIAGNOSTIC.sub("[redacted-phone]", redacted)
    normalized = " ".join(redacted.split())
    return normalized[:limit] or None


def _retry_delay(
    *,
    attempt_number: int,
    retry_after: timedelta | None,
) -> timedelta:
    if retry_after is not None:
        seconds = max(1, int(retry_after.total_seconds()))
        return timedelta(seconds=seconds)
    seconds = min(3600, 30 * (2 ** max(attempt_number - 1, 0)))
    return timedelta(seconds=seconds)


def record_delivery_reconciliation_required(
    db: Session,
    *,
    claim: DeliveryClaim,
    error_type: str,
    error_message: str,
    provider_http_status: int | None = None,
    now: datetime | None = None,
) -> EmailDelivery:
    """Fence an unresolved provider outcome against all automatic retries."""
    completed_at = now or datetime.now(timezone.utc)
    _prelock_campaign_source_for_claim(db, claim)
    delivery = _locked_delivery_for_claim(db, claim)
    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(
            EmailDeliveryAttempt.delivery_id == delivery.id,
            EmailDeliveryAttempt.lease_token == claim.lease_token,
            EmailDeliveryAttempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
        )
        .one_or_none()
    )
    if attempt is None:
        raise DeliveryLeaseLost("delivery attempt is no longer active")

    safe_error_type = _safe_error(error_type, limit=100)
    safe_error_message = _safe_error(error_message, limit=1000)
    if not safe_error_type or not safe_error_message:
        raise ValueError("reconciliation reason is required")

    attempt.completed_at = completed_at
    attempt.outcome = EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    attempt.provider_http_status = provider_http_status
    attempt.error_type = safe_error_type
    attempt.error_message = safe_error_message
    provider_acceptance_verified = _resolve_verified_provider_acceptance(
        db,
        delivery=delivery,
        resolved_at=completed_at,
        project_source=True,
    )
    if not provider_acceptance_verified:
        _mark_reconciliation_required(
            db,
            delivery,
            completed_at=completed_at,
            error_type=safe_error_type,
            error_message=safe_error_message,
        )
        _project_appointment_email_delivery(
            db,
            email_log=delivery.email_log,
            status=EmailStatus.PENDING.value,
            error=safe_error_message,
            occurred_at=completed_at,
        )

    db.commit()
    db.refresh(delivery)
    return delivery


def record_delivery_failure(
    db: Session,
    *,
    claim: DeliveryClaim,
    retryable: bool,
    error_type: str | None,
    error_message: str | None,
    provider_http_status: int | None = None,
    retry_after: timedelta | None = None,
    provider_outcome_unknown: bool = False,
    now: datetime | None = None,
) -> EmailDelivery:
    """Finish the active attempt and either retry or dead-letter the message."""
    failed_at = now or datetime.now(timezone.utc)
    _prelock_campaign_source_for_claim(db, claim)
    delivery = _locked_delivery_for_claim(db, claim)
    attempt = (
        db.query(EmailDeliveryAttempt)
        .filter(
            EmailDeliveryAttempt.delivery_id == delivery.id,
            EmailDeliveryAttempt.lease_token == claim.lease_token,
            EmailDeliveryAttempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value,
        )
        .one_or_none()
    )
    if attempt is None:
        raise DeliveryLeaseLost("delivery attempt is no longer active")

    safe_error_type = _safe_error(error_type, limit=100)
    safe_error_message = _safe_error(error_message, limit=1000)
    if delivery.provider_message_id is not None:
        attempt.completed_at = failed_at
        attempt.outcome = EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
        attempt.provider_http_status = provider_http_status
        attempt.error_type = safe_error_type
        attempt.error_message = safe_error_message
        _resolve_verified_provider_acceptance(
            db,
            delivery=delivery,
            resolved_at=failed_at,
            project_source=True,
        )
        db.commit()
        db.refresh(delivery)
        return delivery

    can_retry = retryable and delivery.attempt_count < delivery.max_attempts
    retry_delay = (
        _retry_delay(
            attempt_number=delivery.attempt_count,
            retry_after=retry_after,
        )
        if can_retry
        else None
    )
    idempotency_window_expired = bool(
        retry_delay is not None
        and delivery.idempotency_expires_at is not None
        and failed_at + retry_delay >= delivery.idempotency_expires_at
    )

    attempt.completed_at = failed_at
    attempt.outcome = (
        EmailDeliveryAttemptOutcome.RETRYABLE_ERROR.value
        if can_retry and not idempotency_window_expired
        else EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
    )
    attempt.provider_http_status = provider_http_status
    attempt.error_type = safe_error_type
    attempt.error_message = safe_error_message

    delivery.last_error_type = safe_error_type
    delivery.last_error = safe_error_message
    delivery.lease_token = None
    delivery.lease_owner = None
    delivery.lease_expires_at = None
    email_log = delivery.email_log
    email_log.error = safe_error_message

    if can_retry and not idempotency_window_expired:
        assert retry_delay is not None
        attempt.retry_after_seconds = int(retry_delay.total_seconds())
        delivery.status = EmailDeliveryStatus.RETRY_SCHEDULED.value
        delivery.run_at = failed_at + retry_delay
        email_log.status = EmailStatus.PENDING.value
    elif idempotency_window_expired:
        _mark_reconciliation_required(db, delivery, completed_at=failed_at)
        _project_appointment_email_delivery(
            db,
            email_log=email_log,
            status=EmailStatus.PENDING.value,
            error=delivery.last_error,
            occurred_at=failed_at,
        )
    elif provider_outcome_unknown:
        _mark_reconciliation_required(
            db,
            delivery,
            completed_at=failed_at,
            error_type="provider_outcome_unknown",
            error_message=_PROVIDER_OUTCOME_UNKNOWN_ERROR,
        )
        _project_appointment_email_delivery(
            db,
            email_log=email_log,
            status=EmailStatus.PENDING.value,
            error=delivery.last_error,
            occurred_at=failed_at,
        )
    else:
        delivery.status = EmailDeliveryStatus.FAILED.value
        delivery.completed_at = failed_at
        email_log.status = EmailStatus.FAILED.value
        _project_source_delivery(
            db,
            email_log=email_log,
            status=EmailStatus.FAILED.value,
            error=safe_error_message,
            occurred_at=failed_at,
        )

    db.commit()
    db.refresh(delivery)
    return delivery
