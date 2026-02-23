"""Ticketing, mailbox sync, and surrogate email linking services."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.core.config import settings
from app.core.encryption import hash_email
from app.db.enums import (
    EmailDirection,
    EmailOccurrenceState,
    JobStatus,
    LinkConfidence,
    MailboxKind,
    RecipientSource,
    TicketLinkStatus,
    TicketPriority,
    TicketStatus,
    SurrogateEmailContactSource,
    JobType,
)
from app.db.models import (
    Attachment,
    EmailMessage,
    EmailMessageAttachment,
    EmailMessageContent,
    EmailMessageOccurrence,
    EmailMessageThreadRef,
    EmailRawBlob,
    Job,
    Mailbox,
    MailboxCredential,
    Membership,
    Surrogate,
    SurrogateEmailContact,
    Ticket,
    TicketEvent,
    TicketMessage,
    TicketNote,
    TicketSurrogateLinkCandidate,
    UserIntegration,
)
from app.jobs.utils import mask_email
from app.services import attachment_service, gmail_service, job_service, oauth_service
from app.utils.normalization import extract_email_domain, normalize_email

logger = logging.getLogger(__name__)

_GMAIL_MESSAGES_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_GMAIL_MESSAGE_GET_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
_GMAIL_HISTORY_URL = "https://gmail.googleapis.com/gmail/v1/users/me/history"
_GMAIL_WATCH_URL = "https://gmail.googleapis.com/gmail/v1/users/me/watch"
_GMAIL_WATCH_RENEW_BEFORE = timedelta(hours=24)

_GMAIL_INBOUND_SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
}

_REPLY_TO_TOKEN_RE = re.compile(r"^ticket\+([a-z0-9\-]+)@", re.IGNORECASE)
_RFC_ID_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TicketListPage:
    """List page result with cursor."""

    items: list[Ticket]
    next_cursor: str | None


@dataclass(frozen=True)
class MailboxSyncStatus:
    """Mailbox sync status summary."""

    mailbox_id: UUID
    is_enabled: bool
    paused_until: datetime | None
    gmail_history_id: int | None
    gmail_watch_expiration_at: datetime | None
    gmail_watch_last_renewed_at: datetime | None
    gmail_watch_topic_name: str | None
    gmail_watch_last_error: str | None
    last_full_sync_at: datetime | None
    last_incremental_sync_at: datetime | None
    last_sync_error: str | None
    queued_jobs_by_type: dict[str, int]
    running_jobs_by_type: dict[str, int]


# =============================================================================
# Utility helpers
# =============================================================================


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: str) -> str | None:
    try:
        return normalize_email(value)
    except Exception:
        return None


def _normalize_email_list(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        email = _normalize_email(value or "")
        if not email:
            continue
        if email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def _subject_norm(subject: str | None) -> str | None:
    if not subject:
        return None
    normalized = " ".join(subject.strip().split())
    lowered = normalized.lower()
    # Strip common reply prefixes repeatedly.
    while lowered.startswith(("re:", "fw:", "fwd:")):
        normalized = normalized.split(":", 1)[1].strip()
        lowered = normalized.lower()
    return normalized or None


def _encode_cursor(*, sort_ts: datetime, row_id: UUID) -> str:
    payload = {"sort_ts": sort_ts.isoformat(), "id": str(row_id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
        sort_ts = datetime.fromisoformat(payload["sort_ts"])
        row_id = UUID(payload["id"])
        if sort_ts.tzinfo is None:
            sort_ts = sort_ts.replace(tzinfo=timezone.utc)
        return sort_ts, row_id
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


def _compute_fingerprint(
    *,
    subject_norm: str | None,
    from_email: str | None,
    to: list[str],
    cc: list[str],
    rfc_message_id: str | None,
) -> str:
    payload = {
        "subject_norm": subject_norm,
        "from": (from_email or "").lower(),
        "to": sorted(email.lower() for email in to),
        "cc": sorted(email.lower() for email in cc),
        "rfc_message_id": (rfc_message_id or "").strip(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _compute_signature(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _extract_rfc_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in _RFC_ID_RE.findall(value) if v.strip()]


def _mailbox_sync_job_key(
    mailbox_id: UUID, job_type: JobType, *, run_scope: str | None = None
) -> str:
    scope = run_scope or _now_utc().strftime("%Y%m%d%H%M%S%f")
    return f"{job_type.value}:{mailbox_id}:{scope}"


def _has_active_mailbox_job(
    db: Session,
    *,
    org_id: UUID,
    mailbox_id: UUID,
    job_type: JobType,
) -> bool:
    return (
        db.query(Job.id)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == job_type.value,
            Job.payload["mailbox_id"].astext == str(mailbox_id),
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
        )
        .first()
        is not None
    )


def _enqueue_mailbox_job(
    db: Session,
    *,
    org_id: UUID,
    mailbox_id: UUID,
    job_type: JobType,
    payload: dict,
    dedupe_suffix: str | None = None,
) -> UUID | None:
    if _has_active_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=mailbox_id,
        job_type=job_type,
    ):
        return None

    idempotency_key = _mailbox_sync_job_key(mailbox_id, job_type)
    if dedupe_suffix:
        idempotency_key = f"{idempotency_key}:{dedupe_suffix}"
    try:
        job = job_service.enqueue_job(
            db=db,
            org_id=org_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            commit=False,
        )
        return job.id
    except IntegrityError:
        db.rollback()
        if _has_active_mailbox_job(
            db,
            org_id=org_id,
            mailbox_id=mailbox_id,
            job_type=job_type,
        ):
            return None
        return None


def _ensure_mailbox_belongs_to_org(db: Session, org_id: UUID, mailbox_id: UUID) -> Mailbox:
    mailbox = (
        db.query(Mailbox)
        .filter(
            Mailbox.organization_id == org_id,
            Mailbox.id == mailbox_id,
        )
        .first()
    )
    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox


def _ensure_ticket_belongs_to_org(db: Session, org_id: UUID, ticket_id: UUID) -> Ticket:
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.organization_id == org_id,
            Ticket.id == ticket_id,
        )
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _ensure_surrogate_belongs_to_org(db: Session, org_id: UUID, surrogate_id: UUID) -> Surrogate:
    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.id == surrogate_id,
        )
        .first()
    )
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    return surrogate


def _gmail_scopes_from_token_response(tokens: dict | None) -> list[str] | None:
    if not isinstance(tokens, dict):
        return None
    scope_raw = tokens.get("scope")
    if not scope_raw or not isinstance(scope_raw, str):
        return None
    scopes = [s.strip() for s in scope_raw.split(" ") if s.strip()]
    return scopes or None


# =============================================================================
# Permissions and integration readiness
# =============================================================================


def integration_has_inbound_scope(integration: UserIntegration | None) -> bool:
    """Return whether the integration has Gmail read scope required for inbound sync."""
    if integration is None:
        return False
    scopes = integration.granted_scopes or []
    if not isinstance(scopes, list):
        return False
    normalized = {str(scope).strip() for scope in scopes if str(scope).strip()}
    return bool(normalized.intersection(_GMAIL_INBOUND_SCOPES))


def _configured_gmail_push_topic() -> str | None:
    topic = (settings.GMAIL_PUSH_TOPIC or "").strip()
    return topic or None


def _configured_gmail_watch_label_ids() -> list[str]:
    labels_raw = (settings.GMAIL_PUSH_LABEL_IDS or "").strip()
    if not labels_raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in labels_raw.split(","):
        token = item.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _parse_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except Exception:
        return None


def _parse_gmail_watch_expiration(value: object | None) -> datetime | None:
    if value is None:
        return None
    try:
        millis = int(str(value))
    except Exception:
        return None
    try:
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
    except Exception:
        return None


def _gmail_watch_is_due(mailbox: Mailbox, *, now: datetime) -> bool:
    if _configured_gmail_push_topic() is None:
        return False
    provider = (
        mailbox.provider.value if hasattr(mailbox.provider, "value") else str(mailbox.provider)
    )
    if provider != "gmail":
        return False
    if not mailbox.is_enabled:
        return False
    topic = _configured_gmail_push_topic()
    if topic and mailbox.gmail_watch_topic_name and mailbox.gmail_watch_topic_name != topic:
        return True
    expiration = mailbox.gmail_watch_expiration_at
    if expiration is None:
        return True
    return expiration <= (now + _GMAIL_WATCH_RENEW_BEFORE)


# =============================================================================
# Ticket numbering
# =============================================================================


def generate_ticket_code(db: Session, org_id: UUID) -> str:
    """Generate next sequential ticket code for an org."""
    result = db.execute(
        text(
            """
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'ticket_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
            """
        ),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError("Failed to generate ticket code")
    return f"T{result:05d}"


# =============================================================================
# Ticket list/detail/query helpers
# =============================================================================


def list_tickets(
    db: Session,
    *,
    org_id: UUID,
    limit: int,
    cursor: str | None,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    queue_id: UUID | None = None,
    assignee_user_id: UUID | None = None,
    surrogate_id: UUID | None = None,
    needs_review: bool | None = None,
    q: str | None = None,
) -> TicketListPage:
    """List tickets with cursor pagination and filters."""
    page_limit = max(1, min(limit, 100))
    sort_ts = func.coalesce(Ticket.last_activity_at, Ticket.created_at)

    query = (
        db.query(Ticket, sort_ts.label("sort_ts"))
        .filter(Ticket.organization_id == org_id)
        .order_by(sort_ts.desc(), Ticket.id.desc())
        .limit(page_limit + 1)
    )

    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority_filter:
        query = query.filter(Ticket.priority == priority_filter)
    if queue_id:
        query = query.filter(Ticket.assignee_queue_id == queue_id)
    if assignee_user_id:
        query = query.filter(Ticket.assignee_user_id == assignee_user_id)
    if surrogate_id:
        query = query.filter(Ticket.surrogate_id == surrogate_id)
    if needs_review is True:
        query = query.filter(Ticket.surrogate_link_status == TicketLinkStatus.NEEDS_REVIEW.value)
    elif needs_review is False:
        query = query.filter(Ticket.surrogate_link_status != TicketLinkStatus.NEEDS_REVIEW.value)

    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Ticket.subject.ilike(search),
                Ticket.requester_email.ilike(search),
                Ticket.ticket_code.ilike(search),
            )
        )

    if cursor:
        cursor_sort_ts, cursor_id = _decode_cursor(cursor)
        query = query.filter(
            or_(
                sort_ts < cursor_sort_ts,
                and_(sort_ts == cursor_sort_ts, Ticket.id < cursor_id),
            )
        )

    rows = query.all()
    has_more = len(rows) > page_limit
    page_rows = rows[:page_limit]

    items = [ticket for ticket, _ in page_rows]

    next_cursor = None
    if has_more and page_rows:
        last_ticket, last_sort_ts = page_rows[-1]
        if last_sort_ts is None:
            last_sort_ts = last_ticket.created_at
        next_cursor = _encode_cursor(sort_ts=last_sort_ts, row_id=last_ticket.id)

    return TicketListPage(items=items, next_cursor=next_cursor)


def get_ticket_detail(db: Session, *, org_id: UUID, ticket_id: UUID) -> dict:
    """Return ticket detail payload with timeline/events/notes/candidates."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    ticket_message_rows = (
        db.query(TicketMessage)
        .filter(
            TicketMessage.organization_id == org_id,
            TicketMessage.ticket_id == ticket_id,
        )
        .order_by(TicketMessage.stitched_at.asc(), TicketMessage.id.asc())
        .all()
    )

    message_ids = [row.message_id for row in ticket_message_rows]
    messages_by_id: dict[UUID, EmailMessage] = {}
    if message_ids:
        for msg in (
            db.query(EmailMessage)
            .filter(
                EmailMessage.organization_id == org_id,
                EmailMessage.id.in_(message_ids),
            )
            .all()
        ):
            messages_by_id[msg.id] = msg

    contents_by_message: dict[UUID, EmailMessageContent] = {}
    if message_ids:
        content_rows = (
            db.query(EmailMessageContent)
            .filter(
                EmailMessageContent.organization_id == org_id,
                EmailMessageContent.message_id.in_(message_ids),
            )
            .order_by(
                EmailMessageContent.message_id.asc(),
                EmailMessageContent.content_version.desc(),
                EmailMessageContent.parsed_at.desc(),
            )
            .all()
        )
        for content in content_rows:
            if content.message_id not in contents_by_message:
                contents_by_message[content.message_id] = content

    attachments_by_message: dict[UUID, list[EmailMessageAttachment]] = {}
    if message_ids:
        attachment_rows = (
            db.query(EmailMessageAttachment)
            .filter(
                EmailMessageAttachment.organization_id == org_id,
                EmailMessageAttachment.message_id.in_(message_ids),
            )
            .order_by(EmailMessageAttachment.created_at.asc(), EmailMessageAttachment.id.asc())
            .all()
        )
        for row in attachment_rows:
            attachments_by_message.setdefault(row.message_id, []).append(row)

    occurrences_by_message: dict[UUID, list[EmailMessageOccurrence]] = {}
    if message_ids:
        occurrence_rows = (
            db.query(EmailMessageOccurrence)
            .filter(
                EmailMessageOccurrence.organization_id == org_id,
                EmailMessageOccurrence.message_id.in_(message_ids),
                EmailMessageOccurrence.ticket_id == ticket_id,
            )
            .order_by(EmailMessageOccurrence.created_at.asc(), EmailMessageOccurrence.id.asc())
            .all()
        )
        for row in occurrence_rows:
            occurrences_by_message.setdefault(row.message_id, []).append(row)

    events = (
        db.query(TicketEvent)
        .filter(
            TicketEvent.organization_id == org_id,
            TicketEvent.ticket_id == ticket_id,
        )
        .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
        .all()
    )
    notes = (
        db.query(TicketNote)
        .filter(
            TicketNote.organization_id == org_id,
            TicketNote.ticket_id == ticket_id,
        )
        .order_by(TicketNote.created_at.asc(), TicketNote.id.asc())
        .all()
    )
    candidates = (
        db.query(TicketSurrogateLinkCandidate)
        .filter(
            TicketSurrogateLinkCandidate.organization_id == org_id,
            TicketSurrogateLinkCandidate.ticket_id == ticket_id,
        )
        .order_by(
            TicketSurrogateLinkCandidate.confidence.asc(),
            TicketSurrogateLinkCandidate.created_at.asc(),
        )
        .all()
    )

    message_items: list[dict] = []
    for link in ticket_message_rows:
        message = messages_by_id.get(link.message_id)
        content = contents_by_message.get(link.message_id)
        if not message:
            continue

        message_items.append(
            {
                "id": link.id,
                "message_id": message.id,
                "direction": message.direction.value
                if hasattr(message.direction, "value")
                else str(message.direction),
                "stitched_at": link.stitched_at,
                "stitch_reason": link.stitch_reason,
                "stitch_confidence": link.stitch_confidence.value
                if hasattr(link.stitch_confidence, "value")
                else str(link.stitch_confidence),
                "rfc_message_id": message.rfc_message_id,
                "gmail_thread_id": message.gmail_thread_id,
                "date_header": content.date_header if content else None,
                "subject": content.subject if content else None,
                "from_email": content.from_email if content else None,
                "from_name": content.from_name if content else None,
                "to_emails": list(content.to_emails or []) if content else [],
                "cc_emails": list(content.cc_emails or []) if content else [],
                "reply_to_emails": list(content.reply_to_emails or []) if content else [],
                "snippet": content.snippet if content else None,
                "body_text": content.body_text if content else None,
                "body_html_sanitized": content.body_html_sanitized if content else None,
                "attachments": [
                    {
                        "id": attach.id,
                        "attachment_id": attach.attachment_id,
                        "filename": attach.filename,
                        "content_type": attach.content_type,
                        "size_bytes": int(attach.size_bytes or 0),
                        "is_inline": bool(attach.is_inline),
                        "content_id": attach.content_id,
                    }
                    for attach in attachments_by_message.get(link.message_id, [])
                ],
                "occurrences": [
                    {
                        "id": occ.id,
                        "mailbox_id": occ.mailbox_id,
                        "gmail_message_id": occ.gmail_message_id,
                        "gmail_thread_id": occ.gmail_thread_id,
                        "state": occ.state.value if hasattr(occ.state, "value") else str(occ.state),
                        "original_recipient": occ.original_recipient,
                        "original_recipient_source": occ.original_recipient_source.value
                        if hasattr(occ.original_recipient_source, "value")
                        else str(occ.original_recipient_source),
                        "original_recipient_confidence": occ.original_recipient_confidence.value
                        if hasattr(occ.original_recipient_confidence, "value")
                        else str(occ.original_recipient_confidence),
                        "original_recipient_evidence": occ.original_recipient_evidence or {},
                        "parse_error": occ.parse_error,
                        "stitch_error": occ.stitch_error,
                        "link_error": occ.link_error,
                        "created_at": occ.created_at,
                    }
                    for occ in occurrences_by_message.get(link.message_id, [])
                ],
            }
        )

    ticket_payload = {
        "id": ticket.id,
        "ticket_code": ticket.ticket_code,
        "status": ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        "priority": ticket.priority.value
        if hasattr(ticket.priority, "value")
        else str(ticket.priority),
        "subject": ticket.subject,
        "requester_email": ticket.requester_email,
        "requester_name": ticket.requester_name,
        "assignee_user_id": ticket.assignee_user_id,
        "assignee_queue_id": ticket.assignee_queue_id,
        "surrogate_id": ticket.surrogate_id,
        "surrogate_link_status": ticket.surrogate_link_status.value
        if hasattr(ticket.surrogate_link_status, "value")
        else str(ticket.surrogate_link_status),
        "first_message_at": ticket.first_message_at,
        "last_message_at": ticket.last_message_at,
        "last_activity_at": ticket.last_activity_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }

    return {
        "ticket": ticket_payload,
        "messages": message_items,
        "events": [
            {
                "id": event.id,
                "actor_user_id": event.actor_user_id,
                "event_type": event.event_type,
                "event_data": event.event_data or {},
                "created_at": event.created_at,
            }
            for event in events
        ],
        "notes": [
            {
                "id": note.id,
                "author_user_id": note.author_user_id,
                "body_markdown": note.body_markdown,
                "body_html_sanitized": note.body_html_sanitized,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
            }
            for note in notes
        ],
        "candidates": [
            {
                "id": candidate.id,
                "surrogate_id": candidate.surrogate_id,
                "confidence": candidate.confidence.value
                if hasattr(candidate.confidence, "value")
                else str(candidate.confidence),
                "evidence_json": candidate.evidence_json or {},
                "is_selected": bool(candidate.is_selected),
                "created_at": candidate.created_at,
            }
            for candidate in candidates
        ],
    }


