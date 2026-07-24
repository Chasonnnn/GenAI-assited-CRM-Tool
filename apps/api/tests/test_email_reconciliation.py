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
            "event_created_at": (detected_at - timedelta(minutes=2))
            .isoformat()
            .replace("+00:00", "Z"),
            "received_at": (detected_at - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "message_id": None,
            "delivery_id": None,
            "attempt_count": None,
            "max_attempts": None,
            "next_attempt_at": None,
            "available_actions": [
                "retry_correlation",
                "link_event",
            ],
            "detected_at": detected_at.isoformat().replace("+00:00", "Z"),
            "updated_at": (detected_at + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
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
        idempotency_key=(f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"),
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
        idempotency_key=(f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"),
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
        idempotency_key=(f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"),
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
    assert stale.json() == {"detail": "Reconciliation case changed; refresh and try again"}


@pytest.mark.asyncio
async def test_retry_correlation_requires_csrf(authed_client):
    from app.core.csrf import CSRF_HEADER

    authed_client.headers.pop(CSRF_HEADER)

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{uuid4()}/retry-correlation",
        json={"expected_version": 1},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_link_orphan_event_projects_existing_message_atomically_without_sending(
    authed_client,
    db,
    test_auth,
    test_org,
    monkeypatch,
):
    detected_at = datetime.now(timezone.utc) - timedelta(hours=1)
    provider_message_id = f"manual-link-{uuid4().hex}"
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="private@example.com",
        subject="Existing message",
        body="<p>Private body</p>",
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        status="sent",
        created_at=detected_at - timedelta(minutes=1),
    )
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        provider_event_id=f"evt_link_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={
            "type": "email.delivered",
            "created_at": detected_at.isoformat(),
            "data": {
                "email_id": provider_message_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(email_log.id),
                },
            },
        },
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="automatic_correlation_exhausted",
        version=6,
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
        status="failed",
        attempts=8,
        max_attempts=8,
        last_error="raw correlation failure",
        idempotency_key=(f"resend-event-reconcile/{test_org.id}/{event.provider_event_id}"),
    )
    db.add_all([email_log, event, case, job])
    db.commit()

    async def _unexpected_provider_send(**_kwargs):
        raise AssertionError("manual link must never send email")

    from app.services import resend_transport

    monkeypatch.setattr(resend_transport, "send_email", _unexpected_provider_send)

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/link-event",
        json={
            "expected_version": 6,
            "email_log_id": str(email_log.id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["reason_code"] == "correlation_succeeded"
    assert payload["version"] == 7
    assert payload["message_id"] == str(email_log.id)
    assert payload["available_actions"] == []
    _assert_no_forbidden_projection_keys(payload)

    db.refresh(event)
    db.refresh(email_log)
    db.refresh(job)
    assert event.email_log_id == email_log.id
    assert event.processed_at is not None
    assert email_log.external_id == provider_message_id
    assert email_log.resend_status == "delivered"
    assert job.status == "completed"
    assert job.last_error is None
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "email_reconciliation_linked",
            AuditLog.target_id == case.id,
        )
        .one()
    )
    assert audit.actor_user_id == test_auth.user.id
    assert audit.details == {
        "action": "link_event",
        "case_type": "orphan_webhook",
        "from_version": 6,
        "reason_code": "correlation_succeeded",
        "to_version": 7,
    }


@pytest.mark.asyncio
async def test_link_orphan_event_rejects_a_message_from_another_delivery_route(
    authed_client,
    db,
    test_org,
):
    detected_at = datetime.now(timezone.utc)
    provider_message_id = f"route-conflict-{uuid4().hex}"
    platform_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="platform@example.com",
        subject="Platform message",
        body="<p>Private body</p>",
        provider="resend",
        provider_scope="platform",
        provider_account_id="platform:default",
        status="sent",
        created_at=detected_at,
    )
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        provider_event_id=f"evt_route_conflict_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={
            "type": "email.delivered",
            "created_at": detected_at.isoformat(),
            "data": {
                "email_id": provider_message_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(platform_log.id),
                },
            },
        },
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="automatic_correlation_exhausted",
        version=1,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    db.add_all([platform_log, event, case])
    db.commit()

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/link-event",
        json={
            "expected_version": 1,
            "email_log_id": str(platform_log.id),
        },
    )

    assert response.status_code == 409
    db.refresh(platform_log)
    db.refresh(event)
    assert platform_log.external_id is None
    assert platform_log.resend_status is None
    assert event.email_log_id is None
    assert event.processed_at is None


