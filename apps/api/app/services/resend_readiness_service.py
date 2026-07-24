"""Live, read-only Resend readiness probes with sanitized persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parseaddr
import hashlib
import json
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    PlatformEmailTemplate,
    PlatformSystemEmailTemplate,
    ResendSettings,
)
from app.services import (
    resend_control_plane,
    resend_event_contract,
    resend_readiness_snapshot_service,
    resend_settings_service,
)


@dataclass(frozen=True, slots=True)
class ReadinessRefreshResult:
    """Internal worker result; only the sanitized probe is persisted."""

    probe: resend_readiness_snapshot_service.ReadinessProbeResult
    persisted: bool
    retry_after_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class _RouteConfiguration:
    organization_id: UUID | None
    provider_account_id: str
    provider_enabled: bool
    api_key: str = field(repr=False)
    required_domains: tuple[str, ...]
    sender_domains: tuple[str, ...]
    missing_sender_count: int
    expected_webhook_endpoint: str
    has_local_signing_secret: bool
    fingerprint: str


def _secret_digest(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def _fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _email_domain(value: str | None) -> str | None:
    address = parseaddr((value or "").strip())[1]
    if "@" not in address:
        return None
    domain = address.rsplit("@", 1)[1].strip().lower().rstrip(".")
    return domain or None


def _resolve_organization_configuration(
    db: Session,
    *,
    organization_id: UUID,
) -> _RouteConfiguration:
    row = (
        db.query(ResendSettings)
        .filter(ResendSettings.organization_id == organization_id)
        .one_or_none()
    )
    if row is None:
        fingerprint = _fingerprint(
            {
                "provider_scope": "organization",
                "provider_account_id": f"organization:{organization_id}",
                "email_provider": None,
            }
        )
        return _RouteConfiguration(
            organization_id=organization_id,
            provider_account_id=f"organization:{organization_id}",
            provider_enabled=False,
            api_key="",
            required_domains=(),
            sender_domains=(),
            missing_sender_count=1,
            expected_webhook_endpoint="",
            has_local_signing_secret=False,
            fingerprint=fingerprint,
        )

    api_key = ""
    if row.email_provider == "resend" and row.api_key_encrypted:
        try:
            api_key = resend_settings_service.decrypt_api_key(row.api_key_encrypted)
        except Exception:
            api_key = ""
    verified_domain = (row.verified_domain or "").strip().lower().rstrip(".")
    from_domain = _email_domain(row.from_email)
    endpoint = resend_settings_service.get_webhook_url(row.webhook_id)
    has_local_signing_secret = False
    if row.webhook_secret_encrypted:
        try:
            has_local_signing_secret = bool(
                resend_settings_service.decrypt_api_key(row.webhook_secret_encrypted).strip()
            )
        except Exception:
            has_local_signing_secret = False
    required_domains = tuple(sorted({domain for domain in (verified_domain,) if domain}))
    fingerprint = _fingerprint(
        {
            "provider_scope": "organization",
            "provider_account_id": f"organization:{organization_id}",
            "email_provider": row.email_provider,
            "api_key_digest": _secret_digest(row.api_key_encrypted),
            "verified_domain": verified_domain or None,
            "from_domain": from_domain,
            "webhook_endpoint": endpoint or None,
            "webhook_secret_digest": _secret_digest(row.webhook_secret_encrypted),
        }
    )
    return _RouteConfiguration(
        organization_id=organization_id,
        provider_account_id=f"organization:{organization_id}",
        provider_enabled=row.email_provider == "resend",
        api_key=api_key,
        required_domains=required_domains,
        sender_domains=tuple(domain for domain in (from_domain,) if domain),
        missing_sender_count=0 if from_domain else 1,
        expected_webhook_endpoint=endpoint,
        has_local_signing_secret=has_local_signing_secret,
        fingerprint=fingerprint,
    )


def _platform_webhook_endpoint() -> str:
    base_url = (settings.API_BASE_URL or settings.FRONTEND_URL or "").strip()
    if not base_url:
        return ""
    return f"{base_url.rstrip('/')}/webhooks/resend/platform"


def _resolve_platform_configuration(db: Session) -> _RouteConfiguration:
    fallback_from = (settings.PLATFORM_EMAIL_FROM or "").strip()
    effective_from_headers: list[str] = []
    if fallback_from:
        effective_from_headers.append(fallback_from)

    active_system_templates = (
        db.query(PlatformSystemEmailTemplate)
        .filter(PlatformSystemEmailTemplate.is_active.is_(True))
        .all()
    )
    for template in active_system_templates:
        effective_from_headers.append((template.from_email or "").strip() or fallback_from)

    published_templates = (
        db.query(PlatformEmailTemplate).filter(PlatformEmailTemplate.published_version > 0).all()
    )
    for template in published_templates:
        effective_from_headers.append(
            (template.published_from_email or "").strip() or fallback_from
        )

    sender_domains = tuple(
        sorted(
            {
                domain
                for from_header in effective_from_headers
                if (domain := _email_domain(from_header)) is not None
            }
        )
    )
    missing_sender_count = sum(
        _email_domain(from_header) is None for from_header in effective_from_headers
    )
    if not effective_from_headers:
        missing_sender_count = 1

    api_key = (settings.PLATFORM_RESEND_API_KEY.get_secret_value() or "").strip()
    webhook_secret = (settings.PLATFORM_RESEND_WEBHOOK_SECRET.get_secret_value() or "").strip()
    endpoint = _platform_webhook_endpoint()
    fingerprint = _fingerprint(
        {
            "provider_scope": "platform",
            "provider_account_id": "platform:default",
            "api_key_digest": _secret_digest(api_key),
            "sender_domains": sender_domains,
            "missing_sender_count": missing_sender_count,
            "webhook_endpoint": endpoint or None,
            "webhook_secret_digest": _secret_digest(webhook_secret),
        }
    )
    return _RouteConfiguration(
        organization_id=None,
        provider_account_id="platform:default",
        provider_enabled=True,
        api_key=api_key,
        required_domains=sender_domains,
        sender_domains=sender_domains,
        missing_sender_count=missing_sender_count,
        expected_webhook_endpoint=endpoint,
        has_local_signing_secret=bool(webhook_secret),
        fingerprint=fingerprint,
    )


def _provider_failure_probe(
    *,
    configuration: _RouteConfiguration,
    started_at: datetime,
    result: resend_control_plane.ResendControlPlaneResult,
) -> resend_readiness_snapshot_service.ReadinessProbeResult:
    checked_at = datetime.now(timezone.utc)
    if result.status is resend_control_plane.ResendControlPlaneStatus.LIMITED:
        probe_status = "limited"
        overall_status = "limited"
        capability_status = "limited"
        issue_code = "limited_visibility"
    elif result.status is resend_control_plane.ResendControlPlaneStatus.FAIL:
        probe_status = "failed"
        overall_status = "needs_attention"
        capability_status = "unknown"
        issue_code = "credential_rejected"
    else:
        probe_status = "failed"
        overall_status = "unknown"
        capability_status = "unknown"
        if result.reason is resend_control_plane.ResendControlPlaneReason.TIMEOUT:
            issue_code = "timeout"
        elif result.reason is resend_control_plane.ResendControlPlaneReason.ADMISSION_UNAVAILABLE:
            issue_code = "admission_unavailable"
        elif result.reason is resend_control_plane.ResendControlPlaneReason.INVALID_RESPONSE:
            issue_code = "invalid_provider_response"
        else:
            issue_code = "provider_unavailable"
    return resend_readiness_snapshot_service.ReadinessProbeResult(
        config_fingerprint=configuration.fingerprint,
        probe_started_at=started_at,
        checked_at=checked_at,
        probe_status=probe_status,
        overall_status=overall_status,
        domain_status=capability_status,
        webhook_status=capability_status,
        sending_status=capability_status,
        delivery_tracking_status=capability_status,
        engagement_tracking_status=capability_status,
        verified_domain_count=0,
        enabled_webhook_count=0,
        issue_codes=(issue_code,),
    )


def _local_configuration_probe(
    *,
    configuration: _RouteConfiguration,
    configured: bool,
) -> resend_readiness_snapshot_service.ReadinessProbeResult:
    checked_at = datetime.now(timezone.utc)
    status = "unknown" if configured else "not_configured"
    return resend_readiness_snapshot_service.ReadinessProbeResult(
        config_fingerprint=configuration.fingerprint,
        probe_started_at=checked_at,
        checked_at=checked_at,
        probe_status="failed" if configured else "succeeded",
        overall_status="needs_attention" if configured else "not_configured",
        domain_status=status,
        webhook_status=status,
        sending_status=status,
        delivery_tracking_status=status,
        engagement_tracking_status=status,
        verified_domain_count=0,
        enabled_webhook_count=0,
        issue_codes=("credential_unavailable",) if configured else (),
    )


async def _probe_configuration(
    db: Session,
    *,
    configuration: _RouteConfiguration,
    control_plane_client_factory: Callable[..., object] = (
        resend_control_plane.ResendControlPlaneClient
    ),
) -> tuple[resend_readiness_snapshot_service.ReadinessProbeResult, int | None]:
    started_at = datetime.now(timezone.utc)
    client = control_plane_client_factory(
        db=db,
        api_key=configuration.api_key,
        provider_account_id=configuration.provider_account_id,
    )
    domains_result = await client.list_domains()
    if (
        domains_result.status is not resend_control_plane.ResendControlPlaneStatus.OK
        or domains_result.value is None
    ):
        return (
            _provider_failure_probe(
                configuration=configuration,
                started_at=started_at,
                result=domains_result,
            ),
            domains_result.retry_after_seconds,
        )

    listed_by_name = {domain.name: domain for domain in domains_result.value}
    details = []
    for domain_name in configuration.required_domains:
        listed = listed_by_name.get(domain_name)
        if listed is None:
            continue
        detail_result = await client.get_domain(listed.id)
        if (
            detail_result.status is not resend_control_plane.ResendControlPlaneStatus.OK
            or detail_result.value is None
        ):
            return (
                _provider_failure_probe(
                    configuration=configuration,
                    started_at=started_at,
                    result=detail_result,
                ),
                detail_result.retry_after_seconds,
            )
        details.append(detail_result.value)

    if configuration.expected_webhook_endpoint:
        webhook_result = await client.list_webhooks(
            expected_endpoint=configuration.expected_webhook_endpoint
        )
        if (
            webhook_result.status is not resend_control_plane.ResendControlPlaneStatus.OK
            or webhook_result.value is None
        ):
            return (
                _provider_failure_probe(
                    configuration=configuration,
                    started_at=started_at,
                    result=webhook_result,
                ),
                webhook_result.retry_after_seconds,
            )
        webhooks = webhook_result.value
    else:
        webhooks = ()

    domain_ready = bool(configuration.required_domains) and len(details) == len(
        configuration.required_domains
    )
    domain_ready = domain_ready and all(
        detail.spf_status == "verified" and detail.dkim_status == "verified" for detail in details
    )
    sending_ready = (
        domain_ready
        and configuration.missing_sender_count == 0
        and bool(configuration.sender_domains)
        and set(configuration.sender_domains).issubset(configuration.required_domains)
        and all(detail.sending == "enabled" for detail in details)
    )
    endpoint_webhooks = tuple(webhook for webhook in webhooks if webhook.endpoint_matches)
    matching_webhooks = tuple(
        webhook for webhook in endpoint_webhooks if webhook.status == "enabled"
    )
    webhook_ready = bool(matching_webhooks)
    tracking_base_ready = webhook_ready and configuration.has_local_signing_secret
    available_events = frozenset(event for webhook in matching_webhooks for event in webhook.events)
    delivery_events = (
        resend_event_contract.RESEND_OUTBOUND_READINESS_EVENT_TYPES
        - resend_event_contract.RESEND_ENGAGEMENT_EVENT_TYPES
    )
    delivery_ready = tracking_base_ready and delivery_events.issubset(available_events)
    engagement_ready = (
        tracking_base_ready
        and resend_event_contract.RESEND_ENGAGEMENT_EVENT_TYPES.issubset(available_events)
        and all(
            detail.open_tracking is True and detail.click_tracking is True for detail in details
        )
    )
    statuses = (
        domain_ready,
        webhook_ready,
        sending_ready,
        delivery_ready,
        engagement_ready,
    )
    issue_codes: list[str] = []
    if not domain_ready:
        issue_codes.append("domain_not_verified")
    elif not sending_ready:
        issue_codes.append("sending_disabled")
    if not webhook_ready:
        issue_codes.append(
            "webhook_disabled"
            if any(webhook.status == "disabled" for webhook in endpoint_webhooks)
            else "webhook_missing"
        )
    elif not configuration.has_local_signing_secret:
        issue_codes.append("webhook_missing")
    elif tracking_base_ready:
        if not delivery_ready:
            issue_codes.append("delivery_events_missing")
        if not engagement_ready:
            issue_codes.append("engagement_events_missing")
    checked_at = datetime.now(timezone.utc)
    probe = resend_readiness_snapshot_service.ReadinessProbeResult(
        config_fingerprint=configuration.fingerprint,
        probe_started_at=started_at,
        checked_at=checked_at,
        probe_status="succeeded",
        overall_status="ready" if all(statuses) else "needs_attention",
        domain_status="ready" if domain_ready else "needs_attention",
        webhook_status="ready" if webhook_ready else "needs_attention",
        sending_status="ready" if sending_ready else "needs_attention",
        delivery_tracking_status="ready" if delivery_ready else "needs_attention",
        engagement_tracking_status="ready" if engagement_ready else "needs_attention",
        verified_domain_count=sum(
            detail.spf_status == "verified" and detail.dkim_status == "verified"
            for detail in details
        ),
        enabled_webhook_count=len(matching_webhooks),
        issue_codes=tuple(issue_codes),
    )

    return probe, None


def _persist_organization_probe(
    db: Session,
    *,
    organization_id: UUID,
    probe: resend_readiness_snapshot_service.ReadinessProbeResult,
    retry_after_seconds: int | None = None,
) -> ReadinessRefreshResult:
    db.expire_all()
    current_configuration = _resolve_organization_configuration(
        db,
        organization_id=organization_id,
    )
    persisted = resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=organization_id,
        current_config_fingerprint=current_configuration.fingerprint,
        probe=probe,
    )
    return ReadinessRefreshResult(
        probe=probe,
        persisted=persisted,
        retry_after_seconds=retry_after_seconds,
    )


def _persist_platform_probe(
    db: Session,
    *,
    probe: resend_readiness_snapshot_service.ReadinessProbeResult,
    retry_after_seconds: int | None = None,
) -> ReadinessRefreshResult:
    db.expire_all()
    current_configuration = _resolve_platform_configuration(db)
    persisted = resend_readiness_snapshot_service.upsert_platform_snapshot(
        db,
        current_config_fingerprint=current_configuration.fingerprint,
        probe=probe,
    )
    return ReadinessRefreshResult(
        probe=probe,
        persisted=persisted,
        retry_after_seconds=retry_after_seconds,
    )


async def refresh_organization_readiness(
    db: Session,
    *,
    organization_id: UUID,
    control_plane_client_factory: Callable[..., object] = (
        resend_control_plane.ResendControlPlaneClient
    ),
) -> ReadinessRefreshResult:
    """Probe and persist the exact organization's current Resend route."""
    configuration = _resolve_organization_configuration(
        db,
        organization_id=organization_id,
    )
    if not configuration.provider_enabled:
        probe = _local_configuration_probe(
            configuration=configuration,
            configured=False,
        )
        retry_after_seconds = None
    elif not configuration.api_key:
        probe = _local_configuration_probe(
            configuration=configuration,
            configured=True,
        )
        retry_after_seconds = None
    else:
        probe, retry_after_seconds = await _probe_configuration(
            db,
            configuration=configuration,
            control_plane_client_factory=control_plane_client_factory,
        )
    return _persist_organization_probe(
        db,
        organization_id=organization_id,
        probe=probe,
        retry_after_seconds=retry_after_seconds,
    )


