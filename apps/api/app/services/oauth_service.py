"""OAuth integration service.

Handles OAuth flows for Gmail, Zoom, and other third-party services.
Stores encrypted tokens per-user.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import UserIntegration

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    """Return True if expires_at is in the past (treat naive datetimes as UTC)."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _now_utc()


# ============================================================================
# Token Encryption
# ============================================================================


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    key = settings.FERNET_KEY
    if not key:
        raise ValueError("FERNET_KEY not configured")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    fernet = _get_fernet()
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted_token.encode()).decode()


# ============================================================================
# Integration CRUD
# ============================================================================


def get_user_integration(
    db: Session, user_id: uuid.UUID, integration_type: str
) -> UserIntegration | None:
    """Get a user's integration by type."""
    return (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == user_id,
            UserIntegration.integration_type == integration_type,
        )
        .first()
    )


def get_user_integrations(db: Session, user_id: uuid.UUID) -> list[UserIntegration]:
    """Get all integrations for a user."""
    return db.query(UserIntegration).filter(UserIntegration.user_id == user_id).all()


def save_integration(
    db: Session,
    user_id: uuid.UUID,
    integration_type: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    account_email: str | None = None,
) -> UserIntegration:
    """Save or update a user's integration tokens."""
    integration = get_user_integration(db, user_id, integration_type)

    token_expires_at = None
    if expires_in:
        token_expires_at = _now_utc() + timedelta(seconds=expires_in)

    if integration:
        integration.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            integration.refresh_token_encrypted = encrypt_token(refresh_token)
        integration.token_expires_at = token_expires_at
        if account_email:
            integration.account_email = account_email
        integration.updated_at = _now_utc()
    else:
        integration = UserIntegration(
            user_id=user_id,
            integration_type=integration_type,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token)
            if refresh_token
            else None,
            token_expires_at=token_expires_at,
            account_email=account_email,
        )
        db.add(integration)

    db.commit()
    db.refresh(integration)
    return integration


def delete_integration(db: Session, user_id: uuid.UUID, integration_type: str) -> bool:
    """Delete a user's integration."""
    integration = get_user_integration(db, user_id, integration_type)
    if integration:
        db.delete(integration)
        db.commit()
        return True
    return False


def get_access_token(
    db: Session, user_id: uuid.UUID, integration_type: str
) -> str | None:
    """Get decrypted access token, refreshing if expired."""
    integration = get_user_integration(db, user_id, integration_type)
    if not integration:
        return None

    # Check if token is expired and needs refresh
    if integration.token_expires_at and _is_expired(integration.token_expires_at):
        if integration.refresh_token_encrypted:
            # Try to refresh
            refreshed = refresh_token(db, integration, integration_type)
            if not refreshed:
                return None

    return decrypt_token(integration.access_token_encrypted)


# ============================================================================
# Gmail OAuth
# ============================================================================

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_gmail_auth_url(redirect_uri: str, state: str) -> str:
    """Generate Gmail OAuth authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GMAIL_AUTH_URL}?{urlencode(params)}"


async def exchange_gmail_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GMAIL_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_gmail_user_info(access_token: str) -> dict[str, Any]:
    """Get user info from Google."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GMAIL_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def refresh_gmail_token(refresh_token: str) -> dict[str, Any] | None:
    """Refresh Gmail access token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GMAIL_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Gmail token refresh failed: {e}")
        return None


# ============================================================================
# Zoom OAuth
# ============================================================================

ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_USER_URL = "https://api.zoom.us/v2/users/me"


def get_zoom_auth_url(redirect_uri: str, state: str) -> str:
    """Generate Zoom OAuth authorization URL."""
    params = {
        "client_id": settings.ZOOM_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    return f"{ZOOM_AUTH_URL}?{urlencode(params)}"


async def exchange_zoom_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange Zoom authorization code for tokens."""
    import base64

    credentials = base64.b64encode(
        f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            ZOOM_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_zoom_user_info(access_token: str) -> dict[str, Any]:
    """Get user info from Zoom."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            ZOOM_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def refresh_zoom_token(refresh_token: str) -> dict[str, Any] | None:
    """Refresh Zoom access token."""
    import base64

    try:
        credentials = base64.b64encode(
            f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                ZOOM_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Zoom token refresh failed: {e}")
        return None


# ============================================================================
# Generic Refresh
# ============================================================================


def refresh_token(
    db: Session, integration: UserIntegration, integration_type: str
) -> bool:
    """Refresh an expired token. Returns True if successful.

    Note: This function creates a new event loop if needed, or uses an existing one.
    """
    import asyncio

    if not integration.refresh_token_encrypted:
        return False

    refresh = decrypt_token(integration.refresh_token_encrypted)

    async def do_refresh():
        if integration_type == "gmail":
            return await refresh_gmail_token(refresh)
        elif integration_type == "zoom":
            return await refresh_zoom_token(refresh)
        return None

    try:
        # Check if we're in an existing event loop
        try:
            asyncio.get_running_loop()
            # We're in an async context - create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, do_refresh()).result()
        except RuntimeError:
            # No event loop running - safe to use asyncio.run
            result = asyncio.run(do_refresh())

        if not result:
            return False

        # Update tokens
        integration.access_token_encrypted = encrypt_token(result["access_token"])
        if "refresh_token" in result:
            integration.refresh_token_encrypted = encrypt_token(result["refresh_token"])
        if "expires_in" in result:
            integration.token_expires_at = _now_utc() + timedelta(
                seconds=result["expires_in"]
            )
        integration.updated_at = _now_utc()
        db.commit()

        return True
    except Exception as e:
        logger.error(f"Token refresh failed for {integration_type}: {e}")
        return False
