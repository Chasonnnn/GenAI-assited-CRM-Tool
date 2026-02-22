"""Pydantic schemas for ticketing + mailbox ingestion APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TicketListItem(BaseModel):
    """Inbox row for a ticket."""

    id: UUID
    ticket_code: str
    status: str
    priority: str
    subject: str | None = None
    requester_email: str | None = None
    requester_name: str | None = None
    assignee_user_id: UUID | None = None
    assignee_queue_id: UUID | None = None
    surrogate_id: UUID | None = None
    surrogate_link_status: str
    first_message_at: datetime | None = None
    last_message_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TicketListResponse(BaseModel):
    """Ticket list response with cursor pagination."""

    items: list[TicketListItem]
    next_cursor: str | None = None


class TicketMessageAttachmentRead(BaseModel):
    """Attachment metadata linked to a ticket message."""

    id: UUID
    attachment_id: UUID
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int
    is_inline: bool
    content_id: str | None = None


class TicketMessageOccurrenceRead(BaseModel):
    """Occurrence metadata for debugging/traceability."""

    id: UUID
    mailbox_id: UUID
    gmail_message_id: str
    gmail_thread_id: str | None = None
    state: str
    original_recipient: str | None = None
    original_recipient_source: str | None = None
    original_recipient_confidence: str | None = None
    original_recipient_evidence: dict = Field(default_factory=dict)
    parse_error: str | None = None
    stitch_error: str | None = None
    link_error: str | None = None
    created_at: datetime


class TicketMessageRead(BaseModel):
    """Message timeline item for a ticket."""

    id: UUID
    message_id: UUID
    direction: str
    stitched_at: datetime
    stitch_reason: str
    stitch_confidence: str
    rfc_message_id: str | None = None
    gmail_thread_id: str | None = None
    date_header: datetime | None = None
    subject: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    reply_to_emails: list[str] = Field(default_factory=list)
    snippet: str | None = None
    body_text: str | None = None
    body_html_sanitized: str | None = None
    attachments: list[TicketMessageAttachmentRead] = Field(default_factory=list)
    occurrences: list[TicketMessageOccurrenceRead] = Field(default_factory=list)


class TicketEventRead(BaseModel):
    """Immutable ticket event."""

    id: UUID
    actor_user_id: UUID | None = None
    event_type: str
    event_data: dict = Field(default_factory=dict)
    created_at: datetime


class TicketNoteRead(BaseModel):
    """Internal ticket note."""

    id: UUID
    author_user_id: UUID | None = None
    body_markdown: str
    body_html_sanitized: str | None = None
    created_at: datetime
    updated_at: datetime


class TicketCandidateRead(BaseModel):
    """Surrogate candidate for manual link review."""

    id: UUID
    surrogate_id: UUID
    confidence: str
    evidence_json: dict = Field(default_factory=dict)
    is_selected: bool
    created_at: datetime


class TicketDetailResponse(BaseModel):
    """Ticket detail response."""

    ticket: TicketListItem
    messages: list[TicketMessageRead] = Field(default_factory=list)
    events: list[TicketEventRead] = Field(default_factory=list)
    notes: list[TicketNoteRead] = Field(default_factory=list)
    candidates: list[TicketCandidateRead] = Field(default_factory=list)


class TicketPatchRequest(BaseModel):
    """Ticket update payload."""

    status: str | None = None
    priority: str | None = None
    assignee_user_id: UUID | None = None
    assignee_queue_id: UUID | None = None


class TicketReplyRequest(BaseModel):
    """Threaded reply payload."""

    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    subject: str | None = None
    body_text: str
    body_html: str | None = None
    idempotency_key: str | None = None


class TicketComposeRequest(BaseModel):
    """New outbound ticket payload."""

    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: str | None = None
    surrogate_id: UUID | None = None
    queue_id: UUID | None = None
    idempotency_key: str | None = None


class TicketSendResult(BaseModel):
    """Compose/reply result payload."""

    status: str
    ticket_id: UUID
    message_id: UUID
    provider: str
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    job_id: UUID | None = None


class TicketNoteCreateRequest(BaseModel):
    """Add note payload."""

    body_markdown: str = Field(min_length=1, max_length=20000)


class TicketLinkSurrogateRequest(BaseModel):
    """Manual link resolution payload."""

    surrogate_id: UUID | None = None
    reason: str | None = None


class TicketSendIdentity(BaseModel):
    """Available sender identity."""

    integration_id: UUID
    account_email: str
    provider: str = "gmail"
    is_default: bool = True


class TicketSendIdentityResponse(BaseModel):
    """List of sender identities."""

    items: list[TicketSendIdentity] = Field(default_factory=list)


class SurrogateTicketEmailItem(BaseModel):
    """Ticket summary for surrogate Emails tab."""

    id: UUID
    ticket_code: str
    subject: str | None = None
    status: str
    priority: str
    requester_email: str | None = None
    last_activity_at: datetime | None = None
    created_at: datetime


class SurrogateTicketEmailListResponse(BaseModel):
    """Surrogate-scoped email history."""

    items: list[SurrogateTicketEmailItem]


class SurrogateEmailContactRead(BaseModel):
    """Surrogate contact email row."""

    id: UUID
    surrogate_id: UUID
    email: str
    email_domain: str | None = None
    source: str
    label: str | None = None
    contact_type: str | None = None
    is_active: bool
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SurrogateEmailContactListResponse(BaseModel):
    """Contact list for surrogate emails."""

    items: list[SurrogateEmailContactRead]


class SurrogateEmailContactCreateRequest(BaseModel):
    """Create manual surrogate email contact."""

    email: str
    label: str | None = None
    contact_type: str | None = None


class SurrogateEmailContactPatchRequest(BaseModel):
    """Update manual surrogate contact."""

    email: str | None = None
    label: str | None = None
    contact_type: str | None = None
    is_active: bool | None = None


class MailboxRead(BaseModel):
    """Mailbox source view."""

    id: UUID
    kind: str
    provider: str
    email_address: str
    display_name: str | None = None
    is_enabled: bool
    ingestion_paused_until: datetime | None = None
    ingestion_pause_reason: str | None = None
    gmail_history_id: int | None = None
    gmail_watch_expiration_at: datetime | None = None
    gmail_watch_last_renewed_at: datetime | None = None
    gmail_watch_topic_name: str | None = None
    gmail_watch_last_error: str | None = None
    last_incremental_sync_at: datetime | None = None
    last_full_sync_at: datetime | None = None
    last_sync_error: str | None = None
    default_queue_id: UUID | None = None
    user_integration_id: UUID | None = None
    credential_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class MailboxListResponse(BaseModel):
    """Mailbox list payload."""

    items: list[MailboxRead]


class MailboxSyncStatusResponse(BaseModel):
    """Mailbox sync status summary."""

    mailbox_id: UUID
    is_enabled: bool
    paused_until: datetime | None = None
    gmail_history_id: int | None = None
    gmail_watch_expiration_at: datetime | None = None
    gmail_watch_last_renewed_at: datetime | None = None
    gmail_watch_topic_name: str | None = None
    gmail_watch_last_error: str | None = None
    last_full_sync_at: datetime | None = None
    last_incremental_sync_at: datetime | None = None
    last_sync_error: str | None = None
    queued_jobs_by_type: dict[str, int] = Field(default_factory=dict)
    running_jobs_by_type: dict[str, int] = Field(default_factory=dict)


class MailboxJobEnqueueResponse(BaseModel):
    """Result for sync enqueue endpoints."""

    queued: bool
    job_id: UUID | None = None
    reason: str | None = None


class MailboxPauseRequest(BaseModel):
    """Pause request payload."""

    minutes: int = Field(default=60, ge=1, le=10080)
    reason: str | None = None


class MailboxPauseResponse(BaseModel):
    """Pause state payload."""

    mailbox_id: UUID
    paused: bool
    paused_until: datetime
    pause_reason: str


class OAuthStartResponse(BaseModel):
    """OAuth start response."""

    auth_url: str


class InternalGmailSyncScheduleResponse(BaseModel):
    """Internal scheduler response for incremental Gmail sync."""

    mailboxes_checked: int
    jobs_created: int
    duplicates_skipped: int
    watch_jobs_created: int = 0
    watch_duplicates_skipped: int = 0
