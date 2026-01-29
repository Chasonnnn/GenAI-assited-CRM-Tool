"""Meta OAuth router for Facebook Login for Business.

Handles OAuth connect/callback flow and connection-scoped asset management.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.encryption import encrypt_token
from app.core.policies import POLICIES
from app.core.security import (
    create_oauth_state_payload,
    generate_oauth_nonce,
    generate_oauth_state,
    parse_oauth_state_payload,
    verify_oauth_state,
)
from app.db.enums import AuditEventType
from app.db.models import MetaAdAccount, MetaOAuthConnection, MetaPageMapping
from app.schemas.auth import UserSession
from app.services import (
    audit_service,
    meta_admin_service,
    meta_oauth_service,
    meta_page_service,
    org_service,
)

router = APIRouter(
    prefix="/integrations/meta",
    tags=["integrations"],
)

logger = logging.getLogger(__name__)

OAUTH_STATE_MAX_AGE = 300  # 5 minutes
OAUTH_STATE_COOKIE_NAME = "meta_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/integrations/meta"


# =============================================================================
# Schemas
# =============================================================================


class MetaOAuthConnectResponse(BaseModel):
    """Response with OAuth URL."""

    auth_url: str


class MetaOAuthConnectionRead(BaseModel):
    """OAuth connection for display."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    meta_user_id: str
    meta_user_name: str | None
    granted_scopes: list[str]
    is_active: bool
    last_validated_at: str | None
    last_error: str | None
    last_error_at: str | None
    last_error_code: str | None
    token_expires_at: str | None
    created_at: str
    updated_at: str


class MetaConnectionsListResponse(BaseModel):
    """List of OAuth connections."""

    connections: list[MetaOAuthConnectionRead]


class AdAccountOption(BaseModel):
    """Ad account available for connection."""

    id: str
    name: str | None
    business_name: str | None = None
    is_connected: bool
    connected_by_meta_user: str | None = None
    connected_by_connection_id: UUID | None = None


class PageOption(BaseModel):
    """Page available for connection."""

    id: str
    name: str | None
    is_connected: bool
    connected_by_meta_user: str | None = None
    connected_by_connection_id: UUID | None = None


class AvailableAssetsResponse(BaseModel):
    """Assets available for a connection."""

    ad_accounts: list[AdAccountOption]
    pages: list[PageOption]
    next_cursor: str | None = None


class ConnectAssetsRequest(BaseModel):
    """Request to connect assets to an OAuth connection."""

    ad_account_ids: list[str] = Field(default_factory=list)
    page_ids: list[str] = Field(default_factory=list)
    overwrite_existing: bool = False


class ConnectAssetsResponse(BaseModel):
    """Response from connecting assets."""

    ad_accounts: list[str]
    pages: list[str]
    overwrites: list[dict[str, Any]]


class DisconnectResponse(BaseModel):
    """Response from disconnecting."""

    success: bool
    unlinked: int


# =============================================================================
# OAuth Connect/Callback
# =============================================================================


@router.get(
    "/connect",
    response_model=MetaOAuthConnectResponse,
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)
def meta_connect(
    request: Request,
    response: Response,
    session: UserSession = Depends(get_current_session),
) -> MetaOAuthConnectResponse:
    """
    Get Meta OAuth authorization URL.

    Frontend should redirect user to this URL to start the OAuth flow.
    Sets a state cookie for CSRF protection.
    """
    if not settings.META_APP_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta integration not configured. Set META_APP_ID.",
        )

    if not settings.META_OAUTH_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta OAuth redirect URI not configured.",
        )

    state = generate_oauth_state()
    nonce = generate_oauth_nonce()
    user_agent = request.headers.get("user-agent", "")
    state_payload = create_oauth_state_payload(state, nonce, user_agent)

    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state_payload,
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path=OAUTH_STATE_COOKIE_PATH,
    )

    auth_url = meta_oauth_service.get_oauth_url(state)
    return MetaOAuthConnectResponse(auth_url=auth_url)


