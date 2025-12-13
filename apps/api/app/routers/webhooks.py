"""Webhooks router - external service integrations."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db

router = APIRouter()


# Meta webhook verification token (set in app config)
# In production, this would be per-org and stored in DB
META_VERIFY_TOKEN = getattr(settings, "META_VERIFY_TOKEN", "")


@router.get("/meta")
async def verify_meta_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification endpoint.
    
    When you configure the webhook in Meta, it sends a GET request
    with a challenge that must be echoed back.
    """
    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return int(challenge) if challenge else ""
    
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta")
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Meta Lead Ads webhook.
    
    NOTE: This is a skeleton. Full implementation requires:
    1. Signature verification (X-Hub-Signature header)
    2. Page-to-org mapping
    3. Lead data retrieval via Meta API
    
    For now, we just acknowledge receipt.
    """
    # Get raw body for signature verification (future)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Log receipt (in production: process asynchronously)
    # TODO: Implement full Meta Lead Ads processing:
    # 1. Verify signature using app secret
    # 2. Extract leadgen_id from webhook payload
    # 3. Call Meta API to get lead details
    # 4. Map page_id to organization
    # 5. Store in meta_leads table
    # 6. Optionally auto-convert to case
    
    # For now, just acknowledge
    return {"status": "received", "object": body.get("object")}


# =============================================================================
# Future: Manual conversion endpoint
# =============================================================================

# @router.post("/meta-leads/{meta_lead_id}/convert")
# async def convert_meta_lead(...):
#     """Manually convert a Meta lead to a case."""
#     pass
