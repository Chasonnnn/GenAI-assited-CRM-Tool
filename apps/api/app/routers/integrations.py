"""User integrations router.

Handles per-user OAuth flows for Gmail, Zoom, etc.
Each user connects their own accounts.
"""
import logging
import secrets
import uuid
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_session, require_csrf_header
from app.schemas.auth import UserSession
from app.services import oauth_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])
logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class IntegrationStatus(BaseModel):
    """Status of a user's integration."""
    integration_type: str
    connected: bool
    account_email: str | None = None
    expires_at: str | None = None


class IntegrationListResponse(BaseModel):
    """List of user's integrations."""
    integrations: list[IntegrationStatus]


# State storage for OAuth CSRF protection (in production, use Redis)
_oauth_state_store: dict[str, dict] = {}


def _generate_state(user_id: uuid.UUID, integration_type: str) -> str:
    """Generate a random state token for OAuth CSRF protection."""
    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = {
        "user_id": str(user_id),
        "integration_type": integration_type,
    }
    return state


def _validate_state(state: str) -> dict | None:
    """Validate and consume a state token."""
    return _oauth_state_store.pop(state, None)


# ============================================================================
# List Integrations
# ============================================================================

@router.get("/", response_model=IntegrationListResponse)
def list_integrations(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> IntegrationListResponse:
    """List user's connected integrations."""
    integrations = oauth_service.get_user_integrations(db, session.user_id)
    
    return IntegrationListResponse(
        integrations=[
            IntegrationStatus(
                integration_type=i.integration_type,
                connected=True,
                account_email=i.account_email,
                expires_at=i.token_expires_at.isoformat() if i.token_expires_at else None,
            )
            for i in integrations
        ]
    )


@router.delete("/{integration_type}", dependencies=[Depends(require_csrf_header)])
def disconnect_integration(
    integration_type: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Disconnect an integration."""
    deleted = oauth_service.delete_integration(db, session.user_id, integration_type)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_type}' not found",
        )
    return {"success": True, "message": f"{integration_type} disconnected"}


# ============================================================================
# Gmail OAuth
# ============================================================================

@router.get("/gmail/connect")
def gmail_connect(
    request: Request,
    session: UserSession = Depends(get_current_session),
) -> dict[str, str]:
    """Get Gmail OAuth authorization URL.
    
    Frontend should redirect user to this URL.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail integration not configured. Set GOOGLE_CLIENT_ID.",
        )
    
    state = _generate_state(session.user_id, "gmail")
    redirect_uri = settings.GMAIL_REDIRECT_URI
    auth_url = oauth_service.get_gmail_auth_url(redirect_uri, state)
    
    return {"auth_url": auth_url}


@router.get("/gmail/callback")
async def gmail_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Gmail OAuth callback."""
    # Validate state
    state_data = _validate_state(state)
    if not state_data:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=invalid_state"
        )
    
    user_id = uuid.UUID(state_data["user_id"])
    
    try:
        # Exchange code for tokens
        redirect_uri = settings.GMAIL_REDIRECT_URI
        tokens = await oauth_service.exchange_gmail_code(code, redirect_uri)
        
        # Get user info
        user_info = await oauth_service.get_gmail_user_info(tokens["access_token"])
        
        # Save integration
        oauth_service.save_integration(
            db,
            user_id,
            "gmail",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=tokens.get("expires_in"),
            account_email=user_info.get("email"),
        )
        
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?success=gmail"
        )
    except Exception as e:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=gmail_failed"
        )


# ============================================================================
# Zoom OAuth
# ============================================================================

@router.get("/zoom/connect")
def zoom_connect(
    request: Request,
    session: UserSession = Depends(get_current_session),
) -> dict[str, str]:
    """Get Zoom OAuth authorization URL."""
    if not settings.ZOOM_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zoom integration not configured. Set ZOOM_CLIENT_ID.",
        )
    
    state = _generate_state(session.user_id, "zoom")
    redirect_uri = settings.ZOOM_REDIRECT_URI
    auth_url = oauth_service.get_zoom_auth_url(redirect_uri, state)
    
    return {"auth_url": auth_url}


@router.get("/zoom/callback")
async def zoom_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Zoom OAuth callback."""
    # Validate state
    state_data = _validate_state(state)
    if not state_data:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=invalid_state"
        )
    
    user_id = uuid.UUID(state_data["user_id"])
    
    try:
        # Exchange code for tokens
        redirect_uri = settings.ZOOM_REDIRECT_URI
        tokens = await oauth_service.exchange_zoom_code(code, redirect_uri)
        
        # Get user info
        user_info = await oauth_service.get_zoom_user_info(tokens["access_token"])
        
        # Save integration
        oauth_service.save_integration(
            db,
            user_id,
            "zoom",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=tokens.get("expires_in"),
            account_email=user_info.get("email"),
        )
        
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?success=zoom"
        )
    except Exception as e:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=zoom_failed"
        )