# =============================================================================
# Ticket mutation operations
# =============================================================================


def patch_ticket(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    status_value: str | None,
    priority_value: str | None,
    assignee_user_id: UUID | None,
    assignee_queue_id: UUID | None,
) -> Ticket:
    """Update ticket mutable fields and append an audit event."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    changes: dict[str, str | None] = {}

    if status_value is not None:
        try:
            next_status = TicketStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid ticket status") from exc
        if ticket.status != next_status:
            changes["status"] = next_status.value
            ticket.status = next_status
            if next_status in {TicketStatus.CLOSED, TicketStatus.RESOLVED}:
                ticket.closed_at = _now_utc()

    if priority_value is not None:
        try:
            next_priority = TicketPriority(priority_value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid ticket priority") from exc
        if ticket.priority != next_priority:
            changes["priority"] = next_priority.value
            ticket.priority = next_priority

    if assignee_user_id is not None and ticket.assignee_user_id != assignee_user_id:
        ticket.assignee_user_id = assignee_user_id
        # Use one assignee mode at a time.
        ticket.assignee_queue_id = None
        changes["assignee_user_id"] = str(assignee_user_id)

    if assignee_queue_id is not None and ticket.assignee_queue_id != assignee_queue_id:
        ticket.assignee_queue_id = assignee_queue_id
        ticket.assignee_user_id = None
        changes["assignee_queue_id"] = str(assignee_queue_id)

    if not changes:
        return ticket

    ticket.updated_at = _now_utc()
    ticket.last_activity_at = ticket.updated_at

    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type="ticket_updated",
            event_data={"changes": changes},
        )
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def add_ticket_note(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    body_markdown: str,
) -> TicketNote:
    """Add an internal ticket note and event."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)
    body = (body_markdown or "").strip()
    if not body:
        raise HTTPException(status_code=422, detail="body_markdown cannot be empty")

    note = TicketNote(
        organization_id=org_id,
        ticket_id=ticket.id,
        author_user_id=actor_user_id,
        body_markdown=body,
        body_html_sanitized=None,
    )
    db.add(note)

    now = _now_utc()
    ticket.updated_at = now
    ticket.last_activity_at = now

    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type="note_added",
            event_data={"note_id": str(note.id)},
        )
    )

    db.commit()
    db.refresh(note)
    return note


