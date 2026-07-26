from datetime import datetime, timedelta, timezone

import pytest


def test_dormant_workflow_maintenance_fallbacks_are_opt_in():
    from app import worker

    assert worker.WORKFLOW_MAINTENANCE_FALLBACK_ENABLED is False
    assert worker.WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED is False


@pytest.mark.parametrize(
    ("function_name", "flag_name"),
    [
        ("maybe_schedule_workflow_sweep_jobs", "WORKFLOW_SWEEP_FALLBACK_ENABLED"),
        (
            "maybe_schedule_workflow_maintenance_jobs",
            "WORKFLOW_MAINTENANCE_FALLBACK_ENABLED",
        ),
        (
            "maybe_schedule_workflow_approval_expiry_jobs",
            "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED",
        ),
    ],
)
def test_workflow_fallback_schedulers_noop_when_disabled(db, monkeypatch, function_name, flag_name):
    from app import worker

    now = datetime(2026, 7, 26, 9, 1, tzinfo=timezone.utc)
    last_run_at = now - timedelta(hours=1)
    monkeypatch.setattr(worker, flag_name, False)

    result = getattr(worker, function_name)(
        db,
        now=now,
        last_run_at=last_run_at,
    )

    assert result == last_run_at


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


def test_maybe_schedule_workflow_sweep_jobs_enqueues_each_org_when_due(db, test_org, monkeypatch):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import AutomationWorkflow, Job

    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Due schedule",
        trigger_type="scheduled",
        trigger_config={"cron": "1 9 * * *", "timezone": "UTC"},
        actions=[],
        is_enabled=True,
    )
    db.add(workflow)
    db.commit()

    now = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_ENABLED", True, raising=False)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_INTERVAL_SECONDS", 60, raising=False)

    last = worker.maybe_schedule_workflow_sweep_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    job = db.scalar(
        select(Job).where(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_SWEEP.value,
        )
    )
    assert last == now
    assert job is not None
    assert job.payload == {
        "org_id": str(test_org.id),
        "sweep_type": "scheduled",
        "evaluated_at": now.isoformat(),
    }
    assert job.idempotency_key == f"workflow-sweep:scheduled:{test_org.id}:20260726T0901Z"


def test_maybe_schedule_workflow_sweep_jobs_skips_org_without_a_due_cron(db, test_org, monkeypatch):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import AutomationWorkflow, Job

    workflow = AutomationWorkflow(
        organization_id=test_org.id,
        name="Not due schedule",
        trigger_type="scheduled",
        trigger_config={"cron": "2 9 * * *", "timezone": "UTC"},
        actions=[],
        is_enabled=True,
    )
    db.add(workflow)
    db.commit()

    now = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_INTERVAL_SECONDS", 60)

    last = worker.maybe_schedule_workflow_sweep_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    job = db.scalar(
        select(Job).where(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_SWEEP.value,
        )
    )
    assert last == now
    assert job is None


def test_workflow_sweep_fallback_is_idempotent_per_minute_and_advances_buckets(
    db, test_org, monkeypatch
):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import AutomationWorkflow, Job

    db.add(
        AutomationWorkflow(
            organization_id=test_org.id,
            name="Every minute schedule",
            trigger_type="scheduled",
            trigger_config={"cron": "* * * * *", "timezone": "UTC"},
            actions=[],
            is_enabled=True,
        )
    )
    db.commit()

    now = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "WORKFLOW_SWEEP_FALLBACK_INTERVAL_SECONDS", 60)

    worker.maybe_schedule_workflow_sweep_jobs(db, now=now, last_run_at=None)
    worker.maybe_schedule_workflow_sweep_jobs(db, now=now, last_run_at=None)
    worker.maybe_schedule_workflow_sweep_jobs(
        db,
        now=now + timedelta(minutes=1),
        last_run_at=None,
    )

    keys = list(
        db.scalars(
            select(Job.idempotency_key)
            .where(
                Job.organization_id == test_org.id,
                Job.job_type == JobType.WORKFLOW_SWEEP.value,
            )
            .order_by(Job.idempotency_key)
        )
    )
    assert keys == [
        f"workflow-sweep:scheduled:{test_org.id}:20260726T0901Z",
        f"workflow-sweep:scheduled:{test_org.id}:20260726T0902Z",
    ]


