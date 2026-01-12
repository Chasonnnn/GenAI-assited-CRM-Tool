"""Appointment Email Service - Email notifications for appointment system.

Provides:
- HTML email templates for all appointment notification types
- Variable building for appointment context
- Functions to send appointment notifications via the email queue
"""

from datetime import datetime, timezone, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models import Appointment, AppointmentEmailLog, Organization, User
from app.db.enums import AppointmentEmailType
from app.services import email_service
from app.services.appointment_service import (
    log_appointment_email,
    mark_email_sent,
    mark_email_failed,
)


# =============================================================================
# Email Template Definitions
# =============================================================================

# Template names in the email_templates table
TEMPLATE_PREFIX = "appointment_"


def _get_template_name(email_type: AppointmentEmailType) -> str:
    """Get the template name for an email type."""
    return f"{TEMPLATE_PREFIX}{email_type.value}"


# Default templates (created on first use if not exists)
DEFAULT_TEMPLATES: dict[AppointmentEmailType, dict[str, str]] = {
    AppointmentEmailType.REQUEST_RECEIVED: {
        "name": "appointment_request_received",
        "subject": "Appointment Request Received - {{appointment_type}}",
        "body": """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Appointment Request Received</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
        <p>Hello {{client_name}},</p>
        <p>Thank you for requesting an appointment. Your request has been submitted and is pending approval.</p>
        
        <div style="background: white; border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid #e5e7eb;">
            <h3 style="margin-top: 0; color: #6366f1;">Appointment Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #6b7280;">Type:</td><td style="padding: 8px 0;"><strong>{{appointment_type}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Date:</td><td style="padding: 8px 0;"><strong>{{scheduled_date}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Time:</td><td style="padding: 8px 0;"><strong>{{scheduled_time}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Duration:</td><td style="padding: 8px 0;"><strong>{{duration}} minutes</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Meeting Mode:</td><td style="padding: 8px 0;"><strong>{{meeting_mode}}</strong></td></tr>
            </table>
        </div>
        
        <p style="color: #6b7280; font-size: 14px;">You will receive another email once your appointment is confirmed.</p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; margin: 0;">
            {{org_name}}<br>
            This is an automated message. Please do not reply directly to this email.
        </p>
    </div>
</body>
</html>""",
    },
    AppointmentEmailType.CONFIRMED: {
        "name": "appointment_confirmed",
        "subject": "Appointment Confirmed - {{appointment_type}} on {{scheduled_date}}",
        "body": """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">✓ Appointment Confirmed</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
        <p>Hello {{client_name}},</p>
        <p>Great news! Your appointment has been confirmed. We look forward to meeting with you.</p>
        
        <div style="background: white; border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid #e5e7eb;">
            <h3 style="margin-top: 0; color: #10b981;">Confirmed Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #6b7280;">Type:</td><td style="padding: 8px 0;"><strong>{{appointment_type}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Date:</td><td style="padding: 8px 0;"><strong>{{scheduled_date}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Time:</td><td style="padding: 8px 0;"><strong>{{scheduled_time}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Duration:</td><td style="padding: 8px 0;"><strong>{{duration}} minutes</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">With:</td><td style="padding: 8px 0;"><strong>{{staff_name}}</strong></td></tr>
            </table>
        </div>
        
        <div style="margin: 25px 0; text-align: center;">
            <a href="{{reschedule_url}}" style="display: inline-block; padding: 12px 24px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; margin-right: 10px; font-weight: 500;">Reschedule</a>
            <a href="{{cancel_url}}" style="display: inline-block; padding: 12px 24px; background: #f3f4f6; color: #374151; text-decoration: none; border-radius: 8px; font-weight: 500;">Cancel</a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; margin: 0;">
            {{org_name}}<br>
            This is an automated message. Please do not reply directly to this email.
        </p>
    </div>
</body>
</html>""",
    },
    AppointmentEmailType.RESCHEDULED: {
        "name": "appointment_rescheduled",
        "subject": "Appointment Rescheduled - {{appointment_type}}",
        "body": """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">📅 Appointment Rescheduled</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
        <p>Hello {{client_name}},</p>
        <p>Your appointment has been rescheduled to a new date and time.</p>
        
        <div style="display: flex; gap: 20px; margin: 20px 0;">
            <div style="flex: 1; background: #fee2e2; border-radius: 8px; padding: 15px; border: 1px solid #fecaca;">
                <p style="margin: 0 0 5px 0; color: #991b1b; font-size: 12px; font-weight: 600;">PREVIOUS</p>
                <p style="margin: 0; text-decoration: line-through; color: #6b7280;">{{old_scheduled_date}}<br>{{old_scheduled_time}}</p>
            </div>
            <div style="flex: 1; background: #dcfce7; border-radius: 8px; padding: 15px; border: 1px solid #bbf7d0;">
                <p style="margin: 0 0 5px 0; color: #166534; font-size: 12px; font-weight: 600;">NEW</p>
                <p style="margin: 0; color: #166534; font-weight: bold;">{{scheduled_date}}<br>{{scheduled_time}}</p>
            </div>
        </div>
        
        <div style="background: white; border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid #e5e7eb;">
            <h3 style="margin-top: 0; color: #f59e0b;">Updated Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #6b7280;">Type:</td><td style="padding: 8px 0;"><strong>{{appointment_type}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">New Date:</td><td style="padding: 8px 0;"><strong>{{scheduled_date}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">New Time:</td><td style="padding: 8px 0;"><strong>{{scheduled_time}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Duration:</td><td style="padding: 8px 0;"><strong>{{duration}} minutes</strong></td></tr>
            </table>
        </div>
        
        <div style="margin: 25px 0; text-align: center;">
            <a href="{{reschedule_url}}" style="display: inline-block; padding: 12px 24px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; margin-right: 10px; font-weight: 500;">Reschedule Again</a>
            <a href="{{cancel_url}}" style="display: inline-block; padding: 12px 24px; background: #f3f4f6; color: #374151; text-decoration: none; border-radius: 8px; font-weight: 500;">Cancel</a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; margin: 0;">
            {{org_name}}<br>
            This is an automated message. Please do not reply directly to this email.
        </p>
    </div>
</body>
</html>""",
    },
    AppointmentEmailType.CANCELLED: {
        "name": "appointment_cancelled",
        "subject": "Appointment Cancelled - {{appointment_type}}",
        "body": """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">Appointment Cancelled</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
        <p>Hello {{client_name}},</p>
        <p>Your appointment has been cancelled.</p>
        
        <div style="background: white; border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid #e5e7eb;">
            <h3 style="margin-top: 0; color: #ef4444;">Cancelled Appointment</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #6b7280;">Type:</td><td style="padding: 8px 0;"><strong>{{appointment_type}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Was Scheduled:</td><td style="padding: 8px 0;"><strong>{{scheduled_date}} at {{scheduled_time}}</strong></td></tr>
            </table>
        </div>
        
        <p>If you would like to book a new appointment, please contact us.</p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; margin: 0;">
            {{org_name}}<br>
            This is an automated message. Please do not reply directly to this email.
        </p>
    </div>
</body>
</html>""",
    },
    AppointmentEmailType.REMINDER: {
        "name": "appointment_reminder",
        "subject": "Reminder: {{appointment_type}} Tomorrow at {{scheduled_time}}",
        "body": """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">⏰ Appointment Reminder</h1>
    </div>
    <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
        <p>Hello {{client_name}},</p>
        <p>This is a friendly reminder about your upcoming appointment.</p>
        
        <div style="background: #eff6ff; border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid #bfdbfe;">
            <h3 style="margin-top: 0; color: #1d4ed8;">📅 Tomorrow</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px 0; color: #6b7280;">Type:</td><td style="padding: 8px 0;"><strong>{{appointment_type}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Date:</td><td style="padding: 8px 0;"><strong>{{scheduled_date}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Time:</td><td style="padding: 8px 0;"><strong>{{scheduled_time}}</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">Duration:</td><td style="padding: 8px 0;"><strong>{{duration}} minutes</strong></td></tr>
                <tr><td style="padding: 8px 0; color: #6b7280;">With:</td><td style="padding: 8px 0;"><strong>{{staff_name}}</strong></td></tr>
            </table>
        </div>
        
        <div style="margin: 25px 0; text-align: center;">
            <a href="{{reschedule_url}}" style="display: inline-block; padding: 12px 24px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; margin-right: 10px; font-weight: 500;">Reschedule</a>
            <a href="{{cancel_url}}" style="display: inline-block; padding: 12px 24px; background: #f3f4f6; color: #374151; text-decoration: none; border-radius: 8px; font-weight: 500;">Cancel</a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; margin: 0;">
            {{org_name}}<br>
            This is an automated message. Please do not reply directly to this email.
        </p>
    </div>
</body>
</html>""",
    },
}


