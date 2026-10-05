from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def gmail_push(client, monkeypatch):
    from app.core import gmail_push_auth
    from app.core.config import settings

    monkeypatch.setattr(settings, "GMAIL_PUSH_AUDIENCE", "https://test/webhooks/google-gmail")
    monkeypatch.setattr(
        settings, "GMAIL_PUSH_SERVICE_ACCOUNT_EMAIL", "push@test.iam.gserviceaccount.com"
    )
    monkeypatch.setattr(
        settings, "GMAIL_PUSH_SUBSCRIPTION", "projects/test-project/subscriptions/gmail-push"
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public_jwk.update(kid="google-test-key", use="sig", alg="RS256")
    keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=5)
    monkeypatch.setattr(keys, "fetch_data", lambda: {"keys": [public_jwk]})
    monkeypatch.setattr(gmail_push_auth, "_google_keys", keys)

    def authenticate(*, claims=None, signing_key=None):
        now = int(datetime.now(UTC).timestamp())
        payload = {
            "iss": "https://accounts.google.com",
            "aud": settings.GMAIL_PUSH_AUDIENCE,
            "iat": now,
            "exp": now + 3600,
            "sub": "123456789",
            "email": settings.GMAIL_PUSH_SERVICE_ACCOUNT_EMAIL,
            "email_verified": True,
        }
        payload.update(claims or {})
        token = jwt.encode(
            payload, signing_key or key, algorithm="RS256", headers={"kid": "google-test-key"}
        )
        client.headers["Authorization"] = f"Bearer {token}"

    authenticate()
    return authenticate


@pytest.mark.asyncio
async def test_google_gmail_push_webhook_requires_authentication(client, db):
    from app.db.models import Job

    response = await client.post(
        "/webhooks/google-gmail",
        json=_push_payload(message_id="unauthorized", email_address="journal@example.com"),
    )

    assert response.status_code == 503
    assert db.query(Job).count() == 0


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
async def test_google_gmail_push_webhook_enqueues_mailbox_history_sync(
    client, db, test_auth, gmail_push
):
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
async def test_google_gmail_push_webhook_dedupes_same_mailbox_sync_job(
    client, db, test_auth, gmail_push
):
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
async def test_google_gmail_push_webhook_ignores_unknown_mailbox(client, db, gmail_push):
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims,expected_status",
    [
        ({"aud": "https://different.example/webhooks/google-gmail"}, 401),
        ({"iss": "https://untrusted.example"}, 401),
        ({"exp": 1}, 401),
        ({"iat": 9999999999}, 401),
        ({"email": "other@test.iam.gserviceaccount.com"}, 403),
        ({"email_verified": False}, 403),
        ({"email_verified": "true"}, 403),
    ],
)
async def test_google_gmail_push_rejects_invalid_identity(
    client, db, gmail_push, claims, expected_status
):
    from app.db.models import Job

    gmail_push(claims=claims)
    response = await client.post(
        "/webhooks/google-gmail",
        json=_push_payload(message_id="denied", email_address="journal@example.com"),
    )
    assert response.status_code == expected_status
    assert db.query(Job).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("credential", ["missing", "forged_signature"])
async def test_google_gmail_push_rejects_untrusted_tokens(client, db, gmail_push, credential):
    from app.db.models import Job

    if credential == "missing":
        del client.headers["Authorization"]
    else:
        gmail_push(signing_key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
    response = await client.post(
        "/webhooks/google-gmail",
        json=_push_payload(message_id="denied", email_address="journal@example.com"),
    )
    assert response.status_code == 401
    assert db.query(Job).count() == 0


@pytest.mark.asyncio
async def test_google_gmail_push_rejects_other_subscription(client, db, gmail_push):
    from app.db.models import Job

    payload = _push_payload(message_id="wrong-subscription", email_address="journal@example.com")
    payload["subscription"] = "projects/other-project/subscriptions/gmail-push"
    response = await client.post("/webhooks/google-gmail", json=payload)
    assert response.status_code == 403
    assert db.query(Job).count() == 0


@pytest.mark.asyncio
async def test_google_gmail_push_key_outage_can_retry(client, db, gmail_push, monkeypatch):
    from app.core import gmail_push_auth
    from app.db.models import Job

    fetch_keys = gmail_push_auth._google_keys.fetch_data

    def unavailable():
        raise jwt.PyJWKClientConnectionError("provider details must not be exposed")

    monkeypatch.setattr(gmail_push_auth._google_keys, "fetch_data", unavailable)
    payload = _push_payload(message_id="retry", email_address="journal@example.com")
    first = await client.post("/webhooks/google-gmail", json=payload)
    assert first.status_code == 503
    assert first.json() == {"detail": "Gmail push verification unavailable"}
    assert db.query(Job).count() == 0

    monkeypatch.setattr(gmail_push_auth._google_keys, "fetch_data", fetch_keys)
    second = await client.post("/webhooks/google-gmail", json=payload)
    assert second.status_code == 202


@pytest.mark.asyncio
async def test_google_gmail_push_uses_matched_mailbox_scope(client, db, test_org, gmail_push):
    from app.db.enums import MailboxKind, MailboxProvider
    from app.db.models import Job, Mailbox, Organization

    other_org = Organization(
        id=uuid.uuid4(), name="Other agency", slug=f"other-{uuid.uuid4().hex[:8]}"
    )
    db.add(other_org)
    db.flush()
    for org, email in [(test_org, "first@example.com"), (other_org, "second@example.com")]:
        db.add(
            Mailbox(
                id=uuid.uuid4(),
                organization_id=org.id,
                kind=MailboxKind.JOURNAL,
                provider=MailboxProvider.GMAIL,
                email_address=email,
                is_enabled=True,
            )
        )
    db.commit()
    payload = _push_payload(message_id="scope", email_address="first@example.com")
    payload["organization_id"] = str(other_org.id)
    response = await client.post("/webhooks/google-gmail", json=payload)
    assert response.status_code == 202
    jobs = db.query(Job).all()
    assert len(jobs) == 1
    assert jobs[0].organization_id == test_org.id
    assert jobs[0].payload["organization_id"] == str(test_org.id)
