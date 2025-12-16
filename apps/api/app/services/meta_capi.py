"""Meta Conversions API (CAPI) service.

Sends lead quality signals back to Meta to optimize ad targeting.
When a case reaches "qualified" status, we notify Meta so they can
train their algorithm on what high-quality leads look like.
"""

import hashlib
import logging
import time
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.services.meta_api import compute_appsecret_proof

logger = logging.getLogger(__name__)

# CAPI endpoint
CAPI_URL = f"https://graph.facebook.com/{settings.META_API_VERSION}"

# HTTP client settings  
HTTPX_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def send_lead_event(
    lead_id: str,
    event_name: str = "Lead",
    custom_data: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a conversion event to Meta CAPI.
    
    Args:
        lead_id: The original Meta leadgen_id
        event_name: Event type (Lead, QualifiedLead, etc.)
        custom_data: Additional data (lead_status, etc.)
        access_token: Page access token (will use system token if not provided)
        
    Returns:
        (success, error) tuple
    """
    if not settings.META_CAPI_ENABLED:
        logger.debug("Meta CAPI disabled, skipping event")
        return True, None
    
    if not settings.META_PIXEL_ID:
        return False, "META_PIXEL_ID not configured"
    
    if settings.META_TEST_MODE:
        logger.info(f"[TEST MODE] Would send CAPI event: {event_name} for lead {lead_id}")
        return True, None
    
    # Use provided token or try to get system access token
    token = access_token
    if not token:
        # In production, you'd want a system user access token
        # For now, we'll require it to be passed in
        return False, "No access token provided for CAPI"
    
    # Build event payload
    event_time = int(time.time())
    
    event_data = {
        "event_name": event_name,
        "event_time": event_time,
        "action_source": "system_generated",
        "user_data": {
            "lead_id": lead_id,
        },
    }
    
    if custom_data:
        event_data["custom_data"] = custom_data
    
    payload = {
        "data": [event_data],
        "access_token": token,
    }
    
    # Add appsecret_proof for security
    if settings.META_APP_SECRET:
        payload["appsecret_proof"] = compute_appsecret_proof(token)
    
    url = f"{CAPI_URL}/{settings.META_PIXEL_ID}/events"
    
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            
            if resp.status_code != 200:
                error_body = resp.text[:500]
                logger.error(f"Meta CAPI error {resp.status_code}: {error_body}")
                return False, f"CAPI error {resp.status_code}: {error_body}"
            
            result = resp.json()
            events_received = result.get("events_received", 0)
            logger.info(f"Meta CAPI: sent {event_name} event for lead {lead_id}, received: {events_received}")
            return True, None
            
    except httpx.TimeoutException:
        return False, "Meta CAPI timeout"
    except httpx.ConnectError:
        return False, "Meta CAPI connection failed"
    except Exception as e:
        return False, f"Meta CAPI error: {str(e)[:200]}"


async def send_qualified_event(
    meta_lead_id: str,
    case_status: str,
    access_token: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a qualified lead event to Meta CAPI.
    
    Called when a Meta-sourced case reaches qualified status.
    """
    return await send_lead_event(
        lead_id=meta_lead_id,
        event_name="Lead",  # Standard Lead event with qualified status
        custom_data={
            "lead_status": "qualified",
            "crm_status": case_status,
        },
        access_token=access_token,
    )


def should_send_capi_event(from_status: str, to_status: str) -> bool:
    """
    Determine if this status change should trigger a CAPI event.
    
    Currently triggers on:
    - Any transition TO qualified status
    - approved → qualified progression
    """
    qualified_statuses = {"qualified", "approved"}
    
    # Trigger when entering qualified-like statuses from non-qualified
    if to_status in qualified_statuses and from_status not in qualified_statuses:
        return True
    
    return False
