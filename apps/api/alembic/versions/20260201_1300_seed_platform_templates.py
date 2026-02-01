"""Seed platform email + workflow templates for ops console.

Revision ID: 20260201_1300
Revises: 20260201_1200
Create Date: 2026-02-01 13:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260201_1300"
down_revision: Union[str, Sequence[str], None] = "20260201_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BASE_EMAIL = """
<div style="background-color: #f5f5f7; padding: 40px 12px; margin: 0;">
  <span style="display:none; max-height:0; max-width:0; color:transparent; height:0; width:0;">
    [[PREHEADER]]
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
                [[TITLE]]
              </h1>
            </td>
          </tr>
          [[BODY]]
          <tr>
            <td style="padding: 24px 40px 32px 40px;">
              <div style="padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">
                <p style="margin: 0;">Need help? Reply to this email and we'll take care of it.</p>
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


def build_email(preheader: str, title: str, body: str) -> str:
    return (
        BASE_EMAIL.replace("[[PREHEADER]]", preheader)
        .replace("[[TITLE]]", title)
        .replace("[[BODY]]", body)
    )


def _insert_email_template(conn: sa.Connection, payload: dict) -> None:
    exists = conn.execute(
        sa.text("SELECT 1 FROM platform_email_templates WHERE name = :name LIMIT 1"),
        {"name": payload["name"]},
    ).first()
    if exists:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO platform_email_templates
            (name, subject, body, from_email, category, status, current_version, published_version, is_published_globally)
            VALUES
            (:name, :subject, :body, NULL, :category, 'draft', 1, 0, false)
            """
        ),
        payload,
    )


def _insert_workflow_template(conn: sa.Connection, payload: dict) -> None:
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM workflow_templates WHERE is_global IS TRUE AND name = :name LIMIT 1"
        ),
        {"name": payload["name"]},
    ).first()
    if exists:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_templates
            (name, description, icon, category, trigger_type, trigger_config, conditions, condition_logic, actions,
             draft_config, is_global, organization_id, status, published_version, is_published_globally, usage_count)
            VALUES
            (:name, :description, :icon, :category, :trigger_type, :trigger_config::jsonb, :conditions::jsonb,
             :condition_logic, :actions::jsonb, :draft_config::jsonb, true, NULL, 'draft', 0, false, 0)
            """
        ),
        payload,
    )


