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

_ORG_INVITE_BODY_V1 = """
<div style="background-color: #f5f5f7; padding: 32px 16px; margin: 0;">
  <span style="display:none; max-height:0; max-width:0; color:transparent; height:0; width:0;">
    You're invited to join {{org_name}}. This link may expire soon.
  </span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f7;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="width: 100%; max-width: 600px; background-color: #ffffff;
                      border: 1px solid #e5e7eb; border-radius: 20px;
                      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
          <tr>
            <td style="padding: 32px 40px 10px 40px;">
              <div style="font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 12px 40px;">
              <h1 style="margin: 0; font-size: 24px; line-height: 1.3; color: #111827;">
                You're invited to join {{org_name}}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 20px 40px;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a
                <strong>{{role_title}}</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 28px 40px;">
              <a href="{{invite_url}}" target="_blank"
                 style="display: inline-block; background-color: #111827; color: #ffffff;
                        text-decoration: none; font-weight: 600; font-size: 15px;
                        padding: 14px 26px; border-radius: 12px;">
                Accept Invitation
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 16px 40px;">
              <div style="border-radius: 14px; background-color: #f9fafb; padding: 16px;">
                <p style="margin: 0 0 10px 0; font-size: 14px; color: #6b7280;">
                  What happens next
                </p>
                <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                  <li>Set up your account in minutes</li>
                  <li>Review your workspace access</li>
                  <li>Start collaborating with your team</li>
                </ul>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 4px 40px 0 40px;">
              <p style="margin: 0; font-size: 13px; color: #6b7280;">
                If the button doesn't work, paste this link into your browser:
              </p>
              <p style="margin: 6px 0 0 0; font-size: 13px;">
                <a href="{{invite_url}}" target="_blank" style="color: #2563eb; text-decoration: none;">
                  {{invite_url}}
                </a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 22px 40px 30px 40px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                {{expires_block}}
                <p style="margin: 8px 0 0 0; color: #9ca3af;">
                  If you didn't expect this invitation, you can safely ignore this email.
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

_ORG_INVITE_BODY = """
<div style="background-color: #f5f5f7; padding: 40px 12px; margin: 0;">
  <span style="display:none; max-height:0; max-width:0; color:transparent; height:0; width:0;">
    You're invited to join {{org_name}}. This link may expire soon.
  </span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f7;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="width: 100%; max-width: 600px; background-color: #ffffff;
                      border: 1px solid #e5e7eb; border-radius: 20px;
                      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
          <tr>
            <td style="padding: 30px 40px 0 40px; text-align: center;">
              <div style="font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 40px 0 40px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; line-height: 1.35; color: #111827; font-weight: 600;">
                You're invited to join {{org_name}}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 48px 0 48px; text-align: center;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited{{inviter_text}} to join <strong>{{org_name}}</strong> as a
                <strong>{{role_title}}</strong>.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 26px 40px 0 40px; text-align: center;">
              <a href="{{invite_url}}" target="_blank"
                 style="display: inline-block; background-color: #111827; color: #ffffff;
                        text-decoration: none; font-weight: 600; font-size: 15px;
                        padding: 14px 28px; border-radius: 999px;">
                Accept Invitation
              </a>
            </td>
          </tr>
          <tr>
            <td style="padding: 28px 40px 0 40px;">
              <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                  What happens next
                </p>
                <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                  <li>Set up your account in minutes</li>
                  <li>Review your workspace access</li>
                  <li>Start collaborating with your team</li>
                </ul>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 18px 40px 0 40px;">
              <p style="margin: 0; font-size: 13px; color: #6b7280;">
                If the button doesn't work, paste this link into your browser:
              </p>
              <p style="margin: 8px 0 0 0; font-size: 13px;">
                <a href="{{invite_url}}" target="_blank" style="color: #2563eb; text-decoration: none;">
                  {{invite_url}}
                </a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 22px 40px 32px 40px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                {{expires_block}}
                <p style="margin: 8px 0 0 0; color: #9ca3af;">
                  If you didn't expect this invitation, you can safely ignore this email.
                </p>
              </div>
            </td>
          </tr>
        </table>
        <div style="margin-top: 14px; text-align: center; font-size: 11px; color: #9ca3af;">
          Copyright 2026 Surrogacy Force. All rights reserved.
        </div>
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
            v1_body = email_service.sanitize_template_html(_ORG_INVITE_BODY_V1)
            if existing.subject == legacy_subject and existing.body == legacy_body:
                existing.subject = defaults["subject"]
                existing.body = defaults["body"]
            elif existing.subject == defaults["subject"] and existing.body == v1_body:
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
