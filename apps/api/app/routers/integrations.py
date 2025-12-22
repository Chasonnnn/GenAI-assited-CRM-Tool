"""User integrations router.

Handles per-user OAuth flows for Gmail, Zoom, etc.
Each user connects their own accounts.
"""
import logging
import uuid
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_session, require_csrf_header
from app.core.security import (
    create_oauth_state_payload,
    generate_oauth_nonce,
    generate_oauth_state,
    parse_oauth_state_payload,
    verify_oauth_state,
)
from app.schemas.auth import UserSession
from app.services import oauth_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])
logger = logging.getLogger(__name__)

OAUTH_STATE_MAX_AGE = 300  # 5 minutes
OAUTH_STATE_COOKIE_PREFIX = "integration_oauth_state_"
OAUTH_STATE_COOKIE_PATH = "/integrations"


def _oauth_cookie_name(integration_type: str) -> str:
    return f"{OAUTH_STATE_COOKIE_PREFIX}{integration_type}"


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
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Disconnect an integration."""
    from app.db.enums import AuditEventType
    from app.services import audit_service

    integration = oauth_service.get_user_integration(db, session.user_id, integration_type)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_type}' not found",
        )

    deleted = oauth_service.delete_integration(db, session.user_id, integration_type)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{integration_type}' not found",
        )

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.INTEGRATION_DISCONNECTED,
        actor_user_id=session.user_id,
        target_type="user_integration",
        target_id=integration.id,
        details={"integration_type": integration_type},
        request=request,
    )
    db.commit()
    return {"success": True, "message": f"{integration_type} disconnected"}


# ============================================================================
# Gmail OAuth
# ============================================================================

@router.get("/gmail/connect")
def gmail_connect(
    request: Request,
    response: Response,
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
    
    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    user_agent = request.headers.get("user-agent", "")
    state_payload = create_oauth_state_payload(state, nonce, user_agent)

    response.set_cookie(
        key=_oauth_cookie_name("gmail"),
        value=state_payload,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path=OAUTH_STATE_COOKIE_PATH,
    )

    redirect_uri = settings.GMAIL_REDIRECT_URI
    auth_url = oauth_service.get_gmail_auth_url(redirect_uri, state)
    
    return {"auth_url": auth_url}


@router.get("/gmail/callback")
async def gmail_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> RedirectResponse:
    """Handle Gmail OAuth callback."""
    cookie_name = _oauth_cookie_name("gmail")
    error_response = RedirectResponse(
        f"{settings.FRONTEND_URL}/settings/integrations?error=invalid_state",
        status_code=302,
    )
    error_response.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)

    state_cookie = request.cookies.get(cookie_name)
    if not state_cookie:
        return error_response

    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
    except Exception:
        return error_response

    user_agent = request.headers.get("user-agent", "")
    valid, _ = verify_oauth_state(stored_payload, state, user_agent)
    if not valid:
        return error_response
    
    try:
        # Exchange code for tokens
        redirect_uri = settings.GMAIL_REDIRECT_URI
        tokens = await oauth_service.exchange_gmail_code(code, redirect_uri)
        
        # Get user info
        user_info = await oauth_service.get_gmail_user_info(tokens["access_token"])
        
        # Save integration
        oauth_service.save_integration(
            db,
            session.user_id,
            "gmail",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=tokens.get("expires_in"),
            account_email=user_info.get("email"),
        )

        # Audit log (no secrets)
        from app.db.enums import AuditEventType
        from app.services import audit_service

        integration = oauth_service.get_user_integration(db, session.user_id, "gmail")
        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.INTEGRATION_CONNECTED,
            actor_user_id=session.user_id,
            target_type="user_integration",
            target_id=integration.id if integration else None,
            details={
                "integration_type": "gmail",
                "account_email": audit_service.hash_email(user_info.get("email", "") or ""),
            },
            request=request,
        )
        db.commit()
        
        success = RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?success=gmail",
            status_code=302,
        )
        success.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)
        return success
    except Exception as e:
        error = RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=gmail_failed",
            status_code=302,
        )
        error.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)
        return error


@router.get("/gmail/status")
def gmail_connection_status(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Check if current user has Gmail connected."""
    integration = oauth_service.get_user_integration(db, session.user_id, "gmail")
    
    return {
        "connected": integration is not None,
        "account_email": integration.account_email if integration else None,
        "expires_at": integration.token_expires_at.isoformat() if integration and integration.token_expires_at else None,
    }


