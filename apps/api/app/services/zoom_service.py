"""Zoom integration service.

Handles Zoom meeting creation and management using the Zoom API.
Uses OAuth tokens stored per-user in UserIntegration table.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.enums import EntityType, TaskType, OwnerType
from app.db.models import EntityNote, Task, ZoomMeeting as ZoomMeetingModel
from app.services import oauth_service

logger = logging.getLogger(__name__)

ZOOM_API_BASE = "https://api.zoom.us/v2"


# ============================================================================
# Response Models
# ============================================================================

class ZoomMeeting(BaseModel):
    """Zoom meeting response."""
    id: int
    uuid: str
    topic: str
    start_time: str | None
    duration: int
    timezone: str
    join_url: str
    start_url: str
    password: str | None = None


class CreateMeetingResult(BaseModel):
    """Result of creating a Zoom meeting with note and meeting task."""
    meeting: ZoomMeeting
    note_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None


def list_zoom_meetings(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
) -> list[ZoomMeetingModel]:
    """List user's recent Zoom meetings."""
    return (
        db.query(ZoomMeetingModel)
        .filter(
            ZoomMeetingModel.organization_id == org_id,
            ZoomMeetingModel.user_id == user_id,
        )
        .order_by(ZoomMeetingModel.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )


# ============================================================================
# Zoom API Functions
# ============================================================================

async def create_zoom_meeting(
    access_token: str,
    topic: str,
    start_time: datetime | None = None,
    duration: int = 30,
    timezone_name: str = "America/Los_Angeles",
) -> ZoomMeeting:
    """Create a Zoom meeting using the Zoom API.
    
    Args:
        access_token: User's Zoom OAuth access token
        topic: Meeting topic/title
        start_time: When meeting starts (None = instant meeting)
        duration: Meeting duration in minutes
        timezone: Meeting timezone
        
    Returns:
        ZoomMeeting with join_url, start_url, etc.
    """
    # Build meeting payload
    meeting_data: dict[str, Any] = {
        "topic": topic,
        "type": 2 if start_time else 1,  # 1=instant, 2=scheduled
        "duration": duration,
        "timezone": timezone_name,
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True,
            "mute_upon_entry": False,
            "waiting_room": False,
            "meeting_authentication": False,
        },
    }
    
    if start_time:
        # Zoom supports local time + separate timezone. Prefer sending local time without
        # an offset so Zoom displays it in the provided timezone.
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = timezone.utc

        if start_time.tzinfo is None:
            local_dt = start_time.replace(tzinfo=tz)
        else:
            local_dt = start_time.astimezone(tz)

        meeting_data["start_time"] = local_dt.replace(tzinfo=None, microsecond=0).isoformat()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ZOOM_API_BASE}/users/me/meetings",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=meeting_data,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    
    return ZoomMeeting(
        id=data["id"],
        uuid=data["uuid"],
        topic=data["topic"],
        start_time=data.get("start_time"),
        duration=data.get("duration", duration),
        timezone=data.get("timezone", timezone_name),
        join_url=data["join_url"],
        start_url=data["start_url"],
        password=data.get("password"),
    )


# ============================================================================
# High-Level Functions (with note/task creation)
# ============================================================================

def get_user_zoom_token(
    db: Session, 
    user_id: uuid.UUID,
) -> str:
    """Get user's Zoom access token, refreshing if expired.

    Raises ValueError if Zoom isn't connected or token refresh fails.
    """
    integration = oauth_service.get_user_integration(db, user_id, "zoom")
    if not integration:
        raise ValueError("Zoom not connected. Please connect in Settings → Integrations.")

    access_token = oauth_service.get_access_token(db, user_id, "zoom")
    if not access_token:
        raise ValueError("Zoom token expired or invalid. Please reconnect in Settings → Integrations.")

    return access_token


