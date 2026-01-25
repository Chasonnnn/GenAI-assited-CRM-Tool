"""Duo MFA service - Web SDK v4 (Universal Prompt) integration.

Provides:
- Duo client initialization
- Auth URL generation for redirect flow
- Callback verification
"""

from typing import Tuple
import logging
import re
from urllib.parse import urlparse
from uuid import UUID

import duo_universal

from app.core.config import settings

logger = logging.getLogger(__name__)

_INVISIBLE_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")


def _strip_invisible(value: str) -> str:
    return "".join(ch for ch in value if ch not in _INVISIBLE_CHARS)


# =============================================================================
# Duo Client
# =============================================================================


def get_duo_client(redirect_uri: str | None = None) -> duo_universal.Client:
    """
    Create a Duo Universal Prompt client.

    Raises:
        ValueError: If Duo is not configured
    """
    if not settings.duo_enabled:
        raise ValueError(
            "Duo MFA is not configured. Set DUO_CLIENT_ID, DUO_CLIENT_SECRET, and DUO_API_HOST."
        )

    # Duo's Python SDK expects strict credential lengths. Secret sources sometimes
    # introduce invisible chars or quotes (e.g. copy/paste), so sanitize gently.
    raw_client_id = _strip_invisible(settings.DUO_CLIENT_ID or "")
    client_id = re.sub(r"[^A-Za-z0-9]", "", raw_client_id)

    client_secret = _strip_invisible(settings.DUO_CLIENT_SECRET or "").strip().strip('"').strip("'")
    host = _strip_invisible(settings.DUO_API_HOST or "").strip().strip('"').strip("'")
    if "://" in host:
        # Allow users to paste "https://api-xxxxx.duosecurity.com" accidentally.
        parsed = urlparse(host)
        host = parsed.hostname or host

    if not (client_id and client_secret and host):
        raise ValueError(
            "Duo MFA is not configured. Set DUO_CLIENT_ID, DUO_CLIENT_SECRET, and DUO_API_HOST."
        )

    client_redirect_uri = (
        _strip_invisible((redirect_uri or settings.DUO_REDIRECT_URI or ""))
        .strip()
        .strip('"')
        .strip("'")
    )
    if not client_redirect_uri:
        raise ValueError("Duo redirect URI is not configured.")

    return duo_universal.Client(
        client_id=client_id,
        client_secret=client_secret,
        host=host,
        redirect_uri=client_redirect_uri,
    )


def health_check() -> Tuple[bool, str]:
    """
    Check Duo API connectivity.

    Returns:
        (is_healthy, message)
    """
    if not settings.duo_enabled:
        return False, "Duo not configured"

    try:
        client = get_duo_client()
        client.health_check()
        return True, "Duo API reachable"
    except Exception as e:
        return False, f"Duo health check failed: {str(e)}"


# =============================================================================
# Auth Flow
# =============================================================================


def create_auth_url(
    user_id: UUID,
    username: str,
    state: str,
    redirect_uri: str | None = None,
) -> str:
    """
    Generate Duo Universal Prompt auth URL.

    Args:
        user_id: Internal user ID (for audit logging)
        username: User's email/username for Duo enrollment
        state: Random state token for CSRF protection

    Returns:
        URL to redirect user to for Duo authentication
    """
    client = get_duo_client(redirect_uri=redirect_uri)

    # The username is used by Duo for enrollment and policy matching
    return client.create_auth_url(username=username, state=state)


def verify_callback(
    code: str,
    state: str,
    expected_state: str,
    username: str,
    redirect_uri: str | None = None,
) -> Tuple[bool, dict | None]:
    """
    Verify the Duo callback and exchange the code for auth result.

    Args:
        code: Authorization code from Duo callback
        state: State returned by Duo
        expected_state: State we originally sent (from session)
        username: Expected username for verification

    Returns:
        (success, auth_result or None)

    The auth_result dict contains:
        - auth_result['sub']: Duo user ID
        - auth_result['preferred_username']: Username
        - auth_result['auth_time']: When authentication occurred
    """
    if state != expected_state:
        return False, None

    try:
        client = get_duo_client(redirect_uri=redirect_uri)
        token = client.exchange_authorization_code_for_2fa_result(
            duoCode=code,
            username=username,
        )
        return True, token
    except Exception as e:
        logger.warning("Duo verification failed: %s", type(e).__name__)
        return False, None


# =============================================================================
# Enrollment Status
# =============================================================================


def is_available() -> bool:
    """Check if Duo integration is available."""
    return settings.duo_enabled