# ============================================================================
# Google Calendar Events
# ============================================================================

class GoogleCalendarEventRead(BaseModel):
    """A Google Calendar event for display."""
    id: str
    summary: str
    start: str  # ISO datetime
    end: str    # ISO datetime
    html_link: str
    is_all_day: bool = False
    source: str = "google"


@router.get("/google/calendar/events", response_model=list[GoogleCalendarEventRead])
async def get_google_calendar_events(
    date_start: str,  # ISO date (YYYY-MM-DD)
    date_end: str,    # ISO date (YYYY-MM-DD)
    timezone: str | None = None,  # Optional: client timezone (e.g., "America/New_York")
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> list[GoogleCalendarEventRead]:
    """
    Get user's Google Calendar events for a date range.
    
    Returns empty list if Google is not connected (no error).
    Events are fetched from the user's primary calendar only.
    
    Query params:
    - date_start: Start date (ISO format YYYY-MM-DD)
    - date_end: End date (ISO format YYYY-MM-DD)
    - timezone: Optional client timezone (e.g., "America/New_York") for accurate day boundaries
    """
    from datetime import datetime as dt, timezone as tz, time as tm
    from zoneinfo import ZoneInfo
    from app.services import calendar_service
    
    # Parse dates
    try:
        start_date = dt.fromisoformat(date_start)
        end_date = dt.fromisoformat(date_end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )
    
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_end must be greater than or equal to date_start.",
        )
    
    # Determine timezone for day boundaries (default to Pacific like rest of app)
    try:
        client_tz = ZoneInfo(timezone) if timezone else ZoneInfo("America/Los_Angeles")
    except Exception:
        # Invalid timezone, fall back to Pacific
        client_tz = ZoneInfo("America/Los_Angeles")
    
    # Convert to datetime with timezone (start of day to end of day in client TZ)
    # Then convert to UTC for the API call
    time_min = dt.combine(start_date.date(), tm.min, tzinfo=client_tz)
    time_max = dt.combine(end_date.date(), tm(23, 59, 59, 999999), tzinfo=client_tz)
    
    # Fetch events - returns empty list if not connected
    events = await calendar_service.get_user_calendar_events(
        db=db,
        user_id=session.user_id,
        time_min=time_min,
        time_max=time_max,
        calendar_id="primary",
    )
    
    return [
        GoogleCalendarEventRead(
            id=e["id"],
            summary=e["summary"],
            start=e["start"].isoformat(),
            end=e["end"].isoformat(),
            html_link=e["html_link"],
            is_all_day=e["is_all_day"],
            source="google",
        )
        for e in events
    ]


# ============================================================================
# Zoom OAuth
# ============================================================================

@router.get("/zoom/connect")
def zoom_connect(
    request: Request,
    response: Response,
    session: UserSession = Depends(get_current_session),
) -> dict[str, str]:
    """Get Zoom OAuth authorization URL."""
    if not settings.ZOOM_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Zoom integration not configured. Set ZOOM_CLIENT_ID.",
        )
    
    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    user_agent = request.headers.get("user-agent", "")
    state_payload = create_oauth_state_payload(state, nonce, user_agent)

    response.set_cookie(
        key=_oauth_cookie_name("zoom"),
        value=state_payload,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path=OAUTH_STATE_COOKIE_PATH,
    )

    redirect_uri = settings.ZOOM_REDIRECT_URI
    auth_url = oauth_service.get_zoom_auth_url(redirect_uri, state)
    
    return {"auth_url": auth_url}


