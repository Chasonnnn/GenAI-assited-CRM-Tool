from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

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


def _multipart_email_bytes() -> bytes:
    return (
        b"From: Sender Name <sender@example.com>\r\n"
        b"To: Recipient One <one@example.com>, two@example.com\r\n"
        b"Cc: cc@example.com\r\n"
        b"Subject: Re: Hello World\r\n"
        b"Message-ID: <msg-1@example.com>\r\n"
        b"Date: Tue, 02 Jan 2024 10:00:00 +0000\r\n"
        b"Content-Type: multipart/mixed; boundary=frontier\r\n"
        b"\r\n"
        b"--frontier\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Plain body text.\r\n"
        b"--frontier\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        b"<p>HTML body text.</p>\r\n"
        b"--frontier\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=\"doc.pdf\"\r\n"
        b"\r\n"
        b"%PDF-1.4\r\n"
        b"--frontier--\r\n"
    )


def test_parse_mime_bytes_extracts_headers_bodies_and_attachments():
    parsed = ticketing_service._parse_mime_bytes(_multipart_email_bytes())

    assert parsed["subject"] == "Re: Hello World"
    assert parsed["subject_norm"] == "Hello World"
    assert parsed["from_email"] == "sender@example.com"
    assert parsed["to_emails"] == ["one@example.com", "two@example.com"]
    assert parsed["cc_emails"] == ["cc@example.com"]
    assert "Plain body text." in (parsed["body_text"] or "")
    assert "HTML body text" in (parsed["body_html"] or "")
    assert parsed["snippet"] is not None
    assert parsed["date_header"] is not None
    assert len(parsed["attachments"]) == 1
    assert parsed["attachments"][0]["filename"] == "doc.pdf"


def test_parse_mime_bytes_plain_text_fallback():
    raw = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Status Update\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Only plain text body."
    )
    parsed = ticketing_service._parse_mime_bytes(raw)
    assert parsed["body_text"] == "Only plain text body."
    assert parsed["body_html"] is None
    assert parsed["attachments"] == []


def test_outbound_header_and_idempotency_helpers():
    ticket_id = uuid4()
    headers = ticketing_service._build_reply_headers(
        ticket_id=ticket_id,
        ticket_code="T10001",
        in_reply_to="<prior@example.com>",
        references=["<ref-1@example.com>", "<ref-2@example.com>"],
    )
    assert headers["X-SF-Ticket-ID"] == str(ticket_id)
    assert headers["In-Reply-To"] == "<prior@example.com>"
    assert "<ref-1@example.com>" in headers["References"]

    assert ticketing_service._normalize_outbound_idempotency_key(None) is None
    assert ticketing_service._normalize_outbound_idempotency_key("abc") == "abc"

    long_value = "x" * 200
    normalized = ticketing_service._normalize_outbound_idempotency_key(long_value)
    assert normalized is not None
    assert len(normalized) == 64

    generated = ticketing_service._resolve_outbound_idempotency_key(None)
    assert generated.startswith("auto-")


def test_process_occurrence_parse_happy_path(db, test_org, monkeypatch):
    from app.db.enums import EmailOccurrenceState
    from app.db.models import EmailMessage, EmailMessageAttachment, EmailMessageContent, EmailMessageOccurrence, EmailRawBlob

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="parse@example.com")
    raw_bytes = _multipart_email_bytes()

    raw_blob = EmailRawBlob(
        organization_id=test_org.id,
        sha256_hex=hashlib.sha256(raw_bytes).hexdigest(),
        storage_key=f"{test_org.id}/raw.eml",
        size_bytes=len(raw_bytes),
        content_type="message/rfc822",
    )
    db.add(raw_blob)
    db.flush()

    occurrence = EmailMessageOccurrence(
        organization_id=test_org.id,
        mailbox_id=mailbox.id,
        gmail_message_id="gmail-msg-1",
        gmail_thread_id="gmail-thread-1",
        raw_blob_id=raw_blob.id,
        state=EmailOccurrenceState.DISCOVERED,
    )
    db.add(occurrence)
    db.commit()

    monkeypatch.setattr(ticketing_service.attachment_service, "load_file_bytes", lambda _key: raw_bytes)
    monkeypatch.setattr(
        ticketing_service.attachment_service,
        "store_file",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(ticketing_service, "_enqueue_mailbox_job", lambda *args, **kwargs: uuid4())

    ticketing_service.process_occurrence_parse(db, occurrence_id=occurrence.id)
    db.refresh(occurrence)

    assert occurrence.state == EmailOccurrenceState.PARSED
    assert occurrence.message_id is not None
    assert occurrence.parse_error is None
    assert occurrence.original_recipient in {"one@example.com", "two@example.com"}

    message = db.query(EmailMessage).filter(EmailMessage.id == occurrence.message_id).one()
    content = (
        db.query(EmailMessageContent)
        .filter(
            EmailMessageContent.organization_id == test_org.id,
            EmailMessageContent.message_id == message.id,
        )
        .first()
    )
    assert content is not None
    assert content.has_attachments is True

    attachment_count = (
        db.query(EmailMessageAttachment)
        .filter(
            EmailMessageAttachment.organization_id == test_org.id,
            EmailMessageAttachment.message_id == message.id,
        )
        .count()
    )
    assert attachment_count == 1


def test_process_occurrence_parse_marks_failed_without_raw_blob(db, test_org):
    from app.db.enums import EmailOccurrenceState
    from app.db.models import EmailMessageOccurrence

    mailbox = _make_mailbox(db, org_id=test_org.id, email_address="missing-raw@example.com")
    occurrence = EmailMessageOccurrence(
        organization_id=test_org.id,
        mailbox_id=mailbox.id,
        gmail_message_id="gmail-msg-missing",
        state=EmailOccurrenceState.DISCOVERED,
        raw_blob_id=None,
    )
    db.add(occurrence)
    db.commit()

    ticketing_service.process_occurrence_parse(db, occurrence_id=occurrence.id)
    db.refresh(occurrence)
    assert occurrence.state == EmailOccurrenceState.FAILED
    assert occurrence.parse_error == "missing raw_blob_id"
