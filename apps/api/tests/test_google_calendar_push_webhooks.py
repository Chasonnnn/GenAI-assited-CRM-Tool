from __future__ import annotations

import pytest


def _push_headers(
    *,
    channel_id: str,
    resource_id: str,
    token: str,
    message_number: str = "1",
    resource_state: str = "exists",
) -> dict[str, str]:
    return {
        "X-Goog-Channel-ID": channel_id,
        "X-Goog-Resource-ID": resource_id,
        "X-Goog-Channel-Token": token,
        "X-Goog-Message-Number": message_number,
        "X-Goog-Resource-State": resource_state,
    }


@pytest.mark.asyncio
async def test_google_calendar_push_webhook_enqueues_sync_job(
    client,
    db,
    test_auth,
):
    from app.db.enums import JobType
    from app.db.models import Job, UserIntegration
    from app.services import oauth_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token",
            account_email="calendar@example.com",
            google_calendar_channel_id="chan-1",
            google_calendar_resource_id="res-1",
            google_calendar_channel_token_encrypted=oauth_service.encrypt_token("watch-token"),
        )
    )
    db.commit()

    response = await client.post(
        "/webhooks/google-calendar",
        headers=_push_headers(
            channel_id="chan-1",
            resource_id="res-1",
            token="watch-token",
            message_number="42",
        ),
    )
    assert response.status_code == 202

    jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_SYNC.value).all()
    assert len(jobs) == 1
    assert jobs[0].payload["user_id"] == str(test_auth.user.id)
    assert jobs[0].idempotency_key == "google-calendar-push:chan-1:42"


@pytest.mark.asyncio
async def test_google_calendar_push_webhook_dedupes_same_message_number(
    client,
    db,
    test_auth,
):
    from app.db.enums import JobType
    from app.db.models import Job, UserIntegration
    from app.services import oauth_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token",
            account_email="calendar@example.com",
            google_calendar_channel_id="chan-2",
            google_calendar_resource_id="res-2",
            google_calendar_channel_token_encrypted=oauth_service.encrypt_token("watch-token-2"),
        )
    )
    db.commit()

    headers = _push_headers(
        channel_id="chan-2",
        resource_id="res-2",
        token="watch-token-2",
        message_number="7",
    )

    first = await client.post("/webhooks/google-calendar", headers=headers)
    second = await client.post("/webhooks/google-calendar", headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202

    jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_SYNC.value).all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_google_calendar_push_webhook_ignores_invalid_channel_token(
    client,
    db,
    test_auth,
):
    from app.db.enums import JobType
    from app.db.models import Job, UserIntegration
    from app.services import oauth_service

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token",
            account_email="calendar@example.com",
            google_calendar_channel_id="chan-3",
            google_calendar_resource_id="res-3",
            google_calendar_channel_token_encrypted=oauth_service.encrypt_token("expected-token"),
        )
    )
    db.commit()

    response = await client.post(
        "/webhooks/google-calendar",
        headers=_push_headers(
            channel_id="chan-3",
            resource_id="res-3",
            token="wrong-token",
            message_number="99",
        ),
    )
    assert response.status_code == 202

    jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_SYNC.value).all()
    assert jobs == []
