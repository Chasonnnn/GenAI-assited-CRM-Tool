import hmac
import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db.models import Appointment
from app.db.enums import AppointmentStatus
from app.core.config import settings


def _sign_zoom(secret: str, timestamp: str, body: str) -> str:
    msg = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _encrypt_plain_token(secret: str, plain_token: str) -> str:
    return hmac.new(secret.encode(), plain_token.encode(), hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_zoom_webhook_url_validation(client, monkeypatch):
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    payload = {
        "event": "endpoint.url_validation",
        "payload": {"plainToken": "plain-token-123"},
    }
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    signature = _sign_zoom(secret, timestamp, body)

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["plainToken"] == "plain-token-123"
    assert data["encryptedToken"] == _encrypt_plain_token(secret, "plain-token-123")


@pytest.mark.asyncio
async def test_zoom_webhook_rejects_bad_signature(client, monkeypatch):
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    payload = {"event": "meeting.started", "payload": {"object": {"id": 123}}}
    body = json.dumps(payload)
    timestamp = str(int(time.time()))

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": "v0=bad",
        },
    )

    assert res.status_code == 403


@pytest.mark.asyncio
async def test_zoom_webhook_meeting_started_sets_timestamp(
    client, db, test_org, test_user, monkeypatch
):
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        client_name="Test Client",
        client_email="client@example.com",
        client_phone="555-111-2222",
        client_timezone="America/New_York",
        scheduled_start=datetime.now(timezone.utc),
        scheduled_end=datetime.now(timezone.utc),
        duration_minutes=30,
        meeting_mode="zoom",
        status=AppointmentStatus.CONFIRMED.value,
        zoom_meeting_id="123456789",
        reschedule_token="r",
        cancel_token="c",
    )
    db.add(appt)
    db.flush()

    payload = {
        "event": "meeting.started",
        "event_ts": "evt_started_1",
        "payload": {"object": {"id": 123456789}},
    }
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    signature = _sign_zoom(secret, timestamp, body)

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )

    assert res.status_code == 200
    db.refresh(appt)
    assert appt.meeting_started_at is not None


@pytest.mark.asyncio
async def test_zoom_webhook_meeting_ended_sets_timestamp(
    client, db, test_org, test_user, monkeypatch
):
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        client_name="Test Client",
        client_email="client@example.com",
        client_phone="555-111-2222",
        client_timezone="America/New_York",
        scheduled_start=datetime.now(timezone.utc),
        scheduled_end=datetime.now(timezone.utc),
        duration_minutes=30,
        meeting_mode="zoom",
        status=AppointmentStatus.CONFIRMED.value,
        zoom_meeting_id="123456789",
        reschedule_token="r",
        cancel_token="c",
    )
    db.add(appt)
    db.flush()

    payload = {
        "event": "meeting.ended",
        "event_ts": "evt_ended_1",
        "payload": {"object": {"id": 123456789}},
    }
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    signature = _sign_zoom(secret, timestamp, body)

    res = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )

    assert res.status_code == 200
    db.refresh(appt)
    assert appt.meeting_ended_at is not None


@pytest.mark.asyncio
async def test_zoom_webhook_dedupes_event_id(client, db, test_org, test_user, monkeypatch):
    secret = "test-zoom-secret"
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET", secret, raising=False)

    appt = Appointment(
        id=uuid4(),
        organization_id=test_org.id,
        user_id=test_user.id,
        client_name="Test Client",
        client_email="client@example.com",
        client_phone="555-111-2222",
        client_timezone="America/New_York",
        scheduled_start=datetime.now(timezone.utc),
        scheduled_end=datetime.now(timezone.utc),
        duration_minutes=30,
        meeting_mode="zoom",
        status=AppointmentStatus.CONFIRMED.value,
        zoom_meeting_id="123456789",
        reschedule_token="r",
        cancel_token="c",
    )
    db.add(appt)
    db.flush()

    payload = {
        "event": "meeting.started",
        "event_ts": "evt_dup_1",
        "payload": {"object": {"id": 123456789}},
    }
    body = json.dumps(payload)
    timestamp = str(int(time.time()))
    signature = _sign_zoom(secret, timestamp, body)

    res1 = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )
    res2 = await client.post(
        "/webhooks/zoom",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-zm-request-timestamp": timestamp,
            "x-zm-signature": signature,
        },
    )

    assert res1.status_code == 200
    assert res2.status_code == 200
