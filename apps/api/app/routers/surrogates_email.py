"""Surrogate email routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


class SendEmailResponse(BaseModel):
    """Response after sending email."""

    success: bool
    email_log_id: UUID | None = None
    message_id: str | None = None
    provider_used: str | None = None
    error: str | None = None


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
    import os

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if not surrogate.email:
        raise HTTPException(status_code=400, detail="Surrogate has no email address")

    template = email_service.get_template(db, data.template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")

    variables = email_service.build_surrogate_template_variables(db, surrogate)

    subject_template = data.subject if data.subject is not None else template.subject
    body_template = data.body if data.body is not None else template.body
    subject, body = email_service.render_template(subject_template, body_template, variables)

    if email_service.is_email_suppressed(db, session.org_id, surrogate.email):
        email_log, _job = email_service.send_email(
            db=db,
            org_id=session.org_id,
            template_id=data.template_id,
            recipient_email=surrogate.email,
            subject=subject,
            body=body,
            surrogate_id=surrogate_id,
        )
        return SendEmailResponse(
            success=False,
            email_log_id=email_log.id,
            error="Email suppressed",
        )

    provider = data.provider
    gmail_connected = oauth_service.get_user_integration(db, session.user_id, "gmail") is not None
    resend_configured = bool(os.getenv("RESEND_API_KEY"))

    use_gmail = False
    use_resend = False

    if provider == "gmail":
        if not gmail_connected:
            return SendEmailResponse(
                success=False,
                error="Gmail not connected. Connect Gmail in Settings > Integrations.",
            )
        use_gmail = True
    elif provider == "resend":
        if not resend_configured:
            return SendEmailResponse(
                success=False, error="Resend not configured. Contact administrator."
            )
        use_resend = True
    else:
        if gmail_connected:
            use_gmail = True
        elif resend_configured:
            use_resend = True
        else:
            return SendEmailResponse(
                success=False,
                error="No email provider available. Connect Gmail in Settings.",
            )

    if use_gmail:
        result = await gmail_service.send_email_logged(
            db=db,
            org_id=session.org_id,
            user_id=str(session.user_id),
            to=surrogate.email,
            subject=subject,
            body=body,
            html=True,
            template_id=data.template_id,
            surrogate_id=surrogate_id,
            idempotency_key=data.idempotency_key,
        )

        if result.get("success"):
            activity_service.log_email_sent(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                actor_user_id=session.user_id,
                email_log_id=result.get("email_log_id"),
                subject=subject,
                provider="gmail",
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

    if use_resend:
        try:
            result = email_service.send_email(
                db=db,
                org_id=session.org_id,
                template_id=data.template_id,
                recipient_email=surrogate.email,
                subject=subject,
                body=body,
                surrogate_id=surrogate_id,
            )

            if result:
                log, _job = result

                activity_service.log_email_sent(
                    db=db,
                    surrogate_id=surrogate_id,
                    organization_id=session.org_id,
                    actor_user_id=session.user_id,
                    email_log_id=log.id,
                    subject=subject,
                    provider="resend",
                )

                return SendEmailResponse(
                    success=True,
                    email_log_id=log.id,
                    provider_used="resend",
                )
            return SendEmailResponse(success=False, error="Failed to queue email")
        except Exception as e:
            return SendEmailResponse(success=False, error=str(e))

    return SendEmailResponse(success=False, error="No provider selected")