@router.get("/zoom/callback")
async def zoom_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> RedirectResponse:
    """Handle Zoom OAuth callback."""
    cookie_name = _oauth_cookie_name("zoom")
    error_response = RedirectResponse(
        f"{settings.FRONTEND_URL}/settings/integrations?error=invalid_state",
        status_code=302,
    )
    error_response.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)

    state_cookie = request.cookies.get(cookie_name)
    if not state_cookie:
        return error_response

    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
    except Exception:
        return error_response

    user_agent = request.headers.get("user-agent", "")
    valid, _ = verify_oauth_state(stored_payload, state, user_agent)
    if not valid:
        return error_response
    
    try:
        # Exchange code for tokens
        redirect_uri = settings.ZOOM_REDIRECT_URI
        tokens = await oauth_service.exchange_zoom_code(code, redirect_uri)
        
        # Get user info
        user_info = await oauth_service.get_zoom_user_info(tokens["access_token"])
        
        # Save integration
        oauth_service.save_integration(
            db,
            session.user_id,
            "zoom",
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_in=tokens.get("expires_in"),
            account_email=user_info.get("email"),
        )

        # Audit log (no secrets)
        from app.db.enums import AuditEventType
        from app.services import audit_service

        integration = oauth_service.get_user_integration(db, session.user_id, "zoom")
        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.INTEGRATION_CONNECTED,
            actor_user_id=session.user_id,
            target_type="user_integration",
            target_id=integration.id if integration else None,
            details={
                "integration_type": "zoom",
                "account_email": audit_service.hash_email(user_info.get("email", "") or ""),
            },
            request=request,
        )
        db.commit()
        
        success = RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?success=zoom",
            status_code=302,
        )
        success.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)
        return success
    except Exception as e:
        error = RedirectResponse(
            f"{settings.FRONTEND_URL}/settings/integrations?error=zoom_failed",
            status_code=302,
        )
        error.delete_cookie(cookie_name, path=OAUTH_STATE_COOKIE_PATH)
        return error


# ============================================================================
# Zoom Meetings
# ============================================================================

class CreateMeetingRequest(BaseModel):
    """Request to create a Zoom meeting."""
    entity_type: str  # "case" or "intended_parent"
    entity_id: uuid.UUID
    topic: str
    start_time: str | None = None  # ISO format datetime
    timezone: str | None = None  # IANA timezone name (e.g. "America/Los_Angeles")
    duration: int = 30  # minutes
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
    - Creates a meeting task
    """
    from datetime import datetime as dt
    from app.db.enums import EntityType
    from app.core.case_access import check_case_access
    from app.services import zoom_service
    from app.services import case_service, ip_service
    
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

    timezone_name = request.timezone or "UTC"
    
    # Validate entity exists and user has access (prevents cross-tenant/task leakage)
    if entity_type == EntityType.CASE:
        case = case_service.get_case(db, session.org_id, request.entity_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    else:
        ip = ip_service.get_intended_parent(db, request.entity_id, session.org_id)
        if not ip:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intended parent not found")

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
            timezone_name=timezone_name,
            duration=request.duration,
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
        "connected_at": integration.created_at.isoformat() if integration and integration.created_at else None,
        "token_expires_at": integration.token_expires_at.isoformat() if integration and integration.token_expires_at else None,
    }


class ZoomMeetingRead(BaseModel):
    """Zoom meeting response for list."""
    id: str
    topic: str
    start_time: str | None
    duration: int
    join_url: str
    case_id: str | None
    intended_parent_id: str | None
    created_at: str


@router.get("/zoom/meetings")
def list_zoom_meetings(
    limit: int = 20,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> list[ZoomMeetingRead]:
    """List user's recently created Zoom meetings."""
    from app.db.models import ZoomMeeting as ZoomMeetingModel
    
    meetings = (
        db.query(ZoomMeetingModel)
        .filter(
            ZoomMeetingModel.organization_id == session.org_id,
            ZoomMeetingModel.user_id == session.user_id,
        )
        .order_by(ZoomMeetingModel.created_at.desc())
        .limit(min(limit, 50))
        .all()
    )
    
    return [
        ZoomMeetingRead(
            id=str(m.id),
            topic=m.topic,
            start_time=m.start_time.isoformat() if m.start_time else None,
            duration=m.duration,
            join_url=m.join_url,
            case_id=str(m.case_id) if m.case_id else None,
            intended_parent_id=str(m.intended_parent_id) if m.intended_parent_id else None,
            created_at=m.created_at.isoformat(),
        )
        for m in meetings
    ]


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
    from app.db.models import Organization, User
    
    # Get host name for template
    user = db.query(User).filter(User.id == session.user_id).first()
    host_name = user.display_name if user else "Your Host"
    
    org = db.query(Organization).filter(Organization.id == session.org_id).first()
    org_timezone = org.timezone if org else "America/Los_Angeles"

    # Build meeting object for template
    meeting = zoom_service.ZoomMeeting(
        id=request.meeting_id,
        uuid="",  # Not needed for email
        topic=request.topic,
        start_time=request.start_time,
        duration=request.duration,
        timezone=org_timezone,
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
