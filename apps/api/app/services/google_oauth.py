"""Google OAuth and OIDC token verification service."""

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

from app.core.config import settings


class GoogleUserInfo(BaseModel):
    """Verified user info extracted from Google ID token."""

    sub: str  # Google's unique user identifier
    email: str  # Normalized to lowercase
    name: str
    picture: str | None
    hd: str | None  # Hosted domain (Google Workspace)


async def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange authorization code for tokens.

    Args:
        code: Authorization code from Google callback

    Returns:
        Token response containing id_token, access_token, etc.

    Raises:
        httpx.HTTPStatusError: If token exchange fails
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


def verify_id_token(token: str, expected_nonce: str) -> GoogleUserInfo:
    """
    Verify Google ID token using google-auth library.

    The google-auth library handles:
    - JWKS fetching and caching
    - Signature verification
    - Standard claim validation (iss, aud, exp, iat)

    We additionally validate:
    - email_verified: Must be true
    - nonce: Must match expected value (replay protection)

    Args:
        token: The ID token from Google
        expected_nonce: The nonce we sent in the auth request

    Returns:
        GoogleUserInfo with verified user details

    Raises:
        ValueError: If any validation fails
    """
    # google-auth handles JWKS fetching, caching, and signature verification
    idinfo = id_token.verify_oauth2_token(
        token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
    )

    # Validate issuer (google-auth should do this, but be explicit)
    if idinfo.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Invalid issuer")

    # Require verified email
    if not idinfo.get("email_verified"):
        raise ValueError("Email not verified by Google")

    # Validate nonce (replay protection)
    if idinfo.get("nonce") != expected_nonce:
        raise ValueError("Nonce mismatch - possible replay attack")

    return GoogleUserInfo(
        sub=idinfo["sub"],
        email=idinfo["email"].lower(),  # Normalize to lowercase
        name=idinfo.get("name", ""),
        picture=idinfo.get("picture"),
        hd=idinfo.get("hd"),
    )


def validate_email_domain(email: str) -> None:
    """
    Validate email is from an allowed domain.

    Uses email suffix check, does NOT rely solely on 'hd' claim
    (which can be absent for personal Google accounts).

    Args:
        email: The user's email address

    Raises:
        ValueError: If domain not in allowlist
    """
    allowed = settings.allowed_domains_list
    if not allowed:
        return  # No restriction configured

    domain = email.split("@")[1].lower()
    if domain not in allowed:
        raise ValueError(
            f"Email domain '{domain}' not allowed. Allowed: {', '.join(allowed)}"
        )
