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
    TwilioReadinessGate,
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


def credentials_configured(settings: TwilioSettings) -> bool:
    return bool(
        settings.account_sid_encrypted
        and settings.api_key_sid_encrypted
        and settings.api_secret_encrypted
        and settings.auth_token_encrypted
    )


def _organization_blockers(settings: TwilioSettings, purpose: str) -> list[tuple[str, str]]:
    """Organization-level no-send reasons that apply to every route of one purpose."""
    blockers: list[tuple[str, str]] = []
    if not settings.enabled:
        blockers.append(("twilio_disabled", "Twilio messaging is disabled for this organization."))
    if not credentials_configured(settings):
        blockers.append(
            ("twilio_credentials_missing", "Twilio REST and webhook credentials are required.")
        )
    if not settings.legal_messaging_brand:
        blockers.append(("legal_messaging_brand_missing", "The legal messaging brand is required."))
    disclosure = (
        settings.operational_disclosure
        if purpose == "operational"
        else settings.promotional_disclosure
    )
    if not disclosure:
        blockers.append(
            (f"{purpose}_disclosure_missing", f"The {purpose} consent disclosure is required.")
        )
    if not (
        _is_public_https_url(settings.sms_terms_url)
        and _is_public_https_url(settings.privacy_policy_url)
    ):
        blockers.append(
            ("public_legal_urls_missing", "Public HTTPS SMS Terms and Privacy URLs are required.")
        )
    if not settings.support_contact:
        blockers.append(("support_contact_missing", "A messaging support contact is required."))
    if not settings.expected_frequency:
        blockers.append(("expected_frequency_missing", "Expected message frequency is required."))
    if settings.counsel_approved_at is None:
        blockers.append(
            ("counsel_approval_missing", "Counsel approval must be recorded before activation.")
        )
    if not _enabled_env("MESSAGING_DELIVERY_DISPATCH_ENABLED"):
        blockers.append(
            ("messaging_dispatch_worker_disabled", "The messaging dispatch worker is disabled.")
        )
    return blockers


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

    organization = dict(_organization_blockers(settings, route.purpose))
    if "twilio_disabled" in organization:
        block("twilio_disabled", organization["twilio_disabled"])
    if not route.enabled:
        block(f"{route.purpose}_route_disabled", f"The {route.purpose} route is disabled.")
    if "twilio_credentials_missing" in organization:
        block("twilio_credentials_missing", organization["twilio_credentials_missing"])
    if not (route.messaging_service_sid_encrypted and route.sender_phone_encrypted):
        block(
            f"{route.purpose}_route_missing",
            f"The {route.purpose} Messaging Service and sender are required.",
        )
    for code, message in organization.items():
        if code not in {"twilio_disabled", "twilio_credentials_missing"}:
            block(code, message)
    if route.advanced_opt_out_status != "verified":
        block(
            f"{route.purpose}_advanced_opt_out_unverified",
            "Advanced Opt-Out has not been proven by a signed Twilio OptOutType webhook.",
        )
    evidence = route.capability_evidence or {}
    provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
    toll_free = provider.get("sender_type") == "toll_free"
    # Carriers enforce toll-free STOP; SMS START/UNSTOP re-opt is handled locally.
    # Remove this exemption when the platform adopts Consent API toll-free re-opt
    # (supported by Twilio since 2026-08-12).
    if not toll_free and route.consent_management_status != "available":
        block(
            f"{route.purpose}_consent_api_unavailable",
            "Consent Management API access has not been proven by a successful synchronized upsert.",
        )

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
        if toll_free:
            if provider.get("toll_free_verification_status") != "TWILIO_APPROVED":
                block(
                    f"{route.purpose}_toll_free_unverified",
                    "The Twilio Toll-Free Verification is not TWILIO_APPROVED.",
                )
        elif str(provider.get("a2p_status") or "").upper() != "VERIFIED":
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