def link_ticket_surrogate(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    surrogate_id: UUID | None,
    reason: str | None = None,
) -> Ticket:
    """Manually link or unlink a ticket to/from a surrogate."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    previous_surrogate_id = ticket.surrogate_id
    previous_status = ticket.surrogate_link_status

    if surrogate_id is None:
        ticket.surrogate_id = None
        ticket.surrogate_link_status = TicketLinkStatus.UNLINKED
        event_type = "surrogate_unlinked"
    else:
        _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
        ticket.surrogate_id = surrogate_id
        ticket.surrogate_link_status = TicketLinkStatus.LINKED
        event_type = "surrogate_linked"

    # mark selected candidate if present
    if surrogate_id is not None:
        (
            db.query(TicketSurrogateLinkCandidate)
            .filter(
                TicketSurrogateLinkCandidate.organization_id == org_id,
                TicketSurrogateLinkCandidate.ticket_id == ticket.id,
            )
            .update({"is_selected": False}, synchronize_session=False)
        )
        (
            db.query(TicketSurrogateLinkCandidate)
            .filter(
                TicketSurrogateLinkCandidate.organization_id == org_id,
                TicketSurrogateLinkCandidate.ticket_id == ticket.id,
                TicketSurrogateLinkCandidate.surrogate_id == surrogate_id,
            )
            .update({"is_selected": True}, synchronize_session=False)
        )

    now = _now_utc()
    ticket.updated_at = now
    ticket.last_activity_at = now

    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_data={
                "from_surrogate_id": str(previous_surrogate_id) if previous_surrogate_id else None,
                "to_surrogate_id": str(surrogate_id) if surrogate_id else None,
                "from_link_status": previous_status.value
                if hasattr(previous_status, "value")
                else str(previous_status),
                "to_link_status": ticket.surrogate_link_status.value,
                "reason": reason,
            },
        )
    )

    db.commit()
    db.refresh(ticket)
    return ticket


# =============================================================================
# Outbound send operations
# =============================================================================


def list_send_identities(db: Session, *, user_id: UUID) -> list[dict]:
    """Return available Gmail sender identities for the current user."""
    rows = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "gmail",
            UserIntegration.account_email.isnot(None),
        )
        .order_by(UserIntegration.created_at.asc())
        .all()
    )
    return [
        {
            "integration_id": row.id,
            "account_email": row.account_email,
            "provider": "gmail",
            "is_default": idx == 0,
        }
        for idx, row in enumerate(rows)
        if row.account_email
    ]


def _pick_sender_integration(db: Session, *, user_id: UUID) -> UserIntegration:
    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == "gmail",
        )
        .order_by(UserIntegration.created_at.asc())
        .first()
    )
    if integration is None:
        raise HTTPException(
            status_code=422,
            detail="Gmail is not connected for this user. Connect Gmail before sending.",
        )
    return integration


def _build_reply_headers(
    *,
    ticket_id: UUID,
    ticket_code: str,
    in_reply_to: str | None,
    references: list[str],
) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-SF-Ticket-ID": str(ticket_id),
        "Reply-To": f"ticket+{ticket_code}@reply.surrogacyforce.local",
    }
    if in_reply_to:
        headers["In-Reply-To"] = in_reply_to
    if references:
        headers["References"] = " ".join(references)
    return headers


def _create_outbound_message_record(
    db: Session,
    *,
    org_id: UUID,
    ticket: Ticket,
    from_email: str,
    to_emails: list[str],
    cc_emails: list[str],
    subject: str,
    body_text: str,
    body_html: str | None,
    gmail_thread_id: str | None,
    gmail_message_id: str | None,
    idempotency_token: str | None = None,
    delivery_state: str = "sent",
) -> EmailMessage:
    signature_input = {
        "ticket_id": str(ticket.id),
        "from": from_email.lower(),
        "to": sorted(email.lower() for email in to_emails),
        "cc": sorted(email.lower() for email in cc_emails),
        "subject": subject,
        "body": body_text,
        "gmail_message_id": gmail_message_id,
        "idempotency_token": idempotency_token,
    }
    signature_raw = json.dumps(signature_input, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    signature = hashlib.sha256(signature_raw).hexdigest()
    fingerprint = _compute_fingerprint(
        subject_norm=_subject_norm(subject),
        from_email=from_email,
        to=to_emails,
        cc=cc_emails,
        rfc_message_id=None,
    )

    existing = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.fingerprint_sha256 == fingerprint,
            EmailMessage.signature_sha256 == signature,
        )
        .first()
    )
    if existing:
        return existing

    message = EmailMessage(
        organization_id=org_id,
        direction=EmailDirection.OUTBOUND,
        rfc_message_id=None,
        gmail_thread_id=gmail_thread_id,
        subject_norm=_subject_norm(subject),
        fingerprint_sha256=fingerprint,
        signature_sha256=signature,
        first_seen_at=_now_utc(),
    )
    db.add(message)
    db.flush()

    db.add(
        EmailMessageContent(
            organization_id=org_id,
            message_id=message.id,
            content_version=1,
            parser_version=1,
            parsed_at=_now_utc(),
            date_header=_now_utc(),
            subject=subject,
            subject_norm=_subject_norm(subject),
            from_email=from_email,
            from_name=None,
            reply_to_emails=[f"ticket+{ticket.ticket_code}@reply.surrogacyforce.local"],
            to_emails=to_emails,
            cc_emails=cc_emails,
            headers_json={
                "X-SF-Ticket-ID": [str(ticket.id)],
                "X-SF-Message-ID": [gmail_message_id] if gmail_message_id else [],
                "X-SF-Outbound-State": [delivery_state],
                "X-SF-Outbound-Idempotency-Key": [idempotency_token] if idempotency_token else [],
            },
            body_text=body_text,
            body_html_sanitized=body_html,
            has_attachments=False,
            attachment_count=0,
            snippet=(body_text or subject)[:280],
        )
    )

    if gmail_message_id:
        # Keep Gmail opaque id in thread refs for matching fallback.
        db.add(
            EmailMessageThreadRef(
                organization_id=org_id,
                message_id=message.id,
                ref_type="gmail_message_id",
                ref_rfc_message_id=gmail_message_id,
            )
        )

    db.flush()
    return message


def _link_outbound_message_to_ticket(
    db: Session,
    *,
    org_id: UUID,
    ticket: Ticket,
    message: EmailMessage,
    actor_user_id: UUID,
    to_emails: list[str],
    cc_emails: list[str],
    event_type: str = "outbound_sent",
    extra_event_data: dict | None = None,
) -> None:
    existing = (
        db.query(TicketMessage)
        .filter(
            TicketMessage.organization_id == org_id,
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.message_id == message.id,
        )
        .first()
    )
    if existing is None:
        db.add(
            TicketMessage(
                organization_id=org_id,
                ticket_id=ticket.id,
                message_id=message.id,
                stitch_reason="outbound_send",
                stitch_confidence=LinkConfidence.HIGH,
            )
        )

    now = _now_utc()
    ticket.last_message_at = now
    ticket.last_activity_at = now
    ticket.updated_at = now
    if ticket.first_message_at is None:
        ticket.first_message_at = now

    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_data={
                "message_id": str(message.id),
                "to_emails": to_emails,
                "cc_emails": cc_emails,
            }
            | (extra_event_data or {}),
        )
    )


def _normalize_outbound_idempotency_key(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) <= 120:
        return raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_outbound_idempotency_key(value: str | None) -> str:
    normalized = _normalize_outbound_idempotency_key(value)
    if normalized:
        return normalized
    return f"auto-{uuid4()}"


def _outbound_job_dedupe_key(*, org_id: UUID, outbound_idempotency_key: str) -> str:
    return f"ticket-outbound:{org_id}:{outbound_idempotency_key}"


def _queued_outbound_result_from_job(db: Session, *, org_id: UUID, job: Job) -> dict:
    payload = job.payload or {}
    ticket_id_raw = payload.get("ticket_id")
    message_id_raw = payload.get("message_id")
    if not ticket_id_raw or not message_id_raw:
        raise HTTPException(status_code=409, detail="Existing outbound job payload is invalid")

    try:
        ticket_id = UUID(str(ticket_id_raw))
        message_id = UUID(str(message_id_raw))
    except ValueError as exc:
        raise HTTPException(
            status_code=409, detail="Existing outbound job payload is invalid"
        ) from exc

    message = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.id == message_id,
        )
        .first()
    )
    ref = (
        db.query(EmailMessageThreadRef)
        .filter(
            EmailMessageThreadRef.organization_id == org_id,
            EmailMessageThreadRef.message_id == message_id,
            EmailMessageThreadRef.ref_type == "gmail_message_id",
        )
        .order_by(EmailMessageThreadRef.created_at.desc(), EmailMessageThreadRef.id.desc())
        .first()
    )
    sent = ref is not None
    return {
        "status": "sent" if sent else "queued",
        "ticket_id": ticket_id,
        "message_id": message_id,
        "provider": "gmail",
        "gmail_message_id": ref.ref_rfc_message_id if ref else None,
        "gmail_thread_id": message.gmail_thread_id if message else None,
        "job_id": job.id,
    }


def _create_ticket_outbound_job(
    db: Session,
    *,
    org_id: UUID,
    outbound_idempotency_key: str,
    payload: dict,
) -> Job:
    dedupe_key = _outbound_job_dedupe_key(
        org_id=org_id,
        outbound_idempotency_key=outbound_idempotency_key,
    )
    try:
        return job_service.enqueue_job(
            db=db,
            org_id=org_id,
            job_type=JobType.TICKET_OUTBOUND_SEND,
            payload=payload,
            idempotency_key=dedupe_key,
            commit=False,
        )
    except IntegrityError:
        db.rollback()
        existing = job_service.get_job_by_idempotency_key(
            db,
            org_id=org_id,
            idempotency_key=dedupe_key,
        )
        if existing:
            return existing
        raise


def _set_outbound_message_sent_state(
    db: Session,
    *,
    org_id: UUID,
    message: EmailMessage,
    gmail_message_id: str | None,
    gmail_thread_id: str | None,
) -> None:
    if gmail_thread_id:
        message.gmail_thread_id = gmail_thread_id

    content = (
        db.query(EmailMessageContent)
        .filter(
            EmailMessageContent.organization_id == org_id,
            EmailMessageContent.message_id == message.id,
        )
        .order_by(
            EmailMessageContent.content_version.desc(),
            EmailMessageContent.parsed_at.desc(),
        )
        .first()
    )
    if content:
        headers_json = dict(content.headers_json or {})
        headers_json["X-SF-Outbound-State"] = ["sent"]
        if gmail_message_id:
            headers_json["X-SF-Message-ID"] = [gmail_message_id]
        content.headers_json = headers_json
        content.parsed_at = _now_utc()
        db.add(content)

    if gmail_message_id:
        existing_ref = (
            db.query(EmailMessageThreadRef)
            .filter(
                EmailMessageThreadRef.organization_id == org_id,
                EmailMessageThreadRef.message_id == message.id,
                EmailMessageThreadRef.ref_type == "gmail_message_id",
                EmailMessageThreadRef.ref_rfc_message_id == gmail_message_id,
            )
            .first()
        )
        if existing_ref is None:
            db.add(
                EmailMessageThreadRef(
                    organization_id=org_id,
                    message_id=message.id,
                    ref_type="gmail_message_id",
                    ref_rfc_message_id=gmail_message_id,
                )
            )


async def process_ticket_outbound_send_job(
    db: Session,
    *,
    job_id: UUID,
    payload: dict,
) -> dict:
    """Worker send path for queued ticket outbound messages."""
    org_id_raw = payload.get("organization_id")
    actor_user_id_raw = payload.get("actor_user_id")
    ticket_id_raw = payload.get("ticket_id")
    message_id_raw = payload.get("message_id")
    if not org_id_raw or not actor_user_id_raw or not ticket_id_raw or not message_id_raw:
        raise ValueError("ticket_outbound_send payload missing required keys")

    org_id = UUID(str(org_id_raw))
    actor_user_id = UUID(str(actor_user_id_raw))
    ticket_id = UUID(str(ticket_id_raw))
    message_id = UUID(str(message_id_raw))

    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)
    message = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.id == message_id,
        )
        .first()
    )
    if message is None:
        raise ValueError("ticket_outbound_send message not found")

    existing_ref = (
        db.query(EmailMessageThreadRef)
        .filter(
            EmailMessageThreadRef.organization_id == org_id,
            EmailMessageThreadRef.message_id == message_id,
            EmailMessageThreadRef.ref_type == "gmail_message_id",
        )
        .first()
    )
    if existing_ref:
        logger.info(
            "Skipping replay for ticket outbound job %s (already sent)",
            job_id,
            extra={
                "job_id": str(job_id),
                "ticket_id": str(ticket_id),
                "message_id": str(message_id),
            },
        )
        return {
            "status": "sent",
            "ticket_id": ticket.id,
            "message_id": message.id,
            "provider": "gmail",
            "gmail_message_id": existing_ref.ref_rfc_message_id,
            "gmail_thread_id": message.gmail_thread_id,
            "job_id": job_id,
        }

    _pick_sender_integration(db, user_id=actor_user_id)

    normalized_to = _normalize_email_list(list(payload.get("to_emails") or []))
    normalized_cc = _normalize_email_list(list(payload.get("cc_emails") or []))
    subject_value = str(payload.get("subject") or ticket.subject or "").strip()
    body_text_clean = str(payload.get("body_text") or "").strip()
    body_html = payload.get("body_html")
    mode = str(payload.get("mode") or "compose")
    outbound_idempotency_key = str(payload.get("outbound_idempotency_key") or "")

    if not normalized_to:
        if ticket.requester_email:
            normalized_to = [ticket.requester_email]
        else:
            raise ValueError("ticket_outbound_send has no recipient email")
    if not subject_value:
        raise ValueError("ticket_outbound_send has no subject")
    if not body_text_clean:
        raise ValueError("ticket_outbound_send has no body_text")

    latest_link = (
        db.query(TicketMessage)
        .join(
            EmailMessage,
            and_(
                EmailMessage.organization_id == TicketMessage.organization_id,
                EmailMessage.id == TicketMessage.message_id,
            ),
        )
        .filter(
            TicketMessage.organization_id == org_id,
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.message_id != message.id,
        )
        .order_by(TicketMessage.stitched_at.desc(), TicketMessage.id.desc())
        .first()
    )

    in_reply_to = None
    references: list[str] = []
    if mode == "reply" and latest_link:
        prior_message = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.organization_id == org_id,
                EmailMessage.id == latest_link.message_id,
            )
            .first()
        )
        if prior_message and prior_message.rfc_message_id:
            in_reply_to = prior_message.rfc_message_id
            references.append(prior_message.rfc_message_id)

    headers = _build_reply_headers(
        ticket_id=ticket.id,
        ticket_code=ticket.ticket_code,
        in_reply_to=in_reply_to,
        references=references,
    )
    if normalized_cc:
        headers["Cc"] = ", ".join(normalized_cc)

    send_result = await gmail_service.send_email(
        db=db,
        user_id=str(actor_user_id),
        to=normalized_to[0],
        subject=subject_value,
        body=body_html or body_text_clean,
        html=bool(body_html),
        headers=headers,
        attachments=None,
    )
    if not send_result.get("success"):
        raise RuntimeError(send_result.get("error") or "Gmail send failed")

    gmail_thread_id = send_result.get("thread_id") or message.gmail_thread_id or ticket.ticket_code
    gmail_message_id = send_result.get("message_id")

    _set_outbound_message_sent_state(
        db,
        org_id=org_id,
        message=message,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
    )

    _link_outbound_message_to_ticket(
        db,
        org_id=org_id,
        ticket=ticket,
        message=message,
        actor_user_id=actor_user_id,
        to_emails=normalized_to,
        cc_emails=normalized_cc,
        event_type="outbound_sent",
        extra_event_data={
            "job_id": str(job_id),
            "outbound_idempotency_key": outbound_idempotency_key,
            "gmail_message_id": gmail_message_id,
            "gmail_thread_id": gmail_thread_id,
        },
    )

    db.commit()
    return {
        "status": "sent",
        "ticket_id": ticket.id,
        "message_id": message.id,
        "provider": "gmail",
        "gmail_message_id": gmail_message_id,
        "gmail_thread_id": gmail_thread_id,
        "job_id": job_id,
    }


def reply_to_ticket(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    to_emails: list[str],
    cc_emails: list[str],
    subject: str | None,
    body_text: str,
    body_html: str | None,
    idempotency_key: str | None,
) -> dict:
    """Queue a threaded Gmail reply and persist canonical outbound metadata."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    normalized_to = _normalize_email_list(to_emails)
    normalized_cc = _normalize_email_list(cc_emails)
    if not normalized_to:
        if ticket.requester_email:
            normalized_to = [ticket.requester_email]
        else:
            raise HTTPException(status_code=422, detail="to_emails must contain at least one email")

    body_text_clean = (body_text or "").strip()
    if not body_text_clean:
        raise HTTPException(status_code=422, detail="body_text cannot be empty")

    subject_value = (subject or ticket.subject or "").strip()
    if not subject_value:
        raise HTTPException(status_code=422, detail="subject cannot be empty")
    outbound_idempotency_key = _resolve_outbound_idempotency_key(idempotency_key)
    dedupe_key = _outbound_job_dedupe_key(
        org_id=org_id,
        outbound_idempotency_key=outbound_idempotency_key,
    )
    existing = job_service.get_job_by_idempotency_key(
        db,
        org_id=org_id,
        idempotency_key=dedupe_key,
    )
    if existing:
        return _queued_outbound_result_from_job(db, org_id=org_id, job=existing)

    integration = _pick_sender_integration(db, user_id=actor_user_id)

    message = _create_outbound_message_record(
        db,
        org_id=org_id,
        ticket=ticket,
        from_email=integration.account_email or "me",
        to_emails=normalized_to,
        cc_emails=normalized_cc,
        subject=subject_value,
        body_text=body_text_clean,
        body_html=body_html,
        gmail_thread_id=ticket.ticket_code,
        gmail_message_id=None,
        idempotency_token=outbound_idempotency_key,
        delivery_state="queued",
    )

    _link_outbound_message_to_ticket(
        db,
        org_id=org_id,
        ticket=ticket,
        message=message,
        actor_user_id=actor_user_id,
        to_emails=normalized_to,
        cc_emails=normalized_cc,
        event_type="outbound_queued",
        extra_event_data={
            "mode": "reply",
            "outbound_idempotency_key": outbound_idempotency_key,
        },
    )

    job = _create_ticket_outbound_job(
        db,
        org_id=org_id,
        outbound_idempotency_key=outbound_idempotency_key,
        payload={
            "organization_id": str(org_id),
            "actor_user_id": str(actor_user_id),
            "ticket_id": str(ticket.id),
            "message_id": str(message.id),
            "mode": "reply",
            "to_emails": normalized_to,
            "cc_emails": normalized_cc,
            "subject": subject_value,
            "body_text": body_text_clean,
            "body_html": body_html,
            "outbound_idempotency_key": outbound_idempotency_key,
        },
    )

    persisted_message = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.id == message.id,
        )
        .first()
    )
    if persisted_message is None:
        return _queued_outbound_result_from_job(db, org_id=org_id, job=job)

    db.commit()

    return {
        "status": "queued",
        "ticket_id": ticket.id,
        "message_id": message.id,
        "provider": "gmail",
        "gmail_message_id": None,
        "gmail_thread_id": message.gmail_thread_id,
        "job_id": job.id,
    }