# =============================================================================
# Variable Building
# =============================================================================

MEETING_MODE_DISPLAY = {
    "zoom": "Zoom Video Call",
    "phone": "Phone Call",
    "in_person": "In-Person Meeting",
}


def build_appointment_variables(
    appointment: Appointment,
    org: Organization,
    staff: User,
    base_url: str = "",
    old_start: datetime | None = None,
) -> dict[str, str]:
    """Build template variables for an appointment context."""
    # Format dates in client's timezone (fall back to Pacific if invalid)
    client_tz_name = appointment.client_timezone or "America/Los_Angeles"
    try:
        client_tz = ZoneInfo(client_tz_name)
    except Exception:
        client_tz = ZoneInfo("America/Los_Angeles")

    # Convert UTC time to client's timezone for display
    scheduled_start = appointment.scheduled_start
    if scheduled_start:
        scheduled_start_local = scheduled_start.astimezone(client_tz)
    else:
        scheduled_start_local = None

    variables = {
        # Client info
        "client_name": appointment.client_name or "",
        "client_email": appointment.client_email or "",
        "client_phone": appointment.client_phone or "",
        # Appointment info
        "appointment_type": appointment.appointment_type.name
        if appointment.appointment_type
        else "",
        "scheduled_date": scheduled_start_local.strftime("%A, %B %d, %Y")
        if scheduled_start_local
        else "",
        "scheduled_time": scheduled_start_local.strftime("%I:%M %p %Z")
        if scheduled_start_local
        else "",
        "duration": str(appointment.duration_minutes or 0),
        "meeting_mode": MEETING_MODE_DISPLAY.get(
            appointment.meeting_mode or "", appointment.meeting_mode or ""
        ),
        # Staff info
        "staff_name": staff.display_name if staff else "",
        "staff_email": staff.email if staff else "",
        # Org info
        "org_name": org.name if org else "",
        # Links - use correct self-service paths (frontend routes)
        "reschedule_url": (
            f"{base_url}/book/{appointment.organization_id}/reschedule/{appointment.reschedule_token}"
        )
        if appointment.reschedule_token
        else "",
        "cancel_url": (
            f"{base_url}/book/{appointment.organization_id}/cancel/{appointment.cancel_token}"
        )
        if appointment.cancel_token
        else "",
        # Zoom (if available)
        "zoom_join_url": appointment.zoom_join_url or "",
        "zoom_meeting_id": appointment.zoom_meeting_id or "",
        # Cancellation
        "cancellation_reason": appointment.cancellation_reason or "",
        # Client notes
        "client_notes": appointment.client_notes or "",
    }

    # Old time for reschedule emails (also convert to client timezone)
    if old_start:
        old_start_local = old_start.astimezone(client_tz)
        variables["old_scheduled_date"] = old_start_local.strftime("%A, %B %d, %Y")
        variables["old_scheduled_time"] = old_start_local.strftime("%I:%M %p %Z")

    return variables


