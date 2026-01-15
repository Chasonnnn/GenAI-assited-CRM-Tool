"""Meta Conversions API (CAPI) service.

Sends lead status updates back to Meta to optimize ad targeting.
When a Meta-sourced case advances, we notify Meta with the
appropriate CRM status label so they can learn lead quality.

Enterprise implementation includes:
- Hashed email/phone for better user matching
- Proper conversion event naming
- Event deduplication via event_id
- Flexible status configuration
- Per-ad-account pixel_id configuration
"""

import hashlib
import logging
import time
from typing import TYPE_CHECKING

import httpx

from app.core.config import settings
from app.services.meta_api import compute_appsecret_proof
from app.types import JsonObject

if TYPE_CHECKING:
    from app.db.models import MetaAdAccount

logger = logging.getLogger(__name__)

# CAPI endpoint
CAPI_URL = f"https://graph.facebook.com/{settings.META_API_VERSION}"

# HTTP client settings
HTTPX_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Meta Ads CRM status labels (must match configured labels in Meta)
META_STATUS_INTAKE = "Intake"
META_STATUS_QUALIFIED = "Qualified/Converted"
META_STATUS_DISQUALIFIED = "Not qualified/Lost"
META_STATUS_LOST = "Lost"

# Surrogate status mapping (slug -> Meta status bucket)
META_INTAKE_STATUSES = {
    "contacted",
    "qualified",
    "interview_scheduled",
}
META_CONVERTED_STATUSES = {
    "application_submitted",
    "under_review",
    "approved",
    "ready_to_match",
    "matched",
    "medical_clearance_passed",
    "legal_clearance_passed",
    "transfer_cycle",
    "second_hcg_confirmed",
    "heartbeat_confirmed",
    "ob_care_established",
    "anatomy_scanned",
    "delivered",
}
META_DISQUALIFIED_STATUSES = {"disqualified"}
META_LOST_STATUSES = {"lost"}


def hash_for_capi(value: str) -> str:
    """
    Hash a value for CAPI using SHA256 (Meta's required format).

    Values should be lowercase and trimmed before hashing.
    """
    return hashlib.sha256(value.lower().strip().encode("utf-8")).hexdigest()