def upgrade() -> None:
    conn = op.get_bind()

    email_templates = [
        {
            "name": "New Surrogate Application Received",
            "subject": "Application received — {{org_name}}",
            "category": "surrogates",
            "body": build_email(
                "We received your application and will review it shortly.",
                "We've received your application",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Thanks for applying to become a surrogate with {{org_name}}. We've received your
                      application and it's now in review.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                        What happens next
                      </p>
                      <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                        <li>We'll review your application within 1-2 business days.</li>
                        <li>If you're a fit, we'll reach out to schedule a screening call.</li>
                      </ul>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 14px 48px 0 48px;">
                    <p style="margin: 0; font-size: 13px; color: #6b7280;">
                      Reference ID: {{surrogate_number}}
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Qualified - Next Steps",
            "subject": "You're qualified — next steps with {{org_name}}",
            "category": "surrogates",
            "body": build_email(
                "You're qualified to move forward.",
                "You're qualified — next steps",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Great news — you're qualified to move forward in the surrogacy process with {{org_name}}.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                        Next steps
                      </p>
                      <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                        <li>Schedule your screening call.</li>
                        <li>Gather any required documents and medical records.</li>
                      </ul>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 14px 48px 0 48px;">
                    <p style="margin: 0; font-size: 14px; color: #6b7280;">
                      Reply with a few times that work for you, and we'll take it from there.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Schedule Screening Call",
            "subject": "Let's schedule your screening call",
            "category": "surrogates",
            "body": build_email(
                "Choose a time for your screening call.",
                "Let's schedule your screening call",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      We'd love to schedule a brief screening call to learn more about you and answer questions.
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
                      The call usually takes 15-20 minutes. Reply with your availability and we'll confirm a time.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Documents Required",
            "subject": "Documents needed to move forward",
            "category": "surrogates",
            "body": build_email(
                "We need a few documents to keep moving.",
                "Documents needed to move forward",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      To keep your application moving, we need the following items:
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 14px; line-height: 1.6;">
                        <li>Government-issued ID</li>
                        <li>Medical records release form</li>
                        <li>Insurance information</li>
                      </ul>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 14px 48px 0 48px;">
                    <p style="margin: 0; font-size: 14px; color: #6b7280;">
                      Reply to this email with any questions or if you need help gathering documents.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Inactivity Check-in",
            "subject": "Checking in from {{org_name}}",
            "category": "surrogates",
            "body": build_email(
                "Checking in to see if you'd like to continue.",
                "Checking in on your application",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      We haven't heard back recently and wanted to check in. If you'd like to continue,
                      just reply here and we'll help with next steps.
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
                      If now isn't the right time, no worries — we'll pause your file until you're ready.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Appointment Scheduled",
            "subject": "Appointment scheduled for {{appointment_date}}",
            "category": "appointments",
            "body": build_email(
                "Your appointment is booked.",
                "Your appointment is scheduled",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Your appointment is confirmed. Here are the details:
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                        Appointment details
                      </p>
                      <p style="margin: 0; font-size: 14px; color: #374151;">Date: {{appointment_date}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Time: {{appointment_time}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Location: {{appointment_location}}</p>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 14px 48px 0 48px;">
                    <p style="margin: 0; font-size: 14px; color: #6b7280;">
                      Need to reschedule? Reply to this email and we'll help.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Appointment Reminder (24 Hours)",
            "subject": "Reminder: appointment on {{appointment_date}}",
            "category": "appointments",
            "body": build_email(
                "Reminder for your upcoming appointment.",
                "Appointment reminder",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      This is a friendly reminder about your appointment.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                        Appointment details
                      </p>
                      <p style="margin: 0; font-size: 14px; color: #374151;">Date: {{appointment_date}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Time: {{appointment_time}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Location: {{appointment_location}}</p>
                    </div>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Appointment Rescheduled",
            "subject": "Appointment rescheduled — {{appointment_date}}",
            "category": "appointments",
            "body": build_email(
                "Your appointment time has changed.",
                "Your appointment was rescheduled",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Your appointment has been updated. Please review the new details below.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 18px 48px 0 48px;">
                    <div style="border-radius: 16px; background-color: #f9fafb; padding: 16px 18px;">
                      <p style="margin: 0 0 10px 0; font-size: 13px; color: #6b7280; font-weight: 600;">
                        Updated appointment details
                      </p>
                      <p style="margin: 0; font-size: 14px; color: #374151;">Date: {{appointment_date}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Time: {{appointment_time}}</p>
                      <p style="margin: 6px 0 0 0; font-size: 14px; color: #374151;">Location: {{appointment_location}}</p>
                    </div>
                  </td>
                </tr>
                """.strip(),
            ),
        },
        {
            "name": "Missed Appointment Follow-up",
            "subject": "We missed you — let's reschedule",
            "category": "appointments",
            "body": build_email(
                "We missed you at your appointment.",
                "We missed you today",
                """
                <tr>
                  <td style="padding: 16px 48px 0 48px;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      Hi {{first_name}},
                    </p>
                    <p style="margin: 12px 0 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                      We missed you at your appointment. If you'd like to reschedule, just reply to this email
                      and we'll find a new time.
                    </p>
                  </td>
                </tr>
                """.strip(),
            ),
        },
    ]

    for template in email_templates:
        _insert_email_template(conn, template)

    workflow_templates = [
        {
            "name": "New Surrogate Intake Follow-up",
            "description": "Create a task and notify the owner when a new surrogate is created.",
            "icon": "mail",
            "category": "onboarding",
            "trigger_type": "surrogate_created",
            "trigger_config": json.dumps({}),
            "conditions": json.dumps([]),
            "condition_logic": "AND",
            "actions": json.dumps(
                [
                    {
                        "action_type": "create_task",
                        "title": "Reach out to new surrogate",
                        "description": "Introduce yourself and schedule a screening call.",
                        "due_days": 1,
                        "assignee": "owner",
                    },
                    {
                        "action_type": "send_notification",
                        "title": "New surrogate created",
                        "body": "A new surrogate case was created. Follow up within 1 business day.",
                        "recipients": "owner",
                    },
                ]
            ),
            "draft_config": json.dumps(
                {
                    "name": "New Surrogate Intake Follow-up",
                    "description": "Create a task and notify the owner when a new surrogate is created.",
                    "icon": "mail",
                    "category": "onboarding",
                    "trigger_type": "surrogate_created",
                    "trigger_config": {},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [
                        {
                            "action_type": "create_task",
                            "title": "Reach out to new surrogate",
                            "description": "Introduce yourself and schedule a screening call.",
                            "due_days": 1,
                            "assignee": "owner",
                        },
                        {
                            "action_type": "send_notification",
                            "title": "New surrogate created",
                            "body": "A new surrogate case was created. Follow up within 1 business day.",
                            "recipients": "owner",
                        },
                    ],
                }
            ),
        },
        {
            "name": "Inactivity 7-Day Check-in",
            "description": "Create a follow-up task when a surrogate has no activity for 7 days.",
            "icon": "clock",
            "category": "follow-up",
            "trigger_type": "inactivity",
            "trigger_config": json.dumps({"days": 7}),
            "conditions": json.dumps([]),
            "condition_logic": "AND",
            "actions": json.dumps(
                [
                    {
                        "action_type": "create_task",
                        "title": "Check in after inactivity",
                        "description": "Send a quick check-in email or call.",
                        "due_days": 1,
                        "assignee": "owner",
                    },
                    {
                        "action_type": "send_notification",
                        "title": "No activity for 7 days",
                        "body": "This case has had no activity for 7 days.",
                        "recipients": "owner",
                    },
                ]
            ),
            "draft_config": json.dumps(
                {
                    "name": "Inactivity 7-Day Check-in",
                    "description": "Create a follow-up task when a surrogate has no activity for 7 days.",
                    "icon": "clock",
                    "category": "follow-up",
                    "trigger_type": "inactivity",
                    "trigger_config": {"days": 7},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [
                        {
                            "action_type": "create_task",
                            "title": "Check in after inactivity",
                            "description": "Send a quick check-in email or call.",
                            "due_days": 1,
                            "assignee": "owner",
                        },
                        {
                            "action_type": "send_notification",
                            "title": "No activity for 7 days",
                            "body": "This case has had no activity for 7 days.",
                            "recipients": "owner",
                        },
                    ],
                }
            ),
        },
        {
            "name": "Status Change - Admin Alert",
            "description": "Notify admins when a surrogate status changes.",
            "icon": "activity",
            "category": "notifications",
            "trigger_type": "status_changed",
            "trigger_config": json.dumps({}),
            "conditions": json.dumps([]),
            "condition_logic": "AND",
            "actions": json.dumps(
                [
                    {
                        "action_type": "send_notification",
                        "title": "Surrogate status changed",
                        "body": "A surrogate status was updated. Review the case if needed.",
                        "recipients": "all_admins",
                    }
                ]
            ),
            "draft_config": json.dumps(
                {
                    "name": "Status Change - Admin Alert",
                    "description": "Notify admins when a surrogate status changes.",
                    "icon": "activity",
                    "category": "notifications",
                    "trigger_type": "status_changed",
                    "trigger_config": {},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [
                        {
                            "action_type": "send_notification",
                            "title": "Surrogate status changed",
                            "body": "A surrogate status was updated. Review the case if needed.",
                            "recipients": "all_admins",
                        }
                    ],
                }
            ),
        },
        {
            "name": "Appointment Scheduled - Owner Notification",
            "description": "Notify the owner when an appointment is scheduled.",
            "icon": "bell",
            "category": "appointments",
            "trigger_type": "appointment_scheduled",
            "trigger_config": json.dumps({}),
            "conditions": json.dumps([]),
            "condition_logic": "AND",
            "actions": json.dumps(
                [
                    {
                        "action_type": "send_notification",
                        "title": "Appointment scheduled",
                        "body": "A new appointment was scheduled. Review details and prep next steps.",
                        "recipients": "owner",
                    }
                ]
            ),
            "draft_config": json.dumps(
                {
                    "name": "Appointment Scheduled - Owner Notification",
                    "description": "Notify the owner when an appointment is scheduled.",
                    "icon": "bell",
                    "category": "appointments",
                    "trigger_type": "appointment_scheduled",
                    "trigger_config": {},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [
                        {
                            "action_type": "send_notification",
                            "title": "Appointment scheduled",
                            "body": "A new appointment was scheduled. Review details and prep next steps.",
                            "recipients": "owner",
                        }
                    ],
                }
            ),
        },
        {
            "name": "Appointment Completed - Owner Notification",
            "description": "Notify the owner when an appointment is completed.",
            "icon": "bell",
            "category": "appointments",
            "trigger_type": "appointment_completed",
            "trigger_config": json.dumps({}),
            "conditions": json.dumps([]),
            "condition_logic": "AND",
            "actions": json.dumps(
                [
                    {
                        "action_type": "send_notification",
                        "title": "Appointment completed",
                        "body": "An appointment was completed. Review notes and plan the next step.",
                        "recipients": "owner",
                    }
                ]
            ),
            "draft_config": json.dumps(
                {
                    "name": "Appointment Completed - Owner Notification",
                    "description": "Notify the owner when an appointment is completed.",
                    "icon": "bell",
                    "category": "appointments",
                    "trigger_type": "appointment_completed",
                    "trigger_config": {},
                    "conditions": [],
                    "condition_logic": "AND",
                    "actions": [
                        {
                            "action_type": "send_notification",
                            "title": "Appointment completed",
                            "body": "An appointment was completed. Review notes and plan the next step.",
                            "recipients": "owner",
                        }
                    ],
                }
            ),
        },
    ]

    for template in workflow_templates:
        _insert_workflow_template(conn, template)


def downgrade() -> None:
    conn = op.get_bind()
    email_names = [
        "New Surrogate Application Received",
        "Qualified - Next Steps",
        "Schedule Screening Call",
        "Documents Required",
        "Inactivity Check-in",
        "Appointment Scheduled",
        "Appointment Reminder (24 Hours)",
        "Appointment Rescheduled",
        "Missed Appointment Follow-up",
    ]
    conn.execute(
        sa.text("DELETE FROM platform_email_templates WHERE name IN :names").bindparams(
            sa.bindparam("names", expanding=True)
        ),
        {"names": email_names},
    )

    workflow_names = [
        "New Surrogate Intake Follow-up",
        "Inactivity 7-Day Check-in",
        "Status Change - Admin Alert",
        "Appointment Scheduled - Owner Notification",
        "Appointment Completed - Owner Notification",
    ]
    conn.execute(
        sa.text(
            "DELETE FROM workflow_templates WHERE is_global IS TRUE AND name IN :names"
        ).bindparams(sa.bindparam("names", expanding=True)),
        {"names": workflow_names},
    )
