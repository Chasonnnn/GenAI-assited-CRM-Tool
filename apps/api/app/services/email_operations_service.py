"""Organization-scoped read models for email operations."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    EmailDelivery,
    EmailDeliveryAttempt,
    EmailLog,
    EmailReconciliationCase,
    ResendSettings,
    ResendWebhookEvent,
)
from app.schemas.email_operations import (
    EmailOperationDelivery,
    EmailOperationDeliveryAttempt,
    EmailOperationMessageDetail,
    EmailOperationMessageListResponse,
    EmailOperationMessageSummary,
    EmailOperationProviderEvent,
    EmailReconciliationCaseListResponse,
    EmailReconciliationCaseSummary,
    EmailReconciliationCounts,
    EmailOperationsReadinessCheck,
    EmailOperationsReadinessResponse,
    EmailOperationsSummary24h,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _encode_cursor(*, created_at: datetime, message_id: UUID) -> str:
    payload = json.dumps(
        {
            "created_at": _as_utc(created_at).isoformat(),
            "id": str(message_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"created_at", "id"}:
            raise ValueError
        if not isinstance(payload["created_at"], str) or not isinstance(payload["id"], str):
            raise ValueError
        created_at = datetime.fromisoformat(payload["created_at"])
        if created_at.tzinfo is None:
            raise ValueError
        return _as_utc(created_at), UUID(payload["id"])
    except (
        binascii.Error,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("Invalid cursor") from exc


def _encode_reconciliation_cursor(*, detected_at: datetime, case_id: UUID) -> str:
    return _encode_cursor(created_at=detected_at, message_id=case_id)


def _decode_reconciliation_cursor(cursor: str) -> tuple[datetime, UUID]:
    return _decode_cursor(cursor)


def _reconciliation_actions(case: EmailReconciliationCase) -> list[str]:
    if case.status != "action_required":
        return []
    if case.case_type == "orphan_webhook":
        actions = ["retry_correlation", "link_event"]
        event_type = (
            case.resend_webhook_event.event_type if case.resend_webhook_event is not None else None
        )
        from app.services.email_reconciliation_service import (
            RECONCILABLE_DELIVERY_EVENT_TYPES,
        )

        if event_type not in RECONCILABLE_DELIVERY_EVENT_TYPES:
            actions.append("dismiss")
        return actions
    return ["confirm_sent", "confirm_not_sent"]


def project_reconciliation_case(
    case: EmailReconciliationCase,
) -> EmailReconciliationCaseSummary:
    event = case.resend_webhook_event
    delivery = case.email_delivery
    next_attempt_at = None
    if delivery is not None and delivery.status in {"pending", "retry_scheduled"}:
        next_attempt_at = delivery.run_at
    return EmailReconciliationCaseSummary(
        id=case.id,
        case_type=case.case_type,
        status=case.status,
        reason_code=case.reason_code,
        version=case.version,
        provider="resend",
        event_type=event.event_type if event else None,
        event_created_at=event.event_created_at if event else None,
        received_at=event.received_at if event else None,
        message_id=(delivery.email_log_id if delivery else event.email_log_id if event else None),
        delivery_id=delivery.id if delivery else None,
        attempt_count=delivery.attempt_count if delivery else None,
        max_attempts=delivery.max_attempts if delivery else None,
        next_attempt_at=next_attempt_at,
        available_actions=_reconciliation_actions(case),
        detected_at=case.detected_at,
        updated_at=case.updated_at,
    )


def list_reconciliation_cases(
    db: Session,
    *,
    organization_id: UUID,
    limit: int,
    cursor: str | None,
    status: str | None,
) -> EmailReconciliationCaseListResponse:
    """List only sanitized, source-linked reconciliation cases for one organization."""
    query = db.query(EmailReconciliationCase).filter(
        EmailReconciliationCase.organization_id == organization_id
    )
    if status == "monitoring":
        query = query.filter(EmailReconciliationCase.status.in_(("pending", "running")))
    elif status:
        query = query.filter(EmailReconciliationCase.status == status)
    if cursor:
        cursor_detected_at, cursor_id = _decode_reconciliation_cursor(cursor)
        query = query.filter(
            or_(
                EmailReconciliationCase.detected_at < cursor_detected_at,
                and_(
                    EmailReconciliationCase.detected_at == cursor_detected_at,
                    EmailReconciliationCase.id < cursor_id,
                ),
            )
        )

    rows = (
        query.order_by(
            EmailReconciliationCase.detected_at.desc(),
            EmailReconciliationCase.id.desc(),
        )
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    next_cursor = None
    if has_more and visible_rows:
        last_case = visible_rows[-1]
        next_cursor = _encode_reconciliation_cursor(
            detected_at=last_case.detected_at,
            case_id=last_case.id,
        )

    count_rows = (
        db.query(
            EmailReconciliationCase.status,
            func.count(EmailReconciliationCase.id),
        )
        .filter(EmailReconciliationCase.organization_id == organization_id)
        .group_by(EmailReconciliationCase.status)
        .all()
    )
    counts_by_status = {row[0]: int(row[1]) for row in count_rows}
    return EmailReconciliationCaseListResponse(
        items=[project_reconciliation_case(case) for case in visible_rows],
        next_cursor=next_cursor,
        counts=EmailReconciliationCounts(
            monitoring=counts_by_status.get("pending", 0) + counts_by_status.get("running", 0),
            action_required=counts_by_status.get("action_required", 0),
            resolved=counts_by_status.get("resolved", 0) + counts_by_status.get("dismissed", 0),
        ),
    )


def _summary_projection(
    message: EmailLog,
    delivery: EmailDelivery | None,
) -> EmailOperationMessageSummary:
    """Project only explicitly approved fields from persisted rows."""
    return EmailOperationMessageSummary(
        id=message.id,
        recipient_email=message.recipient_email,
        subject=message.subject,
        from_email=message.from_email,
        purpose=message.purpose,
        source_type=message.source_type,
        source_id=message.source_id,
        provider=message.provider,
        provider_scope=message.provider_scope,
        provider_account_id=message.provider_account_id,
        # The immutable message row owns its provider identity. Do not infer or
        # backfill it from configuration or from a delivery row.
        provider_message_id=message.external_id,
        status=message.status,
        provider_status=message.resend_status,
        delivery_status=delivery.status if delivery else None,
        attempt_count=delivery.attempt_count if delivery else None,
        max_attempts=delivery.max_attempts if delivery else None,
        created_at=message.created_at,
        sent_at=message.sent_at,
        delivered_at=message.delivered_at,
        bounced_at=message.bounced_at,
        bounce_type=message.bounce_type,
        complained_at=message.complained_at,
        estimated_opened_at=message.opened_at,
        estimated_open_count=message.open_count,
        clicked_at=message.clicked_at,
        click_count=message.click_count,
    )


def list_messages(
    db: Session,
    *,
    organization_id: UUID,
    limit: int,
    cursor: str | None,
) -> EmailOperationMessageListResponse:
    """List one organization's messages using stable descending keyset pagination."""
    query = (
        db.query(EmailLog, EmailDelivery)
        .outerjoin(
            EmailDelivery,
            and_(
                EmailDelivery.organization_id == organization_id,
                EmailDelivery.email_log_id == EmailLog.id,
            ),
        )
        .filter(EmailLog.organization_id == organization_id)
    )
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        query = query.filter(
            or_(
                EmailLog.created_at < cursor_created_at,
                and_(
                    EmailLog.created_at == cursor_created_at,
                    EmailLog.id < cursor_id,
                ),
            )
        )

    rows = query.order_by(EmailLog.created_at.desc(), EmailLog.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    next_cursor = None
    if has_more and visible_rows:
        last_message = visible_rows[-1][0]
        next_cursor = _encode_cursor(
            created_at=last_message.created_at,
            message_id=last_message.id,
        )

    return EmailOperationMessageListResponse(
        items=[_summary_projection(message, delivery) for message, delivery in visible_rows],
        next_cursor=next_cursor,
    )


def get_message(
    db: Session,
    *,
    organization_id: UUID,
    message_id: UUID,
) -> EmailOperationMessageDetail | None:
    """Return one sanitized message detail, or None outside the organization."""
    row = (
        db.query(EmailLog, EmailDelivery)
        .outerjoin(
            EmailDelivery,
            and_(
                EmailDelivery.organization_id == organization_id,
                EmailDelivery.email_log_id == EmailLog.id,
            ),
        )
        .filter(
            EmailLog.organization_id == organization_id,
            EmailLog.id == message_id,
        )
        .one_or_none()
    )
    if row is None:
        return None

    message, delivery = row
    attempts: list[EmailDeliveryAttempt] = []
    if delivery is not None:
        attempts = (
            db.query(EmailDeliveryAttempt)
            .filter(
                EmailDeliveryAttempt.organization_id == organization_id,
                EmailDeliveryAttempt.delivery_id == delivery.id,
            )
            .order_by(
                EmailDeliveryAttempt.attempt_number.asc(),
                EmailDeliveryAttempt.started_at.asc(),
                EmailDeliveryAttempt.id.asc(),
            )
            .all()
        )
    provider_events = (
        db.query(ResendWebhookEvent)
        .filter(
            ResendWebhookEvent.organization_id == organization_id,
            ResendWebhookEvent.email_log_id == message.id,
        )
        .order_by(
            ResendWebhookEvent.event_created_at.asc(),
            ResendWebhookEvent.id.asc(),
        )
        .all()
    )

    summary = _summary_projection(message, delivery)
    return EmailOperationMessageDetail(
        **summary.model_dump(),
        delivery=(
            EmailOperationDelivery(
                id=delivery.id,
                status=delivery.status,
                run_at=delivery.run_at,
                attempt_count=delivery.attempt_count,
                max_attempts=delivery.max_attempts,
                first_attempt_at=delivery.first_attempt_at,
                last_attempt_at=delivery.last_attempt_at,
                completed_at=delivery.completed_at,
                last_error_type=delivery.last_error_type,
                provider_message_id=delivery.provider_message_id,
                created_at=delivery.created_at,
                updated_at=delivery.updated_at,
            )
            if delivery
            else None
        ),
        attempts=[
            EmailOperationDeliveryAttempt(
                id=attempt.id,
                attempt_number=attempt.attempt_number,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
                outcome=attempt.outcome,
                provider_http_status=attempt.provider_http_status,
                error_type=attempt.error_type,
                provider_message_id=attempt.provider_message_id,
                retry_after_seconds=attempt.retry_after_seconds,
            )
            for attempt in attempts
        ],
        provider_events=[
            EmailOperationProviderEvent(
                id=event.id,
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                event_created_at=event.event_created_at,
                received_at=event.received_at,
                processed_at=event.processed_at,
            )
            for event in provider_events
        ],
    )


def _summary_24h(
    db: Session,
    *,
    organization_id: UUID,
    cutoff: datetime,
) -> EmailOperationsSummary24h:
    row = (
        db.query(
            func.count(EmailLog.id).label("messages"),
            func.count(EmailLog.id).filter(EmailLog.status == "pending").label("pending"),
            func.count(EmailLog.id).filter(EmailLog.status == "sent").label("sent"),
            func.count(EmailLog.id).filter(EmailLog.status == "failed").label("failed"),
            func.count(EmailLog.id).filter(EmailLog.delivered_at.is_not(None)).label("delivered"),
            func.count(EmailLog.id).filter(EmailLog.bounced_at.is_not(None)).label("bounced"),
            func.count(EmailLog.id).filter(EmailLog.complained_at.is_not(None)).label("complained"),
            func.coalesce(func.sum(EmailLog.open_count), 0).label("estimated_opens"),
            func.coalesce(func.sum(EmailLog.click_count), 0).label("clicks"),
        )
        .filter(
            EmailLog.organization_id == organization_id,
            EmailLog.created_at >= cutoff,
        )
        .one()
    )
    delivery_attempts = (
        db.query(func.count(EmailDeliveryAttempt.id))
        .filter(
            EmailDeliveryAttempt.organization_id == organization_id,
            EmailDeliveryAttempt.started_at >= cutoff,
        )
        .scalar()
        or 0
    )
    webhook_events = (
        db.query(func.count(ResendWebhookEvent.id))
        .filter(
            ResendWebhookEvent.organization_id == organization_id,
            ResendWebhookEvent.received_at >= cutoff,
        )
        .scalar()
        or 0
    )
    return EmailOperationsSummary24h(
        messages=int(row.messages or 0),
        pending=int(row.pending or 0),
        sent=int(row.sent or 0),
        failed=int(row.failed or 0),
        delivered=int(row.delivered or 0),
        bounced=int(row.bounced or 0),
        complained=int(row.complained or 0),
        estimated_opens=int(row.estimated_opens or 0),
        clicks=int(row.clicks or 0),
        delivery_attempts=int(delivery_attempts),
        webhook_events=int(webhook_events),
    )


def _unknown_check(key: str, detail: str) -> EmailOperationsReadinessCheck:
    return EmailOperationsReadinessCheck(key=key, status="unknown", detail=detail)


def _configured_check(
    *,
    key: str,
    configured: bool,
    pass_detail: str,
    fail_detail: str,
    observed_at: datetime | None = None,
) -> EmailOperationsReadinessCheck:
    return EmailOperationsReadinessCheck(
        key=key,
        status="pass" if configured else "fail",
        detail=pass_detail if configured else fail_detail,
        observed_at=observed_at if configured else None,
    )


def get_readiness(
    db: Session,
    *,
    organization_id: UUID,
    now: datetime | None = None,
) -> EmailOperationsReadinessResponse:
    """Compute readiness solely from persisted configuration and evidence."""
    evaluated_at = _as_utc(now or datetime.now(timezone.utc))
    cutoff = evaluated_at - timedelta(hours=24)
    settings = (
        db.query(ResendSettings)
        .filter(ResendSettings.organization_id == organization_id)
        .one_or_none()
    )
    provider = settings.email_provider if settings else None

    route_evidence = None
    if provider:
        route_evidence = (
            db.query(
                EmailLog.provider,
                EmailLog.provider_scope,
                EmailLog.provider_account_id,
            )
            .filter(
                EmailLog.organization_id == organization_id,
                EmailLog.provider == provider,
                EmailLog.provider_scope.is_not(None),
                EmailLog.provider_account_id.is_not(None),
            )
            .order_by(EmailLog.created_at.desc(), EmailLog.id.desc())
            .first()
        )
    provider_scope = route_evidence.provider_scope if route_evidence else None
    provider_account_id = route_evidence.provider_account_id if route_evidence else None
    summary = _summary_24h(db, organization_id=organization_id, cutoff=cutoff)

    if not provider:
        unconfigured_detail = "No email provider configuration is persisted."
        return EmailOperationsReadinessResponse(
            overall="not_configured",
            can_send=False,
            can_track=False,
            provider=None,
            provider_scope=None,
            provider_account_id=None,
            recent_webhook_activity="unknown",
            last_webhook_received_at=None,
            checks=[
                EmailOperationsReadinessCheck(
                    key="provider_selected",
                    status="fail",
                    detail=unconfigured_detail,
                ),
                _unknown_check("api_key_configured", unconfigured_detail),
                _unknown_check("api_key_validated", unconfigured_detail),
                _unknown_check("sender_configured", unconfigured_detail),
                _unknown_check("domain_verified", unconfigured_detail),
                _unknown_check(
                    "webhook_signing_secret_configured",
                    unconfigured_detail,
                ),
                _unknown_check("recent_webhook_activity", unconfigured_detail),
            ],
            summary_24h=summary,
        )

    if provider != "resend":
        sender_configured = bool(settings and settings.default_sender_user_id)
        not_applicable = "This check does not apply to the selected provider."
        return EmailOperationsReadinessResponse(
            overall="ready" if sender_configured else "needs_attention",
            can_send=sender_configured,
            can_track=False,
            provider=provider,
            provider_scope=provider_scope,
            provider_account_id=provider_account_id,
            recent_webhook_activity="not_applicable",
            last_webhook_received_at=None,
            checks=[
                EmailOperationsReadinessCheck(
                    key="provider_selected",
                    status="pass",
                    detail="An email provider is selected.",
                ),
                EmailOperationsReadinessCheck(
                    key="api_key_configured",
                    status="not_applicable",
                    detail=not_applicable,
                ),
                EmailOperationsReadinessCheck(
                    key="api_key_validated",
                    status="not_applicable",
                    detail=not_applicable,
                ),
                _configured_check(
                    key="sender_configured",
                    configured=sender_configured,
                    pass_detail="A default sender is configured.",
                    fail_detail="A default sender is not configured.",
                ),
                EmailOperationsReadinessCheck(
                    key="domain_verified",
                    status="not_applicable",
                    detail=not_applicable,
                ),
                EmailOperationsReadinessCheck(
                    key="webhook_signing_secret_configured",
                    status="not_applicable",
                    detail=not_applicable,
                ),
                EmailOperationsReadinessCheck(
                    key="recent_webhook_activity",
                    status="not_applicable",
                    detail=not_applicable,
                ),
            ],
            summary_24h=summary,
        )

    assert settings is not None
    api_key_configured = bool(settings.api_key_encrypted)
    api_key_validated = bool(settings.last_key_validated_at)
    sender_configured = bool(settings.from_email)
    domain_verified = bool(settings.verified_domain)
    webhook_secret_configured = bool(settings.webhook_secret_encrypted)
    can_send = all(
        (
            api_key_configured,
            api_key_validated,
            sender_configured,
            domain_verified,
        )
    )
    can_track = domain_verified and webhook_secret_configured

    recent_accepted_messages = (
        db.query(func.count(EmailLog.id))
        .filter(
            EmailLog.organization_id == organization_id,
            EmailLog.provider == "resend",
            EmailLog.external_id.is_not(None),
            EmailLog.created_at >= cutoff,
        )
        .scalar()
        or 0
    )
    latest_webhook_at = (
        db.query(func.max(ResendWebhookEvent.received_at))
        .filter(
            ResendWebhookEvent.organization_id == organization_id,
            ResendWebhookEvent.received_at >= cutoff,
        )
        .scalar()
    )
    if summary.webhook_events:
        activity_check = EmailOperationsReadinessCheck(
            key="recent_webhook_activity",
            status="pass",
            detail="Verified provider webhook activity was received in the last 24 hours.",
            observed_at=latest_webhook_at,
        )
    elif recent_accepted_messages:
        activity_check = EmailOperationsReadinessCheck(
            key="recent_webhook_activity",
            status="fail",
            detail=(
                "Provider messages were accepted in the last 24 hours, but no "
                "verified webhook activity was received."
            ),
        )
    else:
        activity_check = EmailOperationsReadinessCheck(
            key="recent_webhook_activity",
            status="unknown",
            detail=(
                "No recent accepted messages require webhook evidence; activity "
                "cannot yet be evaluated."
            ),
        )

    checks = [
        EmailOperationsReadinessCheck(
            key="provider_selected",
            status="pass",
            detail="Resend is selected as the organization email provider.",
        ),
        _configured_check(
            key="api_key_configured",
            configured=api_key_configured,
            pass_detail="An encrypted Resend API key is stored.",
            fail_detail="No Resend API key is configured.",
        ),
        _configured_check(
            key="api_key_validated",
            configured=api_key_validated,
            pass_detail="The configured API key has persisted validation evidence.",
            fail_detail="The configured API key has no persisted validation evidence.",
            observed_at=settings.last_key_validated_at,
        ),
        _configured_check(
            key="sender_configured",
            configured=sender_configured,
            pass_detail="A sender address is configured.",
            fail_detail="No sender address is configured.",
        ),
        _configured_check(
            key="domain_verified",
            configured=domain_verified,
            pass_detail="A verified sending domain is persisted.",
            fail_detail="No verified sending domain is persisted.",
        ),
        _configured_check(
            key="webhook_signing_secret_configured",
            configured=webhook_secret_configured,
            pass_detail="An encrypted webhook signing secret is stored.",
            fail_detail="No webhook signing secret is configured.",
        ),
        activity_check,
    ]
    overall = (
        "ready" if can_send and can_track and activity_check.status != "fail" else "needs_attention"
    )
    return EmailOperationsReadinessResponse(
        overall=overall,
        can_send=can_send,
        can_track=can_track,
        provider=provider,
        provider_scope=provider_scope,
        provider_account_id=provider_account_id,
        recent_webhook_activity=activity_check.status,
        last_webhook_received_at=latest_webhook_at,
        checks=checks,
        summary_24h=summary,
    )
