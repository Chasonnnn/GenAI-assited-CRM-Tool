"""Authenticate the platform's Gmail Pub/Sub subscription before mailbox lookup."""

import jwt
from fastapi import HTTPException, Request

from app.core.config import settings

# Fixed Google endpoint: never take a key URL from an untrusted JWT header.
# The client bounds network calls, caches JWKS, and rate-limits unknown-key refreshes.
_google_keys = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=5)


def require_gmail_push(request: Request) -> None:
    """Sync dependency: certificate I/O and signature verification run off the event loop."""
    audience = settings.GMAIL_PUSH_AUDIENCE.strip()
    service_account = settings.GMAIL_PUSH_SERVICE_ACCOUNT_EMAIL.strip()
    if not audience or not service_account or not settings.GMAIL_PUSH_SUBSCRIPTION.strip():
        raise HTTPException(status_code=503, detail="Gmail push is not configured")

    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail="Invalid Gmail push authentication")

    try:
        key = _google_keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=["https://accounts.google.com", "accounts.google.com"],
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "email", "email_verified"],
                "strict_aud": True,
            },
        )
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="Gmail push verification unavailable") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid Gmail push authentication") from None

    if claims["email"] != service_account or claims["email_verified"] is not True:
        raise HTTPException(status_code=403, detail="Gmail push sender not allowed")
