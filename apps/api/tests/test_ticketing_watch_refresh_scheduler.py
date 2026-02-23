from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.services import ticketing_service


def _make_mailbox(db, *, org_id, email_address: str):
    from app.db.enums import MailboxKind, MailboxProvider
    from app.db.models import Mailbox

    mailbox = Mailbox(
        id=uuid.uuid4(),
        organization_id=org_id,
        kind=MailboxKind.JOURNAL,
        provider=MailboxProvider.GMAIL,
        email_address=email_address,
        is_enabled=True,
    )
    db.add(mailbox)
    db.commit()
    return mailbox


def test_schedule_incremental_sync_jobs_enqueues_watch_refresh_when_due(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.db.enums import JobType
    from app.db.models import Job

    _make_mailbox(db, org_id=test_org.id, email_address="watch-due@example.com")

    monkeypatch.setattr(settings, "GMAIL_PUSH_TOPIC", "projects/test/topics/gmail")
    monkeypatch.setattr(settings, "GMAIL_PUSH_LABEL_IDS", "INBOX")

    counts = ticketing_service.schedule_incremental_sync_jobs(db)

    assert counts["mailboxes_checked"] == 1
    assert counts["jobs_created"] == 1
    assert counts["watch_jobs_created"] == 1

    job_types = [row.job_type for row in db.query(Job).all()]
    assert JobType.MAILBOX_HISTORY_SYNC.value in job_types
    assert JobType.MAILBOX_WATCH_REFRESH.value in job_types


def test_schedule_incremental_sync_jobs_skips_watch_refresh_when_fresh(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.db.enums import JobType
    from app.db.models import Job

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="watch-fresh@example.com")
    mailbox.gmail_watch_expiration_at = datetime.now(timezone.utc) + timedelta(days=2)
    db.add(mailbox)
    db.commit()

    monkeypatch.setattr(settings, "GMAIL_PUSH_TOPIC", "projects/test/topics/gmail")
    monkeypatch.setattr(settings, "GMAIL_PUSH_LABEL_IDS", "")

    counts = ticketing_service.schedule_incremental_sync_jobs(db)
    assert counts["watch_jobs_created"] == 0

    job_types = [row.job_type for row in db.query(Job).all()]
    assert JobType.MAILBOX_HISTORY_SYNC.value in job_types
    assert JobType.MAILBOX_WATCH_REFRESH.value not in job_types


def test_enqueue_mailbox_history_sync_allows_new_run_after_completion(db, test_org):
    from app.db.enums import JobStatus, JobType
    from app.db.models import Job

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="run-scope@example.com")

    first_job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        reason="test-first-run",
    )
    assert first_job_id is not None

    first_job = db.query(Job).filter(Job.id == first_job_id).one()
    first_job.status = JobStatus.COMPLETED.value
    db.add(first_job)
    db.commit()

    second_job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        reason="test-second-run",
    )
    assert second_job_id is not None
    assert second_job_id != first_job_id

    history_sync_jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.MAILBOX_HISTORY_SYNC.value,
        )
        .all()
    )
    assert len(history_sync_jobs) == 2
