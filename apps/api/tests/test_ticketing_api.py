"""API tests for ticketing and mailbox ingestion endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.db.enums import SurrogateSource
from app.db.models import UserIntegration
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service


def _create_surrogate(db, test_org, test_user, *, email: str = "surrogate@example.com"):
    return surrogate_service.create_surrogate(
        db,
        test_org.id,
        test_user.id,
        SurrogateCreate(
            full_name="Ticketing Test Surrogate",
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


@pytest.mark.asyncio
async def test_ticket_compose_list_detail_and_surrogate_email_history(
    authed_client: AsyncClient, db, test_org, test_user, monkeypatch
):
    from app.services import gmail_service

    surrogate = _create_surrogate(db, test_org, test_user, email="surrogate.history@example.com")
    _create_gmail_integration(db, test_user, account_email=test_user.email)

    async def fake_send_email(*, db, user_id, to, subject, body, html, headers, attachments=None):
        _ = db
        _ = user_id
        _ = to
        _ = subject
        _ = body
        _ = html
        _ = headers
        _ = attachments
        return {
            "success": True,
            "message_id": "gmail-msg-compose-1",
            "thread_id": "gmail-thread-compose-1",
        }

    monkeypatch.setattr(gmail_service, "send_email", fake_send_email)

    compose = await authed_client.post(
        "/tickets/compose",
        json={
            "to_emails": ["surrogate.history@example.com"],
            "subject": "Compose from Ticket API",
            "body_text": "Hello from compose endpoint",
            "surrogate_id": str(surrogate.id),
        },
    )
    assert compose.status_code == 200
    compose_payload = compose.json()
    assert compose_payload["status"] == "queued"
    assert compose_payload["provider"] == "gmail"
    assert compose_payload["job_id"]
    ticket_id = compose_payload["ticket_id"]

    inbox = await authed_client.get("/tickets")
    assert inbox.status_code == 200
    inbox_payload = inbox.json()
    assert inbox_payload["items"]
    created_ticket = next(item for item in inbox_payload["items"] if item["id"] == ticket_id)
    assert created_ticket["surrogate_id"] == str(surrogate.id)
    assert created_ticket["subject"] == "Compose from Ticket API"

    detail = await authed_client.get(f"/tickets/{ticket_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["ticket"]["id"] == ticket_id
    assert detail_payload["messages"]
    assert detail_payload["messages"][0]["direction"] == "outbound"
    assert detail_payload["messages"][0]["subject"] == "Compose from Ticket API"

    surrogate_emails = await authed_client.get(f"/surrogates/{surrogate.id}/emails")
    assert surrogate_emails.status_code == 200
    surrogate_payload = surrogate_emails.json()
    assert surrogate_payload["items"]
    assert any(item["id"] == ticket_id for item in surrogate_payload["items"])


@pytest.mark.asyncio
async def test_surrogate_email_contact_crud(authed_client: AsyncClient, db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org, test_user, email="surrogate.contacts@example.com")

    # System contact should be present from surrogate primary email.
    initial = await authed_client.get(f"/surrogates/{surrogate.id}/email-contacts")
    assert initial.status_code == 200
    initial_payload = initial.json()
    assert any(item["source"] == "system" for item in initial_payload["items"])

    created = await authed_client.post(
        f"/surrogates/{surrogate.id}/email-contacts",
        json={
            "email": "clinic@example.com",
            "label": "Clinic",
            "contact_type": "clinic",
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["source"] == "manual"
    contact_id = created_payload["id"]

    patched = await authed_client.patch(
        f"/surrogates/{surrogate.id}/email-contacts/{contact_id}",
        json={
            "label": "Primary Clinic",
            "contact_type": "provider",
        },
    )
    assert patched.status_code == 200
    patched_payload = patched.json()
    assert patched_payload["label"] == "Primary Clinic"
    assert patched_payload["contact_type"] == "provider"

    removed = await authed_client.delete(f"/surrogates/{surrogate.id}/email-contacts/{contact_id}")
    assert removed.status_code == 200
    assert removed.json()["success"] is True

    final_list = await authed_client.get(f"/surrogates/{surrogate.id}/email-contacts")
    assert final_list.status_code == 200
    final_payload = final_list.json()
    manual = next(item for item in final_payload["items"] if item["id"] == contact_id)
    assert manual["is_active"] is False


@pytest.mark.asyncio
async def test_internal_gmail_sync_scheduler_requires_secret(client: AsyncClient, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "INTERNAL_SECRET", "internal-secret-test")

    forbidden = await client.post(
        "/internal/scheduled/gmail-sync",
        headers={"x-internal-secret": "wrong-secret"},
    )
    assert forbidden.status_code == 403

    ok = await client.post(
        "/internal/scheduled/gmail-sync",
        headers={"x-internal-secret": "internal-secret-test"},
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert "mailboxes_checked" in payload
    assert "jobs_created" in payload
    assert "duplicates_skipped" in payload
