"""Surrogate email routes."""

from __future__ import annotations

import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.ticketing import (
    SurrogateEmailContactCreateRequest,
    SurrogateEmailContactListResponse,
    SurrogateEmailContactPatchRequest,
    SurrogateEmailContactRead,
    SurrogateTicketEmailItem,
    SurrogateTicketEmailListResponse,
)
from app.services import surrogate_service, ticketing_service

router = APIRouter()
logger = logging.getLogger(__name__)


class SendEmailRequest(BaseModel):
    """Request to send email to surrogate contact."""

    template_id: UUID
    subject: str | None = None
    body: str | None = None
    provider: str = "auto"
    idempotency_key: str | None = None
    attachment_ids: list[UUID] = Field(default_factory=list)


class SendEmailResponse(BaseModel):
    """Response after sending email."""

    success: bool
    email_log_id: UUID | None = None
    message_id: str | None = None
    provider_used: str | None = None
    ticket_id: UUID | None = None
    error: str | None = None


@router.get(
    "/{surrogate_id:uuid}/template-variables",
    response_model=dict[str, str],
)
async def get_surrogate_template_variables(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get resolved email template variables for surrogate preview."""
    from app.services import email_service

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    return email_service.build_surrogate_template_variables(db, surrogate)


@router.post(
    "/{surrogate_id:uuid}/send-email",
    response_model=SendEmailResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def send_surrogate_email(
    surrogate_id: UUID,
    data: SendEmailRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Send email to surrogate contact using template.

    Keeps legacy provider behavior (auto/gmail/resend) and writes ticketing
    metadata on successful Gmail sends.
    """
    from app.services import (
        email_composition_service,
        email_service,
        gmail_service,
        oauth_service,
        org_service,
    )

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if not surrogate.email:
        raise HTTPException(status_code=400, detail="Surrogate has no email address")

    template = email_service.get_template(db, data.template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")

    selected_attachments = []
    if data.attachment_ids:
        try:
            selected_attachments = email_service.resolve_surrogate_email_attachments(
                db=db,
                org_id=session.org_id,
                surrogate_id=surrogate_id,
                attachment_ids=data.attachment_ids,
            )
        except email_service.EmailAttachmentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except email_service.EmailAttachmentValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    subject_template = data.subject if data.subject is not None else template.subject
    body_template = data.body if data.body is not None else template.body

    body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(body_template)
    subject, body = email_service.render_template(subject_template, body_template, variables)

    org = org_service.get_org_by_id(db, session.org_id)
    portal_base_url = org_service.get_org_portal_base_url(org)

    body = email_composition_service.compose_template_email_html(
        db=db,
        org_id=session.org_id,
        recipient_email=surrogate.email,
        rendered_body_html=body,
        scope="personal",
        sender_user_id=session.user_id,
        portal_base_url=portal_base_url,
    )

    if email_service.is_email_suppressed(db, session.org_id, surrogate.email):
        email_log, _job = email_service.send_email(
            db=db,
            org_id=session.org_id,
            template_id=data.template_id,
            recipient_email=surrogate.email,
            subject=subject,
            body=body,
            surrogate_id=surrogate_id,
            attachments=selected_attachments,
            sender_user_id=session.user_id,
        )
        return SendEmailResponse(
            success=False,
            email_log_id=email_log.id,
            error="Email suppressed",
        )

    provider = (data.provider or "auto").strip().lower()
    if provider not in {"auto", "gmail", "resend"}:
        return SendEmailResponse(
            success=False,
            error="Invalid email provider. Supported options are auto, gmail, or resend.",
        )

    gmail_connected = oauth_service.get_user_integration(db, session.user_id, "gmail") is not None
    resend_configured = bool(os.getenv("RESEND_API_KEY"))

    resolved_provider = provider
    if provider == "auto":
        if gmail_connected:
            resolved_provider = "gmail"
        elif resend_configured:
            resolved_provider = "resend"
        else:
            return SendEmailResponse(
                success=False,
                error=(
                    "No email provider is available. Connect Gmail or configure "
                    "Resend (RESEND_API_KEY)."
                ),
            )

    if resolved_provider == "gmail" and not gmail_connected:
        return SendEmailResponse(
            success=False,
            error="Gmail not connected. Connect Gmail in Settings > Integrations.",
        )
    if resolved_provider == "resend" and not resend_configured:
        return SendEmailResponse(
            success=False,
            error="Resend not configured. Set RESEND_API_KEY for non-Gmail sends.",
        )

    if resolved_provider == "resend":
        email_log, _job = email_service.send_email(
            db=db,
            org_id=session.org_id,
            template_id=data.template_id,
            recipient_email=surrogate.email,
            subject=subject,
            body=body,
            surrogate_id=surrogate_id,
            attachments=selected_attachments,
            sender_user_id=session.user_id,
        )
        return SendEmailResponse(
            success=True,
            email_log_id=email_log.id,
            provider_used="resend",
        )

    gmail_kwargs = {
        "db": db,
        "org_id": session.org_id,
        "user_id": str(session.user_id),
        "to": surrogate.email,
        "subject": subject,
        "body": body,
        "html": True,
        "template_id": data.template_id,
        "surrogate_id": surrogate_id,
        "idempotency_key": data.idempotency_key,
    }
    if selected_attachments:
        gmail_kwargs["attachment_ids"] = [attachment.id for attachment in selected_attachments]

    result = await gmail_service.send_email_logged(**gmail_kwargs)

    if not result.get("success"):
        return SendEmailResponse(
            success=False,
            email_log_id=result.get("email_log_id"),
            error=result.get("error"),
        )

    email_service.log_surrogate_email_send_success(
        db=db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        email_log_id=result.get("email_log_id"),
        subject=subject,
        provider="gmail",
        template_id=data.template_id,
        actor_user_id=session.user_id,
        attachments=selected_attachments,
    )

    ticket_id: UUID | None = None
    try:
        ticket_id = ticketing_service.record_surrogate_outbound_gmail_send(
            db=db,
            org_id=session.org_id,
            actor_user_id=session.user_id,
            surrogate_id=surrogate_id,
            to_email=surrogate.email,
            subject=subject,
            body_html=body,
            gmail_message_id=result.get("message_id"),
            gmail_thread_id=result.get("thread_id"),
        )
    except Exception:  # pragma: no cover - best-effort ticketing mirror
        db.rollback()
        logger.exception("Failed to mirror surrogate send-email into ticketing records")

    return SendEmailResponse(
        success=True,
        email_log_id=result.get("email_log_id"),
        message_id=result.get("message_id"),
        provider_used="gmail",
        ticket_id=ticket_id,
    )


@router.get(
    "/{surrogate_id:uuid}/emails",
    response_model=SurrogateTicketEmailListResponse,
    dependencies=[Depends(require_permission(POLICIES["tickets"].default))],
)
def list_surrogate_emails(
    surrogate_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> SurrogateTicketEmailListResponse:
    """List ticket/email history linked to a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    tickets = ticketing_service.list_surrogate_ticket_emails(
        db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
    )
    return SurrogateTicketEmailListResponse(
        items=[
            SurrogateTicketEmailItem(
                id=ticket.id,
                ticket_code=ticket.ticket_code,
                subject=ticket.subject,
                status=ticket.status.value
                if hasattr(ticket.status, "value")
                else str(ticket.status),
                priority=ticket.priority.value
                if hasattr(ticket.priority, "value")
                else str(ticket.priority),
                requester_email=ticket.requester_email,
                last_activity_at=ticket.last_activity_at,
                created_at=ticket.created_at,
            )
            for ticket in tickets
        ]
    )


@router.get(
    "/{surrogate_id:uuid}/email-contacts",
    response_model=SurrogateEmailContactListResponse,
    dependencies=[Depends(require_permission(POLICIES["tickets"].default))],
)
def list_surrogate_email_contacts(
    surrogate_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> SurrogateEmailContactListResponse:
    """List surrogate contact emails (system + manual)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    contacts = ticketing_service.list_surrogate_email_contacts(
        db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
    )
    return SurrogateEmailContactListResponse(
        items=[
            SurrogateEmailContactRead(
                id=contact.id,
                surrogate_id=contact.surrogate_id,
                email=contact.email,
                email_domain=contact.email_domain,
                source=contact.source.value
                if hasattr(contact.source, "value")
                else str(contact.source),
                label=contact.label,
                contact_type=contact.contact_type,
                is_active=contact.is_active,
                created_by_user_id=contact.created_by_user_id,
                created_at=contact.created_at,
                updated_at=contact.updated_at,
            )
            for contact in contacts
        ]
    )


@router.post(
    "/{surrogate_id:uuid}/email-contacts",
    response_model=SurrogateEmailContactRead,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["tickets"].actions["link_surrogates"])),
    ],
)
def create_surrogate_email_contact(
    surrogate_id: UUID,
    data: SurrogateEmailContactCreateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> SurrogateEmailContactRead:
    """Add manual surrogate email contact."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    contact = ticketing_service.create_surrogate_email_contact(
        db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        actor_user_id=session.user_id,
        email=data.email,
        label=data.label,
        contact_type=data.contact_type,
    )
    return SurrogateEmailContactRead(
        id=contact.id,
        surrogate_id=contact.surrogate_id,
        email=contact.email,
        email_domain=contact.email_domain,
        source=contact.source.value if hasattr(contact.source, "value") else str(contact.source),
        label=contact.label,
        contact_type=contact.contact_type,
        is_active=contact.is_active,
        created_by_user_id=contact.created_by_user_id,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.patch(
    "/{surrogate_id:uuid}/email-contacts/{contact_id:uuid}",
    response_model=SurrogateEmailContactRead,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["tickets"].actions["link_surrogates"])),
    ],
)
def patch_surrogate_email_contact(
    surrogate_id: UUID,
    contact_id: UUID,
    data: SurrogateEmailContactPatchRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> SurrogateEmailContactRead:
    """Edit manual surrogate email contact."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    contact = ticketing_service.patch_surrogate_email_contact(
        db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        contact_id=contact_id,
        email=data.email,
        label=data.label,
        contact_type=data.contact_type,
        is_active=data.is_active,
    )
    return SurrogateEmailContactRead(
        id=contact.id,
        surrogate_id=contact.surrogate_id,
        email=contact.email,
        email_domain=contact.email_domain,
        source=contact.source.value if hasattr(contact.source, "value") else str(contact.source),
        label=contact.label,
        contact_type=contact.contact_type,
        is_active=contact.is_active,
        created_by_user_id=contact.created_by_user_id,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )


@router.delete(
    "/{surrogate_id:uuid}/email-contacts/{contact_id:uuid}",
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["tickets"].actions["link_surrogates"])),
    ],
)
def delete_surrogate_email_contact(
    surrogate_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, bool]:
    """Deactivate manual surrogate email contact."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    ticketing_service.deactivate_surrogate_email_contact(
        db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        contact_id=contact_id,
    )
    return {"success": True}