@router.get("/callback")
async def meta_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> RedirectResponse:
    """
    Handle Meta OAuth callback.

    Validates state, exchanges code for token, validates scopes, saves connection.
    Redirects to asset selection on success.
    """
    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)

    def error_redirect(error: str, detail: str | None = None) -> RedirectResponse:
        url = f"{base_url}/settings/integrations/meta?error={error}"
        if detail:
            url += f"&detail={detail}"
        resp = RedirectResponse(url, status_code=302)
        resp.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)
        return resp

    # Validate state cookie
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    if not state_cookie:
        logger.warning(f"Meta OAuth callback missing state cookie for user={session.user_id}")
        return error_redirect("invalid_state")

    try:
        stored_payload = parse_oauth_state_payload(state_cookie)
    except Exception as e:
        logger.warning(f"Meta OAuth state parse failed: {e}")
        return error_redirect("invalid_state")

    user_agent = request.headers.get("user-agent", "")
    valid, _ = verify_oauth_state(stored_payload, state, user_agent)
    if not valid:
        logger.warning(f"Meta OAuth state validation failed for user={session.user_id}")
        return error_redirect("invalid_state")

    try:
        # Exchange code for short-lived token
        token_response = await meta_oauth_service.exchange_code_for_token(code)
        short_token = token_response.get("access_token")
        if not short_token:
            logger.error("Meta OAuth token exchange returned no access_token")
            return error_redirect("token_exchange_failed")

        # Exchange for long-lived token
        long_token_response = await meta_oauth_service.exchange_for_long_lived_token(short_token)
        access_token = long_token_response.get("access_token")
        expires_in = long_token_response.get("expires_in")

        if not access_token:
            logger.error("Meta OAuth long-lived token exchange returned no access_token")
            return error_redirect("token_exchange_failed")

        # Get user info
        user_info = await meta_oauth_service.get_user_info(access_token)
        meta_user_id = user_info.get("id")
        meta_user_name = user_info.get("name")

        if not meta_user_id:
            logger.error("Meta OAuth user info returned no id")
            return error_redirect("user_info_failed")

        # Debug token to get granted scopes
        granted_scopes = await meta_oauth_service.debug_token(access_token)

        # HARD FAIL if required scopes missing
        valid_scopes, missing_scopes = meta_oauth_service.validate_required_scopes(granted_scopes)
        if not valid_scopes:
            logger.warning(f"Meta OAuth missing required scopes: {missing_scopes}")
            return error_redirect("missing_scopes", ",".join(missing_scopes))

        # Save or update connection
        connection = meta_oauth_service.save_oauth_connection(
            db=db,
            org_id=session.org_id,
            meta_user_id=meta_user_id,
            meta_user_name=meta_user_name,
            access_token=access_token,
            expires_in=expires_in,
            granted_scopes=granted_scopes,
            connected_by_user_id=session.user_id,
        )

        # Audit log
        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.INTEGRATION_CONNECTED,
            actor_user_id=session.user_id,
            target_type="meta_oauth_connection",
            target_id=connection.id,
            details={
                "integration_type": "meta",
                "meta_user_id": meta_user_id,
                "granted_scopes": granted_scopes,
            },
            request=request,
        )
        db.commit()

        # Redirect to asset selection for this connection
        success = RedirectResponse(
            f"{base_url}/settings/integrations/meta?step=select-assets&connection={connection.id}",
            status_code=302,
        )
        success.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=OAUTH_STATE_COOKIE_PATH)
        return success

    except Exception as e:
        logger.exception(f"Meta OAuth callback failed for user={session.user_id}: {e}")
        return error_redirect("oauth_failed")


# =============================================================================
# Connection Management
# =============================================================================


