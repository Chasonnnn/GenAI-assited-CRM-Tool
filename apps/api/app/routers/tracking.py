"""
Email Tracking Router.

Public endpoints for recording email opens and link clicks.
These endpoints must be unauthenticated since they're called from email clients.
"""

import logging
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.services import tracking_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["tracking"])


# 1x1 transparent GIF (base64 decoded)
TRANSPARENT_GIF = bytes(
    [
        0x47,
        0x49,
        0x46,
        0x38,
        0x39,
        0x61,
        0x01,
        0x00,
        0x01,
        0x00,
        0x80,
        0x00,
        0x00,
        0xFF,
        0xFF,
        0xFF,
        0x00,
        0x00,
        0x00,
        0x21,
        0xF9,
        0x04,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x2C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0x02,
        0x02,
        0x44,
        0x01,
        0x00,
        0x3B,
    ]
)


@router.get("/open/{token}")
async def track_open(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """
    Record an email open event and return a 1x1 transparent GIF.

    Called when email client loads the tracking pixel.
    """
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Record the open (best effort, don't fail on errors)
    try:
        tracking_service.record_open(
            db=db,
            token=token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.warning(f"Failed to record open for token {token}: {e}")

    # Always return the tracking pixel
    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/click/{token}")
async def track_click(
    token: str,
    url: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """
    Record a link click event and redirect to the original URL.

    Called when user clicks a tracked link in the email.
    """
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Record the click and get original URL
    try:
        original_url = tracking_service.record_click(
            db=db,
            token=token,
            url=url,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as e:
        logger.warning(f"Failed to record click for token {token}: {e}")
        original_url = None

    # Redirect to original URL (or fallback if not found)
    if original_url:
        return RedirectResponse(url=original_url, status_code=302)
    else:
        # Token not found - still try to redirect using the provided URL
        from urllib.parse import unquote

        return RedirectResponse(url=unquote(url), status_code=302)
