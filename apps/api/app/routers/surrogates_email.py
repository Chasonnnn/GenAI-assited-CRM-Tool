"""Surrogate email routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.services import surrogate_service

router = APIRouter()


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
    """Send email to surrogate contact using template."""
    from app.services import activity_service, email_service, gmail_service, oauth_service

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
    from app.services import email_composition_service

    body_template = email_composition_service.strip_legacy_unsubscribe_placeholders(body_template)
    subject, body = email_service.render_template(subject_template, body_template, variables)

    from app.services import org_service

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
        )
        return SendEmailResponse(
            success=False,
            email_log_id=email_log.id,
            error="Email suppressed",
        )

    provider = (data.provider or "auto").lower()
    if provider not in {"auto", "gmail", "resend"}:
        return SendEmailResponse(
            success=False,
            error="Invalid email provider. Supported options are auto or gmail.",
        )
    if provider == "resend":
        return SendEmailResponse(
            success=False,
            error="Surrogate emails must be sent from personal Gmail. Resend is not allowed.",
        )

    gmail_connected = oauth_service.get_user_integration(db, session.user_id, "gmail") is not None
    if not gmail_connected:
        return SendEmailResponse(
            success=False,
            error="Gmail not connected. Surrogate emails require personal Gmail in Settings > Integrations.",
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

    if result.get("success"):
        activity_service.log_email_sent(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=session.org_id,
            actor_user_id=session.user_id,
            email_log_id=result.get("email_log_id"),
            subject=subject,
            provider="gmail",
            attachments=selected_attachments,
        )

        return SendEmailResponse(
            success=True,
            email_log_id=result.get("email_log_id"),
            message_id=result.get("message_id"),
            provider_used="gmail",
        )
    return SendEmailResponse(
        success=False,
        email_log_id=result.get("email_log_id"),
        error=result.get("error"),
    )
