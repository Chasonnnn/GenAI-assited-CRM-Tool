"""Sync schedulers that scan every organization.

The scheduler counts include rows from every organization, so these tests run
serially: a parallel worker that commits a mailbox, binding, or job changes them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.db.enums import JobType
from app.db.models import CalendarBinding, Job, UserIntegration
from app.services import ticketing_service
from tests.test_ticketing_watch_refresh_scheduler import _make_mailbox


@pytest.fixture
def binding(db, test_org, test_user, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULING_V2_ENABLED", True)
    integration = UserIntegration(
        user_id=test_user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="scheduler@example.com",
    )
    db.add(integration)
    db.flush()
    binding = CalendarBinding(
        organization_id=test_org.id,
        user_id=test_user.id,
        integration_id=integration.id,
        account_email=integration.account_email,
        calendar_id="team-calendar",
        display_name="Team Calendar",
        access_role="owner",
        check_busy=True,
        show_events=True,
        write_bookings=True,
        is_active=True,
    )
    db.add(binding)
    db.commit()
    return binding


def test_schedule_incremental_sync_jobs_enqueues_watch_refresh_when_due(db, test_org, monkeypatch):
    _make_mailbox(db, org_id=test_org.id, email_address="watch-due@example.com")

    monkeypatch.setattr(settings, "GMAIL_PUSH_TOPIC", "projects/test/topics/gmail")
    monkeypatch.setattr(settings, "GMAIL_PUSH_LABEL_IDS", "INBOX")

    counts = ticketing_service.schedule_incremental_sync_jobs(db)

    assert counts["mailboxes_checked"] == 1
    assert counts["jobs_created"] == 1
    assert counts["watch_jobs_created"] == 1

    job_types = [row.job_type for row in db.query(Job).filter(Job.organization_id == test_org.id)]
    assert JobType.MAILBOX_HISTORY_SYNC.value in job_types
    assert JobType.MAILBOX_WATCH_REFRESH.value in job_types


def test_schedule_incremental_sync_jobs_skips_watch_refresh_when_fresh(db, test_org, monkeypatch):
    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="watch-fresh@example.com")
    mailbox.gmail_watch_expiration_at = datetime.now(UTC) + timedelta(days=2)
    db.add(mailbox)
    db.commit()

    monkeypatch.setattr(settings, "GMAIL_PUSH_TOPIC", "projects/test/topics/gmail")
    monkeypatch.setattr(settings, "GMAIL_PUSH_LABEL_IDS", "")

    counts = ticketing_service.schedule_incremental_sync_jobs(db)
    assert counts["watch_jobs_created"] == 0

    job_types = [row.job_type for row in db.query(Job).filter(Job.organization_id == test_org.id)]
    assert JobType.MAILBOX_HISTORY_SYNC.value in job_types
    assert JobType.MAILBOX_WATCH_REFRESH.value not in job_types


def test_v2_scheduler_queues_explicit_binding_sync_and_retains_tasks(db, binding):
    from app.services import google_calendar_sync_service

    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    counts = google_calendar_sync_service.schedule_google_calendar_sync_jobs(db, now=now)
    jobs = db.query(Job).filter(Job.organization_id == binding.organization_id).all()

    assert counts == {
        "connected_users": 1,
        "jobs_created": 1,
        "duplicates_skipped": 0,
        "task_jobs_created": 1,
        "task_duplicates_skipped": 0,
        "watch_jobs_created": 1,
        "watch_duplicates_skipped": 0,
    }
    assert {
        (job.job_type, job.payload.get("binding_id"))
        for job in jobs
        if job.job_type
        in {JobType.GOOGLE_CALENDAR_SYNC.value, JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value}
    } == {
        (JobType.GOOGLE_CALENDAR_SYNC.value, str(binding.id)),
        (JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value, str(binding.id)),
    }
    task = next(job for job in jobs if job.job_type == JobType.GOOGLE_TASKS_SYNC.value)
    assert task.payload == {"user_id": str(binding.user_id)}

    duplicate_counts = google_calendar_sync_service.schedule_google_calendar_sync_jobs(db, now=now)
    assert duplicate_counts["jobs_created"] == 0
    assert duplicate_counts["duplicates_skipped"] == 1
    assert duplicate_counts["watch_jobs_created"] == 0
    assert duplicate_counts["watch_duplicates_skipped"] == 1
    assert duplicate_counts["task_jobs_created"] == 0
    assert duplicate_counts["task_duplicates_skipped"] == 1