# =============================================================================
# Template Management
# =============================================================================


def get_or_create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    email_type: AppointmentEmailType,
) -> UUID | None:
    """Get or create the template for an appointment email type."""
    template_name = _get_template_name(email_type)
    template = email_service.get_template_by_name(db, template_name, org_id)

    if template:
        return template.id

    # Create default template
    default = DEFAULT_TEMPLATES.get(email_type)
    if not default:
        return None

    template = email_service.create_template(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=default["name"],
        subject=default["subject"],
        body=default["body"],
    )
    return template.id


# =============================================================================
# Email Sending
# =============================================================================


def send_appointment_email(
    db: Session,
    appointment: Appointment,
    email_type: AppointmentEmailType,
    base_url: str = "",
    old_start: datetime | None = None,
    schedule_at: datetime | None = None,
) -> AppointmentEmailLog | None:
    """
    Send an appointment notification email.

    Creates or reuses templates, builds variables, queues the email,
    and logs it in AppointmentEmailLog.
    """
    # Get org and staff
    org = (
        db.query(Organization)
        .filter(Organization.id == appointment.organization_id)
        .first()
    )
    staff = db.query(User).filter(User.id == appointment.user_id).first()

    if not org or not staff:
        return None

    # Get or create template
    # Use a system user ID for template creation (first admin of org)
    template_id = get_or_create_template(
        db,
        org.id,
        staff.id,
        email_type,
    )
    if not template_id:
        return None

    # Build variables
    variables = build_appointment_variables(
        appointment=appointment,
        org=org,
        staff=staff,
        base_url=base_url,
        old_start=old_start,
    )

    # Get template for subject
    template = email_service.get_template(db, template_id, org.id)
    if not template:
        return None

    subject, _ = email_service.render_template(template.subject, "", variables)

    # Log the email
    email_log = log_appointment_email(
        db=db,
        org_id=org.id,
        appointment_id=appointment.id,
        email_type=email_type.value,
        recipient_email=appointment.client_email,
        subject=subject,
    )

    # Queue the email
    try:
        result = email_service.send_from_template(
            db=db,
            org_id=org.id,
            template_id=template_id,
            recipient_email=appointment.client_email,
            variables=variables,
            schedule_at=schedule_at,
        )
        if result:
            _, job = result
            mark_email_sent(db, email_log, str(job.id) if job else None)
    except Exception as e:
        mark_email_failed(db, email_log, str(e))

    return email_log