def compose_ticket(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    to_emails: list[str],
    cc_emails: list[str],
    subject: str,
    body_text: str,
    body_html: str | None,
    surrogate_id: UUID | None,
    queue_id: UUID | None,
    idempotency_key: str | None,
) -> dict:
    """Queue a new outbound email and open a ticket thread."""
    normalized_to = _normalize_email_list(to_emails)
    normalized_cc = _normalize_email_list(cc_emails)
    if not normalized_to:
        raise HTTPException(status_code=422, detail="to_emails must contain at least one email")

    subject_value = (subject or "").strip()
    body_text_clean = (body_text or "").strip()
    if not subject_value:
        raise HTTPException(status_code=422, detail="subject cannot be empty")
    if not body_text_clean:
        raise HTTPException(status_code=422, detail="body_text cannot be empty")

    outbound_idempotency_key = _resolve_outbound_idempotency_key(idempotency_key)
    dedupe_key = _outbound_job_dedupe_key(
        org_id=org_id,
        outbound_idempotency_key=outbound_idempotency_key,
    )
    existing = job_service.get_job_by_idempotency_key(
        db,
        org_id=org_id,
        idempotency_key=dedupe_key,
    )
    if existing:
        return _queued_outbound_result_from_job(db, org_id=org_id, job=existing)

    integration = _pick_sender_integration(db, user_id=actor_user_id)

    if surrogate_id is not None:
        _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)

    ticket = Ticket(
        organization_id=org_id,
        ticket_code=generate_ticket_code(db, org_id),
        status=TicketStatus.NEW,
        priority=TicketPriority.NORMAL,
        subject=subject_value,
        subject_norm=_subject_norm(subject_value),
        requester_email=normalized_to[0],
        requester_name=None,
        assignee_queue_id=queue_id,
        surrogate_id=surrogate_id,
        surrogate_link_status=TicketLinkStatus.LINKED
        if surrogate_id
        else TicketLinkStatus.NEEDS_REVIEW,
        stitch_reason="outbound_compose",
        stitch_confidence=LinkConfidence.HIGH,
        first_message_at=_now_utc(),
        last_message_at=_now_utc(),
        last_activity_at=_now_utc(),
    )
    db.add(ticket)
    db.flush()

    message = _create_outbound_message_record(
        db,
        org_id=org_id,
        ticket=ticket,
        from_email=integration.account_email or "me",
        to_emails=normalized_to,
        cc_emails=normalized_cc,
        subject=subject_value,
        body_text=body_text_clean,
        body_html=body_html,
        gmail_thread_id=ticket.ticket_code,
        gmail_message_id=None,
        idempotency_token=outbound_idempotency_key,
        delivery_state="queued",
    )

    _link_outbound_message_to_ticket(
        db,
        org_id=org_id,
        ticket=ticket,
        message=message,
        actor_user_id=actor_user_id,
        to_emails=normalized_to,
        cc_emails=normalized_cc,
        event_type="outbound_queued",
        extra_event_data={
            "mode": "compose",
            "outbound_idempotency_key": outbound_idempotency_key,
        },
    )

    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type="ticket_created",
            event_data={
                "source": "compose",
                "delivery": "queued",
                "to_emails": normalized_to,
                "cc_emails": normalized_cc,
            },
        )
    )

    job = _create_ticket_outbound_job(
        db,
        org_id=org_id,
        outbound_idempotency_key=outbound_idempotency_key,
        payload={
            "organization_id": str(org_id),
            "actor_user_id": str(actor_user_id),
            "ticket_id": str(ticket.id),
            "message_id": str(message.id),
            "mode": "compose",
            "to_emails": normalized_to,
            "cc_emails": normalized_cc,
            "subject": subject_value,
            "body_text": body_text_clean,
            "body_html": body_html,
            "outbound_idempotency_key": outbound_idempotency_key,
        },
    )

    persisted_message = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.id == message.id,
        )
        .first()
    )
    if persisted_message is None:
        return _queued_outbound_result_from_job(db, org_id=org_id, job=job)

    db.commit()

    if ticket.surrogate_id is None:
        apply_ticket_linking(db, org_id=org_id, ticket_id=ticket.id, actor_user_id=actor_user_id)

    return {
        "status": "queued",
        "ticket_id": ticket.id,
        "message_id": message.id,
        "provider": "gmail",
        "gmail_message_id": None,
        "gmail_thread_id": message.gmail_thread_id,
        "job_id": job.id,
    }


# =============================================================================
# Surrogate email history and contact management
# =============================================================================


