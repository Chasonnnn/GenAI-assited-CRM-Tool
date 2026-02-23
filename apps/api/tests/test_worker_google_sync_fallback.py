from datetime import datetime, timedelta, timezone


def test_maybe_schedule_google_calendar_sync_jobs_calls_scheduler_when_due(db, monkeypatch):
    from app import worker
    from app.services import google_calendar_sync_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    called: list[datetime] = []

    def fake_schedule_google_calendar_sync_jobs(*, db, now):
        called.append(now)
        return {
            "connected_users": 1,
            "jobs_created": 1,
            "duplicates_skipped": 0,
            "task_jobs_created": 1,
            "task_duplicates_skipped": 0,
            "watch_jobs_created": 1,
            "watch_duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "GOOGLE_CALENDAR_SYNC_FALLBACK_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(
        google_calendar_sync_service,
        "schedule_google_calendar_sync_jobs",
        fake_schedule_google_calendar_sync_jobs,
    )

    last = worker.maybe_schedule_google_calendar_sync_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    assert last == now
    assert called == [now]


def test_maybe_schedule_google_calendar_sync_jobs_skips_when_not_due(db, monkeypatch):
    from app import worker
    from app.services import google_calendar_sync_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    last_run_at = now - timedelta(seconds=120)
    called = False

    def fake_schedule_google_calendar_sync_jobs(*, db, now):
        nonlocal called
        called = True
        return {
            "connected_users": 1,
            "jobs_created": 1,
            "duplicates_skipped": 0,
            "task_jobs_created": 1,
            "task_duplicates_skipped": 0,
            "watch_jobs_created": 1,
            "watch_duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "GOOGLE_CALENDAR_SYNC_FALLBACK_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(
        google_calendar_sync_service,
        "schedule_google_calendar_sync_jobs",
        fake_schedule_google_calendar_sync_jobs,
    )

    last = worker.maybe_schedule_google_calendar_sync_jobs(
        db,
        now=now,
        last_run_at=last_run_at,
    )

    assert last == last_run_at
    assert called is False


def test_maybe_schedule_google_calendar_sync_jobs_noop_when_disabled(db, monkeypatch):
    from app import worker
    from app.services import google_calendar_sync_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    last_run_at = now - timedelta(minutes=10)
    called = False

    def fake_schedule_google_calendar_sync_jobs(*, db, now):
        nonlocal called
        called = True
        return {
            "connected_users": 1,
            "jobs_created": 1,
            "duplicates_skipped": 0,
            "task_jobs_created": 1,
            "task_duplicates_skipped": 0,
            "watch_jobs_created": 1,
            "watch_duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED", False)
    monkeypatch.setattr(
        google_calendar_sync_service,
        "schedule_google_calendar_sync_jobs",
        fake_schedule_google_calendar_sync_jobs,
    )

    last = worker.maybe_schedule_google_calendar_sync_jobs(
        db,
        now=now,
        last_run_at=last_run_at,
    )

    assert last == last_run_at
    assert called is False


def test_maybe_schedule_gmail_sync_jobs_calls_scheduler_when_due(db, monkeypatch):
    from app import worker
    from app.services import ticketing_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    called: list[datetime] = []

    def fake_schedule_incremental_sync_jobs(db):
        _ = db
        called.append(now)
        return {
            "mailboxes_checked": 2,
            "jobs_created": 2,
            "duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GMAIL_SYNC_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "GMAIL_SYNC_FALLBACK_INTERVAL_SECONDS", 60)
    monkeypatch.setattr(
        ticketing_service,
        "schedule_incremental_sync_jobs",
        fake_schedule_incremental_sync_jobs,
    )

    last = worker.maybe_schedule_gmail_sync_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    assert last == now
    assert called == [now]


def test_maybe_schedule_gmail_sync_jobs_skips_when_not_due(db, monkeypatch):
    from app import worker
    from app.services import ticketing_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    last_run_at = now - timedelta(seconds=30)
    called = False

    def fake_schedule_incremental_sync_jobs(db):
        _ = db
        nonlocal called
        called = True
        return {
            "mailboxes_checked": 1,
            "jobs_created": 1,
            "duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GMAIL_SYNC_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "GMAIL_SYNC_FALLBACK_INTERVAL_SECONDS", 60)
    monkeypatch.setattr(
        ticketing_service,
        "schedule_incremental_sync_jobs",
        fake_schedule_incremental_sync_jobs,
    )

    last = worker.maybe_schedule_gmail_sync_jobs(
        db,
        now=now,
        last_run_at=last_run_at,
    )

    assert last == last_run_at
    assert called is False


def test_maybe_schedule_gmail_sync_jobs_noop_when_disabled(db, monkeypatch):
    from app import worker
    from app.services import ticketing_service

    now = datetime(2026, 2, 20, 15, 0, tzinfo=timezone.utc)
    last_run_at = now - timedelta(minutes=5)
    called = False

    def fake_schedule_incremental_sync_jobs(db):
        _ = db
        nonlocal called
        called = True
        return {
            "mailboxes_checked": 1,
            "jobs_created": 1,
            "duplicates_skipped": 0,
        }

    monkeypatch.setattr(worker, "GMAIL_SYNC_FALLBACK_ENABLED", False)
    monkeypatch.setattr(
        ticketing_service,
        "schedule_incremental_sync_jobs",
        fake_schedule_incremental_sync_jobs,
    )

    last = worker.maybe_schedule_gmail_sync_jobs(
        db,
        now=now,
        last_run_at=last_run_at,
    )

    assert last == last_run_at
    assert called is False