@pytest.mark.asyncio
async def test_link_orphan_event_rejects_cross_org_and_conflicting_signed_tags(
    authed_client,
    db,
    test_org,
):
    detected_at = datetime.now(timezone.utc)
    other_org = Organization(
        id=uuid4(),
        name="Other Link Target Org",
        slug=f"other-link-target-{uuid4().hex[:8]}",
    )
    other_log = EmailLog(
        id=uuid4(),
        organization_id=other_org.id,
        recipient_email="other@example.com",
        subject="Other org message",
        body="<p>Private</p>",
        provider="resend",
        status="sent",
        created_at=detected_at,
    )
    local_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="local@example.com",
        subject="Local message",
        body="<p>Private</p>",
        provider="resend",
        status="sent",
        created_at=detected_at,
    )
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_conflict_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={
            "type": "email.delivered",
            "data": {
                "email_id": f"provider-{uuid4().hex}",
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(uuid4()),
                },
            },
        },
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="automatic_correlation_exhausted",
        version=1,
        resend_webhook_event_id=event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    db.add_all([other_org, other_log, local_log, event, case])
    db.commit()

    cross_org = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/link-event",
        json={
            "expected_version": 1,
            "email_log_id": str(other_log.id),
        },
    )
    assert cross_org.status_code == 404

    signed_tag_conflict = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/link-event",
        json={
            "expected_version": 1,
            "email_log_id": str(local_log.id),
        },
    )
    assert signed_tag_conflict.status_code == 409

    db.refresh(event)
    db.refresh(case)
    assert event.processed_at is None
    assert event.email_log_id is None
    assert case.status == "action_required"
    assert case.version == 1


@pytest.mark.asyncio
async def test_dismiss_allows_only_controlled_unsupported_orphan_events(
    authed_client,
    db,
    test_auth,
    test_org,
):
    detected_at = datetime.now(timezone.utc)
    unsupported_event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_unsupported_{uuid4().hex}",
        event_type="email.experimental",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"private": "must never enter resolution"},
    )
    unsupported_case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="unsupported_event",
        version=2,
        resend_webhook_event_id=unsupported_event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    known_event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_known_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=detected_at,
        received_at=detected_at,
        payload={"private": "delivery evidence"},
    )
    known_case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="orphan_webhook",
        status="action_required",
        reason_code="automatic_correlation_exhausted",
        version=1,
        resend_webhook_event_id=known_event.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    db.add_all([unsupported_event, unsupported_case, known_event, known_case])
    db.commit()

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{unsupported_case.id}/dismiss",
        json={
            "expected_version": 2,
            "resolution_code": "unsupported_event",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dismissed"
    assert payload["reason_code"] == "operator_dismissed"
    assert payload["version"] == 3
    assert payload["available_actions"] == []
    _assert_no_forbidden_projection_keys(payload)

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.event_type == "email_reconciliation_dismissed",
            AuditLog.target_id == unsupported_case.id,
        )
        .one()
    )
    assert audit.actor_user_id == test_auth.user.id
    assert audit.details["resolution_code"] == "unsupported_event"
    assert "private" not in str(audit.details)

    rejected = await authed_client.post(
        f"/email-operations/reconciliation-cases/{known_case.id}/dismiss",
        json={
            "expected_version": 1,
            "resolution_code": "unsupported_event",
        },
    )
    assert rejected.status_code == 409
    db.refresh(known_case)
    assert known_case.status == "action_required"