def _upsert_system_surrogate_email_contact(db: Session, *, surrogate: Surrogate) -> None:
    email = _normalize_email(surrogate.email or "")
    if not email:
        return
    email_hash = hash_email(email)

    existing = (
        db.query(SurrogateEmailContact)
        .filter(
            SurrogateEmailContact.organization_id == surrogate.organization_id,
            SurrogateEmailContact.surrogate_id == surrogate.id,
            SurrogateEmailContact.email_hash == email_hash,
            SurrogateEmailContact.source == SurrogateEmailContactSource.SYSTEM,
        )
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.updated_at = _now_utc()
            db.add(existing)
        return

    db.add(
        SurrogateEmailContact(
            organization_id=surrogate.organization_id,
            surrogate_id=surrogate.id,
            email=email,
            email_hash=email_hash,
            email_domain=extract_email_domain(email),
            source=SurrogateEmailContactSource.SYSTEM,
            label="Primary",
            contact_type="surrogate",
            is_active=True,
            created_by_user_id=surrogate.created_by_user_id,
        )
    )


def list_surrogate_ticket_emails(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
    limit: int = 100,
) -> list[Ticket]:
    _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
    return (
        db.query(Ticket)
        .filter(
            Ticket.organization_id == org_id,
            Ticket.surrogate_id == surrogate_id,
        )
        .order_by(
            func.coalesce(Ticket.last_activity_at, Ticket.created_at).desc(), Ticket.id.desc()
        )
        .limit(max(1, min(limit, 200)))
        .all()
    )


def list_surrogate_email_contacts(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
) -> list[SurrogateEmailContact]:
    surrogate = _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
    _upsert_system_surrogate_email_contact(db, surrogate=surrogate)
    db.flush()
    return (
        db.query(SurrogateEmailContact)
        .filter(
            SurrogateEmailContact.organization_id == org_id,
            SurrogateEmailContact.surrogate_id == surrogate_id,
        )
        .order_by(SurrogateEmailContact.source.asc(), SurrogateEmailContact.created_at.asc())
        .all()
    )


def create_surrogate_email_contact(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
    actor_user_id: UUID,
    email: str,
    label: str | None,
    contact_type: str | None,
) -> SurrogateEmailContact:
    surrogate = _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
    normalized_email = _normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=422, detail="Invalid email")

    email_hash = hash_email(normalized_email)
    existing = (
        db.query(SurrogateEmailContact)
        .filter(
            SurrogateEmailContact.organization_id == org_id,
            SurrogateEmailContact.surrogate_id == surrogate.id,
            SurrogateEmailContact.email_hash == email_hash,
            SurrogateEmailContact.source == SurrogateEmailContactSource.MANUAL,
        )
        .first()
    )
    if existing:
        existing.email = normalized_email
        existing.label = label
        existing.contact_type = contact_type
        existing.is_active = True
        existing.updated_at = _now_utc()
        db.commit()
        db.refresh(existing)
        return existing

    contact = SurrogateEmailContact(
        organization_id=org_id,
        surrogate_id=surrogate.id,
        email=normalized_email,
        email_hash=email_hash,
        email_domain=extract_email_domain(normalized_email),
        source=SurrogateEmailContactSource.MANUAL,
        label=label,
        contact_type=contact_type,
        is_active=True,
        created_by_user_id=actor_user_id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def patch_surrogate_email_contact(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
    contact_id: UUID,
    email: str | None,
    label: str | None,
    contact_type: str | None,
    is_active: bool | None,
) -> SurrogateEmailContact:
    _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
    contact = (
        db.query(SurrogateEmailContact)
        .filter(
            SurrogateEmailContact.organization_id == org_id,
            SurrogateEmailContact.surrogate_id == surrogate_id,
            SurrogateEmailContact.id == contact_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Email contact not found")
    if contact.source != SurrogateEmailContactSource.MANUAL:
        raise HTTPException(status_code=422, detail="System contacts cannot be edited")

    if email is not None:
        normalized_email = _normalize_email(email)
        if not normalized_email:
            raise HTTPException(status_code=422, detail="Invalid email")
        contact.email = normalized_email
        contact.email_hash = hash_email(normalized_email)
        contact.email_domain = extract_email_domain(normalized_email)

    if label is not None:
        contact.label = label
    if contact_type is not None:
        contact.contact_type = contact_type
    if is_active is not None:
        contact.is_active = is_active

    contact.updated_at = _now_utc()
    db.commit()
    db.refresh(contact)
    return contact


def deactivate_surrogate_email_contact(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID,
    contact_id: UUID,
) -> None:
    _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)
    contact = (
        db.query(SurrogateEmailContact)
        .filter(
            SurrogateEmailContact.organization_id == org_id,
            SurrogateEmailContact.surrogate_id == surrogate_id,
            SurrogateEmailContact.id == contact_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Email contact not found")
    if contact.source != SurrogateEmailContactSource.MANUAL:
        raise HTTPException(status_code=422, detail="System contacts cannot be deactivated")

    contact.is_active = False
    contact.updated_at = _now_utc()
    db.commit()


# =============================================================================
# Attachment download for ticket messages
# =============================================================================


def get_ticket_attachment_download_url(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    ticket_id: UUID,
    attachment_id: UUID,
) -> str:
    _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    linked = (
        db.query(EmailMessageAttachment)
        .join(
            TicketMessage,
            and_(
                TicketMessage.organization_id == EmailMessageAttachment.organization_id,
                TicketMessage.message_id == EmailMessageAttachment.message_id,
            ),
        )
        .filter(
            EmailMessageAttachment.organization_id == org_id,
            EmailMessageAttachment.attachment_id == attachment_id,
            TicketMessage.ticket_id == ticket_id,
        )
        .first()
    )
    if linked is None:
        raise HTTPException(status_code=404, detail="Attachment not found on this ticket")

    url = attachment_service.get_download_url(
        db=db,
        org_id=org_id,
        attachment_id=attachment_id,
        user_id=actor_user_id,
    )
    if not url:
        raise HTTPException(status_code=404, detail="Attachment unavailable")
    db.commit()
    return url


# =============================================================================
# Mailbox administration and sync scheduling
# =============================================================================


def list_mailboxes(db: Session, *, org_id: UUID) -> list[Mailbox]:
    """List mailboxes and lazily ensure user_sent entries for connected Gmail users."""
    _ensure_user_sent_mailboxes(db, org_id=org_id)
    db.flush()
    return (
        db.query(Mailbox)
        .filter(Mailbox.organization_id == org_id)
        .order_by(Mailbox.kind.asc(), Mailbox.created_at.asc())
        .all()
    )


def _ensure_user_sent_mailboxes(db: Session, *, org_id: UUID) -> None:
    """Ensure each Gmail user integration has a matching user_sent mailbox row."""
    rows = (
        db.query(UserIntegration)
        .join(
            Membership,
            and_(
                Membership.user_id == UserIntegration.user_id,
                Membership.organization_id == org_id,
                Membership.is_active.is_(True),
            ),
        )
        .filter(
            UserIntegration.integration_type == "gmail",
            UserIntegration.account_email.isnot(None),
        )
        .all()
    )
    for integration in rows:
        if not integration_has_inbound_scope(integration):
            continue

        existing = (
            db.query(Mailbox)
            .filter(
                Mailbox.organization_id == org_id,
                Mailbox.kind == MailboxKind.USER_SENT,
                Mailbox.user_integration_id == integration.id,
            )
            .first()
        )
        if existing:
            existing.email_address = integration.account_email
            existing.updated_at = _now_utc()
            continue

        db.add(
            Mailbox(
                organization_id=org_id,
                kind=MailboxKind.USER_SENT,
                provider="gmail",
                email_address=integration.account_email,
                display_name="User Sent",
                user_integration_id=integration.id,
                is_enabled=True,
            )
        )


def create_or_update_journal_mailbox(
    db: Session,
    *,
    org_id: UUID,
    account_email: str,
    access_token: str,
    refresh_token: str,
    expires_in: int | None,
    granted_scopes: list[str] | None,
) -> Mailbox:
    """Create/update org journal mailbox credential + mailbox row."""
    normalized_email = _normalize_email(account_email or "")
    if not normalized_email:
        raise HTTPException(status_code=422, detail="Invalid journal account email")

    expires_at = None
    if expires_in:
        expires_at = _now_utc() + timedelta(seconds=int(expires_in))

    credential = (
        db.query(MailboxCredential)
        .filter(
            MailboxCredential.organization_id == org_id,
            MailboxCredential.provider == "gmail",
            MailboxCredential.account_email == normalized_email,
        )
        .first()
    )
    encrypted_access = oauth_service.encrypt_token(access_token)
    encrypted_refresh = oauth_service.encrypt_token(refresh_token) if refresh_token else None

    if credential:
        credential.access_token_encrypted = encrypted_access
        if encrypted_refresh:
            credential.refresh_token_encrypted = encrypted_refresh
        credential.token_expires_at = expires_at
        credential.granted_scopes = granted_scopes
        credential.updated_at = _now_utc()
    else:
        if not encrypted_refresh:
            raise HTTPException(
                status_code=422,
                detail="Google did not return a refresh token. Reconnect with consent prompt.",
            )
        credential = MailboxCredential(
            organization_id=org_id,
            provider="gmail",
            account_email=normalized_email,
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            token_expires_at=expires_at,
            granted_scopes=granted_scopes,
        )
        db.add(credential)
        db.flush()

    mailbox = (
        db.query(Mailbox)
        .filter(
            Mailbox.organization_id == org_id,
            Mailbox.kind == MailboxKind.JOURNAL,
        )
        .first()
    )
    if mailbox:
        mailbox.email_address = normalized_email
        mailbox.credential_id = credential.id
        mailbox.provider = "gmail"
        mailbox.is_enabled = True
        mailbox.updated_at = _now_utc()
    else:
        mailbox = Mailbox(
            organization_id=org_id,
            kind=MailboxKind.JOURNAL,
            provider="gmail",
            email_address=normalized_email,
            display_name="Journal Inbox",
            credential_id=credential.id,
            is_enabled=True,
        )
        db.add(mailbox)

    db.commit()
    db.refresh(mailbox)
    return mailbox


def enqueue_mailbox_backfill(
    db: Session, *, org_id: UUID, mailbox_id: UUID, reason: str
) -> UUID | None:
    """Queue a full mailbox backfill."""
    mailbox = _ensure_mailbox_belongs_to_org(db, org_id, mailbox_id)
    payload = {
        "organization_id": str(org_id),
        "mailbox_id": str(mailbox.id),
        "reason": reason,
    }
    job_id = _enqueue_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=mailbox.id,
        job_type=JobType.MAILBOX_BACKFILL,
        payload=payload,
    )
    db.commit()
    return job_id


def enqueue_mailbox_history_sync(
    db: Session, *, org_id: UUID, mailbox_id: UUID, reason: str
) -> UUID | None:
    """Queue incremental mailbox history sync."""
    mailbox = _ensure_mailbox_belongs_to_org(db, org_id, mailbox_id)
    payload = {
        "organization_id": str(org_id),
        "mailbox_id": str(mailbox.id),
        "reason": reason,
    }
    job_id = _enqueue_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=mailbox.id,
        job_type=JobType.MAILBOX_HISTORY_SYNC,
        payload=payload,
    )
    db.commit()
    return job_id


def pause_mailbox_ingestion(
    db: Session,
    *,
    org_id: UUID,
    mailbox_id: UUID,
    minutes: int,
    reason: str | None,
) -> tuple[datetime, str]:
    """Pause mailbox ingestion for a fixed duration."""
    mailbox = _ensure_mailbox_belongs_to_org(db, org_id, mailbox_id)
    pause_until = _now_utc() + timedelta(minutes=max(1, minutes))
    pause_reason = (reason or f"Manual pause ({minutes} minutes)").strip()

    mailbox.ingestion_paused_until = pause_until
    mailbox.ingestion_pause_reason = pause_reason
    mailbox.updated_at = _now_utc()
    db.commit()

    return pause_until, pause_reason


def resume_mailbox_ingestion(db: Session, *, org_id: UUID, mailbox_id: UUID) -> UUID | None:
    """Resume mailbox ingestion and enqueue an incremental sync."""
    mailbox = _ensure_mailbox_belongs_to_org(db, org_id, mailbox_id)
    mailbox.ingestion_paused_until = None
    mailbox.ingestion_pause_reason = None
    mailbox.updated_at = _now_utc()
    db.flush()

    payload = {
        "organization_id": str(org_id),
        "mailbox_id": str(mailbox.id),
        "reason": "manual_resume",
    }
    job_id = _enqueue_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=mailbox.id,
        job_type=JobType.MAILBOX_HISTORY_SYNC,
        payload=payload,
    )
    db.commit()
    return job_id


def get_mailbox_sync_status(db: Session, *, org_id: UUID, mailbox_id: UUID) -> MailboxSyncStatus:
    """Return mailbox sync health including queued/running job counts."""
    mailbox = _ensure_mailbox_belongs_to_org(db, org_id, mailbox_id)

    rows = (
        db.query(Job.job_type, Job.status, func.count(Job.id))
        .filter(
            Job.organization_id == org_id,
            Job.payload["mailbox_id"].astext == str(mailbox.id),
            Job.status.in_(["pending", "running"]),
        )
        .group_by(Job.job_type, Job.status)
        .all()
    )

    queued_jobs_by_type: dict[str, int] = {}
    running_jobs_by_type: dict[str, int] = {}
    for job_type, status_value, count in rows:
        if status_value == "pending":
            queued_jobs_by_type[job_type] = int(count)
        elif status_value == "running":
            running_jobs_by_type[job_type] = int(count)

    return MailboxSyncStatus(
        mailbox_id=mailbox.id,
        is_enabled=mailbox.is_enabled,
        paused_until=mailbox.ingestion_paused_until,
        gmail_history_id=mailbox.gmail_history_id,
        gmail_watch_expiration_at=mailbox.gmail_watch_expiration_at,
        gmail_watch_last_renewed_at=mailbox.gmail_watch_last_renewed_at,
        gmail_watch_topic_name=mailbox.gmail_watch_topic_name,
        gmail_watch_last_error=mailbox.gmail_watch_last_error,
        last_full_sync_at=mailbox.last_full_sync_at,
        last_incremental_sync_at=mailbox.last_incremental_sync_at,
        last_sync_error=mailbox.last_sync_error,
        queued_jobs_by_type=queued_jobs_by_type,
        running_jobs_by_type=running_jobs_by_type,
    )


def schedule_incremental_sync_jobs(db: Session) -> dict[str, int]:
    """Schedule incremental history sync for all enabled, unpaused mailboxes."""
    now = _now_utc()
    topic = _configured_gmail_push_topic()
    mailboxes = (
        db.query(Mailbox)
        .filter(
            Mailbox.is_enabled.is_(True),
            or_(Mailbox.ingestion_paused_until.is_(None), Mailbox.ingestion_paused_until < now),
        )
        .all()
    )

    jobs_created = 0
    duplicates = 0
    watch_jobs_created = 0
    watch_duplicates = 0
    for mailbox in mailboxes:
        payload = {
            "organization_id": str(mailbox.organization_id),
            "mailbox_id": str(mailbox.id),
            "reason": "scheduled_incremental",
        }
        job_id = _enqueue_mailbox_job(
            db,
            org_id=mailbox.organization_id,
            mailbox_id=mailbox.id,
            job_type=JobType.MAILBOX_HISTORY_SYNC,
            payload=payload,
        )
        if job_id:
            jobs_created += 1
        else:
            duplicates += 1

        if topic and _gmail_watch_is_due(mailbox, now=now):
            watch_job_id = _enqueue_mailbox_job(
                db,
                org_id=mailbox.organization_id,
                mailbox_id=mailbox.id,
                job_type=JobType.MAILBOX_WATCH_REFRESH,
                payload={
                    "organization_id": str(mailbox.organization_id),
                    "mailbox_id": str(mailbox.id),
                    "reason": "scheduled_watch_refresh",
                },
            )
            if watch_job_id:
                watch_jobs_created += 1
            else:
                watch_duplicates += 1

    db.commit()
    return {
        "mailboxes_checked": len(mailboxes),
        "jobs_created": jobs_created,
        "duplicates_skipped": duplicates,
        "watch_jobs_created": watch_jobs_created,
        "watch_duplicates_skipped": watch_duplicates,
    }


def process_mailbox_watch_refresh(db: Session, *, organization_id: UUID, mailbox_id: UUID) -> None:
    """Ensure/renew Gmail users.watch for a mailbox when configured."""
    mailbox = _ensure_mailbox_belongs_to_org(db, organization_id, mailbox_id)
    if not mailbox.is_enabled:
        return

    topic = _configured_gmail_push_topic()
    if not topic:
        mailbox.gmail_watch_last_error = "GMAIL_PUSH_TOPIC not configured"
        mailbox.updated_at = _now_utc()
        db.add(mailbox)
        db.commit()
        return

    now = _now_utc()
    if not _gmail_watch_is_due(mailbox, now=now):
        return

    access_token = _mailbox_access_token(db, mailbox)
    label_ids = _configured_gmail_watch_label_ids()

    try:
        with httpx.Client() as client:
            payload = _gmail_watch(
                client,
                access_token=access_token,
                topic_name=topic,
                label_ids=label_ids,
            )
        mailbox.gmail_watch_expiration_at = _parse_gmail_watch_expiration(payload.get("expiration"))
        mailbox.gmail_watch_last_renewed_at = now
        mailbox.gmail_watch_topic_name = topic
        mailbox.gmail_watch_last_error = None
        mailbox.updated_at = now
        db.add(mailbox)
        db.commit()
    except Exception as exc:
        mailbox.gmail_watch_last_error = str(exc)[:500]
        mailbox.updated_at = _now_utc()
        db.add(mailbox)
        db.commit()
        raise


def process_gmail_push_notification(
    db: Session,
    *,
    email_address: str | None,
    history_id: object | None,
    pubsub_message_id: str | None,
) -> dict[str, object]:
    """Handle Gmail Pub/Sub push payload and enqueue mailbox history sync."""
    normalized_email = _normalize_email(email_address or "")
    if not normalized_email:
        return {"status": "ignored", "reason": "missing_email"}

    mailbox_rows = (
        db.query(Mailbox)
        .filter(
            Mailbox.is_enabled.is_(True),
            Mailbox.provider == "gmail",
            func.lower(Mailbox.email_address) == normalized_email.lower(),
        )
        .all()
    )
    if not mailbox_rows:
        return {"status": "ignored", "reason": "mailbox_not_found"}

    parsed_history_id = _parse_int(history_id)
    jobs_created = 0
    duplicates = 0
    for mailbox in mailbox_rows:
        job_id = _enqueue_mailbox_job(
            db,
            org_id=mailbox.organization_id,
            mailbox_id=mailbox.id,
            job_type=JobType.MAILBOX_HISTORY_SYNC,
            payload={
                "organization_id": str(mailbox.organization_id),
                "mailbox_id": str(mailbox.id),
                "reason": "gmail_push",
                "pubsub_message_id": pubsub_message_id,
                "gmail_push_history_id": parsed_history_id,
            },
        )
        if job_id:
            jobs_created += 1
        else:
            duplicates += 1

    db.commit()
    return {
        "status": "accepted",
        "matched_mailboxes": len(mailbox_rows),
        "jobs_created": jobs_created,
        "duplicates_skipped": duplicates,
    }


# =============================================================================
# Gmail API helpers
# =============================================================================


def _refresh_mailbox_credential(db: Session, credential: MailboxCredential) -> str:
    refresh_token = oauth_service.decrypt_token(credential.refresh_token_encrypted)
    refresh_result = run_async(oauth_service.refresh_gmail_token(refresh_token), timeout=30)
    if not refresh_result:
        raise RuntimeError("Failed to refresh Gmail token")

    access_token = refresh_result.get("access_token")
    if not access_token:
        raise RuntimeError("Gmail refresh did not return access_token")

    credential.access_token_encrypted = oauth_service.encrypt_token(access_token)
    expires_in = refresh_result.get("expires_in")
    if expires_in:
        credential.token_expires_at = _now_utc() + timedelta(seconds=int(expires_in))
    scopes = _gmail_scopes_from_token_response(refresh_result)
    if scopes:
        credential.granted_scopes = scopes
    credential.updated_at = _now_utc()
    db.add(credential)
    db.flush()
    return access_token


def _refresh_user_integration_token(db: Session, integration: UserIntegration) -> str:
    if not integration.refresh_token_encrypted:
        raise RuntimeError("Connected Gmail account has no refresh token; reconnect required")

    refresh_token = oauth_service.decrypt_token(integration.refresh_token_encrypted)
    refresh_result = run_async(oauth_service.refresh_gmail_token(refresh_token), timeout=30)
    if not refresh_result:
        raise RuntimeError("Failed to refresh Gmail integration token")

    access_token = refresh_result.get("access_token")
    if not access_token:
        raise RuntimeError("Gmail refresh did not return access_token")

    integration.access_token_encrypted = oauth_service.encrypt_token(access_token)
    expires_in = refresh_result.get("expires_in")
    if expires_in:
        integration.token_expires_at = _now_utc() + timedelta(seconds=int(expires_in))
    scopes = _gmail_scopes_from_token_response(refresh_result)
    if scopes:
        integration.granted_scopes = scopes
    integration.updated_at = _now_utc()
    db.add(integration)
    db.flush()
    return access_token


def _mailbox_access_token(db: Session, mailbox: Mailbox) -> str:
    """Get valid Gmail access token for a mailbox source."""
    now = _now_utc()

    if mailbox.credential_id:
        credential = (
            db.query(MailboxCredential)
            .filter(
                MailboxCredential.id == mailbox.credential_id,
                MailboxCredential.organization_id == mailbox.organization_id,
            )
            .first()
        )
        if credential is None:
            raise RuntimeError("Mailbox credential not found")

        if credential.token_expires_at and credential.token_expires_at <= (
            now + timedelta(minutes=1)
        ):
            return _refresh_mailbox_credential(db, credential)
        if not credential.access_token_encrypted:
            return _refresh_mailbox_credential(db, credential)
        return oauth_service.decrypt_token(credential.access_token_encrypted)

    if mailbox.user_integration_id:
        integration = (
            db.query(UserIntegration)
            .filter(
                UserIntegration.id == mailbox.user_integration_id,
                UserIntegration.integration_type == "gmail",
            )
            .first()
        )
        if integration is None:
            raise RuntimeError("Mailbox user integration not found")

        if integration.token_expires_at and integration.token_expires_at <= (
            now + timedelta(minutes=1)
        ):
            return _refresh_user_integration_token(db, integration)
        return oauth_service.decrypt_token(integration.access_token_encrypted)

    raise RuntimeError("Mailbox does not have credential binding")


def _gmail_get(
    client: httpx.Client,
    *,
    url: str,
    access_token: str,
    params: dict | None = None,
) -> dict:
    response = client.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30.0,
    )
    if response.status_code >= 400:
        detail = None
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message")
        except Exception:
            detail = response.text
        raise RuntimeError(f"Gmail API error {response.status_code}: {detail or 'unknown error'}")
    return response.json()


def _gmail_watch(
    client: httpx.Client,
    *,
    access_token: str,
    topic_name: str,
    label_ids: list[str] | None = None,
) -> dict:
    payload: dict[str, object] = {"topicName": topic_name}
    if label_ids:
        payload["labelIds"] = label_ids
        payload["labelFilterBehavior"] = "INCLUDE"
    response = client.post(
        _GMAIL_WATCH_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
        timeout=30.0,
    )
    if response.status_code >= 400:
        detail = None
        try:
            data = response.json()
            detail = data.get("error", {}).get("message")
        except Exception:
            detail = response.text
        raise RuntimeError(f"Gmail watch error {response.status_code}: {detail or 'unknown error'}")
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Gmail watch response was not an object")
    return result


def _gmail_list_message_ids(
    client: httpx.Client,
    *,
    access_token: str,
    page_token: str | None,
) -> tuple[list[str], str | None]:
    payload = _gmail_get(
        client,
        url=_GMAIL_MESSAGES_LIST_URL,
        access_token=access_token,
        params={
            "maxResults": 100,
            "includeSpamTrash": "true",
            **({"pageToken": page_token} if page_token else {}),
        },
    )
    messages = payload.get("messages") or []
    message_ids = [str(item.get("id")) for item in messages if item.get("id")]
    next_page_token = payload.get("nextPageToken")
    return message_ids, str(next_page_token) if next_page_token else None


def _gmail_get_message_metadata(
    client: httpx.Client,
    *,
    access_token: str,
    message_id: str,
) -> dict:
    return _gmail_get(
        client,
        url=_GMAIL_MESSAGE_GET_URL.format(message_id=message_id),
        access_token=access_token,
        params={"format": "metadata"},
    )


