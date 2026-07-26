"""Cache-only persistence seams for sanitized Resend readiness snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Literal
from uuid import UUID

from sqlalchemy import case, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import ResendReadinessSnapshot

ReadinessFreshness = Literal["fresh", "stale", "never_checked"]
ReadinessProbeStatus = Literal["succeeded", "limited", "failed"]
ReadinessStatus = Literal[
    "ready",
    "needs_attention",
    "limited",
    "unknown",
    "not_configured",
]

READINESS_FRESH_FOR = timedelta(hours=1)
READINESS_PROBE_STATUSES = frozenset({"succeeded", "limited", "failed"})
READINESS_STATUSES = frozenset({"ready", "needs_attention", "limited", "unknown", "not_configured"})
READINESS_ISSUE_CODES = frozenset(
    {
        "admission_unavailable",
        "credential_rejected",
        "credential_unavailable",
        "delivery_events_missing",
        "domain_not_verified",
        "engagement_events_missing",
        "invalid_provider_response",
        "limited_visibility",
        "provider_unavailable",
        "sending_disabled",
        "snapshot_stale",
        "timeout",
        "webhook_disabled",
        "webhook_missing",
    }
)
_FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class ReadinessProbeResult:
    """Controlled result produced by a readiness probe outside this service."""

    config_fingerprint: str
    probe_started_at: datetime
    checked_at: datetime
    probe_status: ReadinessProbeStatus
    overall_status: ReadinessStatus
    domain_status: ReadinessStatus
    webhook_status: ReadinessStatus
    sending_status: ReadinessStatus
    delivery_tracking_status: ReadinessStatus
    engagement_tracking_status: ReadinessStatus
    verified_domain_count: int
    enabled_webhook_count: int
    issue_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadinessSnapshotView:
    """Safe cache projection; internal routing and fencing fields stay private."""

    freshness: ReadinessFreshness
    probe_status: ReadinessProbeStatus | None
    overall_status: ReadinessStatus
    domain_status: ReadinessStatus
    webhook_status: ReadinessStatus
    sending_status: ReadinessStatus
    delivery_tracking_status: ReadinessStatus
    engagement_tracking_status: ReadinessStatus
    verified_domain_count: int
    enabled_webhook_count: int
    issue_codes: tuple[str, ...]
    checked_at: datetime | None
    last_success_at: datetime | None


def _as_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_fingerprint(value: str) -> None:
    if not _FINGERPRINT_PATTERN.fullmatch(value):
        raise ValueError("config_fingerprint must be a lowercase SHA-256 digest")


def _validated_probe(probe: ReadinessProbeResult) -> tuple[datetime, datetime, list[str]]:
    _validate_fingerprint(probe.config_fingerprint)
    if probe.probe_status not in READINESS_PROBE_STATUSES:
        raise ValueError("Unsupported readiness probe status")
    statuses = (
        probe.overall_status,
        probe.domain_status,
        probe.webhook_status,
        probe.sending_status,
        probe.delivery_tracking_status,
        probe.engagement_tracking_status,
    )
    if any(status not in READINESS_STATUSES for status in statuses):
        raise ValueError("Unsupported readiness status")
    if (
        isinstance(probe.verified_domain_count, bool)
        or not isinstance(probe.verified_domain_count, int)
        or probe.verified_domain_count < 0
        or isinstance(probe.enabled_webhook_count, bool)
        or not isinstance(probe.enabled_webhook_count, int)
        or probe.enabled_webhook_count < 0
    ):
        raise ValueError("Readiness counts must be non-negative integers")
    unsupported_codes = set(probe.issue_codes) - READINESS_ISSUE_CODES
    if unsupported_codes:
        raise ValueError("Unsupported readiness issue code")
    started_at = _as_utc(probe.probe_started_at, field_name="probe_started_at")
    checked_at = _as_utc(probe.checked_at, field_name="checked_at")
    if checked_at < started_at:
        raise ValueError("checked_at must not precede probe_started_at")
    return started_at, checked_at, sorted(set(probe.issue_codes))


def _never_checked_view() -> ReadinessSnapshotView:
    return ReadinessSnapshotView(
        freshness="never_checked",
        probe_status=None,
        overall_status="unknown",
        domain_status="unknown",
        webhook_status="unknown",
        sending_status="unknown",
        delivery_tracking_status="unknown",
        engagement_tracking_status="unknown",
        verified_domain_count=0,
        enabled_webhook_count=0,
        issue_codes=(),
        checked_at=None,
        last_success_at=None,
    )


def _project_snapshot(
    snapshot: ResendReadinessSnapshot | None,
    *,
    current_config_fingerprint: str,
    now: datetime,
    fresh_for: timedelta,
) -> ReadinessSnapshotView:
    _validate_fingerprint(current_config_fingerprint)
    current_time = _as_utc(now, field_name="now")
    if fresh_for.total_seconds() < 0:
        raise ValueError("fresh_for must not be negative")
    if snapshot is None or snapshot.config_fingerprint != current_config_fingerprint:
        return _never_checked_view()

    checked_at = _as_utc(snapshot.checked_at, field_name="snapshot.checked_at")
    last_success_at = (
        _as_utc(snapshot.last_success_at, field_name="snapshot.last_success_at")
        if snapshot.last_success_at is not None
        else None
    )
    is_stale = checked_at < current_time - fresh_for
    if is_stale:
        return ReadinessSnapshotView(
            freshness="stale",
            probe_status=snapshot.probe_status,
            overall_status="unknown",
            domain_status="unknown",
            webhook_status="unknown",
            sending_status="unknown",
            delivery_tracking_status="unknown",
            engagement_tracking_status="unknown",
            verified_domain_count=snapshot.verified_domain_count,
            enabled_webhook_count=snapshot.enabled_webhook_count,
            issue_codes=tuple(sorted({*snapshot.issue_codes, "snapshot_stale"})),
            checked_at=checked_at,
            last_success_at=last_success_at,
        )
    return ReadinessSnapshotView(
        freshness="fresh",
        probe_status=snapshot.probe_status,
        overall_status=snapshot.overall_status,
        domain_status=snapshot.domain_status,
        webhook_status=snapshot.webhook_status,
        sending_status=snapshot.sending_status,
        delivery_tracking_status=snapshot.delivery_tracking_status,
        engagement_tracking_status=snapshot.engagement_tracking_status,
        verified_domain_count=snapshot.verified_domain_count,
        enabled_webhook_count=snapshot.enabled_webhook_count,
        issue_codes=tuple(snapshot.issue_codes),
        checked_at=checked_at,
        last_success_at=last_success_at,
    )


def _upsert_snapshot(
    db: Session,
    *,
    provider_scope: Literal["platform", "organization"],
    organization_id: UUID | None,
    provider_account_id: str,
    current_config_fingerprint: str,
    probe: ReadinessProbeResult,
) -> bool:
    _validate_fingerprint(current_config_fingerprint)
    started_at, checked_at, issue_codes = _validated_probe(probe)
    if probe.config_fingerprint != current_config_fingerprint:
        return False

    statement = insert(ResendReadinessSnapshot).values(
        organization_id=organization_id,
        provider_scope=provider_scope,
        provider_account_id=provider_account_id,
        config_fingerprint=probe.config_fingerprint,
        probe_started_at=started_at,
        checked_at=checked_at,
        probe_status=probe.probe_status,
        overall_status=probe.overall_status,
        domain_status=probe.domain_status,
        webhook_status=probe.webhook_status,
        sending_status=probe.sending_status,
        delivery_tracking_status=probe.delivery_tracking_status,
        engagement_tracking_status=probe.engagement_tracking_status,
        verified_domain_count=probe.verified_domain_count,
        enabled_webhook_count=probe.enabled_webhook_count,
        issue_codes=issue_codes,
        last_success_at=(checked_at if probe.probe_status == "succeeded" else None),
        created_at=checked_at,
        updated_at=checked_at,
    )
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        constraint="uq_resend_readiness_snapshot_route",
        set_={
            "organization_id": excluded.organization_id,
            "config_fingerprint": excluded.config_fingerprint,
            "probe_started_at": excluded.probe_started_at,
            "checked_at": excluded.checked_at,
            "probe_status": excluded.probe_status,
            "overall_status": excluded.overall_status,
            "domain_status": excluded.domain_status,
            "webhook_status": excluded.webhook_status,
            "sending_status": excluded.sending_status,
            "delivery_tracking_status": excluded.delivery_tracking_status,
            "engagement_tracking_status": excluded.engagement_tracking_status,
            "verified_domain_count": excluded.verified_domain_count,
            "enabled_webhook_count": excluded.enabled_webhook_count,
            "issue_codes": excluded.issue_codes,
            "last_success_at": case(
                (excluded.probe_status == "succeeded", excluded.checked_at),
                (
                    excluded.config_fingerprint == ResendReadinessSnapshot.config_fingerprint,
                    ResendReadinessSnapshot.last_success_at,
                ),
                else_=None,
            ),
            "updated_at": excluded.updated_at,
        },
        where=or_(
            excluded.config_fingerprint != ResendReadinessSnapshot.config_fingerprint,
            excluded.probe_started_at > ResendReadinessSnapshot.probe_started_at,
        ),
    ).returning(ResendReadinessSnapshot.id)
    accepted_id = db.execute(statement).scalar_one_or_none()
    db.expire_all()
    return accepted_id is not None


def upsert_organization_snapshot(
    db: Session,
    *,
    organization_id: UUID,
    current_config_fingerprint: str,
    probe: ReadinessProbeResult,
) -> bool:
    """Store a sanitized probe only when it still matches this org's config."""
    return _upsert_snapshot(
        db,
        provider_scope="organization",
        organization_id=organization_id,
        provider_account_id=f"organization:{organization_id}",
        current_config_fingerprint=current_config_fingerprint,
        probe=probe,
    )


