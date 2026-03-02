from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services import ticketing_service


def _make_mailbox(db, *, org_id, email_address: str):
    from app.db.enums import MailboxKind, MailboxProvider
    from app.db.models import Mailbox

    mailbox = Mailbox(
        id=uuid4(),
        organization_id=org_id,
        kind=MailboxKind.JOURNAL,
        provider=MailboxProvider.GMAIL,
        email_address=email_address,
        is_enabled=True,
    )
    db.add(mailbox)
    db.commit()
    return mailbox


def test_ticketing_utility_helpers() -> None:
    normalized = ticketing_service._normalize_email_list(
        ["A@Example.com", "invalid-address", "a@example.com", ""]
    )
    assert normalized == ["a@example.com", "invalid-address"]

    assert ticketing_service._subject_norm("  Re:   Fwd:  hello  world ") == "hello world"
    assert ticketing_service._subject_norm(None) is None

    fp_a = ticketing_service._compute_fingerprint(
        subject_norm="hello",
        from_email="sender@example.com",
        to=["b@example.com", "a@example.com"],
        cc=["c@example.com"],
        rfc_message_id="<id-1@example.com>",
    )
    fp_b = ticketing_service._compute_fingerprint(
        subject_norm="hello",
        from_email="sender@example.com",
        to=["a@example.com", "b@example.com"],
        cc=["c@example.com"],
        rfc_message_id="<id-1@example.com>",
    )
    assert fp_a == fp_b

    assert ticketing_service._extract_rfc_ids("foo <a@example.com> bar <b@example.com>") == [
        "<a@example.com>",
        "<b@example.com>",
    ]


def test_ticketing_cursor_roundtrip_and_invalid() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=123456)
    row_id = uuid4()
    encoded = ticketing_service._encode_cursor(sort_ts=now, row_id=row_id)
    decoded_ts, decoded_id = ticketing_service._decode_cursor(encoded)
    assert decoded_id == row_id
    assert decoded_ts == now

    with pytest.raises(HTTPException) as exc:
        ticketing_service._decode_cursor("not-a-valid-cursor")
    assert exc.value.status_code == 400


def test_ticketing_watch_helpers(monkeypatch) -> None:
    monkeypatch.setattr(ticketing_service.settings, "GMAIL_PUSH_TOPIC", "projects/test/topics/gmail")
    monkeypatch.setattr(ticketing_service.settings, "GMAIL_PUSH_LABEL_IDS", "INBOX,UNREAD,INBOX")

    assert ticketing_service._configured_gmail_push_topic() == "projects/test/topics/gmail"
    assert ticketing_service._configured_gmail_watch_label_ids() == ["INBOX", "UNREAD"]
    assert ticketing_service._parse_int("42") == 42
    assert ticketing_service._parse_int("bad") is None

    future = datetime.now(timezone.utc) + timedelta(days=2)
    mailbox = SimpleNamespace(
        provider=SimpleNamespace(value="gmail"),
        is_enabled=True,
        gmail_watch_topic_name="projects/test/topics/gmail",
        gmail_watch_expiration_at=future,
    )
    assert ticketing_service._gmail_watch_is_due(mailbox, now=datetime.now(timezone.utc)) is False

    mailbox.gmail_watch_expiration_at = datetime.now(timezone.utc) + timedelta(hours=1)
    assert ticketing_service._gmail_watch_is_due(mailbox, now=datetime.now(timezone.utc)) is True

    assert (
        ticketing_service.integration_has_inbound_scope(
            SimpleNamespace(granted_scopes=["https://www.googleapis.com/auth/gmail.readonly"])
        )
        is True
    )
    assert ticketing_service.integration_has_inbound_scope(None) is False
    assert (
        ticketing_service.integration_has_inbound_scope(
            SimpleNamespace(granted_scopes=["https://example.com/custom.scope"])
        )
        is False
    )


def test_pause_resume_and_get_mailbox_sync_status(db, test_org):
    from app.db.enums import JobType
    from app.db.models import Job

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="mailbox-status@example.com")

    pause_until, pause_reason = ticketing_service.pause_mailbox_ingestion(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        minutes=0,
        reason=None,
    )
    assert pause_until > datetime.now(timezone.utc)
    assert "Manual pause" in pause_reason

    db.add_all(
        [
            Job(
                organization_id=test_org.id,
                job_type=JobType.MAILBOX_BACKFILL.value,
                status="pending",
                payload={"mailbox_id": str(mailbox.id)},
            ),
            Job(
                organization_id=test_org.id,
                job_type=JobType.MAILBOX_WATCH_REFRESH.value,
                status="running",
                payload={"mailbox_id": str(mailbox.id)},
            ),
        ]
    )
    db.commit()

    status = ticketing_service.get_mailbox_sync_status(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
    )
    assert status.queued_jobs_by_type[JobType.MAILBOX_BACKFILL.value] == 1
    assert status.running_jobs_by_type[JobType.MAILBOX_WATCH_REFRESH.value] == 1

    resume_job_id = ticketing_service.resume_mailbox_ingestion(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
    )
    assert resume_job_id is not None


def test_enqueue_mailbox_history_sync_dedupes_until_completion(db, test_org):
    from app.db.enums import JobStatus
    from app.db.models import Job

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="mailbox-dedupe@example.com")

    first_job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        reason="first",
    )
    assert first_job_id is not None

    second_job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        reason="second",
    )
    assert second_job_id is None

    first_job = db.query(Job).filter(Job.id == first_job_id).one()
    first_job.status = JobStatus.COMPLETED.value
    db.add(first_job)
    db.commit()

    third_job_id = ticketing_service.enqueue_mailbox_history_sync(
        db,
        org_id=test_org.id,
        mailbox_id=mailbox.id,
        reason="third",
    )
    assert third_job_id is not None