def _gmail_get_message_raw(
    client: httpx.Client,
    *,
    access_token: str,
    message_id: str,
) -> dict:
    return _gmail_get(
        client,
        url=_GMAIL_MESSAGE_GET_URL.format(message_id=message_id),
        access_token=access_token,
        params={"format": "raw"},
    )


def _gmail_list_history(
    client: httpx.Client,
    *,
    access_token: str,
    start_history_id: int,
    page_token: str | None,
) -> dict:
    payload = _gmail_get(
        client,
        url=_GMAIL_HISTORY_URL,
        access_token=access_token,
        params={
            "startHistoryId": str(start_history_id),
            "historyTypes": "messageAdded",
            "maxResults": 500,
            **({"pageToken": page_token} if page_token else {}),
        },
    )
    return payload


def _parse_gmail_internal_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
        return None


def _upsert_occurrence(
    db: Session,
    *,
    org_id: UUID,
    mailbox: Mailbox,
    gmail_message_id: str,
    gmail_thread_id: str | None,
    gmail_history_id: int | None,
    gmail_internal_date: datetime | None,
    label_ids: list[str],
) -> EmailMessageOccurrence:
    occurrence = (
        db.query(EmailMessageOccurrence)
        .filter(
            EmailMessageOccurrence.organization_id == org_id,
            EmailMessageOccurrence.mailbox_id == mailbox.id,
            EmailMessageOccurrence.gmail_message_id == gmail_message_id,
        )
        .first()
    )
    if occurrence:
        occurrence.gmail_thread_id = gmail_thread_id
        occurrence.gmail_history_id = gmail_history_id
        occurrence.gmail_internal_date = gmail_internal_date
        occurrence.label_ids = label_ids
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.flush()
        return occurrence

    occurrence = EmailMessageOccurrence(
        organization_id=org_id,
        mailbox_id=mailbox.id,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
        gmail_history_id=gmail_history_id,
        gmail_internal_date=gmail_internal_date,
        label_ids=label_ids,
        state=EmailOccurrenceState.DISCOVERED,
    )
    db.add(occurrence)
    db.flush()
    return occurrence


def _enqueue_occurrence_fetch_raw(
    db: Session,
    *,
    org_id: UUID,
    mailbox: Mailbox,
    occurrence: EmailMessageOccurrence,
) -> UUID | None:
    return _enqueue_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=mailbox.id,
        job_type=JobType.EMAIL_OCCURRENCE_FETCH_RAW,
        payload={
            "organization_id": str(org_id),
            "mailbox_id": str(mailbox.id),
            "occurrence_id": str(occurrence.id),
        },
        dedupe_suffix=str(occurrence.id),
    )


# =============================================================================
# Worker entrypoints for mailbox ingestion jobs
# =============================================================================


def process_mailbox_backfill(db: Session, *, organization_id: UUID, mailbox_id: UUID) -> None:
    """Full mailbox backfill from Gmail (all available history)."""
    mailbox = _ensure_mailbox_belongs_to_org(db, organization_id, mailbox_id)
    if not mailbox.is_enabled:
        return

    access_token = _mailbox_access_token(db, mailbox)
    highest_history_id = mailbox.gmail_history_id
    page_token: str | None = None

    try:
        with httpx.Client() as client:
            while True:
                message_ids, page_token = _gmail_list_message_ids(
                    client,
                    access_token=access_token,
                    page_token=page_token,
                )
                for message_id in message_ids:
                    metadata = _gmail_get_message_metadata(
                        client,
                        access_token=access_token,
                        message_id=message_id,
                    )
                    history_id = int(metadata["historyId"]) if metadata.get("historyId") else None
                    occurrence = _upsert_occurrence(
                        db,
                        org_id=organization_id,
                        mailbox=mailbox,
                        gmail_message_id=message_id,
                        gmail_thread_id=metadata.get("threadId"),
                        gmail_history_id=history_id,
                        gmail_internal_date=_parse_gmail_internal_date(
                            metadata.get("internalDate")
                        ),
                        label_ids=[str(value) for value in (metadata.get("labelIds") or [])],
                    )
                    _enqueue_occurrence_fetch_raw(
                        db,
                        org_id=organization_id,
                        mailbox=mailbox,
                        occurrence=occurrence,
                    )

                    if history_id is not None and (
                        highest_history_id is None or history_id > highest_history_id
                    ):
                        highest_history_id = history_id

                if not page_token:
                    break
    except Exception as exc:
        mailbox.last_sync_error = str(exc)[:500]
        mailbox.updated_at = _now_utc()
        db.add(mailbox)
        db.commit()
        raise

    now = _now_utc()
    mailbox.last_full_sync_at = now
    mailbox.last_incremental_sync_at = now
    mailbox.last_sync_error = None
    mailbox.gmail_history_id = highest_history_id
    mailbox.updated_at = now
    db.add(mailbox)
    db.commit()


def process_mailbox_history_sync(db: Session, *, organization_id: UUID, mailbox_id: UUID) -> None:
    """Incremental mailbox history sync from last known Gmail history id."""
    mailbox = _ensure_mailbox_belongs_to_org(db, organization_id, mailbox_id)
    if not mailbox.is_enabled:
        return

    if mailbox.gmail_history_id is None:
        enqueue_mailbox_backfill(
            db,
            org_id=organization_id,
            mailbox_id=mailbox.id,
            reason="missing_history_id",
        )
        return

    access_token = _mailbox_access_token(db, mailbox)
    highest_history_id = mailbox.gmail_history_id
    page_token: str | None = None
    seen_message_ids: set[str] = set()

    try:
        with httpx.Client() as client:
            while True:
                try:
                    payload = _gmail_list_history(
                        client,
                        access_token=access_token,
                        start_history_id=mailbox.gmail_history_id,
                        page_token=page_token,
                    )
                except RuntimeError as exc:
                    if "404" in str(exc):
                        mailbox.gmail_history_id = None
                        mailbox.last_sync_error = "Gmail history expired. Scheduled full backfill."
                        mailbox.updated_at = _now_utc()
                        db.add(mailbox)
                        db.flush()
                        enqueue_mailbox_backfill(
                            db,
                            org_id=organization_id,
                            mailbox_id=mailbox.id,
                            reason="history_expired",
                        )
                        db.commit()
                        return
                    raise

                response_history_id = payload.get("historyId")
                if response_history_id:
                    highest_history_id = max(highest_history_id, int(response_history_id))

                history_rows = payload.get("history") or []
                for row in history_rows:
                    history_id = int(row["id"]) if row.get("id") else None
                    if history_id:
                        highest_history_id = max(highest_history_id, history_id)
                    for item in row.get("messagesAdded") or []:
                        msg = item.get("message") or {}
                        message_id = msg.get("id")
                        if not message_id or message_id in seen_message_ids:
                            continue
                        seen_message_ids.add(message_id)

                page_token = payload.get("nextPageToken")
                if not page_token:
                    break

            for message_id in seen_message_ids:
                metadata = _gmail_get_message_metadata(
                    client,
                    access_token=access_token,
                    message_id=message_id,
                )
                history_id = int(metadata["historyId"]) if metadata.get("historyId") else None
                occurrence = _upsert_occurrence(
                    db,
                    org_id=organization_id,
                    mailbox=mailbox,
                    gmail_message_id=message_id,
                    gmail_thread_id=metadata.get("threadId"),
                    gmail_history_id=history_id,
                    gmail_internal_date=_parse_gmail_internal_date(metadata.get("internalDate")),
                    label_ids=[str(value) for value in (metadata.get("labelIds") or [])],
                )
                _enqueue_occurrence_fetch_raw(
                    db,
                    org_id=organization_id,
                    mailbox=mailbox,
                    occurrence=occurrence,
                )

                if history_id is not None:
                    highest_history_id = max(highest_history_id, history_id)

    except Exception as exc:
        mailbox.last_sync_error = str(exc)[:500]
        mailbox.updated_at = _now_utc()
        db.add(mailbox)
        db.commit()
        raise

    mailbox.gmail_history_id = highest_history_id
    mailbox.last_incremental_sync_at = _now_utc()
    mailbox.last_sync_error = None
    mailbox.updated_at = _now_utc()
    db.add(mailbox)
    db.commit()


def process_occurrence_fetch_raw(db: Session, *, occurrence_id: UUID) -> None:
    """Fetch raw RFC822 bytes for an occurrence and persist EmailRawBlob."""
    occurrence = (
        db.query(EmailMessageOccurrence).filter(EmailMessageOccurrence.id == occurrence_id).first()
    )
    if occurrence is None:
        return

    mailbox = (
        db.query(Mailbox)
        .filter(
            Mailbox.id == occurrence.mailbox_id,
            Mailbox.organization_id == occurrence.organization_id,
        )
        .first()
    )
    if mailbox is None:
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.raw_fetch_error = "Mailbox not found"
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        return

    access_token = _mailbox_access_token(db, mailbox)

    try:
        with httpx.Client() as client:
            payload = _gmail_get_message_raw(
                client,
                access_token=access_token,
                message_id=occurrence.gmail_message_id,
            )
        raw_encoded = payload.get("raw")
        if not raw_encoded:
            raise RuntimeError("Gmail raw payload missing")

        # Gmail raw payload is URL-safe base64 without required padding.
        padding = "=" * (-len(raw_encoded) % 4)
        raw_bytes = base64.urlsafe_b64decode((raw_encoded + padding).encode("utf-8"))

        sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
        blob = (
            db.query(EmailRawBlob)
            .filter(
                EmailRawBlob.organization_id == occurrence.organization_id,
                EmailRawBlob.sha256_hex == sha256_hex,
            )
            .first()
        )
        if blob is None:
            storage_key = f"email-raw/{occurrence.organization_id}/{sha256_hex}.eml"
            attachment_service.store_file(
                storage_key,
                io.BytesIO(raw_bytes),
                "message/rfc822",
            )
            blob = EmailRawBlob(
                organization_id=occurrence.organization_id,
                sha256_hex=sha256_hex,
                storage_key=storage_key,
                size_bytes=len(raw_bytes),
                content_type="message/rfc822",
            )
            db.add(blob)
            db.flush()

        occurrence.raw_blob_id = blob.id
        occurrence.raw_fetched_at = _now_utc()
        occurrence.raw_fetch_error = None
        occurrence.state = EmailOccurrenceState.RAW_FETCHED
        occurrence.updated_at = _now_utc()
        db.add(occurrence)

        _enqueue_mailbox_job(
            db,
            org_id=occurrence.organization_id,
            mailbox_id=occurrence.mailbox_id,
            job_type=JobType.EMAIL_OCCURRENCE_PARSE,
            payload={
                "organization_id": str(occurrence.organization_id),
                "mailbox_id": str(occurrence.mailbox_id),
                "occurrence_id": str(occurrence.id),
            },
            dedupe_suffix=str(occurrence.id),
        )

        db.commit()
    except Exception as exc:
        occurrence.raw_fetch_error = str(exc)[:500]
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        raise


def _parse_mime_bytes(raw_bytes: bytes) -> dict:
    """Parse raw MIME bytes into normalized message metadata."""
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    subject = str(message.get("Subject") or "").strip() or None
    from_header = str(message.get("From") or "")
    to_header = str(message.get("To") or "")
    cc_header = str(message.get("Cc") or "")
    reply_to_header = str(message.get("Reply-To") or "")

    from_list = getaddresses([from_header])
    to_list = getaddresses([to_header])
    cc_list = getaddresses([cc_header])
    reply_to_list = getaddresses([reply_to_header])

    from_name = from_list[0][0].strip() if from_list else None
    from_email = _normalize_email(from_list[0][1]) if from_list else None

    to_emails = _normalize_email_list([item[1] for item in to_list])
    cc_emails = _normalize_email_list([item[1] for item in cc_list])
    reply_to_emails = _normalize_email_list([item[1] for item in reply_to_list])

    rfc_message_id = str(message.get("Message-ID") or "").strip() or None
    in_reply_to = str(message.get("In-Reply-To") or "").strip() or None
    references = str(message.get("References") or "").strip() or None

    date_header = None
    try:
        if message.get("Date"):
            date_header = parsedate_to_datetime(str(message.get("Date")))
            if date_header and date_header.tzinfo is None:
                date_header = date_header.replace(tzinfo=timezone.utc)
    except Exception:
        date_header = None

    headers_json: dict[str, list[str]] = {}
    for key in message.keys():
        values = message.get_all(key) or []
        headers_json[key] = [str(v) for v in values]

    body_text = None
    body_html = None
    attachments: list[dict] = []

    if message.is_multipart():
        for part in message.walk():
            content_disposition = str(part.get("Content-Disposition") or "").lower()
            filename = part.get_filename()
            content_type = part.get_content_type()

            if filename or "attachment" in content_disposition:
                payload = part.get_payload(decode=True) or b""
                attachments.append(
                    {
                        "filename": filename or "attachment",
                        "content_type": content_type or "application/octet-stream",
                        "bytes": payload,
                        "content_id": str(part.get("Content-ID") or "").strip("<>") or None,
                        "is_inline": "inline" in content_disposition,
                    }
                )
                continue

            if content_type == "text/plain" and body_text is None:
                payload = part.get_payload(decode=True)
                if payload is not None:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_text = payload.decode(charset, errors="replace")
                    except Exception:
                        body_text = payload.decode("utf-8", errors="replace")
            elif content_type == "text/html" and body_html is None:
                payload = part.get_payload(decode=True)
                if payload is not None:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_html = payload.decode(charset, errors="replace")
                    except Exception:
                        body_html = payload.decode("utf-8", errors="replace")
    else:
        payload = message.get_payload(decode=True)
        content_type = message.get_content_type()
        if payload is not None:
            charset = message.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                body_html = decoded
            else:
                body_text = decoded

    snippet_source = body_text or body_html or subject or ""
    snippet = " ".join(snippet_source.strip().split())[:280] or None

    return {
        "subject": subject,
        "subject_norm": _subject_norm(subject),
        "from_email": from_email,
        "from_name": from_name,
        "to_emails": to_emails,
        "cc_emails": cc_emails,
        "reply_to_emails": reply_to_emails,
        "rfc_message_id": rfc_message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "headers_json": headers_json,
        "body_text": body_text,
        "body_html": body_html,
        "snippet": snippet,
        "date_header": date_header,
        "attachments": attachments,
    }


