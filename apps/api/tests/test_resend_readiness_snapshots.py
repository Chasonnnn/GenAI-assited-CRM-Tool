"""Persistence contracts for sanitized, fenced Resend readiness snapshots."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Organization, ResendReadinessSnapshot
from app.services import resend_readiness_snapshot_service


def _probe(
    *,
    config_fingerprint: str = "a" * 64,
    probe_started_at: datetime | None = None,
    checked_at: datetime | None = None,
) -> resend_readiness_snapshot_service.ReadinessProbeResult:
    started = probe_started_at or datetime(2026, 7, 23, 14, 0, tzinfo=timezone.utc)
    completed = checked_at or datetime(2026, 7, 23, 14, 1, tzinfo=timezone.utc)
    return resend_readiness_snapshot_service.ReadinessProbeResult(
        config_fingerprint=config_fingerprint,
        probe_started_at=started,
        checked_at=completed,
        probe_status="succeeded",
        overall_status="ready",
        domain_status="ready",
        webhook_status="ready",
        sending_status="ready",
        delivery_tracking_status="ready",
        engagement_tracking_status="ready",
        verified_domain_count=2,
        enabled_webhook_count=1,
        issue_codes=(),
    )


def test_organization_snapshot_is_cache_only_and_scoped_to_exact_org(db, test_org):
    other_org = Organization(
        id=uuid4(),
        name="Other readiness organization",
        slug=f"other-readiness-{uuid4().hex[:8]}",
    )
    db.add(other_org)
    db.flush()

    accepted = resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=_probe(),
    )

    own_snapshot = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )
    other_snapshot = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=other_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )

    assert accepted is True
    assert own_snapshot.freshness == "fresh"
    assert own_snapshot.overall_status == "ready"
    assert own_snapshot.verified_domain_count == 2
    assert other_snapshot.freshness == "never_checked"
    assert other_snapshot.overall_status == "unknown"


def test_older_probe_cannot_overwrite_a_newer_result(db, test_org):
    newer = _probe(
        probe_started_at=datetime(2026, 7, 23, 14, 10, tzinfo=timezone.utc),
        checked_at=datetime(2026, 7, 23, 14, 11, tzinfo=timezone.utc),
    )
    older = replace(
        _probe(
            probe_started_at=datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc),
            checked_at=datetime(2026, 7, 23, 14, 20, tzinfo=timezone.utc),
        ),
        probe_status="failed",
        overall_status="unknown",
        domain_status="unknown",
        webhook_status="unknown",
        sending_status="unknown",
        delivery_tracking_status="unknown",
        engagement_tracking_status="unknown",
        verified_domain_count=0,
        enabled_webhook_count=0,
        issue_codes=("provider_unavailable",),
    )

    assert (
        resend_readiness_snapshot_service.upsert_organization_snapshot(
            db,
            organization_id=test_org.id,
            current_config_fingerprint="a" * 64,
            probe=newer,
        )
        is True
    )
    assert (
        resend_readiness_snapshot_service.upsert_organization_snapshot(
            db,
            organization_id=test_org.id,
            current_config_fingerprint="a" * 64,
            probe=older,
        )
        is False
    )

    snapshot = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc),
    )
    assert snapshot.overall_status == "ready"
    assert snapshot.checked_at == newer.checked_at
    assert snapshot.last_success_at == newer.checked_at


def test_database_rejects_uncontrolled_issue_codes(db, test_org):
    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=_probe(),
    )
    persisted = db.query(ResendReadinessSnapshot).one()

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            persisted.issue_codes = ["provider_body:secret"]
            db.flush()


def test_database_rejects_incoherent_scope_and_route(db, test_org):
    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=_probe(),
    )
    persisted = db.query(ResendReadinessSnapshot).one()

    for field_name, invalid_value in (
        ("provider_scope", "platform"),
        ("provider_account_id", "platform:default"),
    ):
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                setattr(persisted, field_name, invalid_value)
                db.flush()
        db.refresh(persisted)


def test_database_rejects_uncontrolled_statuses(db, test_org):
    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=_probe(),
    )
    persisted = db.query(ResendReadinessSnapshot).one()

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            persisted.overall_status = "ready: api-key=secret"
            db.flush()


def test_platform_snapshot_is_isolated_from_organization_snapshots(db, test_org):
    organization_probe = _probe()
    platform_probe = replace(
        _probe(
            probe_started_at=datetime(2026, 7, 23, 14, 2, tzinfo=timezone.utc),
            checked_at=datetime(2026, 7, 23, 14, 3, tzinfo=timezone.utc),
        ),
        overall_status="needs_attention",
        domain_status="needs_attention",
        verified_domain_count=0,
        issue_codes=("domain_not_verified",),
    )

    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=organization_probe,
    )
    resend_readiness_snapshot_service.upsert_platform_snapshot(
        db,
        current_config_fingerprint="a" * 64,
        probe=platform_probe,
    )

    organization_view = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )
    platform_view = resend_readiness_snapshot_service.get_platform_snapshot(
        db,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )

    assert organization_view.overall_status == "ready"
    assert organization_view.verified_domain_count == 2
    assert platform_view.overall_status == "needs_attention"
    assert platform_view.verified_domain_count == 0
    assert platform_view.issue_codes == ("domain_not_verified",)
    assert db.query(ResendReadinessSnapshot).count() == 2


def test_stale_snapshot_downgrades_green_statuses_to_unknown(db, test_org):
    probe = _probe(
        checked_at=datetime(2026, 7, 23, 14, 1, tzinfo=timezone.utc),
    )
    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=probe,
    )

    snapshot = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 15, 2, tzinfo=timezone.utc),
        fresh_for=timedelta(hours=1),
    )

    assert snapshot.freshness == "stale"
    assert snapshot.overall_status == "unknown"
    assert snapshot.domain_status == "unknown"
    assert snapshot.webhook_status == "unknown"
    assert snapshot.sending_status == "unknown"
    assert snapshot.delivery_tracking_status == "unknown"
    assert snapshot.engagement_tracking_status == "unknown"
    assert snapshot.issue_codes == ("snapshot_stale",)
    assert snapshot.last_success_at == probe.checked_at


def test_config_fingerprint_mismatch_is_discarded_on_write_and_read(db, test_org):
    rejected = resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="b" * 64,
        probe=_probe(config_fingerprint="a" * 64),
    )
    assert rejected is False
    assert db.query(ResendReadinessSnapshot).count() == 0

    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=_probe(config_fingerprint="a" * 64),
    )
    fenced_view = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="b" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )

    assert fenced_view.freshness == "never_checked"
    assert fenced_view.checked_at is None
    assert fenced_view.last_success_at is None


def test_failed_probe_retains_success_only_for_the_same_configuration(db, test_org):
    success = _probe()
    failed_same_config = replace(
        _probe(
            probe_started_at=datetime(2026, 7, 23, 14, 10, tzinfo=timezone.utc),
            checked_at=datetime(2026, 7, 23, 14, 11, tzinfo=timezone.utc),
        ),
        probe_status="failed",
        overall_status="unknown",
        domain_status="unknown",
        webhook_status="unknown",
        sending_status="unknown",
        delivery_tracking_status="unknown",
        engagement_tracking_status="unknown",
        verified_domain_count=0,
        enabled_webhook_count=0,
        issue_codes=("provider_unavailable",),
    )
    failed_new_config = replace(
        failed_same_config,
        config_fingerprint="b" * 64,
        probe_started_at=datetime(2026, 7, 23, 14, 20, tzinfo=timezone.utc),
        checked_at=datetime(2026, 7, 23, 14, 21, tzinfo=timezone.utc),
    )

    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=success,
    )
    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        probe=failed_same_config,
    )
    same_config_view = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="a" * 64,
        now=datetime(2026, 7, 23, 14, 15, tzinfo=timezone.utc),
    )
    assert same_config_view.last_success_at == success.checked_at

    resend_readiness_snapshot_service.upsert_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="b" * 64,
        probe=failed_new_config,
    )
    new_config_view = resend_readiness_snapshot_service.get_organization_snapshot(
        db,
        organization_id=test_org.id,
        current_config_fingerprint="b" * 64,
        now=datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc),
    )
    assert new_config_view.last_success_at is None


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("probe_status", "exception: connection refused"),
        ("overall_status", "provider_api_key_invalid"),
        ("domain_status", "verified.example.com"),
        ("issue_codes", ("raw_provider_error",)),
    ],
)
def test_upsert_rejects_uncontrolled_statuses_and_issue_codes(
    db,
    test_org,
    field_name,
    invalid_value,
):
    invalid_probe = replace(_probe(), **{field_name: invalid_value})

    with pytest.raises(ValueError):
        resend_readiness_snapshot_service.upsert_organization_snapshot(
            db,
            organization_id=test_org.id,
            current_config_fingerprint="a" * 64,
            probe=invalid_probe,
        )

    assert db.query(ResendReadinessSnapshot).count() == 0


def test_persisted_and_projected_fields_exclude_provider_secrets_and_bodies():
    persisted_fields = set(ResendReadinessSnapshot.__table__.columns.keys())
    expected_persisted_fields = {
        "id",
        "organization_id",
        "provider_scope",
        "provider_account_id",
        "config_fingerprint",
        "probe_status",
        "overall_status",
        "domain_status",
        "webhook_status",
        "sending_status",
        "delivery_tracking_status",
        "engagement_tracking_status",
        "verified_domain_count",
        "enabled_webhook_count",
        "issue_codes",
        "probe_started_at",
        "checked_at",
        "last_success_at",
        "created_at",
        "updated_at",
    }
    assert persisted_fields == expected_persisted_fields

    projected_fields = {
        field.name for field in fields(resend_readiness_snapshot_service.ReadinessSnapshotView)
    }
    assert projected_fields == {
        "freshness",
        "probe_status",
        "overall_status",
        "domain_status",
        "webhook_status",
        "sending_status",
        "delivery_tracking_status",
        "engagement_tracking_status",
        "verified_domain_count",
        "enabled_webhook_count",
        "issue_codes",
        "checked_at",
        "last_success_at",
    }
    prohibited_fragments = {
        "api_key",
        "secret",
        "endpoint",
        "domain_id",
        "webhook_id",
        "dns",
        "provider_body",
        "raw_error",
    }
    assert not (persisted_fields & prohibited_fragments)
    assert not (projected_fields & prohibited_fragments)
