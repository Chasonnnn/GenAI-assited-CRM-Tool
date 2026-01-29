"""Centralized token resolution for Meta services.

Provides a single point for getting tokens for ad accounts and pages,
with error classification and health tracking.

Error Categories:
- AUTH: Token invalid/expired, needs reauth
- RATE_LIMIT: Retry later, don't reauth
- TRANSIENT: Network/API outage, retry
- PERMISSION: Lead Access Manager issue
- UNKNOWN: Unclassified error
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.encryption import decrypt_token
from app.db.models import MetaAdAccount, MetaOAuthConnection, MetaPageMapping

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Classification of Meta API errors."""

    AUTH = "auth"  # Token invalid, needs reauth
    RATE_LIMIT = "rate_limit"  # Retry later, don't reauth
    TRANSIENT = "transient"  # Network/API outage, retry
    PERMISSION = "permission"  # Lead Access Manager, etc.
    UNKNOWN = "unknown"


@dataclass
class TokenResult:
    """Result of token resolution."""

    token: str | None
    connection_id: UUID | None
    needs_reauth: bool


def classify_meta_error(error: Exception) -> ErrorCategory:
    """
    Classify Meta API errors for appropriate handling.

    Uses error codes from Meta Graph API:
    - 190: Invalid OAuth access token
    - 102: Session expired/invalidated
    - 80004: Rate limit hit
    - 10: Permission denied
    - 1, 2: API Unknown, Service unavailable

    Args:
        error: Exception from Meta API call

    Returns:
        ErrorCategory for the error
    """
    error_str = str(error).lower()

    # Try to extract error code from exception
    error_code = getattr(error, "code", None)

    # If no code attribute, try to parse from string
    if error_code is None:
        if "error_code" in error_str:
            # Try to extract code from JSON-like error message
            import re

            match = re.search(r'"code":\s*(\d+)', error_str)
            if match:
                error_code = int(match.group(1))

    # Classify by error code
    if error_code in (190, 102, 463):
        # 190: Invalid token
        # 102: Session expired
        # 463: Session has expired or is invalid
        return ErrorCategory.AUTH

    if error_code == 80004 or "rate" in error_str or "limit" in error_str:
        return ErrorCategory.RATE_LIMIT

    if error_code == 10 or "permission" in error_str:
        return ErrorCategory.PERMISSION

    if error_code in (1, 2) or "service" in error_str or "temporarily" in error_str:
        return ErrorCategory.TRANSIENT

    # Check error message patterns
    if "invalid" in error_str and "token" in error_str:
        return ErrorCategory.AUTH

    if "expired" in error_str:
        return ErrorCategory.AUTH

    return ErrorCategory.UNKNOWN


# =============================================================================
# Token Resolution
# =============================================================================


def get_token_for_ad_account(db: Session, account: MetaAdAccount) -> TokenResult:
    """
    Get access token for ad account operations.

    Priority:
    1. OAuth connection token (if linked)

    Args:
        db: Database session
        account: MetaAdAccount to get token for

    Returns:
        TokenResult with token and metadata
    """
    # Try OAuth connection first
    if account.oauth_connection_id:
        conn = db.get(MetaOAuthConnection, account.oauth_connection_id)
        if conn and conn.is_active:
            try:
                token = decrypt_token(conn.access_token_encrypted)
                # Only AUTH errors need reauth, not rate limits or transient
                needs_reauth = conn.last_error_code == ErrorCategory.AUTH.value
                return TokenResult(
                    token=token,
                    connection_id=conn.id,
                    needs_reauth=needs_reauth,
                )
            except Exception as e:
                logger.warning(f"Failed to decrypt OAuth token for account {account.id}: {e}")
                return TokenResult(
                    token=None,
                    connection_id=conn.id,
                    needs_reauth=True,
                )

    # No token available
    return TokenResult(
        token=None,
        connection_id=None,
        needs_reauth=True,
    )


