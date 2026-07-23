"""Contract tests for the organization email reconciliation workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.models import (
    AuditLog,
    EmailReconciliationCase,
    EmailDelivery,
    EmailLog,
    Job,
    Organization,
    ResendWebhookEvent,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260723_0220_add_email_reconciliation_cases.py"
)


def _load_reconciliation_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_20260723_0220",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load reconciliation migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_no_forbidden_projection_keys(value: object) -> None:
    forbidden = {
        "payload",
        "recipient_email",
        "subject",
        "body",
        "text_body",
        "headers",
        "raw_error",
        "last_error",
        "url",
        "ip",
        "user_agent",
        "user-agent",
        "lease_token",
        "lease_owner",
        "provider_account_id",
        "credential",
        "secret",
    }
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            _assert_no_forbidden_projection_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_forbidden_projection_keys(nested)


@pytest.mark.asyncio
async def test_reconciliation_queue_requires_authentication(client):
    response = await client.get("/email-operations/reconciliation-cases")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reconciliation_queue_requires_manage_ops(
    authed_client,
    monkeypatch,
):
    from app.services import permission_service

    monkeypatch.setattr(
        permission_service,
        "check_permission",
        lambda *_args, **_kwargs: False,
    )

    response = await authed_client.get("/email-operations/reconciliation-cases")

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: manage_ops"


@pytest.mark.asyncio
async def test_reconciliation_queue_starts_empty_for_an_organization(authed_client):
    response = await authed_client.get("/email-operations/reconciliation-cases")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "next_cursor": None,
        "counts": {
            "monitoring": 0,
            "action_required": 0,
            "resolved": 0,
        },
    }


@pytest.mark.asyncio
async def test_reconciliation_queue_is_org_scoped_and_never_projects_raw_event_data(
    authed_client,
    db,
    test_org,
):
    detected_at = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id="evt_operator_case",
        event_type="email.delivered",
        event_created_at=detected_at - timedelta(minutes=2),
        received_at=detected_at - timedelta(minutes=1),
        payload={
            "data": {
                "to": ["private@example.com"],
                "url": "https://example.com/private",
                "headers": {"authorization": "Bearer secret"},
            },
            "ip": "192.0.2.10",
            "user_agent": "private-agent",
            "webhook_secret": "must-never-project",
        },
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="correlation_exhausted",
        version=3,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at + timedelta(minutes=5),
    )

    other_org = Organization(
        id=uuid4(),
        name="Other Reconciliation Org",
        slug=f"other-reconciliation-{uuid4().hex[:8]}",
    )
    other_event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=other_org.id,
        provider_event_id="evt_other_org",
        event_type="email.bounced",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"secret": "cross-org"},
    )
    other_case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=other_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="correlation_exhausted",
        resend_webhook_event_id=other_event.id,
        detected_at=detected_at + timedelta(minutes=10),
        updated_at=detected_at + timedelta(minutes=10),
    )
    db.add_all([event, case, other_org, other_event, other_case])
    db.commit()

    response = await authed_client.get(
        "/email-operations/reconciliation-cases?status=action_required&limit=25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["next_cursor"] is None
    assert payload["counts"] == {
        "monitoring": 0,
        "action_required": 1,
        "resolved": 0,
    }
    assert payload["items"] == [
        {
            "id": str(case.id),
            "case_type": "orphan_webhook",
            "status": "action_required",
            "reason_code": "correlation_exhausted",
            "version": 3,
            "provider": "resend",
            "event_type": "email.delivered",
            "event_created_at": (detected_at - timedelta(minutes=2)).isoformat().replace(
                "+00:00", "Z"
            ),
            "received_at": (detected_at - timedelta(minutes=1)).isoformat().replace(
                "+00:00", "Z"
            ),
            "message_id": None,
            "delivery_id": None,
            "attempt_count": None,
            "max_attempts": None,
            "next_attempt_at": None,
            "available_actions": [
                "retry_correlation",
                "link_event",
                "dismiss",
            ],
            "detected_at": detected_at.isoformat().replace("+00:00", "Z"),
            "updated_at": (detected_at + timedelta(minutes=5))
            .isoformat()
            .replace("+00:00", "Z"),
        }
    ]
    _assert_no_forbidden_projection_keys(payload)


def test_reconciliation_migration_backfills_only_source_ids_and_controlled_codes(
    db,
    test_org,
):
    detected_at = datetime(2026, 7, 23, 13, 0, tzinfo=timezone.utc)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id="evt_existing_orphan",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={
            "recipient_email": "private@example.com",
            "url": "https://example.com/private",
            "last_error": "raw provider detail",
        },
    )
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="private@example.com",
        subject="Private subject",
        body="<p>Private body</p>",
        status="pending",
        created_at=detected_at,
    )
    delivery = EmailDelivery(
        id=uuid4(),
        organization_id=test_org.id,
        email_log_id=email_log.id,
        provider="resend",
        provider_scope="organization",
        provider_account_id="private-provider-account",
        idempotency_key=f"backfill/{uuid4()}",
        request_fingerprint="f" * 64,
        status="reconciliation_required",
        run_at=detected_at,
        attempt_count=1,
        max_attempts=5,
        completed_at=detected_at + timedelta(minutes=1),
        last_error_type="lease_expired",
        last_error="private raw error",
        created_at=detected_at,
        updated_at=detected_at + timedelta(minutes=1),
    )
    db.add_all([event, email_log, delivery])
    db.flush()

    migration = _load_reconciliation_migration()
    migration._backfill_reconciliation_cases(db.connection())
    db.expire_all()

    cases = (
        db.query(EmailReconciliationCase)
        .filter(EmailReconciliationCase.organization_id == test_org.id)
        .order_by(EmailReconciliationCase.case_type)
        .all()
    )
    assert [(case.case_type, case.reason_code) for case in cases] == [
        ("orphan_webhook", "correlation_pending"),
        ("unknown_delivery", "delivery_lease_expired"),
    ]
    assert cases[0].resend_webhook_event_id == event.id
    assert cases[0].email_delivery_id is None
    assert cases[1].email_delivery_id == delivery.id
    assert cases[1].resend_webhook_event_id is None
    for case in cases:
        assert set(case.__table__.columns.keys()).isdisjoint(
            {
                "payload",
                "recipient_email",
                "subject",
                "body",
                "headers",
                "last_error",
                "provider_account_id",
            }
        )


def test_final_automatic_correlation_failure_requires_operator_action(
    db,
    test_org,
):
    from app.services import job_service

    detected_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_exhausted_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"last_error": "private provider detail"},
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="pending",
        reason_code="correlation_pending",
        version=2,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type="resend_event_reconcile",
        payload={"event_id": str(event.id)},
        run_at=detected_at,
        status="running",
        attempts=8,
        max_attempts=8,
        idempotency_key=(
            f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"
        ),
    )
    db.add_all([event, case, job])
    db.commit()

    job_service.mark_job_failed(
        db,
        job,
        "raw exception containing private@example.com",
    )

    db.refresh(case)
    assert job.status == "failed"
    assert case.status == "action_required"
    assert case.reason_code == "automatic_correlation_exhausted"
    assert case.version == 3
    assert case.resolution_code is None


def test_stale_reconciliation_claim_is_recovered_and_old_worker_is_fenced(
    db,
    test_org,
):
    from app.services import job_service

    detected_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_stale_claim_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"data": {"email_id": "unmatched-provider-message"}},
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="pending",
        reason_code="correlation_pending",
        version=1,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type="resend_event_reconcile",
        payload={"event_id": str(event.id)},
        run_at=detected_at,
        status="pending",
        attempts=0,
        max_attempts=2,
        idempotency_key=(
            f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"
        ),
    )
    db.add_all([event, case, job])
    db.commit()

    first_claim = job_service.claim_job_for_dispatch(db, job.id)
    assert first_claim is not None
    first_token = first_claim.claim_token
    assert first_token is not None
    first_claim.claimed_at = detected_at
    db.commit()

    summary = job_service.recover_stale_resend_reconciliation_jobs(
        db,
        now=datetime.now(timezone.utc),
        stale_after=timedelta(minutes=5),
        limit=100,
    )

    db.refresh(job)
    db.refresh(case)
    assert summary.requeued >= 1
    assert job.status == "pending"
    assert job.claim_token is None
    assert job.claimed_at is None
    assert case.status == "pending"
    assert case.reason_code == "worker_claim_expired"
    assert case.version == 2

    second_claim = job_service.claim_job_for_dispatch(db, job.id)
    assert second_claim is not None
    second_token = second_claim.claim_token
    assert second_token is not None
    assert second_token != first_token

    with pytest.raises(job_service.JobClaimLost):
        job_service.complete_claimed_job(
            db,
            job_id=job.id,
            claim_token=first_token,
        )

    db.expire_all()
    current = db.get(Job, job.id)
    assert current.status == "running"
    assert current.claim_token == second_token

    current.attempts = current.max_attempts
    current.claimed_at = detected_at
    db.commit()
    final_summary = job_service.recover_stale_resend_reconciliation_jobs(
        db,
        now=datetime.now(timezone.utc),
        stale_after=timedelta(minutes=5),
        limit=100,
    )

    db.refresh(current)
    db.refresh(case)
    assert final_summary.failed >= 1
    assert current.status == "failed"
    assert current.claim_token is None
    assert current.claimed_at is None
    assert case.status == "action_required"
    assert case.reason_code == "automatic_correlation_exhausted"
    assert case.version == 3


@pytest.mark.asyncio
async def test_retry_correlation_requeues_only_local_work_with_version_and_audit_fencing(
    authed_client,
    db,
    test_auth,
    test_org,
    monkeypatch,
):
    detected_at = datetime.now(timezone.utc) - timedelta(hours=2)
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_retry_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"data": {"email_id": "provider-id-with-no-local-message"}},
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="automatic_correlation_exhausted",
        version=4,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    job = Job(
        id=uuid4(),
        organization_id=test_org.id,
        job_type="resend_event_reconcile",
        payload={"event_id": str(event.id), "private": "never-project"},
        run_at=detected_at,
        status="failed",
        attempts=8,
        max_attempts=8,
        last_error="raw reconciliation failure",
        idempotency_key=(
            f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"
        ),
    )
    db.add_all([event, case, job])
    db.commit()

    async def _unexpected_provider_send(**_kwargs):
        raise AssertionError("operator correlation retry must never send email")

    from app.services import resend_transport

    monkeypatch.setattr(resend_transport, "send_email", _unexpected_provider_send)

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/retry-correlation",
        json={"expected_version": 4},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(case.id)
    assert payload["status"] == "pending"
    assert payload["reason_code"] == "operator_retry_requested"
    assert payload["version"] == 5
    assert payload["available_actions"] == []
    _assert_no_forbidden_projection_keys(payload)

    db.refresh(job)
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.last_error is None
    assert job.run_at >= detected_at
    assert (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == "resend_event_reconcile",
        )
        .count()
        == 1
    )
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "email_reconciliation_retried",
            AuditLog.target_id == case.id,
        )
        .one()
    )
    assert audit.actor_user_id == test_auth.user.id
    assert audit.details == {
        "action": "retry_correlation",
        "case_type": "orphan_webhook",
        "from_version": 4,
        "reason_code": "operator_retry_requested",
        "to_version": 5,
    }

    stale = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/retry-correlation",
        json={"expected_version": 4},
    )
    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "Reconciliation case changed; refresh and try again"
    }


@pytest.mark.asyncio
async def test_retry_correlation_requires_csrf(authed_client):
    from app.core.csrf import CSRF_HEADER

    authed_client.headers.pop(CSRF_HEADER)

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{uuid4()}/retry-correlation",
        json={"expected_version": 1},
    )

    assert response.status_code == 403