# ============================================================================
# Zoom Meetings
# ============================================================================

class CreateMeetingRequest(BaseModel):
    """Request to create a Zoom meeting."""
    entity_type: str  # "case" or "intended_parent"
    entity_id: uuid.UUID
    topic: str
    start_time: str | None = None  # ISO format datetime
    duration: int = 30  # minutes
    create_task: bool = True
    contact_name: str | None = None


class CreateMeetingResponse(BaseModel):
    """Response from creating a Zoom meeting."""
    join_url: str
    start_url: str
    meeting_id: int
    password: str | None = None
    note_id: str | None = None
    task_id: str | None = None


@router.post("/zoom/meetings", response_model=CreateMeetingResponse, dependencies=[Depends(require_csrf_header)])
async def create_zoom_meeting(
    request: CreateMeetingRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> CreateMeetingResponse:
    """Create a Zoom meeting for a case or intended parent.
    
    Automatically:
    - Creates meeting via Zoom API
    - Adds note to the entity with meeting link
    - Optionally creates a follow-up task
    """
    from datetime import datetime as dt
    from app.db.enums import EntityType
    from app.services import zoom_service
    
    # Parse entity type
    if request.entity_type == "case":
        entity_type = EntityType.CASE
    elif request.entity_type == "intended_parent":
        entity_type = EntityType.INTENDED_PARENT
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {request.entity_type}. Must be 'case' or 'intended_parent'.",
        )
    
    # Parse start time
    start_time = None
    if request.start_time:
        try:
            start_time = dt.fromisoformat(request.start_time.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_time format. Use ISO format (e.g., 2024-01-15T10:00:00).",
            )
    
    # Check user has Zoom connected
    if not zoom_service.check_user_has_zoom(db, session.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zoom not connected. Please connect Zoom in Settings → Integrations.",
        )
    
    try:
        result = await zoom_service.schedule_zoom_meeting(
            db=db,
            user_id=session.user_id,
            org_id=session.org_id,
            entity_type=entity_type,
            entity_id=request.entity_id,
            topic=request.topic,
            start_time=start_time,
            duration=request.duration,
            create_task=request.create_task,
            contact_name=request.contact_name,
        )
        
        return CreateMeetingResponse(
            join_url=result.meeting.join_url,
            start_url=result.meeting.start_url,
            meeting_id=result.meeting.id,
            password=result.meeting.password,
            note_id=str(result.note_id) if result.note_id else None,
            task_id=str(result.task_id) if result.task_id else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.error(f"Zoom API error: {e.response.text}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Zoom API error. Please try again or reconnect Zoom.",
        )


@router.get("/zoom/status")
def zoom_connection_status(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Check if current user has Zoom connected."""
    from app.services import zoom_service
    
    integration = oauth_service.get_user_integration(db, session.user_id, "zoom")
    
    return {
        "connected": integration is not None,
        "account_email": integration.account_email if integration else None,
    }


class SendMeetingInviteRequest(BaseModel):
    """Request to send a Zoom meeting invite email."""
    recipient_email: str
    meeting_id: int
    join_url: str
    topic: str
    start_time: str | None = None
    duration: int = 30
    password: str | None = None
    contact_name: str
    case_id: str | None = None


class SendMeetingInviteResponse(BaseModel):
    """Response from sending meeting invite."""
    email_log_id: str
    success: bool


@router.post("/zoom/send-invite", response_model=SendMeetingInviteResponse, dependencies=[Depends(require_csrf_header)])
def send_zoom_meeting_invite(
    request: SendMeetingInviteRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> SendMeetingInviteResponse:
    """Send a Zoom meeting invite email using the org's template.
    
    Uses the 'Zoom Meeting Invite' template (auto-created if missing).
    """
    from app.services import zoom_service
    from app.db.models import User
    
    # Get host name for template
    user = db.query(User).filter(User.id == session.user_id).first()
    host_name = user.display_name if user else "Your Host"
    
    # Build meeting object for template
    meeting = zoom_service.ZoomMeeting(
        id=request.meeting_id,
        uuid="",  # Not needed for email
        topic=request.topic,
        start_time=request.start_time,
        duration=request.duration,
        timezone="America/New_York",
        join_url=request.join_url,
        start_url="",  # Not needed for attendee
        password=request.password,
    )
    
    # Parse case_id
    case_id = None
    if request.case_id:
        try:
            case_id = uuid.UUID(request.case_id)
        except ValueError:
            pass
    
    # Send invite
    email_log_id = zoom_service.send_meeting_invite(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        recipient_email=request.recipient_email,
        meeting=meeting,
        contact_name=request.contact_name,
        host_name=host_name,
        case_id=case_id,
    )
    
    if not email_log_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invite email",
        )
    
    return SendMeetingInviteResponse(
        email_log_id=str(email_log_id),
        success=True,
    )