def get_token_for_page(db: Session, page: MetaPageMapping) -> TokenResult:
    """
    Get access token for page operations.

    Priority:
    1. Page access token (stored from OAuth)
    2. OAuth connection token fallback (if needed)

    Args:
        db: Database session
        page: MetaPageMapping to get token for

    Returns:
        TokenResult with token and metadata
    """
    # Prefer page token (needed for leadgen/forms APIs)
    if page.access_token_encrypted:
        try:
            token = decrypt_token(page.access_token_encrypted)
            return TokenResult(
                token=token,
                connection_id=None,
                needs_reauth=False,
            )
        except Exception as e:
            logger.warning(f"Failed to decrypt page token for page {page.id}: {e}")

    # Fallback to OAuth connection token (for non-page endpoints)
    if page.oauth_connection_id:
        conn = db.get(MetaOAuthConnection, page.oauth_connection_id)
        if conn and conn.is_active:
            try:
                token = decrypt_token(conn.access_token_encrypted)
                needs_reauth = conn.last_error_code == ErrorCategory.AUTH.value
                return TokenResult(
                    token=token,
                    connection_id=conn.id,
                    needs_reauth=needs_reauth,
                )
            except Exception as e:
                logger.warning(f"Failed to decrypt OAuth token for page {page.id}: {e}")
                return TokenResult(
                    token=None,
                    connection_id=conn.id,
                    needs_reauth=True,
                )

    # No token available
    return TokenResult(
        token=None,
        connection_id=None,
        needs_reauth=True,
    )


def get_capi_token_for_account(db: Session, account: MetaAdAccount) -> TokenResult:
    """
    Get CAPI token for sending conversion events.

    Priority:
    1. OAuth connection token (if linked)

    Args:
        db: Database session
        account: MetaAdAccount to get CAPI token for

    Returns:
        TokenResult with token and metadata
    """
    # Try OAuth connection first - CAPI uses same token
    if account.oauth_connection_id:
        conn = db.get(MetaOAuthConnection, account.oauth_connection_id)
        if conn and conn.is_active:
            try:
                token = decrypt_token(conn.access_token_encrypted)
                needs_reauth = conn.last_error_code == ErrorCategory.AUTH.value
                return TokenResult(
                    token=token,
                    connection_id=conn.id,
                    needs_reauth=needs_reauth,
                )
            except Exception as e:
                logger.warning(f"Failed to decrypt OAuth token for CAPI: {e}")
            return TokenResult(
                token=None,
                connection_id=conn.id if conn else None,
                needs_reauth=True,
            )

    # No token available
    return TokenResult(
        token=None,
        connection_id=None,
        needs_reauth=True,
    )


# =============================================================================
# Health Tracking
# =============================================================================


def mark_token_valid(db: Session, connection_id: UUID) -> None:
    """
    Update connection health after successful API call.

    Clears any previous error state.

    Args:
        db: Database session
        connection_id: ID of the OAuth connection
    """
    conn = db.get(MetaOAuthConnection, connection_id)
    if conn:
        now = datetime.now(timezone.utc)
        conn.last_validated_at = now
        # Clear error state on success
        if conn.last_error:
            conn.last_error = None
            conn.last_error_at = None
            conn.last_error_code = None
        conn.updated_at = now
        db.commit()


def mark_token_error(db: Session, connection_id: UUID, error: Exception) -> ErrorCategory:
    """
    Update connection health after API error.

    Classifies the error and records it for UI display and alerting.

    Args:
        db: Database session
        connection_id: ID of the OAuth connection
        error: The exception that occurred

    Returns:
        The classified error category
    """
    category = classify_meta_error(error)
    conn = db.get(MetaOAuthConnection, connection_id)
    if conn:
        now = datetime.now(timezone.utc)
        conn.last_error = str(error)[:1000]  # Truncate long errors
        conn.last_error_at = now
        conn.last_error_code = category.value
        conn.updated_at = now
        db.commit()
    return category


def get_connection_health_status(connection: MetaOAuthConnection) -> str:
    """
    Get human-readable health status for a connection.

    Args:
        connection: OAuth connection to check

    Returns:
        Status string: "healthy", "needs_reauth", "rate_limited", "error"
    """
    if not connection.last_error:
        return "healthy"

    if connection.last_error_code == ErrorCategory.AUTH.value:
        return "needs_reauth"

    if connection.last_error_code == ErrorCategory.RATE_LIMIT.value:
        return "rate_limited"

    if connection.last_error_code == ErrorCategory.PERMISSION.value:
        return "permission_error"

    return "error"
