"""Tests for queued ticket outbound sends and DLQ replay controls."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient

from app.db.enums import JobStatus, JobType, SurrogateSource
from app.db.models import EmailMessageThreadRef, Job, UserIntegration
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service


def _create_surrogate(db, test_org, test_user, *, email: str = "surrogate@example.com"):
    return surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Ticketing Queue Surrogate",
            email=email,
            source=SurrogateSource.MANUAL,
        ),
    )


def _create_gmail_integration(db, test_user, *, account_email: str):
    integration = UserIntegration(
        id=uuid.uuid4(),
        user_id=test_user.id,
        integration_type="gmail",
        access_token_encrypted="encrypted-access-token",
        refresh_token_encrypted="encrypted-refresh-token",
        account_email=account_email,
    )
    db.add(integration)
    db.commit()
    return integration


def _make_failed_job(db, test_org, *, job_type: JobType) -> Job:
    job = Job(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        job_type=job_type.value,
        payload={"organization_id": str(test_org.id), "test": True},
        run_at=datetime.now(timezone.utc),
        status=JobStatus.FAILED.value,
        attempts=3,
        max_attempts=3,
        last_error="forced failure",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.mark.asyncio
async def test_compose_enqueues_ticket_outbound_send_job(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    surrogate = _create_surrogate(db, test_org, test_user, email="queued.compose@example.com")
    _create_gmail_integration(db, test_user, account_email=test_user.email)

    response = await authed_client.post(
        "/tickets/compose",
        json={
            "to_emails": ["queued.compose@example.com"],
            "subject": "Queued compose",
            "body_text": "Message should be queued for worker send.",
            "surrogate_id": str(surrogate.id),
            "idempotency_key": "compose-queue-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["provider"] == "gmail"
    assert payload["ticket_id"]
    assert payload["message_id"]
    assert payload["job_id"]

    job = db.query(Job).filter(Job.id == uuid.UUID(payload["job_id"])).first()
    assert job is not None
    assert job.job_type == JobType.TICKET_OUTBOUND_SEND.value
    assert job.status == JobStatus.PENDING.value
    assert (job.payload or {}).get("ticket_id") == payload["ticket_id"]
    assert (job.payload or {}).get("message_id") == payload["message_id"]
    assert (job.payload or {}).get("outbound_idempotency_key") == "compose-queue-1"

    detail = await authed_client.get(f"/tickets/{payload['ticket_id']}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert any(
        message["message_id"] == payload["message_id"] for message in detail_payload["messages"]
    )
    assert any(event["event_type"] == "outbound_queued" for event in detail_payload["events"])


@pytest.mark.asyncio
async def test_ticket_outbound_handler_is_idempotent_on_replay(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from app.jobs.handlers import ticketing as ticketing_job_handlers
    from app.services import gmail_service

    surrogate = _create_surrogate(db, test_org, test_user, email="queued.replay@example.com")
    _create_gmail_integration(db, test_user, account_email=test_user.email)

    compose = await authed_client.post(
        "/tickets/compose",
        json={
            "to_emails": ["queued.replay@example.com"],
            "subject": "Replay-safe send",
            "body_text": "Only one Gmail send should happen for replay.",
            "surrogate_id": str(surrogate.id),
            "idempotency_key": "replay-safe-1",
        },
    )
    assert compose.status_code == 200
    compose_payload = compose.json()
    assert compose_payload["status"] == "queued"

    send_calls = {"count": 0}

    async def fake_send_email(*, db, user_id, to, subject, body, html, headers, attachments=None):
        _ = db
        _ = user_id
        _ = to
        _ = subject
        _ = body
        _ = html
        _ = headers
        _ = attachments
        send_calls["count"] += 1
        return {
            "success": True,
            "message_id": "gmail-message-replay-safe",
            "thread_id": "gmail-thread-replay-safe",
        }

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    job = db.query(Job).filter(Job.id == uuid.UUID(compose_payload["job_id"])).first()
    assert job is not None

    await ticketing_job_handlers.process_ticket_outbound_send(db, job)
    await ticketing_job_handlers.process_ticket_outbound_send(db, job)

    assert send_calls["count"] == 1

    refs = (
        db.query(EmailMessageThreadRef)
        .filter(
            EmailMessageThreadRef.organization_id == test_org.id,
            EmailMessageThreadRef.message_id == uuid.UUID(compose_payload["message_id"]),
            EmailMessageThreadRef.ref_type == "gmail_message_id",
        )
        .all()
    )
    assert len(refs) == 1
    assert refs[0].ref_rfc_message_id == "gmail-message-replay-safe"


@pytest.mark.asyncio
async def test_compose_idempotency_returns_existing_queued_job(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    _create_gmail_integration(db, test_user, account_email=test_user.email)
    idem_key = "compose-dedupe-1"

    first = await authed_client.post(
        "/tickets/compose",
        json={
            "to_emails": ["dedupe@example.com"],
            "subject": "Idempotent compose",
            "body_text": "This should only queue once.",
            "idempotency_key": idem_key,
        },
    )
    second = await authed_client.post(
        "/tickets/compose",
        json={
            "to_emails": ["dedupe@example.com"],
            "subject": "Idempotent compose",
            "body_text": "This should only queue once.",
            "idempotency_key": idem_key,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()

    assert first_payload["status"] == "queued"
    assert second_payload["status"] == "queued"
    assert second_payload["job_id"] == first_payload["job_id"]
    assert second_payload["message_id"] == first_payload["message_id"]
    assert second_payload["ticket_id"] == first_payload["ticket_id"]

    jobs = [
        row
        for row in db.query(Job).filter(Job.job_type == JobType.TICKET_OUTBOUND_SEND.value).all()
        if (row.payload or {}).get("outbound_idempotency_key") == idem_key
    ]
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_jobs_dlq_and_single_replay_endpoint(
    authed_client: AsyncClient,
    db,
    test_org,
):
    failed = _make_failed_job(db, test_org, job_type=JobType.TICKET_OUTBOUND_SEND)

    dlq = await authed_client.get("/jobs/dlq")
    assert dlq.status_code == 200
    items = dlq.json()
    assert any(item["id"] == str(failed.id) for item in items)

    replay = await authed_client.post(
        f"/jobs/{failed.id}/replay",
        json={"reason": "operator replay"},
    )
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["id"] == str(failed.id)
    assert payload["status"] == JobStatus.PENDING.value
    assert payload["attempts"] == 0
    assert payload["last_error"] is None


@pytest.mark.asyncio
async def test_jobs_dlq_bulk_replay_endpoint(
    authed_client: AsyncClient,
    db,
    test_org,
):
    first = _make_failed_job(db, test_org, job_type=JobType.TICKET_OUTBOUND_SEND)
    second = _make_failed_job(db, test_org, job_type=JobType.TICKET_OUTBOUND_SEND)
    _make_failed_job(db, test_org, job_type=JobType.MAILBOX_HISTORY_SYNC)

    replay = await authed_client.post(
        "/jobs/dlq/replay",
        json={
            "job_type": JobType.TICKET_OUTBOUND_SEND.value,
            "limit": 1,
            "reason": "bulk replay",
        },
    )
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["replayed"] == 1
    assert len(payload["job_ids"]) == 1

    db.refresh(first)
    db.refresh(second)
    pending_count = int(first.status == JobStatus.PENDING.value) + int(
        second.status == JobStatus.PENDING.value
    )
    assert pending_count == 1
