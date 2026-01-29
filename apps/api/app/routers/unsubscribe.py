"""Public unsubscribe endpoints."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.services import campaign_service, unsubscribe_service

router = APIRouter(prefix="/email", tags=["email"])


def _unsubscribe_response(success: bool) -> HTMLResponse:
    title = "Unsubscribed" if success else "Unsubscribe request received"
    body = (
        "<p>You have been unsubscribed from future emails.</p>"
        if success
        else "<p>If this email address exists, it has been unsubscribed.</p>"
    )
    html = f"""
    <html>
      <head><title>{title}</title></head>
      <body style="font-family: sans-serif; padding: 24px;">
        <h2>{title}</h2>
        {body}
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


@router.get("/unsubscribe/{token}")
@limiter.exempt
async def unsubscribe_get(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Process unsubscribe link clicks (one-click and manual)."""
    parsed = unsubscribe_service.parse_unsubscribe_token(token)
    if not parsed:
        return _unsubscribe_response(False)

    org_id, email = parsed
    campaign_service.add_to_suppression(
        db,
        org_id=org_id,
        email=email,
        reason="opt_out",
        source_type="unsubscribe",
    )
    db.commit()
    return _unsubscribe_response(True)


@router.post("/unsubscribe/{token}")
@limiter.exempt
async def unsubscribe_post(
    token: str, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    """Handle List-Unsubscribe-Post one-click requests."""
    _ = await request.body()  # body not required; consumed to avoid warnings
    return await unsubscribe_get(token, db)
