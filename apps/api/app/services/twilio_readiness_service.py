"""Cache-only Twilio readiness projection and fenced no-send refresh."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.models import TwilioSettings
from app.db.models.messaging_delivery import (
    MessageDelivery,
    MessageReconciliationCase,
    MessageWebhookEvent,
)
from app.schemas.twilio import (
    TwilioLocalReadiness,
    TwilioProviderCapabilities,
    TwilioProviderReadiness,
    TwilioQueueReadiness,
    TwilioReadinessIssue,
    TwilioReadinessResponse,
    TwilioReconciliationReadiness,
    TwilioRouteReadiness,
)
from app.services import twilio_provider_service, twilio_settings_service

PROVIDER_EVIDENCE_MAX_AGE = timedelta(hours=24)


def _enabled_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_public_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _append_issue(
    issues: list[TwilioReadinessIssue],
    *,
    code: str,
    message: str,
    route: str | None = None,
) -> None:
    issues.append(
        TwilioReadinessIssue(
            code=code,
            severity="error",
            message=message,
            route=route,
        )
    )


def route_send_blockers(
    settings: TwilioSettings,
    route,
    *,
    requires_mms: bool = False,
    now: datetime | None = None,
) -> list[tuple[str, str]]:
    """Return the authoritative no-send reasons for one purpose-bound route."""
    now = now or datetime.now(UTC)
    blockers: list[tuple[str, str]] = []

    def block(code: str, message: str) -> None:
        blockers.append((code, message))

    if not settings.enabled:
        block("twilio_disabled", "Twilio messaging is disabled for this organization.")
    if not route.enabled:
        block(f"{route.purpose}_route_disabled", f"The {route.purpose} route is disabled.")
    if not (
        settings.account_sid_encrypted
        and settings.api_key_sid_encrypted
        and settings.api_secret_encrypted
        and settings.auth_token_encrypted
    ):
        block("twilio_credentials_missing", "Twilio REST and webhook credentials are required.")
    if not (route.messaging_service_sid_encrypted and route.sender_phone_encrypted):
        block(
            f"{route.purpose}_route_missing",
            f"The {route.purpose} Messaging Service and sender are required.",
        )
    if not settings.legal_messaging_brand:
        block("legal_messaging_brand_missing", "The legal messaging brand is required.")
    disclosure = (
        settings.operational_disclosure
        if route.purpose == "operational"
        else settings.promotional_disclosure
    )
    if not disclosure:
        block(
            f"{route.purpose}_disclosure_missing",
            f"The {route.purpose} consent disclosure is required.",
        )
    if not (
        _is_public_https_url(settings.sms_terms_url)
        and _is_public_https_url(settings.privacy_policy_url)
    ):
        block("public_legal_urls_missing", "Public HTTPS SMS Terms and Privacy URLs are required.")
    if not settings.support_contact:
        block("support_contact_missing", "A messaging support contact is required.")
    if not settings.expected_frequency:
        block("expected_frequency_missing", "Expected message frequency is required.")
    if settings.counsel_approved_at is None:
        block("counsel_approval_missing", "Counsel approval must be recorded before activation.")
    if not _enabled_env("MESSAGING_DELIVERY_DISPATCH_ENABLED"):
        block("messaging_dispatch_worker_disabled", "The messaging dispatch worker is disabled.")
    if route.advanced_opt_out_status != "verified":
        block(
            f"{route.purpose}_advanced_opt_out_unverified",
            "Advanced Opt-Out has not been proven by a signed Twilio OptOutType webhook.",
        )
    if route.consent_management_status != "available":
        block(
            f"{route.purpose}_consent_api_unavailable",
            "Consent Management API access has not been proven by a successful synchronized upsert.",
        )

    evidence = route.capability_evidence or {}
    provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
    checked_at = provider.get("checked_at")
    try:
        checked = datetime.fromisoformat(str(checked_at)) if checked_at else None
        if checked is not None and checked.tzinfo is None:
            checked = checked.replace(tzinfo=UTC)
    except ValueError:
        checked = None
    if (
        checked is None
        or now - checked.astimezone(UTC) > PROVIDER_EVIDENCE_MAX_AGE
        or provider.get("settings_version") != settings.current_version
    ):
        block(
            f"{route.purpose}_provider_evidence_stale",
            "A fresh, version-matched Twilio readiness check is required.",
        )
    else:
        required_provider_facts = {
            "account_active": "The Twilio account is not active.",
            "service_verified": "Messaging Service could not be verified.",
            "sender_in_pool": "The exact sender is not in the Messaging Service sender pool.",
            "sms": "The exact sender is not SMS capable.",
            "inbound_webhook_matches": "The Messaging Service inbound webhook does not match.",
            "status_callback_matches": "The Messaging Service status callback does not match.",
        }
        for fact, message in required_provider_facts.items():
            if provider.get(fact) is not True:
                block(f"{route.purpose}_{fact}_unverified", message)
        if str(provider.get("a2p_status") or "").upper() != "VERIFIED":
            block(
                f"{route.purpose}_a2p_unverified",
                "The Twilio A2P campaign is not VERIFIED.",
            )
        if requires_mms and provider.get("mms") is not True:
            block(f"{route.purpose}_mms_unverified", "The exact sender is not MMS capable.")
        if requires_mms and not app_settings.ATTACHMENT_SCAN_ENABLED:
            block("media_scanning_disabled", "Attachment scanning must be enabled for MMS.")

    if settings.phi_enabled and not (
        settings.twilio_edition and settings.baa_verified_at and settings.compliance_approved_at
    ):
        block(
            "phi_gate_incomplete",
            "PHI messaging requires an eligible Twilio Edition, BAA, and compliance approval.",
        )
    return blockers


def _readiness_snapshot(settings: TwilioSettings) -> dict | None:
    snapshots = [(route.capability_evidence or {}).get("readiness") for route in settings.routes]
    valid = [
        item
        for item in snapshots
        if isinstance(item, dict) and item.get("settings_version") == settings.current_version
    ]
    if not valid:
        return None
    # Both purpose routes receive the same fenced probe. If only one survived a
    # manual edit, use the newest safe snapshot and keep route evidence separate.
    return max(valid, key=lambda item: str(item.get("checked_at") or ""))


def refresh_readiness(
    db: Session,
    *,
    organization_id: uuid.UUID,
    expected_settings_version: int,
) -> bool:
    """Probe Twilio without sending and persist only sanitized, version-fenced evidence."""
    settings = twilio_settings_service.get_settings(db, organization_id)
    if settings is None or settings.current_version != expected_settings_version:
        return False
    result = twilio_provider_service.test_configuration(settings)
    checked_at = datetime.now(UTC).isoformat()
    snapshot = {
        "checked_at": checked_at,
        "settings_version": expected_settings_version,
        "credentials_valid": result.valid,
        "account_status": result.account_status,
        "capabilities": result.capabilities,
        "route_capabilities": result.route_capabilities,
        "error_code": result.error,
        "warning": result.warning,
    }

    # Re-read under lock after provider I/O so a concurrent settings save fences
    # the stale result. No credential, phone, endpoint, or provider prose is stored.
    current = db.execute(
        select(TwilioSettings)
        .where(TwilioSettings.organization_id == organization_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).scalar_one()
    if current.current_version != expected_settings_version:
        db.rollback()
        return False
    for route in current.routes:
        evidence = dict(route.capability_evidence or {})
        evidence["readiness"] = snapshot
        provider_evidence = result.route_capabilities.get(route.purpose)
        if provider_evidence is not None:
            evidence["provider"] = {
                **provider_evidence,
                "account_active": result.account_status == "active",
                "checked_at": checked_at,
                "settings_version": expected_settings_version,
            }
            provider_a2p_status = str(provider_evidence.get("a2p_status") or "").upper()
            route.a2p_status = (
                "approved"
                if provider_a2p_status == "VERIFIED"
                else ("rejected" if provider_a2p_status == "FAILED" else "pending")
            )
        route.capability_evidence = evidence
        route.updated_at = datetime.now(UTC)
    db.commit()
    return True


def _local_queue_readiness(
    db: Session,
    organization_id: uuid.UUID,
) -> TwilioQueueReadiness:
    grouped = dict(
        db.execute(
            select(MessageDelivery.status, func.count(MessageDelivery.id))
            .where(MessageDelivery.organization_id == organization_id)
            .group_by(MessageDelivery.status)
        ).all()
    )
    queued = int(grouped.get("pending", 0)) + int(grouped.get("retry_scheduled", 0))
    processing = int(grouped.get("leased", 0))
    failed = int(grouped.get("failed", 0))
    oldest = db.execute(
        select(func.min(MessageDelivery.run_at)).where(
            MessageDelivery.organization_id == organization_id,
            MessageDelivery.status.in_(("pending", "retry_scheduled")),
        )
    ).scalar_one()
    status = "action_required" if failed else "ready"
    return TwilioQueueReadiness(
        status=status,
        queued_count=queued,
        processing_count=processing,
        failed_count=failed,
        oldest_queued_at=oldest.isoformat() if oldest else None,
    )


def _local_reconciliation_readiness(
    db: Session,
    organization_id: uuid.UUID,
) -> TwilioReconciliationReadiness:
    action_required = db.execute(
        select(func.count(MessageReconciliationCase.id)).where(
            MessageReconciliationCase.organization_id == organization_id,
            MessageReconciliationCase.status.in_(("pending", "running", "action_required")),
        )
    ).scalar_one()
    unresolved_events = db.execute(
        select(func.count(MessageWebhookEvent.id)).where(
            MessageWebhookEvent.organization_id == organization_id,
            MessageWebhookEvent.processed_at.is_(None),
        )
    ).scalar_one()
    last_reconciled = db.execute(
        select(func.max(MessageReconciliationCase.resolved_at)).where(
            MessageReconciliationCase.organization_id == organization_id,
            MessageReconciliationCase.resolved_at.is_not(None),
        )
    ).scalar_one()
    return TwilioReconciliationReadiness(
        status=("action_required" if action_required or unresolved_events else "ready"),
        action_required_count=int(action_required or 0),
        unresolved_event_count=int(unresolved_events or 0),
        last_reconciled_at=(last_reconciled.isoformat() if last_reconciled else None),
    )


def get_readiness(db: Session, organization_id: uuid.UUID) -> TwilioReadinessResponse:
    """Project persisted evidence only; this function never contacts Twilio."""
    settings = twilio_settings_service.get_or_create_settings(db, organization_id)
    issues: list[TwilioReadinessIssue] = []
    if not settings.enabled:
        issues.append(
            TwilioReadinessIssue(
                code="twilio_disabled",
                severity="info",
                message="Twilio messaging is disabled for this organization.",
                route=None,
            )
        )

    credentials_configured = bool(
        settings.account_sid_encrypted
        and settings.api_key_sid_encrypted
        and settings.api_secret_encrypted
        and settings.auth_token_encrypted
    )
    if not credentials_configured:
        issues.append(
            TwilioReadinessIssue(
                code="twilio_credentials_missing",
                severity="error",
                message="Twilio REST and webhook credentials are not fully configured.",
                route=None,
            )
        )

    snapshot = _readiness_snapshot(settings)
    credentials_valid = bool(snapshot and snapshot.get("credentials_valid"))
    checked_at = str(snapshot.get("checked_at")) if snapshot else None
    account_status = (
        str(snapshot.get("account_status")) if snapshot and snapshot.get("account_status") else None
    )
    provider_capability_evidence = snapshot.get("capabilities") if snapshot else {}
    if not isinstance(provider_capability_evidence, dict):
        provider_capability_evidence = {}

    route_readiness: dict = {}
    for route in settings.routes:
        configured = bool(route.messaging_service_sid_encrypted and route.sender_phone_encrypted)
        if not configured:
            route_readiness[route.purpose] = TwilioRouteReadiness(
                status="not_configured",
                can_send_sms=False,
                can_send_mms=False,
                can_receive=False,
                issues=["Messaging Service and sender are not configured."],
            )
            code = f"{route.purpose}_route_missing"
            if code not in {issue.code for issue in issues}:
                _append_issue(
                    issues,
                    code=code,
                    message=f"The {route.purpose} Messaging Service and sender are required.",
                    route=route.purpose,
                )
            continue
        evidence = route.capability_evidence or {}
        provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
        blockers = route_send_blockers(settings, route)
        route_issues = [message for _, message in blockers]
        existing_issue_codes = {issue.code for issue in issues}
        for code, message in blockers:
            if code == "twilio_disabled" or code in existing_issue_codes:
                continue
            _append_issue(issues, code=code, message=message, route=route.purpose)
            existing_issue_codes.add(code)
        route_status = "ready" if not blockers else ("not_configured" if not configured else "blocked")
        route_readiness[route.purpose] = TwilioRouteReadiness(
            status=route_status,
            can_send_sms=route_status == "ready",
            can_send_mms=route_status == "ready" and provider.get("mms") is True,
            can_receive=(
                route.enabled
                and credentials_valid
                and provider.get("sender_in_pool") is True
                and provider.get("inbound_webhook_matches") is True
            ),
            issues=route_issues,
        )

    if not credentials_configured:
        provider_status = "not_configured"
    elif snapshot is None:
        provider_status = "unknown"
    elif credentials_valid:
        provider_status = "ready"
    else:
        provider_status = "blocked"
        issues.append(
            TwilioReadinessIssue(
                code="twilio_provider_check_failed",
                severity="error",
                message="The last no-send Twilio provider check failed.",
                route=None,
            )
        )

    queue = _local_queue_readiness(db, organization_id)
    reconciliation = _local_reconciliation_readiness(db, organization_id)
    if not settings.enabled:
        overall_status = "not_configured"
    elif provider_status != "ready":
        overall_status = provider_status
    elif any(route.status != "ready" for route in route_readiness.values()) or any(
        issue.severity == "error" for issue in issues
    ):
        overall_status = "blocked"
    elif queue.status != "ready" or reconciliation.status != "ready":
        overall_status = "action_required"
    else:
        overall_status = "ready"

    return TwilioReadinessResponse(
        overall_status=overall_status,
        checked_at=checked_at,
        provider=TwilioProviderReadiness(
            status=provider_status,
            credentials_valid=credentials_valid,
            account_status=account_status,
            checked_at=checked_at,
            capabilities=TwilioProviderCapabilities(
                send_sms=any(route.can_send_sms for route in route_readiness.values()),
                send_mms=any(route.can_send_mms for route in route_readiness.values()),
                receive_sms=any(route.can_receive for route in route_readiness.values()),
                receive_mms=any(
                    route.can_receive
                    and (
                        ((settings_route.capability_evidence or {}).get("provider") or {}).get("mms")
                        is True
                    )
                    for settings_route in settings.routes
                    for route in [route_readiness[settings_route.purpose]]
                ),
                status_callbacks=credentials_valid
                and bool(provider_capability_evidence.get("webhook_validation")),
            ),
            routes=route_readiness,
        ),
        local=TwilioLocalReadiness(
            queue=queue,
            reconciliation=reconciliation,
        ),
        issues=issues,
    )
