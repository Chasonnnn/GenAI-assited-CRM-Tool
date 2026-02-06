"""System email templates.

These templates are used for *system/platform* transactional emails (e.g. org invites).
They are stored as platform-level records and managed exclusively from the ops console.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import EmailTemplate, PlatformSystemEmailTemplate


ORG_INVITE_SYSTEM_KEY = "org_invite"

_LEGACY_ORG_INVITE_SUBJECT = "Invitation to join {{org_name}} as {{role_title}}"
_LEGACY_ORG_INVITE_BODY = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f4f4f5; margin: 0; padding: 20px;">
  <div style="max-width: 560px; margin: 0 auto; background: white;
              border-radius: 12px; padding: 40px;">
    <h1 style="font-size: 24px; font-weight: 600; color: #18181b; margin: 0 0 6px 0;">
      You're invited to join
    </h1>
    <div style="font-size: 20px; font-weight: 600; color: #18181b; margin: 0 0 24px 0;">
      {{org_name}}
    </div>
    <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 16px 0;">
      You've been invited to join
    </p>
    <p style="font-size: 16px; color: #3f3f46; line-height: 1.6; margin: 0 0 16px 0;">
      as a <strong>{{role_title}}</strong>.
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
                You're invited to join
              </h1>
              <div style="margin-top: 4px; font-size: 20px; line-height: 1.3; color: #111827; font-weight: 600;">
                {{org_name}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 20px 40px;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited to join
              </p>
              <p style="margin: 6px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                as a <strong>{{role_title}}</strong>.
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
              {{platform_logo_block}}
              <div style="margin-top: 12px; font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 40px 0 40px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; line-height: 1.35; color: #111827; font-weight: 600;">
                You're invited to join
              </h1>
              <div style="margin-top: 6px; font-size: 22px; line-height: 1.3; color: #111827; font-weight: 600;">
                {{org_name}}
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 48px 0 48px; text-align: center;">
              <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                You've been invited to join
              </p>
              <p style="margin: 6px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                as a <strong>{{role_title}}</strong>.
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
    },
    "platform_update": {
        "category": "system",
        "name": "Platform Update",
        "subject": "Update for {{org_name}} from Surrogacy Force",
        "body": """
<div style="background-color: #f5f5f7; padding: 40px 12px; margin: 0;">
  <span style="display:none; max-height:0; max-width:0; color:transparent; height:0; width:0;">
    Important update for {{org_name}}.
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
              {{platform_logo_block}}
              <div style="margin-top: 12px; font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase;
                          font-weight: 600; color: #6b7280;">
                Surrogacy Force
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 16px 40px 0 40px; text-align: center;">
              <h1 style="margin: 0; font-size: 26px; line-height: 1.35; color: #111827; font-weight: 600;">
                Platform update
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 14px 48px 0 48px;">
              <p style="margin: 0; font-size: 16px; line-height: 1.7; color: #374151;">
                Hi {{first_name}},
              </p>
              <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.7; color: #374151;">
                Here is the latest update for <strong>{{org_name}}</strong>. You can customize this content
                for announcements, policy changes, or product improvements.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 22px 40px 0 40px;">
              <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                  Suggested highlights
                </p>
                <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                  <li>Include the most important change first</li>
                  <li>Note any action items for your team</li>
                  <li>Share what to expect next</li>
                </ul>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 22px 40px 32px 40px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                <p style="margin: 0;">
                  Manage email preferences:
                  <a href="{{unsubscribe_url}}" target="_blank" style="color: #2563eb; text-decoration: none;">
                    Unsubscribe
                  </a>
                </p>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
""".strip(),
    },
}


class SystemTemplateAlreadyExistsError(ValueError):
    """Raised when attempting to create a system template that already exists."""


def list_platform_system_templates(db: Session) -> list[PlatformSystemEmailTemplate]:
    """List all platform system email templates (built-ins + custom).

    Ensures built-in templates exist before returning the full list.
    """

    for system_key in DEFAULT_SYSTEM_TEMPLATES.keys():
        ensure_system_template(db, system_key=system_key)
    db.commit()

    return (
        db.query(PlatformSystemEmailTemplate).order_by(PlatformSystemEmailTemplate.name.asc()).all()
    )


def create_platform_system_template(
    db: Session,
    *,
    system_key: str,
    name: str,
    subject: str,
    body: str,
    from_email: str | None,
    is_active: bool,
) -> PlatformSystemEmailTemplate:
    """Create a custom platform system email template."""

    existing = get_system_template(db, system_key=system_key)
    if existing:
        raise SystemTemplateAlreadyExistsError("System template already exists")

    from app.services import email_service

    template = PlatformSystemEmailTemplate(
        system_key=system_key,
        name=name,
        subject=subject,
        body=email_service.sanitize_template_html(body),
        from_email=(from_email.strip() or None) if from_email else None,
        is_active=is_active,
        current_version=1,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_system_template_defaults(system_key: str) -> dict[str, str]:
    defaults = DEFAULT_SYSTEM_TEMPLATES.get(system_key)
    if not defaults:
        raise ValueError("Unknown system template key")

    # Local import to avoid circular imports (email_service also needs access to the
    # platform system template registry for filtering).
    from app.services import email_service

    return {
        **defaults,
        "body": email_service.sanitize_template_html(defaults["body"]),
    }


def get_system_template(db: Session, *, system_key: str) -> PlatformSystemEmailTemplate | None:
    return (
        db.query(PlatformSystemEmailTemplate)
        .filter(PlatformSystemEmailTemplate.system_key == system_key)
        .first()
    )


def ensure_system_template(db: Session, *, system_key: str) -> PlatformSystemEmailTemplate:
    existing = get_system_template(db, system_key=system_key)
    if existing:
        return existing

    migrated_subject = None
    migrated_body = None
    migrated_from_email = None
    if system_key == ORG_INVITE_SYSTEM_KEY:
        legacy = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.is_system_template.is_(True),
                EmailTemplate.system_key == system_key,
            )
            .order_by(EmailTemplate.updated_at.desc().nullslast())
            .first()
        )
        if legacy:
            migrated_subject = legacy.subject
            migrated_body = legacy.body
            migrated_from_email = legacy.from_email

    defaults = get_system_template_defaults(system_key)

    template = PlatformSystemEmailTemplate(
        system_key=system_key,
        name=defaults["name"],
        subject=migrated_subject or defaults["subject"],
        body=migrated_body or defaults["body"],
        from_email=migrated_from_email,
        is_active=True,
        current_version=1,
    )
    db.add(template)
    db.flush()
    return template
