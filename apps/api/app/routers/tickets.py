"""Ticket inbox/detail/reply APIs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.ticketing import (
    TicketDetailResponse,
    TicketListItem,
    TicketListResponse,
    TicketPatchRequest,
    TicketReplyRequest,
    TicketComposeRequest,
    TicketSendResult,
    TicketNoteCreateRequest,
    TicketNoteRead,
    TicketLinkSurrogateRequest,
    TicketSendIdentityResponse,
)
from app.services import ticketing_service

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    dependencies=[Depends(require_permission(POLICIES["tickets"].default))],
)


@router.get("", response_model=TicketListResponse)
def list_tickets(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    queue_id: UUID | None = None,
    assignee_user_id: UUID | None = None,
    surrogate_id: UUID | None = None,
    needs_review: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> TicketListResponse:
    """List tickets with cursor pagination + inbox filters."""
    page = ticketing_service.list_tickets(
        db,
        org_id=session.org_id,
        limit=limit,
        cursor=cursor,
        status_filter=status,
        priority_filter=priority,
        queue_id=queue_id,
        assignee_user_id=assignee_user_id,
        surrogate_id=surrogate_id,
        needs_review=needs_review,
        q=q,
    )
    items = [
        TicketListItem(
            id=ticket.id,
            ticket_code=ticket.ticket_code,
            status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            priority=ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
            subject=ticket.subject,
            requester_email=ticket.requester_email,
            requester_name=ticket.requester_name,
            assignee_user_id=ticket.assignee_user_id,
            assignee_queue_id=ticket.assignee_queue_id,
            surrogate_id=ticket.surrogate_id,
            surrogate_link_status=ticket.surrogate_link_status.value
            if hasattr(ticket.surrogate_link_status, "value")
            else str(ticket.surrogate_link_status),
            first_message_at=ticket.first_message_at,
            last_message_at=ticket.last_message_at,
            last_activity_at=ticket.last_activity_at,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )
        for ticket in page.items
    ]
    return TicketListResponse(items=items, next_cursor=page.next_cursor)


@router.get("/send-identities", response_model=TicketSendIdentityResponse)
def list_send_identities(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["tickets"].actions["reply"])),
) -> TicketSendIdentityResponse:
    """List available Gmail sender identities for the current user."""
    identities = ticketing_service.list_send_identities(db, user_id=session.user_id)
    return TicketSendIdentityResponse(items=identities)


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket_detail(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> TicketDetailResponse:
    """Return ticket detail timeline and metadata."""
    payload = ticketing_service.get_ticket_detail(
        db,
        org_id=session.org_id,
        ticket_id=ticket_id,
    )
    return TicketDetailResponse(**payload)


@router.patch(
    "/{ticket_id}",
    response_model=TicketListItem,
    dependencies=[Depends(require_csrf_header)],
)
def patch_ticket(
    ticket_id: UUID,
    data: TicketPatchRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["tickets"].actions["edit"])),
) -> TicketListItem:
    """Update status/priority/assignment."""
    ticket = ticketing_service.patch_ticket(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        ticket_id=ticket_id,
        status_value=data.status,
        priority_value=data.priority,
        assignee_user_id=data.assignee_user_id,
        assignee_queue_id=data.assignee_queue_id,
    )
    return TicketListItem(
        id=ticket.id,
        ticket_code=ticket.ticket_code,
        status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        priority=ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
        subject=ticket.subject,
        requester_email=ticket.requester_email,
        requester_name=ticket.requester_name,
        assignee_user_id=ticket.assignee_user_id,
        assignee_queue_id=ticket.assignee_queue_id,
        surrogate_id=ticket.surrogate_id,
        surrogate_link_status=ticket.surrogate_link_status.value
        if hasattr(ticket.surrogate_link_status, "value")
        else str(ticket.surrogate_link_status),
        first_message_at=ticket.first_message_at,
        last_message_at=ticket.last_message_at,
        last_activity_at=ticket.last_activity_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post(
    "/{ticket_id}/reply",
    response_model=TicketSendResult,
    dependencies=[Depends(require_csrf_header)],
)
def reply_ticket(
    ticket_id: UUID,
    data: TicketReplyRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["tickets"].actions["reply"])),
) -> TicketSendResult:
    """Send threaded reply via Gmail."""
    payload = ticketing_service.reply_to_ticket(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        ticket_id=ticket_id,
        to_emails=data.to_emails,
        cc_emails=data.cc_emails,
        subject=data.subject,
        body_text=data.body_text,
        body_html=data.body_html,
        idempotency_key=data.idempotency_key,
    )
    return TicketSendResult(**payload)


@router.post(
    "/compose",
    response_model=TicketSendResult,
    dependencies=[Depends(require_csrf_header)],
)
def compose_ticket(
    data: TicketComposeRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["tickets"].actions["reply"])),
) -> TicketSendResult:
    """Compose a new outbound ticket message."""
    payload = ticketing_service.compose_ticket(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        to_emails=data.to_emails,
        cc_emails=data.cc_emails,
        subject=data.subject,
        body_text=data.body_text,
        body_html=data.body_html,
        surrogate_id=data.surrogate_id,
        queue_id=data.queue_id,
        idempotency_key=data.idempotency_key,
    )
    return TicketSendResult(**payload)


@router.post(
    "/{ticket_id}/notes",
    response_model=TicketNoteRead,
    dependencies=[Depends(require_csrf_header)],
)
def add_ticket_note(
    ticket_id: UUID,
    data: TicketNoteCreateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["tickets"].actions["edit"])),
) -> TicketNoteRead:
    """Add an internal ticket note."""
    note = ticketing_service.add_ticket_note(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        ticket_id=ticket_id,
        body_markdown=data.body_markdown,
    )
    return TicketNoteRead(
        id=note.id,
        author_user_id=note.author_user_id,
        body_markdown=note.body_markdown,
        body_html_sanitized=note.body_html_sanitized,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.post(
    "/{ticket_id}/link-surrogate",
    response_model=TicketListItem,
    dependencies=[Depends(require_csrf_header)],
)
def link_ticket_surrogate(
    ticket_id: UUID,
    data: TicketLinkSurrogateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(
        require_permission(POLICIES["tickets"].actions["link_surrogates"])
    ),
) -> TicketListItem:
    """Manually link/unlink surrogate mapping for a ticket."""
    ticket = ticketing_service.link_ticket_surrogate(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        ticket_id=ticket_id,
        surrogate_id=data.surrogate_id,
        reason=data.reason,
    )
    return TicketListItem(
        id=ticket.id,
        ticket_code=ticket.ticket_code,
        status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
        priority=ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
        subject=ticket.subject,
        requester_email=ticket.requester_email,
        requester_name=ticket.requester_name,
        assignee_user_id=ticket.assignee_user_id,
        assignee_queue_id=ticket.assignee_queue_id,
        surrogate_id=ticket.surrogate_id,
        surrogate_link_status=ticket.surrogate_link_status.value
        if hasattr(ticket.surrogate_link_status, "value")
        else str(ticket.surrogate_link_status),
        first_message_at=ticket.first_message_at,
        last_message_at=ticket.last_message_at,
        last_activity_at=ticket.last_activity_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("/{ticket_id}/attachments/{attachment_id}/download")
def download_ticket_attachment(
    ticket_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, str]:
    """Return secure signed URL for ticket attachment download."""
    url = ticketing_service.get_ticket_attachment_download_url(
        db,
        org_id=session.org_id,
        actor_user_id=session.user_id,
        ticket_id=ticket_id,
        attachment_id=attachment_id,
    )
    return {"download_url": url}