@router.get(
    "/connections",
    response_model=MetaConnectionsListResponse,
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)
def list_connections(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MetaConnectionsListResponse:
    """List all Meta OAuth connections for the organization."""
    connections = meta_oauth_service.get_oauth_connections(db, session.org_id)

    return MetaConnectionsListResponse(
        connections=[
            MetaOAuthConnectionRead(
                id=c.id,
                meta_user_id=c.meta_user_id,
                meta_user_name=c.meta_user_name,
                granted_scopes=c.granted_scopes or [],
                is_active=c.is_active,
                last_validated_at=c.last_validated_at.isoformat() if c.last_validated_at else None,
                last_error=c.last_error,
                last_error_at=c.last_error_at.isoformat() if c.last_error_at else None,
                last_error_code=c.last_error_code,
                token_expires_at=c.token_expires_at.isoformat() if c.token_expires_at else None,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
            )
            for c in connections
        ]
    )


@router.get(
    "/connections/{connection_id}",
    response_model=MetaOAuthConnectionRead,
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)
def get_connection(
    connection_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> MetaOAuthConnectionRead:
    """Get a specific OAuth connection."""
    connection = meta_oauth_service.get_oauth_connection(db, connection_id, session.org_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    return MetaOAuthConnectionRead(
        id=connection.id,
        meta_user_id=connection.meta_user_id,
        meta_user_name=connection.meta_user_name,
        granted_scopes=connection.granted_scopes or [],
        is_active=connection.is_active,
        last_validated_at=connection.last_validated_at.isoformat()
        if connection.last_validated_at
        else None,
        last_error=connection.last_error,
        last_error_at=connection.last_error_at.isoformat() if connection.last_error_at else None,
        last_error_code=connection.last_error_code,
        token_expires_at=connection.token_expires_at.isoformat()
        if connection.token_expires_at
        else None,
        created_at=connection.created_at.isoformat(),
        updated_at=connection.updated_at.isoformat(),
    )


@router.delete(
    "/connections/{connection_id}",
    response_model=DisconnectResponse,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["meta_leads"].default)),
    ],
)
def disconnect_connection(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> DisconnectResponse:
    """
    Disconnect a Meta OAuth connection.

    Unlinks all assets and deactivates the connection.
    Unlinked assets will skip sync silently (not log errors).
    """
    connection = meta_oauth_service.get_oauth_connection(db, connection_id, session.org_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Unlink ad accounts - they become tokenless
    unlinked_accounts = (
        db.execute(
            update(MetaAdAccount)
            .where(MetaAdAccount.oauth_connection_id == connection_id)
            .values(oauth_connection_id=None)
            .returning(MetaAdAccount.id)
        )
        .scalars()
        .all()
    )

    # Unlink pages
    unlinked_pages = (
        db.execute(
            update(MetaPageMapping)
            .where(MetaPageMapping.oauth_connection_id == connection_id)
            .values(oauth_connection_id=None)
            .returning(MetaPageMapping.id)
        )
        .scalars()
        .all()
    )

    # Deactivate connection (preserve for history)
    meta_oauth_service.deactivate_oauth_connection(db, connection)

    # Audit log
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.INTEGRATION_DISCONNECTED,
        actor_user_id=session.user_id,
        target_type="meta_oauth_connection",
        target_id=connection.id,
        details={
            "unlinked_ad_accounts": len(unlinked_accounts),
            "unlinked_pages": len(unlinked_pages),
        },
        request=request,
    )
    db.commit()

    return DisconnectResponse(
        success=True,
        unlinked=len(unlinked_accounts) + len(unlinked_pages),
    )


# =============================================================================
# Connection-Scoped Asset Management
# =============================================================================


@router.get(
    "/connections/{connection_id}/available-assets",
    response_model=AvailableAssetsResponse,
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)
async def list_available_assets(
    connection_id: UUID,
    cursor: str | None = Query(None, description="Pagination cursor"),
    search: str | None = Query(None, description="Search filter for asset names"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> AvailableAssetsResponse:
    """
    List assets available for a specific OAuth connection.

    Returns ad accounts and pages accessible by the connected Meta user.
    Indicates which assets are already connected and by whom.
    """
    connection = meta_oauth_service.get_oauth_connection(db, connection_id, session.org_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    if not connection.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is not active",
        )

    token = meta_oauth_service.get_decrypted_token(connection)

    # Fetch ad accounts from Meta
    ad_accounts_result = await meta_oauth_service.fetch_user_ad_accounts(token, cursor)

    # Fetch pages from Meta
    pages_result = await meta_oauth_service.fetch_user_pages(token, cursor)

    # Get existing assets to show ownership
    existing_accounts = {
        a.ad_account_external_id: a for a in meta_admin_service.list_ad_accounts(db, session.org_id)
    }
    existing_pages = {p.page_id: p for p in meta_page_service.list_meta_pages(db, session.org_id)}

    # Helper to get connection owner name
    def get_owner_name(asset) -> str | None:
        if not asset or not asset.oauth_connection_id:
            return None
        conn = db.get(MetaOAuthConnection, asset.oauth_connection_id)
        return conn.meta_user_name if conn else None

    # Build ad account options
    ad_account_options = []
    for a in ad_accounts_result.data:
        account_id = a.get("id", "")
        name = a.get("name", "")

        # Apply search filter
        if search and search.lower() not in (name or "").lower():
            continue

        existing = existing_accounts.get(account_id)
        ad_account_options.append(
            AdAccountOption(
                id=account_id,
                name=name,
                business_name=a.get("business_name"),
                is_connected=existing is not None,
                connected_by_meta_user=get_owner_name(existing),
                connected_by_connection_id=existing.oauth_connection_id if existing else None,
            )
        )

    # Build page options
    page_options = []
    for p in pages_result.data:
        page_id = p.get("id", "")
        name = p.get("name", "")

        # Apply search filter
        if search and search.lower() not in (name or "").lower():
            continue

        existing = existing_pages.get(page_id)
        page_options.append(
            PageOption(
                id=page_id,
                name=name,
                is_connected=existing is not None,
                connected_by_meta_user=get_owner_name(existing),
                connected_by_connection_id=existing.oauth_connection_id if existing else None,
            )
        )

    return AvailableAssetsResponse(
        ad_accounts=ad_account_options,
        pages=page_options,
        next_cursor=ad_accounts_result.next_cursor or pages_result.next_cursor,
    )


@router.post(
    "/connections/{connection_id}/connect-assets",
    response_model=ConnectAssetsResponse,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["meta_leads"].default)),
    ],
)
async def connect_assets(
    connection_id: UUID,
    data: ConnectAssetsRequest,
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> ConnectAssetsResponse:
    """
    Connect assets using a specific OAuth connection.

    Creates or updates ad accounts and pages to use the connection's token.
    Auto-subscribes pages to leadgen webhooks.
    """
    connection = meta_oauth_service.get_oauth_connection(db, connection_id, session.org_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    if not connection.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is not active",
        )

    token = meta_oauth_service.get_decrypted_token(connection)

    results: dict[str, Any] = {"ad_accounts": [], "pages": [], "overwrites": []}

    # Connect ad accounts
    for account_id in data.ad_account_ids:
        existing = meta_admin_service.get_ad_account_by_external_id(db, session.org_id, account_id)

        if existing and existing.oauth_connection_id != connection.id:
            if not data.overwrite_existing:
                old_conn = db.get(MetaOAuthConnection, existing.oauth_connection_id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Asset {account_id} is connected by {old_conn.meta_user_name if old_conn else 'another user'}",
                )

            # Log overwrite
            old_conn = db.get(MetaOAuthConnection, existing.oauth_connection_id)
            results["overwrites"].append(
                {
                    "asset_id": account_id,
                    "asset_type": "ad_account",
                    "previous_user": old_conn.meta_user_name if old_conn else "unknown",
                }
            )

        if existing:
            # Update existing account
            existing.oauth_connection_id = connection.id
        else:
            # Create new ad account
            meta_admin_service.create_ad_account(
                db=db,
                org_id=session.org_id,
                ad_account_external_id=account_id,
                oauth_connection_id=connection.id,
            )

        results["ad_accounts"].append(account_id)

    # Connect pages with webhook subscription
    # Fetch page tokens from /me/accounts (need page token for webhook)
    pages_response = await meta_oauth_service.fetch_user_pages(token)
    page_tokens = {p["id"]: p.get("access_token") for p in pages_response.data}

    for page_id in data.page_ids:
        page_token = page_tokens.get(page_id)
        if not page_token:
            logger.warning(f"No page token for {page_id}, skipping webhook subscription")

        # Auto-subscribe to leadgen webhook (idempotent)
        if page_token:
            try:
                await meta_oauth_service.subscribe_page_to_leadgen(page_token, page_id)
            except Exception as e:
                logger.warning(f"Webhook subscription failed for {page_id}: {e}")
                # Continue - page still linked, webhook can be retried

        # Get page name from response
        page_info = next((p for p in pages_response.data if p.get("id") == page_id), {})
        page_name = page_info.get("name")

        # Create/update mapping
        existing = meta_page_service.get_mapping_by_page_id(db, session.org_id, page_id)
        encrypted_page_token = encrypt_token(page_token) if page_token else None

        if existing:
            if existing.oauth_connection_id != connection.id:
                if not data.overwrite_existing:
                    old_conn = db.get(MetaOAuthConnection, existing.oauth_connection_id)
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Page {page_id} is connected by {old_conn.meta_user_name if old_conn else 'another user'}",
                    )

                old_conn = db.get(MetaOAuthConnection, existing.oauth_connection_id)
                results["overwrites"].append(
                    {
                        "asset_id": page_id,
                        "asset_type": "page",
                        "previous_user": old_conn.meta_user_name if old_conn else "unknown",
                    }
                )

            existing.oauth_connection_id = connection.id
            if page_name:
                existing.page_name = page_name
            if encrypted_page_token:
                existing.access_token_encrypted = encrypted_page_token
        else:
            # Create new page mapping
            new_page = MetaPageMapping(
                organization_id=session.org_id,
                page_id=page_id,
                page_name=page_name,
                oauth_connection_id=connection.id,
                access_token_encrypted=encrypted_page_token,
                is_active=True,
            )
            db.add(new_page)

        results["pages"].append(page_id)

    # Audit log with details
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.META_ASSETS_CONNECTED,
        actor_user_id=session.user_id,
        target_type="meta_oauth_connection",
        target_id=connection.id,
        details={
            "ad_accounts": results["ad_accounts"],
            "pages": results["pages"],
            "overwrites": results["overwrites"],
        },
        request=request,
    )

    db.commit()

    return ConnectAssetsResponse(
        ad_accounts=results["ad_accounts"],
        pages=results["pages"],
        overwrites=results["overwrites"],
    )