@pytest.mark.asyncio
async def test_unknown_delivery_resolutions_are_audited_and_never_resend(
    authed_client,
    db,
    test_auth,
    test_org,
    monkeypatch,
):
    detected_at = datetime.now(timezone.utc) - timedelta(minutes=30)

    def _unknown_delivery_case(label: str):
        email_log = EmailLog(
            id=uuid4(),
            organization_id=test_org.id,
            recipient_email=f"{label}@example.com",
            subject=f"{label} private subject",
            body="<p>Private</p>",
            provider="resend",
            provider_scope="organization",
            provider_account_id=f"organization:{test_org.id}",
            status="pending",
            created_at=detected_at,
        )
        delivery = EmailDelivery(
            id=uuid4(),
            organization_id=test_org.id,
            email_log_id=email_log.id,
            provider="resend",
            provider_scope="organization",
            provider_account_id=f"organization:{test_org.id}",
            idempotency_key=f"operator-resolution/{label}/{uuid4()}",
            request_fingerprint="f" * 64,
            status="reconciliation_required",
            run_at=detected_at,
            attempt_count=1,
            max_attempts=5,
            completed_at=detected_at,
            last_error_type="provider_outcome_unknown",
            last_error="private transport detail",
            created_at=detected_at,
            updated_at=detected_at,
        )
        case = EmailReconciliationCase(
            id=uuid4(),
            organization_id=test_org.id,
            case_type="unknown_delivery",
            status="action_required",
            reason_code="provider_outcome_unknown",
            version=1,
            email_delivery_id=delivery.id,
            detected_at=detected_at,
            updated_at=detected_at,
        )
        db.add_all([email_log, delivery, case])
        return email_log, delivery, case

    sent_log, sent_delivery, sent_case = _unknown_delivery_case("confirmed-sent")
    not_sent_log, not_sent_delivery, not_sent_case = _unknown_delivery_case("confirmed-not-sent")
    db.commit()

    async def _unexpected_provider_send(**_kwargs):
        raise AssertionError("operator resolution must never send email")

    from app.services import resend_transport

    monkeypatch.setattr(resend_transport, "send_email", _unexpected_provider_send)
    provider_message_id = f"operator-confirmed-{uuid4().hex}"

    sent_response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{sent_case.id}/resolve-delivery",
        json={
            "expected_version": 1,
            "outcome": "confirm_sent",
            "provider_message_id": provider_message_id,
        },
    )
    assert sent_response.status_code == 200
    sent_payload = sent_response.json()
    assert sent_payload["status"] == "resolved"
    assert sent_payload["reason_code"] == "operator_confirmed_sent"
    assert sent_payload["version"] == 2
    assert sent_payload["available_actions"] == []
    _assert_no_forbidden_projection_keys(sent_payload)

    db.refresh(sent_delivery)
    db.refresh(sent_log)
    assert sent_delivery.status == "sent"
    assert sent_delivery.provider_message_id == provider_message_id
    assert sent_log.status == "sent"
    assert sent_log.external_id == provider_message_id

    not_sent_response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{not_sent_case.id}/resolve-delivery",
        json={
            "expected_version": 1,
            "outcome": "confirm_not_sent",
        },
    )
    assert not_sent_response.status_code == 200
    not_sent_payload = not_sent_response.json()
    assert not_sent_payload["status"] == "resolved"
    assert not_sent_payload["reason_code"] == "operator_confirmed_not_sent"
    assert not_sent_payload["version"] == 2
    _assert_no_forbidden_projection_keys(not_sent_payload)

    db.refresh(not_sent_delivery)
    db.refresh(not_sent_log)
    assert not_sent_delivery.status == "failed"
    assert not_sent_delivery.provider_message_id is None
    assert not_sent_log.status == "failed"
    assert not_sent_delivery.last_error_type == "operator_confirmed_not_sent"

    audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == test_org.id,
            AuditLog.target_id.in_([sent_case.id, not_sent_case.id]),
        )
        .order_by(AuditLog.created_at, AuditLog.id)
        .all()
    )
    assert {audit.event_type for audit in audits} == {
        "email_reconciliation_confirmed_sent",
        "email_reconciliation_confirmed_not_sent",
    }
    assert all(audit.actor_user_id == test_auth.user.id for audit in audits)
    assert all(provider_message_id not in str(audit.details) for audit in audits)


