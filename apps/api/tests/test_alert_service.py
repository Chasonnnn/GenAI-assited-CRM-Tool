"""Tests for system alert upsert/reopen behavior."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.db.enums import AlertSeverity, AlertStatus, AlertType
from app.db.models import Organization, SystemAlert
from app.db.session import SessionLocal
from app.services import alert_service


def test_create_or_update_alert_upserts_and_reopens_resolved(db, test_org, test_user):
    """Matching dedupe keys should update in-place and reopen resolved alerts."""
    alert = alert_service.create_or_update_alert(
        db=db,
        org_id=test_org.id,
        alert_type=AlertType.API_ERROR,
        severity=AlertSeverity.ERROR,
        title="API error",
        message="first",
        integration_key="/surrogates",
        error_class="RuntimeError",
        http_status=500,
    )
    db.commit()

    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by_user_id = test_user.id
    db.commit()

    updated = alert_service.create_or_update_alert(
        db=db,
        org_id=test_org.id,
        alert_type=AlertType.API_ERROR,
        severity=AlertSeverity.ERROR,
        title="API error",
        message="second",
        integration_key="/surrogates",
        error_class="RuntimeError",
        http_status=500,
    )
    db.commit()
    db.refresh(updated)

    assert updated.id == alert.id
    assert updated.occurrence_count == 2
    assert updated.message == "second"
    assert updated.status == AlertStatus.OPEN.value
    assert updated.resolved_at is None
    assert updated.resolved_by_user_id is None


def test_create_or_update_alert_snooze_reopen_semantics(db, test_org):
    """Snoozed alerts stay snoozed until expiration, then reopen."""
    alert = alert_service.create_or_update_alert(
        db=db,
        org_id=test_org.id,
        alert_type=AlertType.WORKER_JOB_FAILED,
        severity=AlertSeverity.ERROR,
        title="Worker failed",
        message="first",
        integration_key="worker",
        error_class="WorkerError",
    )
    db.commit()

    alert.status = AlertStatus.SNOOZED.value
    alert.snoozed_until = datetime.now(timezone.utc) + timedelta(hours=1)
    db.commit()

    still_snoozed = alert_service.create_or_update_alert(
        db=db,
        org_id=test_org.id,
        alert_type=AlertType.WORKER_JOB_FAILED,
        severity=AlertSeverity.ERROR,
        title="Worker failed",
        message="second",
        integration_key="worker",
        error_class="WorkerError",
    )
    db.commit()
    db.refresh(still_snoozed)

    assert still_snoozed.status == AlertStatus.SNOOZED.value
    assert still_snoozed.occurrence_count == 2

    still_snoozed.snoozed_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    reopened = alert_service.create_or_update_alert(
        db=db,
        org_id=test_org.id,
        alert_type=AlertType.WORKER_JOB_FAILED,
        severity=AlertSeverity.ERROR,
        title="Worker failed",
        message="third",
        integration_key="worker",
        error_class="WorkerError",
    )
    db.commit()
    db.refresh(reopened)

    assert reopened.status == AlertStatus.OPEN.value
    assert reopened.snoozed_until is None
    assert reopened.occurrence_count == 3


def test_create_or_update_alert_concurrent_dedupe_upsert(db_engine):
    """Concurrent writers to the same dedupe key should not create duplicate alerts."""
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent upsert semantics require PostgreSQL")

    setup_conn = db_engine.connect()
    setup_session = SessionLocal(bind=setup_conn)
    cleanup_conn = db_engine.connect()
    cleanup_session = SessionLocal(bind=cleanup_conn)

    org_id = None
    try:
        org = Organization(
            id=uuid.uuid4(),
            name="Alert Concurrency Org",
            slug=f"alert-concurrency-{uuid.uuid4().hex[:8]}",
        )
        setup_session.add(org)
        setup_session.commit()
        org_id = org.id

        workers = 6

        def _write_alert() -> None:
            alert = alert_service.record_alert_isolated(
                org_id=org.id,
                alert_type=AlertType.WORKER_JOB_FAILED,
                severity=AlertSeverity.ERROR,
                title="Concurrent failure",
                message="worker failed",
                integration_key="worker",
                error_class="WorkerError",
            )
            assert alert is not None

        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda _i: _write_alert(), range(workers)))

        alerts = (
            cleanup_session.query(SystemAlert)
            .filter(
                SystemAlert.organization_id == org.id,
                SystemAlert.alert_type == AlertType.WORKER_JOB_FAILED.value,
                SystemAlert.integration_key == "worker",
                SystemAlert.title == "Concurrent failure",
            )
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0].occurrence_count == workers
    finally:
        if org_id:
            cleanup_session.query(SystemAlert).filter(
                SystemAlert.organization_id == org_id
            ).delete()
            cleanup_session.query(Organization).filter(Organization.id == org_id).delete()
            cleanup_session.commit()
        cleanup_session.close()
        cleanup_conn.close()
        setup_session.close()
        setup_conn.close()