async def schedule_zoom_meeting(
    db: Session,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    topic: str,
    start_time: datetime | None = None,
    timezone_name: str = "America/Los_Angeles",
    duration: int = 30,
    contact_name: str | None = None,
) -> CreateMeetingResult:
    """Schedule a Zoom meeting and add note + meeting task.
    
    Args:
        db: Database session
        user_id: User scheduling the meeting
        org_id: Organization ID
        entity_type: CASE or INTENDED_PARENT
        entity_id: ID of the case or intended parent
        topic: Meeting topic
        start_time: When meeting starts (None = instant)
        duration: Duration in minutes
        contact_name: Name of person meeting is with (for note)
        
    Returns:
        CreateMeetingResult with meeting details and note/task IDs
    """
    # Get user's Zoom token
    access_token = get_user_zoom_token(db, user_id)
    
    # Create the Zoom meeting
    meeting = await create_zoom_meeting(
        access_token=access_token,
        topic=topic,
        start_time=start_time,
        duration=duration,
        timezone_name=timezone_name,
    )

    meeting_start_time = None
    if meeting.start_time:
        try:
            meeting_start_time = datetime.fromisoformat(
                meeting.start_time.replace("Z", "+00:00")
            )
        except ValueError:
            meeting_start_time = start_time
    
    # Build note content
    from html import escape
    from app.services import note_service

    display_dt: datetime
    if start_time:
        if start_time.tzinfo is None:
            try:
                display_dt = start_time.replace(tzinfo=ZoneInfo(timezone_name))
            except Exception:
                display_dt = start_time.replace(tzinfo=timezone.utc)
        else:
            try:
                display_dt = start_time.astimezone(ZoneInfo(timezone_name))
            except Exception:
                display_dt = start_time.astimezone(timezone.utc)
    else:
        try:
            display_dt = datetime.now(ZoneInfo(timezone_name))
        except Exception:
            display_dt = datetime.now(timezone.utc)

    end_dt = display_dt + timedelta(minutes=duration)
    time_str = f"{display_dt.strftime('%B %d, %Y %I:%M %p %Z')} – {end_dt.strftime('%I:%M %p %Z')} ({duration} min)"
    join_url = escape(meeting.join_url)
    safe_topic = escape(topic)

    note_content = (
        "<p>📹 <strong>Zoom Meeting Scheduled</strong></p>"
        f"<p><strong>Topic:</strong> {safe_topic}<br/>"
        f"<strong>Time:</strong> {escape(time_str)}<br/>"
        f"<strong>Duration:</strong> {duration} minutes</p>"
        f"<p><strong>Join Link:</strong> <a href=\"{join_url}\" target=\"_blank\">{join_url}</a></p>"
    )
    if meeting.password:
        note_content += f"<p><strong>Password:</strong> {escape(meeting.password)}</p>"
    if contact_name:
        note_content += f"<p><strong>With:</strong> {escape(contact_name)}</p>"

    note_content = note_service.sanitize_html(note_content)
    
    # Create note
    note = EntityNote(
        organization_id=org_id,
        entity_type=entity_type.value,
        entity_id=entity_id,
        content=note_content,
        author_id=user_id,
    )
    db.add(note)
    db.flush()  # get note.id for activity log

    # Log case activity (case only)
    if entity_type == EntityType.CASE:
        from app.services import activity_service
        activity_service.log_note_added(
            db=db,
            case_id=entity_id,
            organization_id=org_id,
            actor_user_id=user_id,
            note_id=note.id,
            content=note_content,
        )
    
    # Always create a meeting task aligned with the scheduled time + duration.
    task = Task(
        organization_id=org_id,
        title=f"Zoom Meeting: {topic}",
        description=f"{time_str}\nJoin link: {meeting.join_url}",
        task_type=TaskType.MEETING.value,
        due_date=display_dt.date(),
        due_time=display_dt.time().replace(tzinfo=None, second=0, microsecond=0),
        duration_minutes=duration,
        owner_type=OwnerType.USER.value,
        owner_id=user_id,
        created_by_user_id=user_id,
        case_id=entity_id if entity_type == EntityType.CASE else None,
        # Note: intended_parent_id would need to be added to Task model
    )
    db.add(task)
    db.flush()
    task_id = task.id
    
    # Save meeting to zoom_meetings table for history
    zoom_meeting_record = ZoomMeetingModel(
        organization_id=org_id,
        user_id=user_id,
        case_id=entity_id if entity_type == EntityType.CASE else None,
        intended_parent_id=entity_id if entity_type == EntityType.INTENDED_PARENT else None,
        zoom_meeting_id=str(meeting.id),
        topic=meeting.topic,
        start_time=meeting_start_time,
        duration=duration,
        timezone=meeting.timezone or timezone_name,
        join_url=meeting.join_url,
        start_url=meeting.start_url,
        password=meeting.password,
    )
    db.add(zoom_meeting_record)
    
    db.commit()
    db.refresh(note)
    
    return CreateMeetingResult(
        meeting=meeting,
        note_id=note.id,
        task_id=task_id,
    )


def check_user_has_zoom(db: Session, user_id: uuid.UUID) -> bool:
    """Check if user has connected Zoom."""
    integration = oauth_service.get_user_integration(db, user_id, "zoom")
    return integration is not None


# ============================================================================
# Email Invite Template
# ============================================================================

ZOOM_TEMPLATE_NAME = "Zoom Meeting Invite"

DEFAULT_ZOOM_TEMPLATE_SUBJECT = "Meeting Scheduled: {{topic}}"
DEFAULT_ZOOM_TEMPLATE_BODY = """Hi {{contact_name}},

I've scheduled a Zoom meeting for us:

📅 **{{topic}}**
🕐 **Time:** {{meeting_time}}
⏱️ **Duration:** {{duration}} minutes

🔗 **Join the meeting:**
{{meeting_link}}

{{password_line}}

Looking forward to speaking with you!

Best regards,
{{host_name}}
"""


def get_or_create_zoom_template(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> uuid.UUID:
    """Get the Zoom meeting invite template, creating if it doesn't exist.
    
    Returns the template ID.
    """
    from app.services import email_service
    
    # Check if template exists
    template = email_service.get_template_by_name(db, ZOOM_TEMPLATE_NAME, org_id)
    if template:
        return template.id
    
    # Create default template
    template = email_service.create_template(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name=ZOOM_TEMPLATE_NAME,
        subject=DEFAULT_ZOOM_TEMPLATE_SUBJECT,
        body=DEFAULT_ZOOM_TEMPLATE_BODY,
    )
    return template.id


def send_meeting_invite(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    recipient_email: str,
    meeting: ZoomMeeting,
    contact_name: str,
    host_name: str,
    case_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Send a Zoom meeting invite email using the org's template.
    
    Returns the email_log ID or None if template not found.
    """
    from app.services import email_service
    
    # Get or create template
    template_id = get_or_create_zoom_template(db, org_id, user_id)
    
    # Build variables
    time_str = meeting.start_time if meeting.start_time else "Instant meeting"
    password_line = f"🔒 **Password:** {meeting.password}" if meeting.password else ""
    variables = {
        "topic": meeting.topic,
        "meeting_link": meeting.join_url,
        "meeting_time": time_str,
        "duration": str(meeting.duration),
        "password": meeting.password or "",
        "password_line": password_line,
        "contact_name": contact_name,
        "host_name": host_name,
    }
    
    # Send via template
    result = email_service.send_from_template(
        db=db,
        org_id=org_id,
        template_id=template_id,
        recipient_email=recipient_email,
        variables=variables,
        case_id=case_id,
    )
    
    if result:
        email_log, _ = result
        return email_log.id
    return None
