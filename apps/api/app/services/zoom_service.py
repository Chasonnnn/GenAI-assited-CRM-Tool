"""Zoom integration service.

Handles Zoom meeting creation and management using the Zoom API.
Uses OAuth tokens stored per-user in UserIntegration table.
"""
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.enums import EntityType
from app.db.models import EntityNote, Task, UserIntegration
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
    """Result of creating a Zoom meeting with note and optional task."""
    meeting: ZoomMeeting
    note_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None


# ============================================================================
# Zoom API Functions
# ============================================================================

async def create_zoom_meeting(
    access_token: str,
    topic: str,
    start_time: datetime | None = None,
    duration: int = 30,
    timezone: str = "America/New_York",
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
        "timezone": timezone,
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
        meeting_data["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    
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
        timezone=data.get("timezone", timezone),
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
) -> str | None:
    """Get and refresh user's Zoom access token if needed.
    
    Returns None if user hasn't connected Zoom.
    """
    integration = oauth_service.get_user_integration(db, user_id, "zoom")
    if not integration:
        return None
    
    # Check if token needs refresh
    if integration.token_expires_at and integration.token_expires_at < datetime.utcnow():
        # Try to refresh
        if integration.refresh_token_encrypted:
            refresh_token = oauth_service.decrypt_token(integration.refresh_token_encrypted)
            # Note: refresh happens in the oauth_service
            new_tokens = oauth_service.auto_refresh_if_needed(
                db, user_id, "zoom", integration
            )
            if new_tokens:
                return oauth_service.decrypt_token(integration.access_token_encrypted)
        return None
    
    return oauth_service.decrypt_token(integration.access_token_encrypted)


async def schedule_zoom_meeting(
    db: Session,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    entity_type: EntityType,
    entity_id: uuid.UUID,
    topic: str,
    start_time: datetime | None = None,
    duration: int = 30,
    create_task: bool = True,
    contact_name: str | None = None,
) -> CreateMeetingResult:
    """Schedule a Zoom meeting and add note + optional task.
    
    Args:
        db: Database session
        user_id: User scheduling the meeting
        org_id: Organization ID
        entity_type: CASE or INTENDED_PARENT
        entity_id: ID of the case or intended parent
        topic: Meeting topic
        start_time: When meeting starts (None = instant)
        duration: Duration in minutes
        create_task: Whether to create a follow-up task
        contact_name: Name of person meeting is with (for note)
        
    Returns:
        CreateMeetingResult with meeting details and note/task IDs
    """
    # Get user's Zoom token
    access_token = get_user_zoom_token(db, user_id)
    if not access_token:
        raise ValueError("User has not connected Zoom. Please connect in Settings → Integrations.")
    
    # Create the Zoom meeting
    meeting = await create_zoom_meeting(
        access_token=access_token,
        topic=topic,
        start_time=start_time,
        duration=duration,
    )
    
    # Build note content
    time_str = start_time.strftime("%B %d, %Y at %I:%M %p") if start_time else "Instant meeting"
    note_content = f"""📹 **Zoom Meeting Scheduled**

**Topic:** {topic}
**Time:** {time_str}
**Duration:** {duration} minutes

**Join Link:** {meeting.join_url}
"""
    if meeting.password:
        note_content += f"**Password:** {meeting.password}\n"
    if contact_name:
        note_content += f"\n**With:** {contact_name}"
    
    # Create note
    note = EntityNote(
        organization_id=org_id,
        entity_type=entity_type.value,
        entity_id=entity_id,
        content=note_content,
        author_id=user_id,
    )
    db.add(note)
    
    # Create task if requested
    task_id = None
    if create_task and start_time:
        task = Task(
            organization_id=org_id,
            title=f"Zoom Call: {topic}",
            description=f"Join link: {meeting.join_url}",
            due_date=start_time.date(),
            assigned_to_user_id=user_id,
            created_by_user_id=user_id,
            case_id=entity_id if entity_type == EntityType.CASE else None,
            # Note: intended_parent_id would need to be added to Task model
        )
        db.add(task)
        db.flush()
        task_id = task.id
    
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
