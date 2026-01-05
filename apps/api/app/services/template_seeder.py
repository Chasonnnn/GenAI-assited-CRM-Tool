"""
System email template and workflow seeder.

Provides idempotent seeding of default system templates and workflows
that are pre-configured for common surrogacy agency use cases.
"""

from uuid import UUID
from sqlalchemy.orm import Session

from app.db.models import EmailTemplate, AutomationWorkflow


# =============================================================================
# System Email Templates
# =============================================================================

SYSTEM_TEMPLATES = [
    {
        "system_key": "welcome_new_lead",
        "category": "welcome",
        "name": "Welcome New Lead",
        "subject": "Welcome to {{org_name}}!",
        "body": """Hi {{full_name}},

Thank you for reaching out to {{org_name}}! We're excited to connect with you and learn more about your surrogacy journey.

A member of our team will be in touch within the next 24-48 hours to discuss the next steps.

In the meantime, feel free to reply to this email if you have any questions.

Warm regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "application_next_steps",
        "category": "status",
        "name": "Application Next Steps",
        "subject": "Next Steps for Your Application",
        "body": """Hi {{full_name}},

Thank you for submitting your application! We're reviewing your information and will be in touch soon.

Here's what to expect:
1. Our team will review your application within 3-5 business days
2. We may reach out with additional questions
3. Once approved, we'll schedule an introductory call

If you have any questions, please don't hesitate to reach out.

Best regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "document_request",
        "category": "request",
        "name": "Document Request",
        "subject": "Documents Needed - {{case_number}}",
        "body": """Hi {{full_name}},

We're making progress on your case ({{case_number}}) and need a few additional documents to move forward.

Please submit the following at your earliest convenience:
- [Document 1]
- [Document 2]

You can reply to this email with the requested documents or upload them directly through your portal.

Thank you for your prompt attention to this matter.

Best,
The {{org_name}} Team""",
    },
    {
        "system_key": "appointment_reminder_24h",
        "category": "appointment",
        "name": "Appointment Reminder (24h)",
        "subject": "Reminder: Your Appointment Tomorrow",
        "body": """Hi {{full_name}},

This is a friendly reminder that you have an appointment scheduled for tomorrow:

📅 Date: {{appointment_date}}
🕐 Time: {{appointment_time}}
📍 Location: {{appointment_location}}

If you need to reschedule, please let us know as soon as possible.

See you soon!
The {{org_name}} Team""",
    },
    {
        "system_key": "appointment_confirmed",
        "category": "appointment",
        "name": "Appointment Confirmed",
        "subject": "Appointment Confirmed - {{appointment_date}}",
        "body": """Hi {{full_name}},

Your appointment has been confirmed!

📅 Date: {{appointment_date}}
🕐 Time: {{appointment_time}}
📍 Location: {{appointment_location}}

We've added this to your calendar. If you need to make any changes, please contact us.

Looking forward to meeting with you!
The {{org_name}} Team""",
    },
    {
        "system_key": "status_update",
        "category": "status",
        "name": "Status Update",
        "subject": "Update on Your Application - {{case_number}}",
        "body": """Hi {{full_name}},

We wanted to give you a quick update on your case ({{case_number}}).

Your status has been updated to: {{new_status}}

Our team is continuing to work on your file and will be in touch if we need anything from you.

Best regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "match_proposal_intro",
        "category": "match",
        "name": "Match Proposal Introduction",
        "subject": "Exciting News About Your Potential Match!",
        "body": """Hi {{full_name}},

We have some exciting news! We believe we've found a potential match for you.

Our team will be reaching out shortly to discuss this opportunity in detail and provide you with more information.

We're thrilled to be at this stage of your journey!

Warm regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "match_accepted",
        "category": "match",
        "name": "Match Accepted Congratulations",
        "subject": "Congratulations on Your Match!",
        "body": """Hi {{full_name}},

Congratulations! We're thrilled to confirm that your match has been accepted!

This is a wonderful milestone in your surrogacy journey. Our team will be in touch soon to discuss the next steps.

Thank you for entrusting us with this important chapter of your life.

With warmest congratulations,
The {{org_name}} Team""",
    },
    {
        "system_key": "inactivity_followup",
        "category": "followup",
        "name": "Inactivity Follow-up",
        "subject": "We're Here to Help - Checking In",
        "body": """Hi {{full_name}},

We noticed it's been a while since we last connected, and we wanted to check in.

Is there anything we can help you with? Whether you have questions or just need more time, we're here for you.

Feel free to reply to this email or give us a call whenever you're ready.

Best regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "contract_ready",
        "category": "legal",
        "name": "Contract Ready for Review",
        "subject": "Your Contract is Ready for Review",
        "body": """Hi {{full_name}},

Great news! Your contract is ready for review.

Please review the attached documents at your earliest convenience. If you have any questions or concerns, our team is here to help.

Once you've reviewed everything, please let us know so we can proceed with the next steps.

Best regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "initial_outreach",
        "category": "outreach",
        "name": "Initial Outreach",
        "subject": "Thanks for reaching out to {{org_name}}",
        "body": """Hi {{full_name}},

Thank you for your interest in {{org_name}}. We're excited to learn more about your goals and answer any questions you may have.

Our team will reach out shortly to schedule a brief call. If you prefer, reply with a few times that work for you and we'll do our best to accommodate.

Warm regards,
The {{org_name}} Team""",
    },
    {
        "system_key": "followup_checkin",
        "category": "followup",
        "name": "Follow-up Check-In",
        "subject": "Checking in from {{org_name}}",
        "body": """Hi {{full_name}},

Just checking in to see if you have any questions about the surrogacy process or your next steps.

If you're still interested, we'd love to schedule a quick call to learn more about your goals.

Best,
The {{org_name}} Team""",
    },
    {
        "system_key": "consult_booking_invite",
        "category": "appointment",
        "name": "Consultation Booking Invite",
        "subject": "Schedule Your Consultation",
        "body": """Hi {{full_name}},

You're ready for the next step! Please schedule a consultation with our team so we can walk through the program details and answer your questions.

If you need a new booking link, just reply and we will send it right away.

Looking forward to speaking with you,
The {{org_name}} Team""",
    },
    {
        "system_key": "application_reminder",
        "category": "application",
        "name": "Application Reminder",
        "subject": "Reminder: Your application is waiting",
        "body": """Hi {{full_name}},

This is a friendly reminder that your application is still pending. If you need help completing it, we're here to support you.

Reply to this email and we'll send a fresh link or answer any questions.

Thank you,
The {{org_name}} Team""",
    },
    {
        "system_key": "post_consult_summary",
        "category": "appointment",
        "name": "Post-Consult Summary",
        "subject": "Thank you for meeting with {{org_name}}",
        "body": """Hi {{full_name}},

Thank you for meeting with us today. It was great to learn more about your goals.

We'll send a follow-up with next steps shortly. In the meantime, reply to this email if any new questions come up.

Best,
The {{org_name}} Team""",
    },
    {
        "system_key": "not_eligible_update",
        "category": "status",
        "name": "Not Eligible Update",
        "subject": "Update on Your Application",
        "body": """Hi {{full_name}},

Thank you for taking the time to connect with {{org_name}}. After reviewing your information, we are unable to move forward at this time.

We truly appreciate your interest and wish you the very best.

Sincerely,
The {{org_name}} Team""",
    },
    {
        "system_key": "missing_information_request",
        "category": "request",
        "name": "Missing Information Request",
        "subject": "Additional Information Needed - {{case_number}}",
        "body": """Hi {{full_name}},

We're reviewing your case ({{case_number}}) and need a few additional details to proceed:

- [Item 1]
- [Item 2]

Reply to this email with the information above, and we'll keep things moving.

Thank you,
The {{org_name}} Team""",
    },
]


