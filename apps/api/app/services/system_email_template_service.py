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

_LEGACY_ORG_INVITE_SUBJECT = "Invitation to join {{org_name}} as {{role_title}}"
_LEGACY_ORG_INVITE_BODY = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f4f4f5; margin: 0; padding: 20px;">
  <div style="max-width: 560px; margin: 0 auto; background: white;
              border-radius: 12px; padding: 40px;">
    <h1 style="font-size: 24px; font-weight: 600; color: #18181b; margin: 0 0 24px 0;">
      You're invited to join {{org_name}}
    </h1>
    <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 16px 0;">
      You've been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a
      <strong>{{role_title}}</strong>.
    </p>
    <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 32px 0;">
      Click the button below to accept the invitation and set up your account.
    </p>
    <a href="{{invite_url}}" target="_blank"
       style="display: inline-block; background-color: #18181b; color: white;
              text-decoration: none; font-weight: 500; font-size: 15px;
              padding: 12px 24px; border-radius: 8px;">
      Accept Invitation
    </a>
    <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e4e4e7;
                color: #666; font-size: 13px;">
      {{expires_block}}
      <p style="color: #a1a1aa; font-size: 13px; margin: 8px 0 0 0;">
        If you didn't expect this invitation, you can safely ignore this email.
      </p>
    </div>
  </div>
</div>
""".strip()

_ORG_INVITE_BODY = """
<div style="background-color: #f5f5f7; padding: 24px; margin: 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f7;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="width: 100%; max-width: 600px; background-color: #ffffff;
                      border: 1px solid #e5e7eb; border-radius: 16px;">
          <tr>
            <td style="padding: 32px 32px 8px 32px;">
              <div style="font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 12px 32px;">
              <h1 style="margin: 0; font-size: 24px; line-height: 1.3; color: #111827;">
                You’re invited to join {{org_name}}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 18px 32px;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You’ve been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a
                <strong>{{role_title}}</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 24px 32px;">
              <a href="{{invite_url}}" target="_blank"
                 style="display: inline-block; background-color: #111827; color: #ffffff;
                        text-decoration: none; font-weight: 600; font-size: 15px;
                        padding: 12px 22px; border-radius: 10px;">
                Accept Invitation
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 32px 8px 32px;">
              <p style="margin: 0 0 10px 0; font-size: 14px; color: #6b7280;">
                What happens next
              </p>
              <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                <li>Set up your account in minutes</li>
                <li>Review your workspace access</li>
                <li>Start collaborating with your team</li>
              </ul>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 32px 0 32px;">
              <p style="margin: 0; font-size: 13px; color: #6b7280;">
                If the button doesn’t work, paste this link into your browser:
              </p>
              <p style="margin: 6px 0 0 0; font-size: 13px;">
                <a href="{{invite_url}}" target="_blank" style="color: #2563eb; text-decoration: none;">
                  {{invite_url}}
                </a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 32px 28px 32px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                {{expires_block}}
                <p style="margin: 8px 0 0 0; color: #9ca3af;">
                  If you didn’t expect this invitation, you can safely ignore this email.
                </p>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
""".strip()

DEFAULT_SYSTEM_TEMPLATES: dict[str, dict[str, str]] = {
    ORG_INVITE_SYSTEM_KEY: {
        "category": "system",
        "name": "Organization Invite",
        "subject": "Invitation to join {{org_name}} as {{role_title}}",
        # NOTE: This HTML must remain compatible with email_service.sanitize_template_html.
        "body": _ORG_INVITE_BODY,
    }
}


def get_system_template_defaults(system_key: str) -> dict[str, str]:
    defaults = DEFAULT_SYSTEM_TEMPLATES.get(system_key)
    if not defaults:
        raise ValueError("Unknown system template key")

    return {
        **defaults,
        "body": email_service.sanitize_template_html(defaults["body"]),
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
        if system_key == ORG_INVITE_SYSTEM_KEY:
            legacy_body = email_service.sanitize_template_html(_LEGACY_ORG_INVITE_BODY)
            legacy_subject = _LEGACY_ORG_INVITE_SUBJECT
            defaults = get_system_template_defaults(system_key)
            if existing.subject == legacy_subject and existing.body == legacy_body:
                existing.subject = defaults["subject"]
                existing.body = defaults["body"]
        return existing

    defaults = get_system_template_defaults(system_key)

    template = EmailTemplate(
        organization_id=org_id,
        name=defaults["name"],
        subject=defaults["subject"],
        body=defaults["body"],
        is_active=True,
        is_system_template=True,
        system_key=system_key,
        category=defaults["category"],
    )
    db.add(template)
    db.flush()
    return template
