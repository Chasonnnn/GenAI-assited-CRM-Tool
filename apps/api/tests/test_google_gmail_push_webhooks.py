from __future__ import annotations

import base64
import json
import uuid

import pytest


def _push_payload(
    *,
    message_id: str,
    email_address: str,
    history_id: str = "12345",
) -> dict:
    message = {"emailAddress": email_address, "historyId": history_id}
    encoded = base64.b64encode(json.dumps(message).encode("utf-8")).decode("utf-8")
    return {
        "message": {
            "data": encoded,
            "messageId": message_id,
        },
        "subscription": "projects/test-project/subscriptions/gmail-push",
    }


@pytest.mark.asyncio
async def test_google_gmail_push_webhook_enqueues_mailbox_history_sync(client, db, test_auth):
    from app.db.enums import JobType, MailboxKind, MailboxProvider
    from app.db.models import Job, Mailbox

    mailbox = Mailbox(
        id=uuid.uuid4(),
        organization_id=test_auth.org.id,
        kind=MailboxKind.JOURNAL,
        provider=MailboxProvider.GMAIL,
        email_address="journal@example.com",
        is_enabled=True,
    )
    db.add(mailbox)
    db.commit()

    response = await client.post(
        "/webhooks/google-gmail",
        json=_push_payload(
            message_id="pubsub-msg-1",
            email_address="journal@example.com",
            history_id="99999",
        ),
    )
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    jobs = db.query(Job).filter(Job.job_type == JobType.MAILBOX_HISTORY_SYNC.value).all()
    assert len(jobs) == 1
    assert jobs[0].payload["mailbox_id"] == str(mailbox.id)
    assert jobs[0].payload["reason"] == "gmail_push"
    assert jobs[0].payload["pubsub_message_id"] == "pubsub-msg-1"
    assert jobs[0].payload["gmail_push_history_id"] == 99999


@pytest.mark.asyncio
async def test_google_gmail_push_webhook_dedupes_same_mailbox_sync_job(client, db, test_auth):
    from app.db.enums import JobType, MailboxKind, MailboxProvider
    from app.db.models import Job, Mailbox

    db.add(
        Mailbox(
            id=uuid.uuid4(),
            organization_id=test_auth.org.id,
            kind=MailboxKind.JOURNAL,
            provider=MailboxProvider.GMAIL,
            email_address="journal-dedupe@example.com",
            is_enabled=True,
        )
    )
    db.commit()

    payload = _push_payload(
        message_id="pubsub-msg-2",
        email_address="journal-dedupe@example.com",
        history_id="10001",
    )

    first = await client.post("/webhooks/google-gmail", json=payload)
    second = await client.post("/webhooks/google-gmail", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202

    jobs = db.query(Job).filter(Job.job_type == JobType.MAILBOX_HISTORY_SYNC.value).all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_google_gmail_push_webhook_ignores_unknown_mailbox(client, db):
    from app.db.enums import JobType
    from app.db.models import Job

    response = await client.post(
        "/webhooks/google-gmail",
        json=_push_payload(
            message_id="pubsub-msg-3",
            email_address="does-not-exist@example.com",
        ),
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"

    jobs = db.query(Job).filter(Job.job_type == JobType.MAILBOX_HISTORY_SYNC.value).all()
    assert jobs == []