def schedule_reminder_email(
    db: Session,
    appointment: Appointment,
    base_url: str = "",
    hours_before: int = 24,
) -> AppointmentEmailLog | None:
    """Schedule a reminder email for hours_before the appointment."""
    if not appointment.scheduled_start:
        return None

    remind_at = appointment.scheduled_start - timedelta(hours=hours_before)

    # Don't schedule if reminder time is in the past
    if remind_at <= datetime.now(timezone.utc):
        return None

    return send_appointment_email(
        db=db,
        appointment=appointment,
        email_type=AppointmentEmailType.REMINDER,
        base_url=base_url,
        schedule_at=remind_at,
    )


# =============================================================================
# Convenience Functions
# =============================================================================


def send_request_received(
    db: Session, appointment: Appointment, base_url: str = ""
) -> AppointmentEmailLog | None:
    """Send 'request received' email to client."""
    return send_appointment_email(
        db, appointment, AppointmentEmailType.REQUEST_RECEIVED, base_url
    )


def send_confirmed(
    db: Session, appointment: Appointment, base_url: str = ""
) -> AppointmentEmailLog | None:
    """Send confirmation email to client."""
    return send_appointment_email(
        db, appointment, AppointmentEmailType.CONFIRMED, base_url
    )


def send_rescheduled(
    db: Session, appointment: Appointment, old_start: datetime, base_url: str = ""
) -> AppointmentEmailLog | None:
    """Send reschedule notification to client."""
    return send_appointment_email(
        db, appointment, AppointmentEmailType.RESCHEDULED, base_url, old_start=old_start
    )


def send_cancelled(
    db: Session, appointment: Appointment, base_url: str = ""
) -> AppointmentEmailLog | None:
    """Send cancellation notification to client."""
    return send_appointment_email(
        db, appointment, AppointmentEmailType.CANCELLED, base_url
    )


def send_reminder(
    db: Session,
    appointment: Appointment,
    base_url: str = "",
    hours_before: int = 24,
) -> AppointmentEmailLog | None:
    """Send/schedule reminder email to client."""
    return schedule_reminder_email(db, appointment, base_url, hours_before)
