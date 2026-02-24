"""Invite email service.

Invites are always sent via the platform/system sender (Resend).
"""

import logging
import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import AlertSeverity, AlertType
from app.db.models import OrgInvite
from app.services import (
    email_service,
    org_service,
    platform_branding_service,
    platform_email_service,
    system_email_template_service,
)
from app.utils.presentation import humanize_identifier

logger = logging.getLogger(__name__)


def _strip_role_articles(html: str, *, role_title: str) -> str:
    """Normalize invite copy to 'as <role>' (no a/an), regardless of template."""
    role_title = (role_title or "").strip()
    if not role_title:
        return html

    # Keep this targeted to the role phrase only to avoid mutating unrelated copy.
    pattern = re.compile(
        rf"(\bas)\s+(?:a|an)\s+((?:<[^>]+>\s*)*){re.escape(role_title)}",
        flags=re.IGNORECASE,
    )

    return pattern.sub(lambda m: f"{m.group(1)} {m.group(2)}{role_title}", html)


def _build_invite_url(invite_id: UUID, base_url: str) -> str:
    """Build the invite acceptance URL."""
    return f"{base_url.rstrip('/')}/invite/{invite_id}"


def _build_invite_text(
    org_name: str,
    role: str,
    invite_url: str,
    expires_at: str | None,
    inviter_name: str | None,
) -> str:
    """Build plain text email body for invite."""
    role_title = humanize_identifier(role)
    expiry_text = f"\nThis invitation expires {expires_at}.\n" if expires_at else ""
    inviter_line = (
        f"You've been invited by {inviter_name} to join"
        if inviter_name
        else "You've been invited to join"
    )

    return f"""You're invited to join
{org_name}

{inviter_line}
as {role_title}.

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

    Uses the platform/system sender (Resend).

    Returns:
        {"success": True, "message_id": "..."} or {"success": False, "error": "..."}
    """
    # Get org name
    org = org_service.get_org_by_id(db, invite.organization_id)
    if not org:
        return {"success": False, "error": "Organization not found"}
    org_name = org_service.get_org_display_name(org)
    base_url = org_service.get_org_portal_base_url(org)

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
    inviter_name = None
    if invite.invited_by_user_id:
        from app.db.models import User

        inviter = db.query(User).filter(User.id == invite.invited_by_user_id).first()
        if inviter and inviter.display_name:
            inviter_name = inviter.display_name

    text_body = _build_invite_text(org_name, invite.role, invite_url, expires_at, inviter_name)
    idempotency_key = f"invite:{invite.id}:v{invite.resend_count}"

    if not platform_email_service.platform_sender_configured():
        return {"success": False, "error": "Platform email sender is not configured"}

    # Prefer the platform-level system template (global).
    template = system_email_template_service.ensure_system_template(
        db, system_key=system_email_template_service.ORG_INVITE_SYSTEM_KEY
    )

    # Always allow the system template to define the sender, even if the body is
    # disabled (in that case we fall back to the built-in HTML, but still need a
    # From address for platform/system sending).
    template_from_email = template.from_email if template else None

    inviter_text = f" by {inviter_name}" if inviter_name else ""
    expires_block = f"<p>This invitation expires {expires_at}.</p>" if expires_at else ""
    branding = platform_branding_service.get_branding(db)
    platform_logo_url = (branding.logo_url or "").strip()
    platform_logo_block = (
        f'<img src="{platform_logo_url}" alt="Platform logo" style="max-width: 180px; height: auto; display: block; margin: 0 auto 6px auto;" />'
        if platform_logo_url
        else ""
    )

    variables = {
        "org_name": org_name,
        "org_slug": org.slug,
        "inviter_text": inviter_text,
        "role_title": humanize_identifier(invite.role),
        "invite_url": invite_url,
        "expires_block": expires_block,
        "platform_logo_url": platform_logo_url,
        "platform_logo_block": platform_logo_block,
    }

    if template and template.is_active:
        subject_template = template.subject
        body_template = template.body
    else:
        defaults = system_email_template_service.get_system_template_defaults(
            system_email_template_service.ORG_INVITE_SYSTEM_KEY
        )
        subject_template = defaults["subject"]
        body_template = defaults["body"]

    subject, html_body = email_service.render_template(
        subject_template,
        body_template,
        variables,
        safe_html_vars={"expires_block", "platform_logo_block"},
    )

    html_body = _strip_role_articles(html_body, role_title=variables["role_title"])

    if inviter_name:
        if "You've been invited to join" in html_body:
            html_body = html_body.replace(
                "You've been invited to join",
                f"You've been invited by {inviter_name} to join",
                1,
            )
        elif "You&#x27;ve been invited to join" in html_body:
            html_body = html_body.replace(
                "You&#x27;ve been invited to join",
                f"You&#x27;ve been invited by {inviter_name} to join",
                1,
            )

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=invite.organization_id,
        to_email=invite.email,
        subject=subject,
        from_email=template_from_email,
        html=html_body,
        text=text_body,
        template_id=None,
        surrogate_id=None,
        idempotency_key=idempotency_key,
    )
    integration_key = "resend_platform"

    if result.get("success"):
        from app.services import audit_service

        logger.info(
            "Sent invite email to %s for org %s",
            audit_service.hash_email(invite.email),
            org_name,
        )
    else:
        logger.error(f"Failed to send invite email: {result.get('error')}")
        from app.services import alert_service

        alert_service.record_alert_isolated(
            org_id=invite.organization_id,
            alert_type=AlertType.INVITE_SEND_FAILED,
            severity=AlertSeverity.ERROR,
            title="Invite email failed to send",
            message=result.get("error", "Unknown error")[:500],
            integration_key=integration_key,
            error_class="EmailSendError",
        )

    return result
