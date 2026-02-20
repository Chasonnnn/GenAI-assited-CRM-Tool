import uuid

import pytest


@pytest.mark.asyncio
async def test_internal_google_calendar_sync_schedules_jobs_for_connected_users(
    client,
    db,
    monkeypatch,
    test_auth,
):
    from app.core.config import settings
    from app.db.enums import JobType, Role
    from app.db.models import Job, Membership, User, UserIntegration
    from app.routers import internal as internal_router

    monkeypatch.setattr(settings, "INTERNAL_SECRET", "secret")

    class _TestSession:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(internal_router, "SessionLocal", lambda: _TestSession())

    # Existing authed user with Google Calendar connected.
    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token-1",
            account_email="owner@example.com",
        )
    )

    # Another user in the same org with Google Calendar connected.
    user_2 = User(
        id=uuid.uuid4(),
        email=f"gcal-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Calendar User 2",
        token_version=1,
        is_active=True,
    )
    db.add(user_2)
    db.flush()
    db.add(
        Membership(
            id=uuid.uuid4(),
            user_id=user_2.id,
            organization_id=test_auth.org.id,
            role=Role.DEVELOPER,
            is_active=True,
        )
    )
    db.add(
        UserIntegration(
            user_id=user_2.id,
            integration_type="google_calendar",
            access_token_encrypted="token-2",
            account_email="user2@example.com",
        )
    )

    # Non-calendar integration should be ignored.
    db.add(
        UserIntegration(
            user_id=user_2.id,
            integration_type="gmail",
            access_token_encrypted="token-3",
            account_email="user2@example.com",
        )
    )
    db.commit()

    response = await client.post(
        "/internal/scheduled/google-calendar-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connected_users"] == 2
    assert data["jobs_created"] == 2
    assert data["duplicates_skipped"] == 0
    assert data["watch_jobs_created"] == 2
    assert data["watch_duplicates_skipped"] == 0
    assert data["task_jobs_created"] == 2
    assert data["task_duplicates_skipped"] == 0

    jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_SYNC.value).all()
    assert len(jobs) == 2
    payload_user_ids = {job.payload["user_id"] for job in jobs}
    assert payload_user_ids == {str(test_auth.user.id), str(user_2.id)}

    watch_jobs = (
        db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value).all()
    )
    assert len(watch_jobs) == 2

    task_jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_TASKS_SYNC.value).all()
    assert len(task_jobs) == 2


@pytest.mark.asyncio
async def test_internal_google_calendar_sync_skips_duplicate_jobs_in_same_window(
    client,
    db,
    monkeypatch,
    test_auth,
):
    from app.core.config import settings
    from app.db.enums import JobType
    from app.db.models import Job, UserIntegration
    from app.routers import internal as internal_router

    monkeypatch.setattr(settings, "INTERNAL_SECRET", "secret")

    class _TestSession:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(internal_router, "SessionLocal", lambda: _TestSession())

    db.add(
        UserIntegration(
            user_id=test_auth.user.id,
            integration_type="google_calendar",
            access_token_encrypted="token-1",
            account_email="owner@example.com",
        )
    )
    db.commit()

    first = await client.post(
        "/internal/scheduled/google-calendar-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert first.status_code == 200
    assert first.json()["jobs_created"] == 1
    assert first.json()["duplicates_skipped"] == 0
    assert first.json()["watch_jobs_created"] == 1
    assert first.json()["watch_duplicates_skipped"] == 0
    assert first.json()["task_jobs_created"] == 1
    assert first.json()["task_duplicates_skipped"] == 0

    second = await client.post(
        "/internal/scheduled/google-calendar-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert second.status_code == 200
    assert second.json()["connected_users"] == 1
    assert second.json()["jobs_created"] == 0
    assert second.json()["duplicates_skipped"] == 1
    assert second.json()["watch_jobs_created"] == 0
    assert second.json()["watch_duplicates_skipped"] == 1
    assert second.json()["task_jobs_created"] == 0
    assert second.json()["task_duplicates_skipped"] == 1

    jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_SYNC.value).all()
    assert len(jobs) == 1

    watch_jobs = (
        db.query(Job).filter(Job.job_type == JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value).all()
    )
    assert len(watch_jobs) == 1

    task_jobs = db.query(Job).filter(Job.job_type == JobType.GOOGLE_TASKS_SYNC.value).all()
    assert len(task_jobs) == 1
