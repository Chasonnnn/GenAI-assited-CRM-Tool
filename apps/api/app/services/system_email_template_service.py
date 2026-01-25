"""System email templates.

These templates are used for *system/platform* transactional emails (e.g. org invites).

We intentionally store them in the existing EmailTemplate table as `is_system_template=True`
with a stable `system_key`, so they can be managed from the ops console and audited.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import EmailTemplate
from app.services import email_service


ORG_INVITE_SYSTEM_KEY = "org_invite"


DEFAULT_SYSTEM_TEMPLATES: dict[str, dict[str, str]] = {
    ORG_INVITE_SYSTEM_KEY: {
        "category": "system",
        "name": "Organization Invite",
        "subject": "Invitation to join {{org_name}} as {{role_title}}",
        # NOTE: This HTML must remain compatible with email_service.sanitize_template_html.
        "body": """
<h1>You're invited to join {{org_name}}</h1>

<p>You've been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a <strong>{{role_title}}</strong>.</p>

<p>Use the link below to accept your invitation:</p>

<p><a href="{{invite_url}}" target="_blank"><strong>Accept invitation</strong></a></p>

{{expires_block}}

<h2>What happens next</h2>
<ul>
  <li>Set up your account</li>
  <li>Review your workspace access</li>
  <li>Start collaborating with your team</li>
</ul>

<p>If the button doesn't work, paste this link into your browser:</p>
<p><a href="{{invite_url}}" target="_blank">{{invite_url}}</a></p>

<p>If you didn't expect this invitation, you can safely ignore this email.</p>
<p>Need help? Reply to this email and our team will assist.</p>
""".strip(),
    }
}


def get_system_template(db: Session, *, org_id: UUID, system_key: str) -> EmailTemplate | None:
    return (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == org_id,
            EmailTemplate.is_system_template.is_(True),
            EmailTemplate.system_key == system_key,
        )
        .first()
    )


def ensure_system_template(db: Session, *, org_id: UUID, system_key: str) -> EmailTemplate:
    existing = get_system_template(db, org_id=org_id, system_key=system_key)
    if existing:
        return existing

    defaults = DEFAULT_SYSTEM_TEMPLATES.get(system_key)
    if not defaults:
        raise ValueError("Unknown system template key")

    template = EmailTemplate(
        organization_id=org_id,
        name=defaults["name"],
        subject=defaults["subject"],
        body=email_service.sanitize_template_html(defaults["body"]),
        is_active=True,
        is_system_template=True,
        system_key=system_key,
        category=defaults["category"],
    )
    db.add(template)
    db.flush()
    return template