async def send_lead_event(
    lead_id: str,
    event_name: str = "Lead",
    user_data: JsonObject | None = None,
    custom_data: JsonObject | None = None,
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
    token = access_token or getattr(settings, "META_CAPI_ACCESS_TOKEN", None)
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
            logger.info(
                f"Meta CAPI: sent {event_name} event for lead {lead_id}, received: {events_received}"
            )
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


def map_surrogate_status_to_meta_status(surrogate_status: str) -> str | None:
    """Map internal case status slug to Meta Ads CRM status label."""
    if not surrogate_status:
        return None
    if surrogate_status in META_LOST_STATUSES:
        return META_STATUS_LOST
    if surrogate_status in META_DISQUALIFIED_STATUSES:
        return META_STATUS_DISQUALIFIED
    if surrogate_status in META_CONVERTED_STATUSES:
        return META_STATUS_QUALIFIED
    if surrogate_status in META_INTAKE_STATUSES:
        return META_STATUS_INTAKE
    return None


def _normalize_event_id_value(value: str) -> str:
    """Normalize text for stable event_id values (ASCII-safe)."""
    return value.lower().replace(" ", "_").replace("/", "_")


async def send_status_event(
    meta_lead_id: str,
    surrogate_status: str,
    meta_status: str,
    email: str | None = None,
    phone: str | None = None,
    access_token: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a lead status update to Meta CAPI.

    Args:
        meta_lead_id: Original Meta leadgen_id
        surrogate_status: The CRM status that triggered this
        meta_status: Meta Ads CRM status label
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
        phone_digits = "".join(c for c in phone if c.isdigit())
        if len(phone_digits) >= 10:
            user_data["ph"] = hash_for_capi(phone_digits)

    # Generate event_id for deduplication
    meta_status_id = _normalize_event_id_value(meta_status)
    event_id = f"capi_{meta_lead_id}_{meta_status_id}"

    return await send_lead_event(
        lead_id=meta_lead_id,
        event_name="Lead",  # Lead status update (Meta reads lead_status)
        user_data=user_data,
        custom_data={
            "lead_status": meta_status,
            "crm_status": surrogate_status,
        },
        access_token=access_token,
        event_id=event_id,
    )


def should_send_capi_event(from_status: str, to_status: str) -> bool:
    """
    Determine if this status change should trigger a CAPI event.

    Triggers on:
    - Any transition into a different Meta status bucket
    """
    from_meta = map_surrogate_status_to_meta_status(from_status)
    to_meta = map_surrogate_status_to_meta_status(to_status)
    if not to_meta:
        return False
    return from_meta != to_meta


# =============================================================================
# Per-Account CAPI Support
# =============================================================================


async def send_lead_event_for_account(
    lead_id: str,
    ad_account: "MetaAdAccount",
    event_name: str = "Lead",
    user_data: JsonObject | None = None,
    custom_data: JsonObject | None = None,
    event_id: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a conversion event using per-account pixel configuration.

    Uses ad_account.pixel_id and ad_account.capi_token_encrypted
    instead of global settings.

    Args:
        lead_id: The original Meta leadgen_id
        ad_account: MetaAdAccount with pixel_id and CAPI token
        event_name: Event type (Lead, CompleteRegistration, etc.)
        user_data: Hashed user identifiers
        custom_data: Additional data (lead_status, value, etc.)
        event_id: Unique event ID for deduplication

    Returns:
        (success, error) tuple
    """
    from app.core.encryption import decrypt_token

    if not ad_account.capi_enabled:
        logger.debug(f"CAPI disabled for ad account {ad_account.ad_account_external_id}")
        return True, None

    if not ad_account.pixel_id:
        logger.warning(f"No pixel_id configured for ad account {ad_account.ad_account_external_id}")
        return False, "No pixel_id configured"

    if settings.META_TEST_MODE:
        logger.info(
            f"[TEST MODE] Would send CAPI event: {event_name} for lead {lead_id} "
            f"to pixel {ad_account.pixel_id}"
        )
        return True, None

    # Get CAPI token
    if ad_account.capi_token_encrypted:
        try:
            token = decrypt_token(ad_account.capi_token_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt CAPI token: {e}")
            return False, "Failed to decrypt CAPI token"
    else:
        # Fall back to global token if available
        token = getattr(settings, "META_CAPI_ACCESS_TOKEN", None)
        if not token:
            logger.warning("No CAPI token available (account or global)")
            return False, "No CAPI token available"

    # Build event payload
    event_time = int(time.time())

    final_user_data = {"lead_id": lead_id}
    if user_data:
        final_user_data.update(user_data)

    event_data = {
        "event_name": event_name,
        "event_time": event_time,
        "action_source": "system_generated",
        "user_data": final_user_data,
    }

    if event_id:
        event_data["event_id"] = event_id

    if custom_data:
        event_data["custom_data"] = custom_data

    payload = {
        "data": [event_data],
        "access_token": token,
    }

    if settings.META_APP_SECRET:
        payload["appsecret_proof"] = compute_appsecret_proof(token)

    url = f"{CAPI_URL}/{ad_account.pixel_id}/events"

    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            resp = await client.post(url, json=payload)

            if resp.status_code != 200:
                error_body = resp.text[:500]
                logger.error(f"Meta CAPI error {resp.status_code}: {error_body}")
                return False, f"CAPI error {resp.status_code}: {error_body}"

            result = resp.json()
            events_received = result.get("events_received", 0)
            logger.info(
                f"Meta CAPI: sent {event_name} to pixel {ad_account.pixel_id} "
                f"for lead {lead_id}, received: {events_received}"
            )
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


async def send_status_event_for_account(
    meta_lead_id: str,
    ad_account: "MetaAdAccount",
    surrogate_status: str,
    meta_status: str,
    email: str | None = None,
    phone: str | None = None,
) -> tuple[bool, str | None]:
    """
    Send a lead status update using per-account configuration.

    Args:
        meta_lead_id: Original Meta leadgen_id
        ad_account: MetaAdAccount with CAPI configuration
        surrogate_status: The CRM status that triggered this
        meta_status: Meta Ads CRM status label
        email: Optional email for hashed matching
        phone: Optional phone for hashed matching
    """
    user_data = {}
    if email and "@" in email and "placeholder" not in email:
        user_data["em"] = hash_for_capi(email)
    if phone:
        phone_digits = "".join(c for c in phone if c.isdigit())
        if len(phone_digits) >= 10:
            user_data["ph"] = hash_for_capi(phone_digits)

    meta_status_id = _normalize_event_id_value(meta_status)
    event_id = f"capi_{meta_lead_id}_{meta_status_id}"

    return await send_lead_event_for_account(
        lead_id=meta_lead_id,
        ad_account=ad_account,
        event_name="Lead",
        user_data=user_data,
        custom_data={
            "lead_status": meta_status,
            "crm_status": surrogate_status,
        },
        event_id=event_id,
    )