def _store_message_attachment(
    db: Session,
    *,
    organization_id: UUID,
    email_message_id: UUID,
    attachment_payload: dict,
) -> EmailMessageAttachment:
    raw_bytes = attachment_payload["bytes"]
    filename = str(attachment_payload.get("filename") or "attachment")
    content_type = str(attachment_payload.get("content_type") or "application/octet-stream")

    checksum_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    storage_key = f"email-attachments/{organization_id}/{uuid4()}/{filename}"
    attachment_service.store_file(storage_key, io.BytesIO(raw_bytes), content_type)

    attachment = Attachment(
        organization_id=organization_id,
        surrogate_id=None,
        intended_parent_id=None,
        uploaded_by_user_id=None,
        filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size=len(raw_bytes),
        checksum_sha256=checksum_sha256,
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()

    link = EmailMessageAttachment(
        organization_id=organization_id,
        message_id=email_message_id,
        attachment_id=attachment.id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(raw_bytes),
        is_inline=bool(attachment_payload.get("is_inline")),
        content_id=attachment_payload.get("content_id"),
    )
    db.add(link)
    db.flush()
    return link


def process_occurrence_parse(db: Session, *, occurrence_id: UUID) -> None:
    """Parse raw MIME, upsert canonical message/content, and enqueue stitch."""
    occurrence = (
        db.query(EmailMessageOccurrence).filter(EmailMessageOccurrence.id == occurrence_id).first()
    )
    if occurrence is None:
        return
    if occurrence.raw_blob_id is None:
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.parse_error = "missing raw_blob_id"
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        return

    raw_blob = (
        db.query(EmailRawBlob)
        .filter(
            EmailRawBlob.id == occurrence.raw_blob_id,
            EmailRawBlob.organization_id == occurrence.organization_id,
        )
        .first()
    )
    if raw_blob is None:
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.parse_error = "raw blob missing"
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        return

    try:
        raw_bytes = attachment_service.load_file_bytes(raw_blob.storage_key)
        parsed = _parse_mime_bytes(raw_bytes)

        fingerprint = _compute_fingerprint(
            subject_norm=parsed["subject_norm"],
            from_email=parsed["from_email"],
            to=parsed["to_emails"],
            cc=parsed["cc_emails"],
            rfc_message_id=parsed["rfc_message_id"],
        )
        signature = _compute_signature(raw_bytes)

        message = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.organization_id == occurrence.organization_id,
                EmailMessage.fingerprint_sha256 == fingerprint,
                EmailMessage.signature_sha256 == signature,
            )
            .first()
        )
        if message is None:
            message = EmailMessage(
                organization_id=occurrence.organization_id,
                direction=EmailDirection.INBOUND,
                rfc_message_id=parsed["rfc_message_id"],
                gmail_thread_id=occurrence.gmail_thread_id,
                subject_norm=parsed["subject_norm"],
                fingerprint_sha256=fingerprint,
                signature_sha256=signature,
                first_seen_at=_now_utc(),
            )
            db.add(message)
            db.flush()

        content_exists = (
            db.query(EmailMessageContent)
            .filter(
                EmailMessageContent.organization_id == occurrence.organization_id,
                EmailMessageContent.message_id == message.id,
            )
            .first()
        )
        if content_exists is None:
            db.add(
                EmailMessageContent(
                    organization_id=occurrence.organization_id,
                    message_id=message.id,
                    content_version=1,
                    parser_version=1,
                    parsed_at=_now_utc(),
                    date_header=parsed["date_header"],
                    subject=parsed["subject"],
                    subject_norm=parsed["subject_norm"],
                    from_email=parsed["from_email"],
                    from_name=parsed["from_name"],
                    reply_to_emails=parsed["reply_to_emails"],
                    to_emails=parsed["to_emails"],
                    cc_emails=parsed["cc_emails"],
                    headers_json=parsed["headers_json"],
                    body_text=parsed["body_text"],
                    body_html_sanitized=parsed["body_html"],
                    has_attachments=bool(parsed["attachments"]),
                    attachment_count=len(parsed["attachments"]),
                    snippet=parsed["snippet"],
                )
            )

            if parsed["in_reply_to"]:
                for rfc in _extract_rfc_ids(parsed["in_reply_to"]):
                    db.add(
                        EmailMessageThreadRef(
                            organization_id=occurrence.organization_id,
                            message_id=message.id,
                            ref_type="in_reply_to",
                            ref_rfc_message_id=rfc,
                        )
                    )
            if parsed["references"]:
                for rfc in _extract_rfc_ids(parsed["references"]):
                    db.add(
                        EmailMessageThreadRef(
                            organization_id=occurrence.organization_id,
                            message_id=message.id,
                            ref_type="references",
                            ref_rfc_message_id=rfc,
                        )
                    )

            for attachment_payload in parsed["attachments"]:
                _store_message_attachment(
                    db,
                    organization_id=occurrence.organization_id,
                    email_message_id=message.id,
                    attachment_payload=attachment_payload,
                )

        occurrence.message_id = message.id
        occurrence.parsed_at = _now_utc()
        occurrence.parse_error = None
        occurrence.state = EmailOccurrenceState.PARSED

        original_recipient = None
        source = RecipientSource.UNKNOWN
        confidence = LinkConfidence.LOW
        headers_json = parsed["headers_json"] or {}
        for key, source_key in (
            ("X-Gm-Original-To", RecipientSource.WORKSPACE_HEADER),
            ("Delivered-To", RecipientSource.DELIVERED_TO),
            ("X-Original-To", RecipientSource.X_ORIGINAL_TO),
        ):
            values = headers_json.get(key) or []
            if values:
                candidate = _normalize_email(values[0])
                if candidate:
                    original_recipient = candidate
                    source = source_key
                    confidence = LinkConfidence.HIGH
                    break

        if original_recipient is None:
            scan_candidates = parsed["to_emails"] + parsed["cc_emails"]
            if scan_candidates:
                original_recipient = scan_candidates[0]
                source = RecipientSource.TO_CC_SCAN
                confidence = LinkConfidence.MEDIUM

        occurrence.original_recipient = original_recipient
        occurrence.original_recipient_source = source
        occurrence.original_recipient_confidence = confidence
        occurrence.original_recipient_evidence = {
            "from": parsed["from_email"],
            "to": parsed["to_emails"],
            "cc": parsed["cc_emails"],
        }
        occurrence.updated_at = _now_utc()

        db.add(occurrence)

        _enqueue_mailbox_job(
            db,
            org_id=occurrence.organization_id,
            mailbox_id=occurrence.mailbox_id,
            job_type=JobType.EMAIL_OCCURRENCE_STITCH,
            payload={
                "organization_id": str(occurrence.organization_id),
                "mailbox_id": str(occurrence.mailbox_id),
                "occurrence_id": str(occurrence.id),
            },
            dedupe_suffix=str(occurrence.id),
        )

        db.commit()
    except Exception as exc:
        occurrence.parse_error = str(exc)[:500]
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        raise


def _find_ticket_by_reply_token(
    db: Session, *, organization_id: UUID, reply_to_emails: list[str]
) -> UUID | None:
    for email in reply_to_emails:
        match = _REPLY_TO_TOKEN_RE.match((email or "").strip().lower())
        if not match:
            continue
        code = match.group(1)
        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.organization_id == organization_id,
                func.lower(Ticket.ticket_code) == code,
            )
            .first()
        )
        if ticket:
            return ticket.id
    return None


def _find_ticket_by_rfc_thread_refs(
    db: Session,
    *,
    organization_id: UUID,
    message_id: UUID,
) -> UUID | None:
    refs = (
        db.query(EmailMessageThreadRef)
        .filter(
            EmailMessageThreadRef.organization_id == organization_id,
            EmailMessageThreadRef.message_id == message_id,
            EmailMessageThreadRef.ref_type.in_(["in_reply_to", "references"]),
        )
        .order_by(EmailMessageThreadRef.created_at.asc())
        .all()
    )
    if not refs:
        return None

    rfc_ids = [ref.ref_rfc_message_id for ref in refs if ref.ref_rfc_message_id]
    if not rfc_ids:
        return None

    linked = (
        db.query(TicketMessage.ticket_id)
        .join(
            EmailMessage,
            and_(
                EmailMessage.organization_id == TicketMessage.organization_id,
                EmailMessage.id == TicketMessage.message_id,
            ),
        )
        .filter(
            TicketMessage.organization_id == organization_id,
            EmailMessage.rfc_message_id.in_(rfc_ids),
        )
        .order_by(TicketMessage.stitched_at.asc())
        .first()
    )
    return linked[0] if linked else None


def _find_ticket_by_gmail_thread(
    db: Session,
    *,
    organization_id: UUID,
    gmail_thread_id: str | None,
) -> UUID | None:
    if not gmail_thread_id:
        return None

    existing = (
        db.query(EmailMessageOccurrence)
        .filter(
            EmailMessageOccurrence.organization_id == organization_id,
            EmailMessageOccurrence.gmail_thread_id == gmail_thread_id,
            EmailMessageOccurrence.ticket_id.isnot(None),
        )
        .order_by(EmailMessageOccurrence.created_at.desc())
        .first()
    )
    return existing.ticket_id if existing else None


def _find_ticket_by_subject_participants(
    db: Session,
    *,
    organization_id: UUID,
    subject_norm: str | None,
    requester_email: str | None,
) -> UUID | None:
    if not subject_norm or not requester_email:
        return None

    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.organization_id == organization_id,
            Ticket.subject_norm == subject_norm,
            func.lower(Ticket.requester_email) == requester_email.lower(),
            Ticket.status.notin_([TicketStatus.CLOSED.value, TicketStatus.SPAM.value]),
        )
        .order_by(func.coalesce(Ticket.last_activity_at, Ticket.created_at).desc())
        .first()
    )
    return ticket.id if ticket else None


def _create_ticket_for_occurrence(
    db: Session,
    *,
    organization_id: UUID,
    subject: str | None,
    subject_norm: str | None,
    requester_email: str | None,
    requester_name: str | None,
    first_message_at: datetime | None,
    stitch_reason: str,
    stitch_confidence: LinkConfidence,
) -> Ticket:
    now = _now_utc()
    event_time = first_message_at or now
    ticket = Ticket(
        organization_id=organization_id,
        ticket_code=generate_ticket_code(db, organization_id),
        status=TicketStatus.NEW,
        priority=TicketPriority.NORMAL,
        subject=subject,
        subject_norm=subject_norm,
        requester_email=requester_email,
        requester_name=requester_name,
        surrogate_link_status=TicketLinkStatus.NEEDS_REVIEW,
        stitch_reason=stitch_reason,
        stitch_confidence=stitch_confidence,
        first_message_at=event_time,
        last_message_at=event_time,
        last_activity_at=event_time,
    )
    db.add(ticket)
    db.flush()
    return ticket


def _link_message_to_ticket(
    db: Session,
    *,
    organization_id: UUID,
    ticket_id: UUID,
    message_id: UUID,
    reason: str,
    confidence: LinkConfidence,
) -> None:
    existing = (
        db.query(TicketMessage)
        .filter(
            TicketMessage.organization_id == organization_id,
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.message_id == message_id,
        )
        .first()
    )
    if existing:
        return

    db.add(
        TicketMessage(
            organization_id=organization_id,
            ticket_id=ticket_id,
            message_id=message_id,
            stitch_reason=reason,
            stitch_confidence=confidence,
        )
    )