@pytest.mark.asyncio
async def test_verified_provider_evidence_supersedes_operator_not_sent_resolution(
    authed_client,
    db,
    test_org,
):
    detected_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    email_log = EmailLog(
        id=uuid4(),
        organization_id=test_org.id,
        recipient_email="private@example.com",
        subject="Private subject",
        body="<p>Private</p>",
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        status="pending",
        created_at=detected_at,
    )
    delivery = EmailDelivery(
        id=uuid4(),
        organization_id=test_org.id,
        email_log_id=email_log.id,
        provider="resend",
        provider_scope="organization",
        provider_account_id=f"organization:{test_org.id}",
        idempotency_key=f"operator-superseded/{uuid4()}",
        request_fingerprint="f" * 64,
        status="reconciliation_required",
        run_at=detected_at,
        attempt_count=1,
        max_attempts=5,
        completed_at=detected_at,
        last_error_type="provider_outcome_unknown",
        last_error="private transport detail",
        created_at=detected_at,
        updated_at=detected_at,
    )
    case = EmailReconciliationCase(
        id=uuid4(),
        organization_id=test_org.id,
        case_type="unknown_delivery",
        status="action_required",
        reason_code="provider_outcome_unknown",
        version=1,
        email_delivery_id=delivery.id,
        detected_at=detected_at,
        updated_at=detected_at,
    )
    db.add_all([email_log, delivery, case])
    db.commit()

    response = await authed_client.post(
        f"/email-operations/reconciliation-cases/{case.id}/resolve-delivery",
        json={
            "expected_version": 1,
            "outcome": "confirm_not_sent",
        },
    )
    assert response.status_code == 200

    event_created_at = datetime.now(timezone.utc)
    provider_message_id = f"verified-later-{uuid4().hex}"
    payload = {
        "type": "email.delivered",
        "created_at": event_created_at.isoformat(),
        "data": {
            "email_id": provider_message_id,
            "tags": {
                "organization_id": str(test_org.id),
                "email_log_id": str(email_log.id),
            },
        },
    }
    event = ResendWebhookEvent(
        id=uuid4(),
        organization_id=test_org.id,
        provider_event_id=f"evt_supersede_{uuid4().hex}",
        event_type="email.delivered",
        event_created_at=event_created_at,
        received_at=event_created_at,
        payload=payload,
    )
    db.add(event)
    db.commit()

    from app.services.webhooks.resend import _process_verified_payload

    result = _process_verified_payload(
        db,
        event=event,
        email_log=email_log,
        payload=payload,
    )
    assert result == {"status": "ok"}

    db.expire_all()
    delivery = db.get(EmailDelivery, delivery.id)
    email_log = db.get(EmailLog, email_log.id)
    case = db.get(EmailReconciliationCase, case.id)
    assert delivery is not None
    assert email_log is not None
    assert case is not None
    assert delivery.status == "sent"
    assert delivery.provider_message_id == provider_message_id
    assert delivery.last_error is None
    assert email_log.status == "sent"
    assert email_log.external_id == provider_message_id
    assert email_log.resend_status == "delivered"
    assert case.status == "resolved"
    assert case.reason_code == "provider_acceptance_verified"
    assert case.resolution_code == "provider_evidence_superseded"
    assert case.resolved_by_user_id is None
    assert case.version == 3