_PROVIDER_FACTS = (
    "account_active",
    "service_verified",
    "sender_in_pool",
    "sms",
    "inbound_webhook_matches",
    "status_callback_matches",
)
_CONSENT_RECORD_CODES = {
    "legal_messaging_brand_missing",
    "operational_disclosure_missing",
    "public_legal_urls_missing",
    "support_contact_missing",
    "expected_frequency_missing",
}
_ROUTE_PREFIX = {"operational": "Operational", "promotional": "Promotional"}
_SENDER_TYPE_LABEL = {"toll_free": "toll-free", "10dlc": "10DLC"}


def _gate(
    key: str,
    label: str,
    status: str,
    detail: str | None = None,
    route: str | None = None,
) -> TwilioReadinessGate:
    return TwilioReadinessGate(key=key, label=label, status=status, detail=detail, route=route)


def build_readiness_gates(
    settings: TwilioSettings,
    *,
    route_blockers: dict[str, list[tuple[str, str]]],
    snapshot: dict | None,
    credentials_valid: bool,
    account_status: str | None,
) -> list[TwilioReadinessGate]:
    """Project the no-send blockers as one checklist row per launch requirement.

    Rows derive from the same codes that gate sending, so the checklist can never
    disagree with the send path. Unconfigured, disabled promotional routes are omitted.
    """
    organization = dict(_organization_blockers(settings, "operational"))
    gates: list[TwilioReadinessGate] = []
    gates.append(
        _gate(
            "messaging_enabled",
            "Organization messaging",
            "fail" if "twilio_disabled" in organization else "pass",
            organization.get("twilio_disabled"),
        )
    )
    if "twilio_credentials_missing" in organization:
        connection = ("fail", organization["twilio_credentials_missing"])
    elif snapshot is None:
        connection = ("pending", "Not checked for the current settings.")
    elif not credentials_valid:
        connection = ("fail", "The last Twilio check could not sign in with these credentials.")
    else:
        account = twilio_settings_service.mask_credential(settings.account_sid_encrypted)
        connection = ("pass", f"Account {account} is {account_status or 'active'}.")
    gates.append(_gate("connection", "Connection", *connection))
    record_failures = [
        message for code, message in organization.items() if code in _CONSENT_RECORD_CODES
    ]
    gates.append(
        _gate(
            "consent_record",
            "Consent record",
            "fail" if record_failures else "pass",
            record_failures[0] if record_failures else settings.legal_messaging_brand,
        )
    )
    counsel = organization.get("counsel_approval_missing")
    gates.append(
        _gate(
            "counsel_approval",
            "Counsel approval",
            "fail" if counsel else "pass",
            counsel
            or (
                f"Recorded {settings.counsel_approved_at:%Y-%m-%d}"
                if settings.counsel_approved_at
                else None
            ),
        )
    )
    dispatch = organization.get("messaging_dispatch_worker_disabled")
    gates.append(
        _gate(
            "dispatch_worker",
            "Dispatch worker",
            "fail" if dispatch else "pass",
            dispatch or "Delivery jobs run on the worker service.",
        )
    )
    if settings.phi_enabled:
        phi = next(
            (
                message
                for blockers in route_blockers.values()
                for code, message in blockers
                if code == "phi_gate_incomplete"
            ),
            None,
        )
        gates.append(
            _gate("phi_messaging", "PHI messaging", "fail" if phi else "pass", phi or "Approved.")
        )

    for route in sorted(settings.routes, key=lambda item: item.purpose != "operational"):
        purpose = route.purpose
        prefix = _ROUTE_PREFIX[purpose]
        configured = bool(route.messaging_service_sid_encrypted and route.sender_phone_encrypted)
        if purpose == "promotional" and not configured and not route.enabled:
            continue
        if not configured:
            gates.append(
                _gate(
                    f"{purpose}_route",
                    f"{prefix} route",
                    "fail",
                    f"The {purpose} Messaging Service and sender are required.",
                    purpose,
                )
            )
            continue
        codes = dict(route_blockers.get(purpose, []))
        evidence = route.capability_evidence or {}
        provider = evidence.get("provider") if isinstance(evidence.get("provider"), dict) else {}
        sender_type = provider.get("sender_type")
        sender = f"+1•••{route.sender_phone_last4}" if route.sender_phone_last4 else "Sender saved"
        sender_label = _SENDER_TYPE_LABEL.get(str(sender_type))
        disabled = codes.get(f"{purpose}_route_disabled")
        gates.append(
            _gate(
                f"{purpose}_route",
                f"{prefix} route",
                "fail" if disabled else "pass",
                disabled or (f"{sender} · {sender_label}" if sender_label else sender),
                purpose,
            )
        )
        stale = codes.get(f"{purpose}_provider_evidence_stale")
        registration_label = {
            "toll_free": "Toll-free verification",
            "10dlc": "A2P campaign",
        }.get(str(sender_type), "Sender registration")
        registration_failure = codes.get(f"{purpose}_toll_free_unverified") or codes.get(
            f"{purpose}_a2p_unverified"
        )
        if stale:
            registration = ("pending", "Run a readiness check for the current settings.")
        elif registration_failure:
            registration = ("fail", registration_failure)
        elif sender_type == "toll_free":
            registration = ("pass", "Approved by Twilio.")
        else:
            registration = ("pass", "Campaign verified by Twilio.")
        gates.append(
            _gate(f"{purpose}_sender_registration", registration_label, *registration, purpose)
        )
        opt_out = codes.get(f"{purpose}_advanced_opt_out_unverified")
        gates.append(
            _gate(
                f"{purpose}_advanced_opt_out",
                "Advanced Opt-Out",
                "fail" if opt_out else "pass",
                opt_out or "Proven by a signed Twilio opt-out webhook.",
                purpose,
            )
        )
        if sender_type == "toll_free":
            consent_api = ("skipped", "Not required for toll-free senders.")
        elif codes.get(f"{purpose}_consent_api_unavailable"):
            consent_api = ("fail", codes[f"{purpose}_consent_api_unavailable"])
        else:
            consent_api = ("pass", "Synchronized consent upsert succeeded.")
        gates.append(_gate(f"{purpose}_consent_api", "Consent API", *consent_api, purpose))
        fact_failures = [
            codes[f"{purpose}_{fact}_unverified"]
            for fact in _PROVIDER_FACTS
            if f"{purpose}_{fact}_unverified" in codes
        ]
        if stale:
            evidence_gate = ("pending", "Run a readiness check for the current settings.")
        elif fact_failures:
            evidence_gate = ("fail", fact_failures[0])
        else:
            evidence_gate = ("pass", "Account, sender pool, and webhooks verified.")
        gates.append(
            _gate(f"{purpose}_provider_evidence", "Provider evidence", *evidence_gate, purpose)
        )
    return gates


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
            # Toll-free senders and unconfigured routes have no A2P campaign status.
            if provider_evidence.get("a2p_status") is None:
                route.a2p_status = "unconfigured"
            else:
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

    configured_credentials = credentials_configured(settings)
    if not configured_credentials:
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
    route_blockers: dict[str, list[tuple[str, str]]] = {}
    skipped_purposes: set[str] = set()
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
            if (
                route.purpose == "promotional"
                and not route.enabled
                and not route.messaging_service_sid_encrypted
                and not route.sender_phone_encrypted
            ):
                skipped_purposes.add(route.purpose)
                continue
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
        route_blockers[route.purpose] = blockers
        route_issues = [message for _, message in blockers]
        existing_issue_codes = {issue.code for issue in issues}
        for code, message in blockers:
            if code == "twilio_disabled" or code in existing_issue_codes:
                continue
            _append_issue(issues, code=code, message=message, route=route.purpose)
            existing_issue_codes.add(code)
        route_status = (
            "ready" if not blockers else ("not_configured" if not configured else "blocked")
        )
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
            sender_type=provider.get("sender_type"),
            toll_free_verification_status=provider.get("toll_free_verification_status"),
            issues=route_issues,
        )

    if not configured_credentials:
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
    elif any(
        route.status != "ready"
        for purpose, route in route_readiness.items()
        if purpose not in skipped_purposes
    ) or any(issue.severity == "error" for issue in issues):
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
                        ((settings_route.capability_evidence or {}).get("provider") or {}).get(
                            "mms"
                        )
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
        gates=build_readiness_gates(
            settings,
            route_blockers=route_blockers,
            snapshot=snapshot,
            credentials_valid=credentials_valid,
            account_status=account_status,
        ),
    )