def test_maybe_schedule_workflow_maintenance_jobs_enqueues_hourly_sweeps(db, test_org, monkeypatch):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import AutomationWorkflow, Job

    db.add_all(
        [
            AutomationWorkflow(
                organization_id=test_org.id,
                name=f"{sweep_type} workflow",
                trigger_type=sweep_type,
                trigger_config={},
                actions=[],
                is_enabled=True,
            )
            for sweep_type in ("inactivity", "task_due", "task_overdue")
        ]
    )
    db.commit()

    now = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_MAINTENANCE_FALLBACK_ENABLED", True, raising=False)
    monkeypatch.setattr(
        worker,
        "WORKFLOW_MAINTENANCE_FALLBACK_INTERVAL_SECONDS",
        3600,
        raising=False,
    )

    last = worker.maybe_schedule_workflow_maintenance_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    jobs = list(
        db.scalars(
            select(Job)
            .where(
                Job.organization_id == test_org.id,
                Job.job_type == JobType.WORKFLOW_SWEEP.value,
            )
            .order_by(Job.idempotency_key)
        )
    )
    assert last == now
    assert [job.payload["sweep_type"] for job in jobs] == [
        "inactivity",
        "task_due",
        "task_overdue",
    ]
    assert [job.idempotency_key for job in jobs] == [
        f"workflow-sweep:inactivity:{test_org.id}:20260726",
        f"workflow-sweep:task_due:{test_org.id}:20260726T09Z",
        f"workflow-sweep:task_overdue:{test_org.id}:20260726",
    ]


def test_maybe_schedule_workflow_maintenance_jobs_skips_unconfigured_types(
    db, test_org, monkeypatch
):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import Job

    now = datetime(2026, 7, 26, 9, 1, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_MAINTENANCE_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "WORKFLOW_MAINTENANCE_FALLBACK_INTERVAL_SECONDS", 3600)

    last = worker.maybe_schedule_workflow_maintenance_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    jobs = list(
        db.scalars(
            select(Job).where(
                Job.organization_id == test_org.id,
                Job.job_type == JobType.WORKFLOW_SWEEP.value,
            )
        )
    )
    assert last == now
    assert jobs == []


def test_maybe_schedule_workflow_approval_expiry_jobs_enqueues_each_org_when_due(
    db, test_org, test_user, monkeypatch
):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType, OwnerType, TaskStatus, TaskType
    from app.db.models import Job, Task

    now = datetime(2026, 7, 26, 9, 3, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(
        worker,
        "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        worker,
        "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_INTERVAL_SECONDS",
        300,
        raising=False,
    )
    db.add(
        Task(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            owner_type=OwnerType.USER.value,
            owner_id=test_user.id,
            title="Approve workflow",
            task_type=TaskType.WORKFLOW_APPROVAL.value,
            status=TaskStatus.PENDING.value,
            due_at=now - timedelta(minutes=1),
        )
    )
    db.commit()

    last = worker.maybe_schedule_workflow_approval_expiry_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    job = db.scalar(
        select(Job).where(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_APPROVAL_EXPIRY.value,
        )
    )
    assert last == now
    assert job is not None
    assert job.payload == {"org_id": str(test_org.id)}
    assert job.idempotency_key == f"workflow-approval-expiry:{test_org.id}:20260726T0900Z"


def test_maybe_schedule_workflow_approval_expiry_jobs_skips_org_without_due_tasks(
    db, test_org, monkeypatch
):
    from sqlalchemy import select

    from app import worker
    from app.db.enums import JobType
    from app.db.models import Job

    now = datetime(2026, 7, 26, 9, 3, 37, tzinfo=timezone.utc)
    monkeypatch.setattr(worker, "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_ENABLED", True)
    monkeypatch.setattr(worker, "WORKFLOW_APPROVAL_EXPIRY_FALLBACK_INTERVAL_SECONDS", 300)

    last = worker.maybe_schedule_workflow_approval_expiry_jobs(
        db,
        now=now,
        last_run_at=None,
    )

    job = db.scalar(
        select(Job).where(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.WORKFLOW_APPROVAL_EXPIRY.value,
        )
    )
    assert last == now
    assert job is None
