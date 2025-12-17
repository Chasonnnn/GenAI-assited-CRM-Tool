"""User integrations router.

Handles per-user OAuth flows for Gmail, Zoom, etc.
Each user connects their own accounts.
"""
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_session, require_csrf_header
from app.schemas.auth import UserSession
from app.services import oauth_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])


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