async def refresh_platform_readiness(
    db: Session,
    *,
    control_plane_client_factory: Callable[..., object] = (
        resend_control_plane.ResendControlPlaneClient
    ),
) -> ReadinessRefreshResult:
    """Probe and persist the exact platform Resend route."""
    configuration = _resolve_platform_configuration(db)
    if not configuration.api_key:
        probe = _local_configuration_probe(
            configuration=configuration,
            configured=True,
        )
        retry_after_seconds = None
    else:
        probe, retry_after_seconds = await _probe_configuration(
            db,
            configuration=configuration,
            control_plane_client_factory=control_plane_client_factory,
        )
    return _persist_platform_probe(
        db,
        probe=probe,
        retry_after_seconds=retry_after_seconds,
    )


def get_cached_organization_readiness(
    db: Session,
    *,
    organization_id: UUID,
) -> resend_readiness_snapshot_service.ReadinessSnapshotView:
    """Read the current organization's fenced snapshot without provider I/O."""
    configuration = _resolve_organization_configuration(
        db,
        organization_id=organization_id,
    )
    return resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=organization_id,
        current_config_fingerprint=configuration.fingerprint,
    )


def get_cached_platform_readiness(
    db: Session,
) -> resend_readiness_snapshot_service.ReadinessSnapshotView:
    """Read the current platform snapshot without provider I/O."""
    configuration = _resolve_platform_configuration(db)
    return resend_readiness_snapshot_service.get_platform_snapshot(
        db,
        current_config_fingerprint=configuration.fingerprint,
    )
