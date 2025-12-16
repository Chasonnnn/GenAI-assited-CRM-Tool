"""Meta Conversions API (CAPI) service.

Sends lead quality signals back to Meta to optimize ad targeting.
When a case reaches "approved" status, we notify Meta so they can
train their algorithm on what high-quality leads look like.

Enterprise implementation includes:
- Hashed email/phone for better user matching
- Proper conversion event naming
- Event deduplication via event_id
- Flexible status configuration
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

# Statuses that trigger CAPI conversion events
# "qualified" = applicant confirmed as high-quality lead
# "approved" = full approval (also triggers if auto-transition is removed)
CAPI_TRIGGER_STATUSES = {"qualified", "approved"}


def hash_for_capi(value: str) -> str:
    """
    Hash a value for CAPI using SHA256 (Meta's required format).
    
    Values should be lowercase and trimmed before hashing.
    """
    return hashlib.sha256(value.lower().strip().encode('utf-8')).hexdigest()


async def send_lead_event(
    lead_id: str,
    event_name: str = "Lead",
    user_data: dict[str, Any] | None = None,
    custom_data: dict[str, Any] | None = None,
    access_token: str | None = None,
    event_id: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a conversion event to Meta CAPI.
    
    Args:
        lead_id: The original Meta leadgen_id
        event_name: Event type (Lead, CompleteRegistration, etc.)
        user_data: Hashed user identifiers (em, ph, lead_id, etc.)
        custom_data: Additional data (lead_status, value, etc.)
        access_token: CAPI access token
        event_id: Unique event ID for deduplication
        
    Returns:
        (success, error) tuple
    """
    if not settings.META_CAPI_ENABLED:
        logger.debug("Meta CAPI disabled, skipping event")
        return True, None
    
    if not settings.META_PIXEL_ID:
        logger.warning("Meta CAPI: META_PIXEL_ID not configured")
        return False, "META_PIXEL_ID not configured"
    
    if settings.META_TEST_MODE:
        logger.info(f"[TEST MODE] Would send CAPI event: {event_name} for lead {lead_id}")
        return True, None
    
    # Use provided token or system token from config
    token = access_token or getattr(settings, 'META_CAPI_ACCESS_TOKEN', None)
    if not token:
        logger.warning("Meta CAPI: No access token available")
        return False, "No access token provided for CAPI"
    
    # Build event payload
    event_time = int(time.time())
    
    # User data with lead_id (and optionally hashed identifiers)
    final_user_data = {"lead_id": lead_id}
    if user_data:
        final_user_data.update(user_data)
    
    event_data = {
        "event_name": event_name,
        "event_time": event_time,
        "action_source": "system_generated",
        "user_data": final_user_data,
    }
    
    # Add event_id for deduplication
    if event_id:
        event_data["event_id"] = event_id
    
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
        logger.error(f"Meta CAPI timeout for lead {lead_id}")
        return False, "Meta CAPI timeout"
    except httpx.ConnectError:
        logger.error(f"Meta CAPI connection failed for lead {lead_id}")
        return False, "Meta CAPI connection failed"
    except Exception as e:
        logger.error(f"Meta CAPI error for lead {lead_id}: {e}")
        return False, f"Meta CAPI error: {str(e)[:200]}"


async def send_qualified_event(
    meta_lead_id: str,
    case_status: str,
    email: str | None = None,
    phone: str | None = None,
    access_token: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a qualified lead event to Meta CAPI.
    
    Called when a Meta-sourced case reaches approved/qualified status.
    
    Args:
        meta_lead_id: Original Meta leadgen_id
        case_status: The CRM status that triggered this
        email: Optional email for hashed matching
        phone: Optional phone for hashed matching
        access_token: CAPI access token
    """
    # Build user_data with hashed identifiers for better matching
    user_data = {}
    if email and "@" in email and "placeholder" not in email:
        user_data["em"] = hash_for_capi(email)
    if phone:
        # Remove non-digits and hash
        phone_digits = ''.join(c for c in phone if c.isdigit())
        if len(phone_digits) >= 10:
            user_data["ph"] = hash_for_capi(phone_digits)
    
    # Generate event_id for deduplication
    event_id = f"capi_{meta_lead_id}_{case_status}_{int(time.time())}"
    
    return await send_lead_event(
        lead_id=meta_lead_id,
        event_name="Lead",  # Standard Lead event with qualified status
        user_data=user_data,
        custom_data={
            "lead_status": "qualified",
            "crm_status": case_status,
        },
        access_token=access_token,
        event_id=event_id,
    )


def should_send_capi_event(from_status: str, to_status: str) -> bool:
    """
    Determine if this status change should trigger a CAPI event.
    
    Triggers on:
    - Any transition TO approved status (before auto-transition)
    - Or directly to pending_handoff from non-qualified status
    """
    # Only trigger when entering a qualified-like status for the first time
    if to_status in CAPI_TRIGGER_STATUSES and from_status not in CAPI_TRIGGER_STATUSES:
        return True
    
    return False
