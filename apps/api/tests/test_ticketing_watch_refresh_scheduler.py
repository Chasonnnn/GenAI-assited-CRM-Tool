from __future__ import annotations

import uuid

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