# =============================================================================
# System Workflows
# =============================================================================

SYSTEM_WORKFLOWS = [
    {
        "system_key": "new_lead_welcome",
        "name": "New Lead Welcome",
        "description": "Sends a welcome email when a new case is created",
        "icon": "mail",
        "trigger_type": "case_created",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [{"action_type": "send_email", "template_key": "welcome_new_lead"}],
        "is_enabled": False,  # Disabled by default
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "application_followup",
        "name": "Application Follow-up",
        "description": "Sends next steps email when status changes to Applied",
        "icon": "file-text",
        "trigger_type": "status_changed",
        "trigger_config": {"to_stage_slug": "applied"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_email", "template_key": "application_next_steps"}
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "appointment_reminder",
        "name": "Appointment Reminder",
        "description": "Sends a reminder email 24 hours before an appointment",
        "icon": "calendar",
        "trigger_type": "scheduled",
        "trigger_config": {"hours_before": 24, "entity_type": "appointment"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_email", "template_key": "appointment_reminder_24h"},
            {"action_type": "send_notification", "title": "Appointment Reminder Sent"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "match_notification",
        "name": "Match Notification",
        "description": "Notifies case manager and sends intro email when a match is proposed",
        "icon": "heart",
        "trigger_type": "match_proposed",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_notification", "title": "New Match Proposed"},
            {"action_type": "send_email", "template_key": "match_proposal_intro"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "inactivity_nudge",
        "name": "Inactivity Nudge",
        "description": "Sends a follow-up email after 7 days of inactivity",
        "icon": "clock",
        "trigger_type": "inactivity",
        "trigger_config": {"days": 7},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_email", "template_key": "inactivity_followup"},
            {"action_type": "create_task", "title": "Follow up on inactive case"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "weekly_nurture",
        "name": "Weekly Nurture Campaign",
        "description": "Sends weekly promotional content to inactive leads",
        "icon": "repeat",
        "trigger_type": "scheduled",
        "trigger_config": {"interval": "weekly", "day_of_week": 1},  # Monday
        "conditions": [
            {"field": "status", "operator": "not_in", "value": ["matched", "closed"]}
        ],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_notification", "title": "Weekly nurture email sent"}
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "recurring",
        "recurrence_interval_hours": 168,  # Weekly
    },
    {
        "system_key": "new_lead_outreach_task",
        "name": "New Lead Outreach Task",
        "description": "Creates an outreach task and notifies the owner when a new case is created",
        "icon": "task",
        "trigger_type": "case_created",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "create_task",
                "title": "Initial outreach",
                "description": "Contact the lead and log the outcome.",
                "due_days": 1,
                "assignee": "owner",
            },
            {
                "action_type": "send_notification",
                "title": "New lead assigned",
                "body": "A new case was created and assigned to you.",
                "recipients": "owner",
            },
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "application_submitted_review",
        "name": "Application Submitted Review",
        "description": "Notifies the owner and creates a review task when an application is submitted",
        "icon": "file-text",
        "trigger_type": "status_changed",
        "trigger_config": {"to_stage_slug": "application_submitted"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "create_task",
                "title": "Review application",
                "description": "Review the submitted application and update case status.",
                "due_days": 1,
                "assignee": "owner",
            },
            {
                "action_type": "send_notification",
                "title": "Application submitted",
                "body": "A new application was submitted and needs review.",
                "recipients": "owner",
            },
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "approved_booking_invite",
        "name": "Approved Booking Invite",
        "description": "Sends a booking invite when a case is approved",
        "icon": "calendar",
        "trigger_type": "status_changed",
        "trigger_config": {"to_stage_slug": "approved"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {"action_type": "send_email", "template_key": "consult_booking_invite"},
            {
                "action_type": "send_notification",
                "title": "Booking invite sent",
                "body": "An approved case received the consultation invite.",
                "recipients": "owner",
            },
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "appointment_scheduled_notice",
        "name": "Appointment Scheduled Notice",
        "description": "Notifies the owner when an appointment is scheduled",
        "icon": "calendar",
        "trigger_type": "appointment_scheduled",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "send_notification",
                "title": "Appointment booked",
                "body": "A new appointment was scheduled.",
                "recipients": "owner",
            },
            {"action_type": "send_email", "template_key": "appointment_confirmed"},
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "task_overdue_escalation",
        "name": "Task Overdue Escalation",
        "description": "Notifies admins when tasks become overdue",
        "icon": "alert",
        "trigger_type": "task_overdue",
        "trigger_config": {},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "send_notification",
                "title": "Task overdue",
                "body": "A task is overdue and needs attention.",
                "recipients": "all_admins",
            }
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
    {
        "system_key": "lead_marked_lost",
        "name": "Lead Marked Lost",
        "description": "Notifies the owner when a case is marked lost",
        "icon": "x-circle",
        "trigger_type": "status_changed",
        "trigger_config": {"to_stage_slug": "lost"},
        "conditions": [],
        "condition_logic": "AND",
        "actions": [
            {
                "action_type": "send_notification",
                "title": "Lead marked lost",
                "body": "The case has been marked as lost.",
                "recipients": "owner",
            },
            {
                "action_type": "add_note",
                "content": "Lead marked lost after multiple outreach attempts.",
            },
        ],
        "is_enabled": False,
        "requires_review": True,
        "recurrence_mode": "one_time",
    },
]


def seed_system_templates(db: Session, org_id: UUID) -> int:
    """
    Seed system email templates for an organization.

    Idempotent: skips templates where system_key already exists for this org.

    Returns:
        Number of templates created.
    """
    created_count = 0

    for template_data in SYSTEM_TEMPLATES:
        # Check if template already exists
        existing = (
            db.query(EmailTemplate)
            .filter(
                EmailTemplate.organization_id == org_id,
                EmailTemplate.system_key == template_data["system_key"],
            )
            .first()
        )

        if existing:
            continue

        # Create new template
        template = EmailTemplate(
            organization_id=org_id,
            name=template_data["name"],
            subject=template_data["subject"],
            body=template_data["body"],
            is_system_template=True,
            system_key=template_data["system_key"],
            category=template_data["category"],
            is_active=True,
        )
        db.add(template)
        created_count += 1

    if created_count > 0:
        db.flush()

    return created_count


def seed_system_workflows(
    db: Session, org_id: UUID, user_id: UUID | None = None
) -> int:
    """
    Seed system automation workflows for an organization.

    Idempotent: skips workflows where system_key already exists for this org.

    Note: Workflows are created disabled by default and require admin review.

    Returns:
        Number of workflows created.
    """
    created_count = 0

    from app.services import pipeline_service

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    pipeline_service.sync_missing_stages(db, pipeline, user_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    stage_map = {s.slug: str(s.id) for s in stages}

    # First, get the template IDs for this org
    template_keys = [t["system_key"] for t in SYSTEM_TEMPLATES]
    templates = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.organization_id == org_id,
            EmailTemplate.system_key.in_(template_keys),
        )
        .all()
    )
    template_map = {t.system_key: str(t.id) for t in templates}

    for workflow_data in SYSTEM_WORKFLOWS:
        # Check if workflow already exists
        existing = (
            db.query(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == org_id,
                AutomationWorkflow.system_key == workflow_data["system_key"],
            )
            .first()
        )

        if existing:
            continue

        trigger_config = workflow_data.get("trigger_config", {}).copy()
        if workflow_data.get("trigger_type") == "status_changed":
            to_slug = trigger_config.pop("to_stage_slug", None)
            from_slug = trigger_config.pop("from_stage_slug", None)
            if to_slug and to_slug in stage_map:
                trigger_config["to_stage_id"] = stage_map[to_slug]
            if from_slug and from_slug in stage_map:
                trigger_config["from_stage_id"] = stage_map[from_slug]

        # Resolve template_key to template_id in actions
        actions = []
        for action in workflow_data.get("actions", []):
            action_copy = action.copy()
            if "template_key" in action_copy:
                template_key = action_copy.pop("template_key")
                if template_key in template_map:
                    action_copy["template_id"] = template_map[template_key]
            actions.append(action_copy)

        # Create new workflow
        workflow = AutomationWorkflow(
            organization_id=org_id,
            name=workflow_data["name"],
            description=workflow_data.get("description"),
            icon=workflow_data.get("icon", "workflow"),
            trigger_type=workflow_data["trigger_type"],
            trigger_config=trigger_config,
            conditions=workflow_data.get("conditions", []),
            condition_logic=workflow_data.get("condition_logic", "AND"),
            actions=actions,
            is_enabled=workflow_data.get("is_enabled", False),
            is_system_workflow=True,
            system_key=workflow_data["system_key"],
            requires_review=workflow_data.get("requires_review", True),
            recurrence_mode=workflow_data.get("recurrence_mode", "one_time"),
            recurrence_interval_hours=workflow_data.get("recurrence_interval_hours"),
            recurrence_stop_on_status=workflow_data.get("recurrence_stop_on_status"),
            created_by_user_id=user_id,
        )
        db.add(workflow)
        created_count += 1

    if created_count > 0:
        db.flush()

    return created_count


def seed_all(db: Session, org_id: UUID, user_id: UUID | None = None) -> dict:
    """
    Seed all system templates and workflows for an organization.

    Returns:
        Dictionary with counts of created items.
    """
    templates_created = seed_system_templates(db, org_id)
    workflows_created = seed_system_workflows(db, org_id, user_id)

    return {
        "templates_created": templates_created,
        "workflows_created": workflows_created,
    }