def upsert_platform_snapshot(
    db: Session,
    *,
    current_config_fingerprint: str,
    probe: ReadinessProbeResult,
) -> bool:
    """Store a sanitized probe only when it still matches platform config."""
    return _upsert_snapshot(
        db,
        provider_scope="platform",
        organization_id=None,
        provider_account_id="platform:default",
        current_config_fingerprint=current_config_fingerprint,
        probe=probe,
    )


def get_organization_snapshot(
    db: Session,
    *,
    organization_id: UUID,
    current_config_fingerprint: str,
    now: datetime | None = None,
    fresh_for: timedelta = READINESS_FRESH_FOR,
) -> ReadinessSnapshotView:
    """Read one org's persisted snapshot without making provider requests."""
    snapshot = (
        db.query(ResendReadinessSnapshot)
        .filter(
            ResendReadinessSnapshot.provider_scope == "organization",
            ResendReadinessSnapshot.provider_account_id == f"organization:{organization_id}",
            ResendReadinessSnapshot.organization_id == organization_id,
        )
        .one_or_none()
    )
    return _project_snapshot(
        snapshot,
        current_config_fingerprint=current_config_fingerprint,
        now=now or datetime.now(timezone.utc),
        fresh_for=fresh_for,
    )


def get_platform_snapshot(
    db: Session,
    *,
    current_config_fingerprint: str,
    now: datetime | None = None,
    fresh_for: timedelta = READINESS_FRESH_FOR,
) -> ReadinessSnapshotView:
    """Read the platform snapshot without falling through to any tenant."""
    snapshot = (
        db.query(ResendReadinessSnapshot)
        .filter(
            ResendReadinessSnapshot.provider_scope == "platform",
            ResendReadinessSnapshot.provider_account_id == "platform:default",
            ResendReadinessSnapshot.organization_id.is_(None),
        )
        .one_or_none()
    )
    return _project_snapshot(
        snapshot,
        current_config_fingerprint=current_config_fingerprint,
        now=now or datetime.now(timezone.utc),
        fresh_for=fresh_for,
    )
