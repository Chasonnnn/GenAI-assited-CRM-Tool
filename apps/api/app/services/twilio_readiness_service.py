"""Cache-only Twilio readiness projection and fenced no-send refresh."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
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


def _append_activation_issues(
    settings: TwilioSettings,
    issues: list[TwilioReadinessIssue],
) -> None:
    if not settings.enabled:
        return
    if not settings.legal_messaging_brand:
        _append_issue(
            issues,
            code="legal_messaging_brand_missing",
            message="The organization's legal messaging brand is required.",
        )
    if not settings.operational_disclosure or not settings.promotional_disclosure:
        _append_issue(
            issues,
            code="messaging_disclosures_missing",
            message="Counsel-approved operational and promotional disclosures are required.",
        )
    if not (
        _is_public_https_url(settings.sms_terms_url)
        and _is_public_https_url(settings.privacy_policy_url)
    ):
        _append_issue(
            issues,
            code="public_legal_urls_missing",
            message="Public HTTPS SMS Terms and Privacy URLs are required.",
        )
    if not settings.support_contact:
        _append_issue(
            issues,
            code="support_contact_missing",
            message="A messaging support contact is required.",
        )
    if not settings.expected_frequency:
        _append_issue(
            issues,
            code="expected_frequency_missing",
            message="Expected message frequency is required.",
        )
    if settings.counsel_approved_at is None:
        _append_issue(
            issues,
            code="counsel_approval_missing",
            message="Counsel approval must be recorded before activation.",
        )
    if not _enabled_env("MESSAGING_DELIVERY_DISPATCH_ENABLED"):
        _append_issue(
            issues,
            code="messaging_dispatch_worker_disabled",
            message="The durable messaging dispatch worker is disabled.",
        )
    if not app_settings.ATTACHMENT_SCAN_ENABLED:
        _append_issue(
            issues,
            code="media_scanning_disabled",
            message="Attachment scanning must be enabled for MMS.",
        )
    if settings.phi_enabled and not (
        settings.twilio_edition and settings.baa_verified_at and settings.compliance_approved_at
    ):
        _append_issue(
            issues,
            code="phi_gate_incomplete",
            message="PHI messaging requires an eligible Twilio Edition, BAA, and compliance approval.",
        )


def _readiness_snapshot(settings: TwilioSettings) -> dict | None:
    snapshots = [(route.capability_evidence or {}).get("readiness") for route in settings.routes]
    valid = [item for item in snapshots if isinstance(item, dict)]
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

    _append_activation_issues(settings, issues)

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
            issues.append(
                TwilioReadinessIssue(
                    code=f"{route.purpose}_route_missing",
                    severity="error",
                    message=f"The {route.purpose} Messaging Service and sender are required.",
                    route=route.purpose,
                )
            )
            continue

        route_issues: list[str] = []
        if route.a2p_status != "approved":
            route_issues.append("A2P registration is not approved.")
        if route.advanced_opt_out_status != "verified":
            route_issues.append("Advanced Opt-Out is not verified.")
        if route.consent_management_status != "available":
            route_issues.append("Consent Management API access is not verified.")
            _append_issue(
                issues,
                code=f"{route.purpose}_consent_api_unavailable",
                message=f"Consent Management API access is required for the {route.purpose} route.",
                route=route.purpose,
            )
        evidence = route.capability_evidence or {}
        if evidence.get("sender_type") != "10dlc":
            route_issues.append("The exact sender is not verified as US 10DLC.")
            _append_issue(
                issues,
                code=f"{route.purpose}_sender_not_10dlc",
                message=f"The {route.purpose} sender must be a registered US 10DLC number.",
                route=route.purpose,
            )
        if evidence.get("mms") is not True:
            route_issues.append("MMS capability is not verified.")
            _append_issue(
                issues,
                code=f"{route.purpose}_mms_unverified",
                message=f"MMS capability is required for the {route.purpose} route.",
                route=route.purpose,
            )
        if route.purpose == "operational" and evidence.get("meta_consent_mapping_verified") is not True:
            route_issues.append("Meta consent mapping is not verified.")
            _append_issue(
                issues,
                code="meta_consent_mapping_unverified",
                message="Meta form consent mappings must be verified before activation.",
                route=route.purpose,
            )
        if snapshot is None:
            route_issues.append("Provider readiness has not been checked.")
        elif not credentials_valid:
            route_issues.append("Provider credentials or Messaging Service validation failed.")
        route_status = (
            "ready" if not route_issues and route.enabled and settings.enabled else "blocked"
        )
        route_readiness[route.purpose] = TwilioRouteReadiness(
            status=route_status,
            can_send_sms=route_status == "ready",
            can_send_mms=route_status == "ready"
            and bool((route.capability_evidence or {}).get("mms")),
            can_receive=route.enabled and credentials_valid,
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
                send_sms=credentials_valid,
                send_mms=credentials_valid
                and any(
                    bool((route.capability_evidence or {}).get("mms")) for route in settings.routes
                ),
                receive_sms=credentials_valid,
                receive_mms=credentials_valid
                and any(
                    bool((route.capability_evidence or {}).get("mms")) for route in settings.routes
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
