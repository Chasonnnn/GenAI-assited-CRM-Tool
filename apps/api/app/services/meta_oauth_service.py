"""Meta OAuth service for Facebook Login for Business.

Handles:
- OAuth token exchange (code → short-lived → long-lived)
- User profile and scope fetching
- Paginated asset discovery (ad accounts, pages)
- Page webhook subscription
- Scope validation (hard fail on missing required scopes)
- MetaOAuthConnection CRUD
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.db.models import MetaOAuthConnection
from app.services.meta_api import compute_appsecret_proof

logger = logging.getLogger(__name__)


# Graph API base URL with version
def _graph_base() -> str:
    return f"https://graph.facebook.com/{settings.META_API_VERSION}"


# HTTP client settings
HTTPX_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# OAuth URLs
META_OAUTH_URL = f"https://www.facebook.com/{settings.META_API_VERSION}/dialog/oauth"
META_TOKEN_URL = f"{_graph_base()}/oauth/access_token"

# Required scopes - HARD FAIL if any missing
REQUIRED_SCOPES = {
    "ads_management",
    "ads_read",
    "leads_retrieval",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_ads",
    "pages_manage_metadata",
}

# All scopes to request
OAUTH_SCOPES = [
    "ads_management",
    "ads_read",
    "leads_retrieval",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_ads",
    "pages_manage_metadata",
]


@dataclass
class PaginatedResult:
    """Result with pagination cursor."""

    data: list[dict]
    next_cursor: str | None


# =============================================================================
# OAuth URL Generation
# =============================================================================


def get_oauth_url(state: str) -> str:
    """
    Generate Meta OAuth authorization URL.

    Args:
        state: CSRF state token to validate callback

    Returns:
        Authorization URL to redirect user to
    """
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_OAUTH_REDIRECT_URI,
        "state": state,
        "scope": ",".join(OAUTH_SCOPES),
        "response_type": "code",
    }
    return f"{META_OAUTH_URL}?{urlencode(params)}"


# =============================================================================
# Token Exchange
# =============================================================================


async def exchange_code_for_token(code: str) -> dict:
    """
    Exchange authorization code for short-lived access token.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Token response containing access_token, token_type, expires_in

    Raises:
        httpx.HTTPStatusError: If token exchange fails
    """
    params = {
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "redirect_uri": settings.META_OAUTH_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(META_TOKEN_URL, params=params)
        response.raise_for_status()
        return response.json()


async def exchange_for_long_lived_token(short_token: str) -> dict:
    """
    Exchange short-lived token for long-lived token (60 days).

    Args:
        short_token: Short-lived access token

    Returns:
        Token response containing access_token, token_type, expires_in

    Raises:
        httpx.HTTPStatusError: If token exchange fails
    """
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "fb_exchange_token": short_token,
    }

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(META_TOKEN_URL, params=params)
        response.raise_for_status()
        return response.json()


# =============================================================================
# User Info & Token Debug
# =============================================================================


async def get_user_info(token: str) -> dict:
    """
    Fetch Meta user profile.

    Args:
        token: Access token

    Returns:
        User info with id and name (no email - Facebook doesn't expose it by default)
    """
    proof = compute_appsecret_proof(token)
    url = f"{_graph_base()}/me"
    params = {
        "access_token": token,
        "appsecret_proof": proof,
        "fields": "id,name",
    }

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def debug_token(token: str) -> list[str]:
    """
    Debug token to get granted scopes.

    Args:
        token: Access token to debug

    Returns:
        List of granted scope strings
    """
    url = f"{_graph_base()}/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{settings.META_APP_ID}|{settings.META_APP_SECRET}",
    }

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("scopes", [])


# =============================================================================
# Scope Validation
# =============================================================================


def validate_required_scopes(granted: list[str]) -> tuple[bool, list[str]]:
    """
    Validate that all required scopes were granted.

    Args:
        granted: List of granted scope strings

    Returns:
        (valid, missing_scopes) - valid is True if all required scopes present
    """
    granted_set = set(granted)
    missing = list(REQUIRED_SCOPES - granted_set)
    return len(missing) == 0, missing


# =============================================================================
# Asset Discovery (Paginated)
# =============================================================================


async def fetch_user_ad_accounts(token: str, cursor: str | None = None) -> PaginatedResult:
    """
    Fetch ad accounts accessible by the authenticated user.

    Args:
        token: User access token
        cursor: Pagination cursor (after parameter)

    Returns:
        PaginatedResult with ad accounts and next cursor
    """
    proof = compute_appsecret_proof(token)
    url = f"{_graph_base()}/me/adaccounts"
    params = {
        "access_token": token,
        "appsecret_proof": proof,
        "fields": "id,name,account_status,business_name",
        "limit": 100,
    }
    if cursor:
        params["after"] = cursor

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        next_cursor = None
        paging = data.get("paging", {})
        if "cursors" in paging:
            next_cursor = paging["cursors"].get("after")

        return PaginatedResult(
            data=data.get("data", []),
            next_cursor=next_cursor,
        )


async def fetch_user_pages(token: str, cursor: str | None = None) -> PaginatedResult:
    """
    Fetch pages managed by the authenticated user.

    The response includes page-specific access tokens in each page object.

    Args:
        token: User access token
        cursor: Pagination cursor (after parameter)

    Returns:
        PaginatedResult with pages and next cursor
    """
    proof = compute_appsecret_proof(token)
    url = f"{_graph_base()}/me/accounts"
    params = {
        "access_token": token,
        "appsecret_proof": proof,
        "fields": "id,name,access_token,tasks",
        "limit": 100,
    }
    if cursor:
        params["after"] = cursor

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        next_cursor = None
        paging = data.get("paging", {})
        if "cursors" in paging:
            next_cursor = paging["cursors"].get("after")

        return PaginatedResult(
            data=data.get("data", []),
            next_cursor=next_cursor,
        )


# =============================================================================
# Webhook Subscription
# =============================================================================


async def subscribe_page_to_leadgen(page_token: str, page_id: str) -> bool:
    """
    Subscribe a page to leadgen webhooks.

    Uses the PAGE TOKEN (not user token) for subscription.
    This is idempotent - handles already-subscribed gracefully.

    Args:
        page_token: Page-specific access token (from /me/accounts response)
        page_id: Meta page ID

    Returns:
        True if subscription succeeded or already exists

    Raises:
        httpx.HTTPStatusError: If subscription fails
    """
    proof = compute_appsecret_proof(page_token)
    url = f"{_graph_base()}/{page_id}/subscribed_apps"
    params = {
        "access_token": page_token,
        "appsecret_proof": proof,
        "subscribed_fields": "leadgen",
    }

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.post(url, params=params)

        # Handle already-subscribed case (returns success)
        if response.status_code == 200:
            data = response.json()
            return data.get("success", False)

        # Log error but don't raise for non-critical failures
        logger.warning(
            f"Webhook subscription for page {page_id} returned {response.status_code}: "
            f"{response.text[:200]}"
        )
        return False


# =============================================================================
# Connection CRUD
# =============================================================================


def get_oauth_connections(db: Session, org_id: UUID) -> list[MetaOAuthConnection]:
    """Get all OAuth connections for an organization."""
    return (
        db.query(MetaOAuthConnection)
        .filter(MetaOAuthConnection.organization_id == org_id)
        .order_by(MetaOAuthConnection.created_at.desc())
        .all()
    )


def get_active_oauth_connections(db: Session, org_id: UUID) -> list[MetaOAuthConnection]:
    """Get active OAuth connections for an organization."""
    return (
        db.query(MetaOAuthConnection)
        .filter(
            MetaOAuthConnection.organization_id == org_id,
            MetaOAuthConnection.is_active.is_(True),
        )
        .order_by(MetaOAuthConnection.created_at.desc())
        .all()
    )


def list_active_oauth_connections_any_org(db: Session) -> list[MetaOAuthConnection]:
    """List active OAuth connections across all organizations."""
    return (
        db.query(MetaOAuthConnection)
        .filter(MetaOAuthConnection.is_active.is_(True))
        .order_by(MetaOAuthConnection.created_at.desc())
        .all()
    )


def get_oauth_connection(
    db: Session, connection_id: UUID, org_id: UUID
) -> MetaOAuthConnection | None:
    """Get a specific OAuth connection scoped to org."""
    return (
        db.query(MetaOAuthConnection)
        .filter(
            MetaOAuthConnection.id == connection_id,
            MetaOAuthConnection.organization_id == org_id,
        )
        .first()
    )


def get_oauth_connection_by_id(
    db: Session, connection_id: UUID
) -> MetaOAuthConnection | None:
    """Get OAuth connection by ID (no org scoping)."""
    return db.get(MetaOAuthConnection, connection_id)


def get_oauth_connection_by_meta_user(
    db: Session, org_id: UUID, meta_user_id: str
) -> MetaOAuthConnection | None:
    """Get OAuth connection by Meta user ID."""
    return (
        db.query(MetaOAuthConnection)
        .filter(
            MetaOAuthConnection.organization_id == org_id,
            MetaOAuthConnection.meta_user_id == meta_user_id,
        )
        .first()
    )


def save_oauth_connection(
    db: Session,
    org_id: UUID,
    meta_user_id: str,
    meta_user_name: str | None,
    access_token: str,
    expires_in: int | None,
    granted_scopes: list[str],
    connected_by_user_id: UUID,
) -> MetaOAuthConnection:
    """
    Save or update an OAuth connection.

    If a connection for this org+meta_user already exists, update it.
    Otherwise create a new one.
    """
    now = datetime.now(timezone.utc)
    token_expires_at = None
    if expires_in:
        token_expires_at = now + timedelta(seconds=expires_in)

    # Check for existing connection
    existing = get_oauth_connection_by_meta_user(db, org_id, meta_user_id)

    if existing:
        # Update existing connection
        existing.access_token_encrypted = encrypt_token(access_token)
        existing.token_expires_at = token_expires_at
        existing.granted_scopes = granted_scopes
        existing.meta_user_name = meta_user_name
        existing.is_active = True
        existing.last_error = None
        existing.last_error_at = None
        existing.last_error_code = None
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing

    # Create new connection
    connection = MetaOAuthConnection(
        organization_id=org_id,
        meta_user_id=meta_user_id,
        meta_user_name=meta_user_name,
        access_token_encrypted=encrypt_token(access_token),
        token_expires_at=token_expires_at,
        granted_scopes=granted_scopes,
        connected_by_user_id=connected_by_user_id,
        is_active=True,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def deactivate_oauth_connection(db: Session, connection: MetaOAuthConnection) -> None:
    """Deactivate an OAuth connection (soft delete)."""
    connection.is_active = False
    connection.updated_at = datetime.now(timezone.utc)
    db.commit()


def get_decrypted_token(connection: MetaOAuthConnection) -> str:
    """Get decrypted access token from connection."""
    return decrypt_token(connection.access_token_encrypted)
