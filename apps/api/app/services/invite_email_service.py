"""Invite email service.

Preferred path: send via platform/system sender (Resend) if configured.
Fallback: send via the inviting user's Gmail integration when platform sender is not configured.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import OrgInvite, Organization, User
from app.services import (
    email_service,
    gmail_service,
    org_service,
    platform_email_service,
    system_email_template_service,
)

logger = logging.getLogger(__name__)


def _build_invite_url(invite_id: UUID, base_url: str) -> str:
    """Build the invite acceptance URL."""
    return f"{base_url.rstrip('/')}/invite/{invite_id}"


def _build_invite_html(
    org_name: str,
    inviter_name: str | None,
    role: str,
    invite_url: str,
    expires_at: str | None,
) -> str:
    """Build HTML email body for invite."""
    inviter_text = f" by {inviter_name}" if inviter_name else ""
    expiry_text = (
        f"<p style='color: #666; font-size: 13px;'>This invitation expires {expires_at}.</p>"
        if expires_at
        else ""
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
             background-color: #f4f4f5; margin: 0; padding: 20px;">
    <div style="max-width: 560px; margin: 0 auto; background: white; 
                border-radius: 12px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
        
        <h1 style="font-size: 24px; font-weight: 600; color: #18181b; margin: 0 0 24px 0;">
            You're invited to join {org_name}
        </h1>
        
        <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 16px 0;">
            You've been invited{inviter_text} to join <strong>{org_name}</strong> as a <strong>{role.title()}</strong>.
        </p>
        
        <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 32px 0;">
            Click the button below to accept the invitation and set up your account.
        </p>
        
        <a href="{invite_url}" 
           style="display: inline-block; background-color: #18181b; color: white; 
                  text-decoration: none; font-weight: 500; font-size: 15px; 
                  padding: 12px 24px; border-radius: 8px;">
            Accept Invitation
        </a>
        
        <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e4e4e7;">
            {expiry_text}
            <p style="color: #a1a1aa; font-size: 13px; margin: 8px 0 0 0;">
                If you didn't expect this invitation, you can safely ignore this email.
            </p>
        </div>
    </div>
</body>
</html>
"""


def _build_invite_text(
    org_name: str,
    inviter_name: str | None,
    role: str,
    invite_url: str,
    expires_at: str | None,
) -> str:
    """Build plain text email body for invite."""
    inviter_text = f" by {inviter_name}" if inviter_name else ""
    expiry_text = f"\nThis invitation expires {expires_at}.\n" if expires_at else ""

    return f"""You're invited to join {org_name}

You've been invited{inviter_text} to join {org_name} as a {role.title()}.

Accept your invitation here:
{invite_url}
{expiry_text}
If you didn't expect this invitation, you can safely ignore this email.
"""


async def send_invite_email(
    db: Session,
    invite: OrgInvite,
) -> dict:
    """
    Send invitation email to invitee.

    Uses the inviting user's Gmail account to send the email.

    Returns:
        {"success": True, "message_id": "..."} or {"success": False, "error": "..."}
    """
    # Get org name
    org = org_service.get_org_by_id(db, invite.organization_id)
    if not org:
        return {"success": False, "error": "Organization not found"}
    org_name = org_service.get_org_display_name(org)
    base_url = org_service.get_org_portal_base_url(org)

    # Get inviter name
    inviter_name = None
    if invite.invited_by_user_id:
        inviter = db.query(User).filter(User.id == invite.invited_by_user_id).first()
        inviter_name = inviter.display_name if inviter else None

    # Format expiry
    expires_at = None
    if invite.expires_at:
        from datetime import datetime, timezone

        days_remaining = (invite.expires_at - datetime.now(timezone.utc)).days
        if days_remaining > 0:
            expires_at = f"in {days_remaining} day{'s' if days_remaining != 1 else ''}"
        else:
            expires_at = "soon"

    # Build URLs and content
    invite_url = _build_invite_url(invite.id, base_url)
    text_body = _build_invite_text(org_name, inviter_name, invite.role, invite_url, expires_at)
    idempotency_key = f"invite:{invite.id}:v{invite.resend_count}"

    # Prefer the org-scoped system template (editable in ops). Fallback to built-in HTML.
    template = system_email_template_service.get_system_template(
        db,
        org_id=invite.organization_id,
        system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY,
    )

    # Always allow the system template to define the sender, even if the body is
    # disabled (in that case we fall back to the built-in HTML, but still need a
    # From address for platform/system sending).
    template_from_email = template.from_email if template else None

    if template and template.is_active:
        inviter_text = f" by {inviter_name}" if inviter_name else ""
        expires_block = f"<p>This invitation expires {expires_at}.</p>" if expires_at else ""
        variables = {
            "org_name": org_name,
            "inviter_text": inviter_text,
            "role_title": invite.role.title(),
            "invite_url": invite_url,
            "expires_block": expires_block,
        }
        subject, html_body = email_service.render_template(
            template.subject,
            template.body,
            variables,
        )
        template_id = template.id
    else:
        subject = f"You're invited to join {org_name}"
        html_body = _build_invite_html(org_name, inviter_name, invite.role, invite_url, expires_at)
        template_id = None
        # template_from_email already set from the system template (if any)

    # Send via platform/system sender when configured (preferred)
    if platform_email_service.platform_sender_configured():
        result = await platform_email_service.send_email_logged(
            db=db,
            org_id=invite.organization_id,
            to_email=invite.email,
            subject=subject,
            from_email=template_from_email,
            html=html_body,
            text=text_body,
            template_id=template_id,
            surrogate_id=None,
            idempotency_key=idempotency_key,
        )
        integration_key = "resend"
    else:
        # Fallback: send via inviter's Gmail integration
        sender_user_id = invite.invited_by_user_id
        if not sender_user_id:
            logger.warning("No inviter for invite %s, cannot send email", invite.id)
            return {"success": False, "error": "No inviter to send from"}

        result = await gmail_service.send_email_logged(
            db=db,
            org_id=invite.organization_id,
            user_id=str(sender_user_id),
            to=invite.email,
            subject=subject,
            body=html_body,
            html=True,
            template_id=template_id,
            surrogate_id=None,
            idempotency_key=idempotency_key,
        )
        integration_key = "gmail"

    if result.get("success"):
        from app.services import audit_service

        logger.info(
            "Sent invite email to %s for org %s",
            audit_service.hash_email(invite.email),
            org_name,
        )
    else:
        logger.error(f"Failed to send invite email: {result.get('error')}")
        # Create system alert for failed invite email
        try:
            from app.services import alert_service
            from app.db.enums import AlertType, AlertSeverity

            alert_service.create_or_update_alert(
                db=db,
                org_id=invite.organization_id,
                alert_type=AlertType.INVITE_SEND_FAILED,
                severity=AlertSeverity.ERROR,
                title="Invite email failed to send",
                message=result.get("error", "Unknown error")[:500],
                integration_key=integration_key,
                error_class="EmailSendError",
            )
        except Exception as alert_err:
            logger.warning(f"Failed to create alert for invite failure: {alert_err}")

    return result