def process_occurrence_stitch(db: Session, *, occurrence_id: UUID) -> None:
    """Stitch parsed occurrence to an existing/new ticket."""
    occurrence = (
        db.query(EmailMessageOccurrence).filter(EmailMessageOccurrence.id == occurrence_id).first()
    )
    if occurrence is None:
        return
    if occurrence.message_id is None:
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.stitch_error = "missing message_id"
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        return

    org_id = occurrence.organization_id

    existing_link = (
        db.query(TicketMessage)
        .filter(
            TicketMessage.organization_id == org_id,
            TicketMessage.message_id == occurrence.message_id,
        )
        .first()
    )
    if existing_link:
        occurrence.ticket_id = existing_link.ticket_id
        occurrence.stitched_at = _now_utc()
        occurrence.stitch_error = None
        occurrence.state = EmailOccurrenceState.STITCHED
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        _enqueue_mailbox_job(
            db,
            org_id=org_id,
            mailbox_id=occurrence.mailbox_id,
            job_type=JobType.TICKET_APPLY_LINKING,
            payload={
                "organization_id": str(org_id),
                "mailbox_id": str(occurrence.mailbox_id),
                "ticket_id": str(existing_link.ticket_id),
            },
            dedupe_suffix=str(existing_link.ticket_id),
        )
        db.commit()
        return

    content = (
        db.query(EmailMessageContent)
        .filter(
            EmailMessageContent.organization_id == org_id,
            EmailMessageContent.message_id == occurrence.message_id,
        )
        .order_by(EmailMessageContent.content_version.desc(), EmailMessageContent.parsed_at.desc())
        .first()
    )
    if content is None:
        occurrence.state = EmailOccurrenceState.FAILED
        occurrence.stitch_error = "missing message content"
        occurrence.updated_at = _now_utc()
        db.add(occurrence)
        db.commit()
        return

    headers_json = content.headers_json or {}
    header_ticket_id = None
    for key in ("X-SF-Ticket-ID", "X-OSS-Ticket-ID", "X-CRM-Ticket-ID"):
        values = headers_json.get(key) or []
        if not values:
            continue
        try:
            header_ticket_id = UUID(str(values[0]))
        except Exception:
            continue
        break

    ticket: Ticket | None = None
    stitch_reason = "new_ticket"
    stitch_confidence = LinkConfidence.LOW

    if header_ticket_id is not None:
        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.organization_id == org_id,
                Ticket.id == header_ticket_id,
            )
            .first()
        )
        if ticket:
            stitch_reason = "explicit_header"
            stitch_confidence = LinkConfidence.HIGH

    if ticket is None:
        reply_ticket_id = _find_ticket_by_reply_token(
            db,
            organization_id=org_id,
            reply_to_emails=list(content.reply_to_emails or []),
        )
        if reply_ticket_id:
            ticket = _ensure_ticket_belongs_to_org(db, org_id, reply_ticket_id)
            stitch_reason = "reply_token"
            stitch_confidence = LinkConfidence.HIGH

    if ticket is None:
        ref_ticket_id = _find_ticket_by_rfc_thread_refs(
            db,
            organization_id=org_id,
            message_id=occurrence.message_id,
        )
        if ref_ticket_id:
            ticket = _ensure_ticket_belongs_to_org(db, org_id, ref_ticket_id)
            stitch_reason = "rfc_references"
            stitch_confidence = LinkConfidence.MEDIUM

    if ticket is None:
        thread_ticket_id = _find_ticket_by_gmail_thread(
            db,
            organization_id=org_id,
            gmail_thread_id=occurrence.gmail_thread_id,
        )
        if thread_ticket_id:
            ticket = _ensure_ticket_belongs_to_org(db, org_id, thread_ticket_id)
            stitch_reason = "gmail_thread"
            stitch_confidence = LinkConfidence.MEDIUM

    if ticket is None:
        subject_ticket_id = _find_ticket_by_subject_participants(
            db,
            organization_id=org_id,
            subject_norm=content.subject_norm,
            requester_email=content.from_email,
        )
        if subject_ticket_id:
            ticket = _ensure_ticket_belongs_to_org(db, org_id, subject_ticket_id)
            stitch_reason = "subject_participant"
            stitch_confidence = LinkConfidence.LOW

    if ticket is None:
        ticket = _create_ticket_for_occurrence(
            db,
            organization_id=org_id,
            subject=content.subject,
            subject_norm=content.subject_norm,
            requester_email=content.from_email,
            requester_name=content.from_name,
            first_message_at=content.date_header,
            stitch_reason="new_message",
            stitch_confidence=LinkConfidence.LOW,
        )
        db.add(
            TicketEvent(
                organization_id=org_id,
                ticket_id=ticket.id,
                actor_user_id=None,
                event_type="ticket_created",
                event_data={"source": "inbound_stitch"},
            )
        )

    _link_message_to_ticket(
        db,
        organization_id=org_id,
        ticket_id=ticket.id,
        message_id=occurrence.message_id,
        reason=stitch_reason,
        confidence=stitch_confidence,
    )

    event_time = content.date_header or _now_utc()
    if ticket.first_message_at is None or ticket.first_message_at > event_time:
        ticket.first_message_at = event_time
    if ticket.last_message_at is None or ticket.last_message_at < event_time:
        ticket.last_message_at = event_time
    ticket.last_activity_at = max(ticket.last_activity_at or event_time, event_time)
    ticket.updated_at = _now_utc()

    occurrence.ticket_id = ticket.id
    occurrence.stitched_at = _now_utc()
    occurrence.stitch_error = None
    occurrence.state = EmailOccurrenceState.STITCHED
    occurrence.updated_at = _now_utc()

    db.add(ticket)
    db.add(occurrence)

    _enqueue_mailbox_job(
        db,
        org_id=org_id,
        mailbox_id=occurrence.mailbox_id,
        job_type=JobType.TICKET_APPLY_LINKING,
        payload={
            "organization_id": str(org_id),
            "mailbox_id": str(occurrence.mailbox_id),
            "ticket_id": str(ticket.id),
        },
        dedupe_suffix=str(ticket.id),
    )

    db.commit()


# =============================================================================
# Surrogate linking workflow (auto + needs review)
# =============================================================================


def _ticket_participant_emails(db: Session, *, org_id: UUID, ticket_id: UUID) -> list[str]:
    rows = (
        db.query(EmailMessageContent)
        .join(
            TicketMessage,
            and_(
                TicketMessage.organization_id == EmailMessageContent.organization_id,
                TicketMessage.message_id == EmailMessageContent.message_id,
            ),
        )
        .filter(
            EmailMessageContent.organization_id == org_id,
            TicketMessage.ticket_id == ticket_id,
        )
        .all()
    )

    participants: list[str] = []
    for row in rows:
        if row.from_email:
            participants.append(row.from_email)
        participants.extend(list(row.to_emails or []))
        participants.extend(list(row.cc_emails or []))
        participants.extend(list(row.reply_to_emails or []))

    occurrences = (
        db.query(EmailMessageOccurrence)
        .filter(
            EmailMessageOccurrence.organization_id == org_id,
            EmailMessageOccurrence.ticket_id == ticket_id,
            EmailMessageOccurrence.original_recipient.isnot(None),
        )
        .all()
    )
    for occ in occurrences:
        if occ.original_recipient:
            participants.append(occ.original_recipient)

    return _normalize_email_list(participants)


def apply_ticket_linking(
    db: Session,
    *,
    org_id: UUID,
    ticket_id: UUID,
    actor_user_id: UUID | None = None,
) -> Ticket:
    """Conservative surrogate linking: auto-link only when exactly one candidate."""
    ticket = _ensure_ticket_belongs_to_org(db, org_id, ticket_id)

    participants = _ticket_participant_emails(db, org_id=org_id, ticket_id=ticket.id)
    participant_hashes = {hash_email(email) for email in participants}

    surrogate_ids: set[UUID] = set()
    evidence_by_surrogate: dict[UUID, dict] = {}

    if participant_hashes:
        direct = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == org_id,
                Surrogate.email_hash.in_(participant_hashes),
            )
            .all()
        )
        for surrogate in direct:
            surrogate_ids.add(surrogate.id)
            evidence_by_surrogate[surrogate.id] = {
                "source": "surrogate_primary_email",
                "emails": [mask_email(surrogate.email)],
            }

        contacts = (
            db.query(SurrogateEmailContact)
            .filter(
                SurrogateEmailContact.organization_id == org_id,
                SurrogateEmailContact.is_active.is_(True),
                SurrogateEmailContact.email_hash.in_(participant_hashes),
            )
            .all()
        )
        for contact in contacts:
            surrogate_ids.add(contact.surrogate_id)
            entry = evidence_by_surrogate.setdefault(
                contact.surrogate_id,
                {
                    "source": "surrogate_email_contact",
                    "emails": [],
                    "contact_ids": [],
                },
            )
            entry.setdefault("emails", []).append(mask_email(contact.email))
            entry.setdefault("contact_ids", []).append(str(contact.id))

    # Replace candidate rows.
    (
        db.query(TicketSurrogateLinkCandidate)
        .filter(
            TicketSurrogateLinkCandidate.organization_id == org_id,
            TicketSurrogateLinkCandidate.ticket_id == ticket.id,
        )
        .delete(synchronize_session=False)
    )

    for surrogate_id in sorted(surrogate_ids, key=str):
        db.add(
            TicketSurrogateLinkCandidate(
                organization_id=org_id,
                ticket_id=ticket.id,
                surrogate_id=surrogate_id,
                confidence=LinkConfidence.HIGH,
                evidence_json=evidence_by_surrogate.get(surrogate_id, {}),
                is_selected=False,
            )
        )

    now = _now_utc()
    if len(surrogate_ids) == 1:
        selected = next(iter(surrogate_ids))
        ticket.surrogate_id = selected
        ticket.surrogate_link_status = TicketLinkStatus.LINKED
        (
            db.query(TicketSurrogateLinkCandidate)
            .filter(
                TicketSurrogateLinkCandidate.organization_id == org_id,
                TicketSurrogateLinkCandidate.ticket_id == ticket.id,
                TicketSurrogateLinkCandidate.surrogate_id == selected,
            )
            .update({"is_selected": True}, synchronize_session=False)
        )
        event_type = "surrogate_auto_linked"
        event_data = {"surrogate_id": str(selected), "participants": participants}
    else:
        ticket.surrogate_id = None
        ticket.surrogate_link_status = TicketLinkStatus.NEEDS_REVIEW
        event_type = "surrogate_needs_review"
        event_data = {
            "candidate_count": len(surrogate_ids),
            "candidate_ids": [str(sid) for sid in sorted(surrogate_ids, key=str)],
            "participants": participants,
        }

    ticket.updated_at = now
    ticket.last_activity_at = now

    db.add(ticket)
    db.add(
        TicketEvent(
            organization_id=org_id,
            ticket_id=ticket.id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_data=event_data,
        )
    )

    # Mark linked state on occurrences for this ticket.
    (
        db.query(EmailMessageOccurrence)
        .filter(
            EmailMessageOccurrence.organization_id == org_id,
            EmailMessageOccurrence.ticket_id == ticket.id,
        )
        .update(
            {
                "state": EmailOccurrenceState.LINKED.value,
                "linked_at": now,
                "link_error": None,
                "updated_at": now,
            },
            synchronize_session=False,
        )
    )

    db.commit()
    db.refresh(ticket)
    return ticket


# =============================================================================
# Integrations helpers used by routers
# =============================================================================


def parse_granted_scopes_from_tokens(tokens: dict | None) -> list[str] | None:
    """Parse `scope` string from OAuth token response."""
    return _gmail_scopes_from_token_response(tokens)


# =============================================================================
# Legacy surrogate send-email mirroring helper
# =============================================================================


def _find_ticket_by_gmail_thread(
    db: Session,
    *,
    org_id: UUID,
    gmail_thread_id: str | None,
) -> Ticket | None:
    if not gmail_thread_id:
        return None

    return (
        db.query(Ticket)
        .join(
            TicketMessage,
            and_(
                TicketMessage.organization_id == Ticket.organization_id,
                TicketMessage.ticket_id == Ticket.id,
            ),
        )
        .join(
            EmailMessage,
            and_(
                EmailMessage.organization_id == TicketMessage.organization_id,
                EmailMessage.id == TicketMessage.message_id,
            ),
        )
        .filter(
            Ticket.organization_id == org_id,
            EmailMessage.gmail_thread_id == gmail_thread_id,
        )
        .order_by(Ticket.last_activity_at.desc().nullslast(), Ticket.created_at.desc())
        .first()
    )


def record_surrogate_outbound_gmail_send(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    surrogate_id: UUID,
    to_email: str,
    subject: str,
    body_html: str,
    gmail_message_id: str | None,
    gmail_thread_id: str | None,
) -> UUID:
    """Mirror legacy surrogate Gmail send-email success into ticketing tables."""
    _ensure_surrogate_belongs_to_org(db, org_id, surrogate_id)

    normalized_to = _normalize_email_list([to_email])
    if not normalized_to:
        raise HTTPException(status_code=422, detail="Recipient email is required")

    subject_value = (subject or "").strip() or "(No subject)"
    body_text = re.sub(r"<[^>]+>", " ", body_html or "")
    body_text = " ".join(body_text.split()) or "Message"
    now = _now_utc()

    ticket = _find_ticket_by_gmail_thread(
        db,
        org_id=org_id,
        gmail_thread_id=gmail_thread_id,
    )
    if ticket is None:
        ticket = Ticket(
            organization_id=org_id,
            ticket_code=generate_ticket_code(db, org_id),
            status=TicketStatus.NEW,
            priority=TicketPriority.NORMAL,
            subject=subject_value,
            subject_norm=_subject_norm(subject_value),
            requester_email=normalized_to[0],
            requester_name=None,
            assignee_queue_id=None,
            surrogate_id=surrogate_id,
            surrogate_link_status=TicketLinkStatus.LINKED,
            stitch_reason="surrogate_send_email",
            stitch_confidence=LinkConfidence.HIGH,
            first_message_at=now,
            last_message_at=now,
            last_activity_at=now,
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketEvent(
                organization_id=org_id,
                ticket_id=ticket.id,
                actor_user_id=actor_user_id,
                event_type="ticket_created",
                event_data={"source": "surrogate_send_email"},
            )
        )
    else:
        ticket.surrogate_id = surrogate_id
        ticket.surrogate_link_status = TicketLinkStatus.LINKED
        if not ticket.subject:
            ticket.subject = subject_value
            ticket.subject_norm = _subject_norm(subject_value)

    integration = oauth_service.get_user_integration(db, actor_user_id, "gmail")
    from_email = getattr(integration, "account_email", None) if integration is not None else None

    message = _create_outbound_message_record(
        db,
        org_id=org_id,
        ticket=ticket,
        from_email=from_email or "me",
        to_emails=normalized_to,
        cc_emails=[],
        subject=subject_value,
        body_text=body_text,
        body_html=body_html,
        gmail_thread_id=gmail_thread_id or ticket.ticket_code,
        gmail_message_id=gmail_message_id,
    )

    _link_outbound_message_to_ticket(
        db,
        org_id=org_id,
        ticket=ticket,
        message=message,
        actor_user_id=actor_user_id,
        to_emails=normalized_to,
        cc_emails=[],
    )

    db.commit()
    db.refresh(ticket)
    return ticket.id


# =============================================================================
# Compatibility wrapper for surrogate send-email endpoint
# =============================================================================


def compose_surrogate_template_email(
    db: Session,
    *,
    org_id: UUID,
    actor_user_id: UUID,
    surrogate_id: UUID,
    to_email: str,
    subject: str,
    body_html: str,
    idempotency_key: str | None,
) -> dict:
    """Route legacy surrogate send-email flow through ticket compose."""
    body_text = re.sub(r"<[^>]+>", " ", body_html or "")
    body_text = " ".join(body_text.split()) or "Message"
    return compose_ticket(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
        to_emails=[to_email],
        cc_emails=[],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        surrogate_id=surrogate_id,
        queue_id=None,
        idempotency_key=idempotency_key,
    )
