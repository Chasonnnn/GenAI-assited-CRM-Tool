"""Meta Graph API client for Lead Ads integration.

Handles:
- Webhook signature verification (HMAC-SHA256)
- Lead data fetching with appsecret_proof
- Field data normalization for form variations
- Test mode with mock data
"""

import hmac
import hashlib
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings


# Graph API base URL with version
def _graph_base() -> str:
    return f"https://graph.facebook.com/{settings.META_API_VERSION}"


# HTTP client settings
HTTPX_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verify X-Hub-Signature-256 HMAC signature.

    Args:
        payload: Raw request body bytes
        signature: Value of X-Hub-Signature-256 header

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not signature.startswith("sha256="):
        return False

    if not settings.META_APP_SECRET:
        return False

    expected = hmac.new(
        settings.META_APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


def compute_appsecret_proof(access_token: str) -> str:
    """
    Compute appsecret_proof for secure Graph API calls.

    This is HMAC-SHA256 of the access token with the app secret.
    Required for secure server-to-server API calls.
    """
    if not settings.META_APP_SECRET:
        return ""

    return hmac.new(
        settings.META_APP_SECRET.encode(), access_token.encode(), hashlib.sha256
    ).hexdigest()


async def fetch_lead_details(
    leadgen_id: str,
    access_token: str,
) -> tuple[dict | None, str | None]:
    """
    Fetch lead details from Meta Graph API.

    Args:
        leadgen_id: Meta leadgen ID from webhook
        access_token: Page access token (decrypted)

    Returns:
        (data, error) tuple - data is None if error
    """
    if settings.META_TEST_MODE:
        return _mock_lead_data(leadgen_id), None

    if not access_token:
        return None, "No access token provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{leadgen_id}"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": "id,created_time,field_data,form_id,page_id,ad_id",
    }

    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                error_body = resp.text[:500]
                return None, f"Meta API {resp.status_code}: {error_body}"

            return resp.json(), None

    except httpx.TimeoutException:
        return None, "Meta API timeout"
    except httpx.ConnectError:
        return None, "Meta API connection failed"
    except Exception as e:
        return None, f"Meta API error: {str(e)[:200]}"


def normalize_field_data(field_data_list: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Normalize Meta field_data array to dict with standard keys.

    Handles common field name variations across different forms:
    - phone_number, mobile_phone, phone, cell_phone → phone
    - full_name, name, first_name + last_name → full_name
    - email, email_address → email
    - state, us_state → state
    """
    result: dict[str, Any] = {}

    for field in field_data_list:
        name = field.get("name", "").lower().replace(" ", "_")
        values = field.get("values", [])
        value = values[0] if values else None

        if not value:
            continue

        # Phone variations
        if name in ("phone_number", "mobile_phone", "phone", "cell_phone", "telephone"):
            result["phone"] = value

        # Name handling
        elif name in ("full_name", "name"):
            result["full_name"] = value
        elif name == "first_name":
            result["first_name"] = value
            # Combine if we have both
            if "last_name" in result:
                result["full_name"] = f"{value} {result['last_name']}"
        elif name == "last_name":
            result["last_name"] = value
            if "first_name" in result:
                result["full_name"] = f"{result['first_name']} {value}"

        # Email variations
        elif name in ("email", "email_address", "e-mail"):
            result["email"] = value

        # State variations
        elif name in ("state", "us_state", "province"):
            result["state"] = value

        # Date of birth variations
        elif name in ("date_of_birth", "dob", "birthday", "birth_date"):
            result["date_of_birth"] = value

        # Everything else - keep original key
        else:
            result[name] = value

    return result


def parse_meta_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse Meta's timestamp format to datetime."""
    if not timestamp_str:
        return None

    # Meta uses ISO 8601 format: 2025-12-15T12:00:00+0000
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except ValueError:
            continue

    return None


def _mock_lead_data(leadgen_id: str) -> dict:
    """Return mock data for test mode."""
    return {
        "id": leadgen_id,
        "created_time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+0000"),
        "field_data": [
            {"name": "full_name", "values": [f"Test User {leadgen_id[:8]}"]},
            {"name": "email", "values": [f"test_{leadgen_id[:8]}@example.com"]},
            {"name": "phone_number", "values": ["+15551234567"]},
            {"name": "state", "values": ["CA"]},
        ],
        "form_id": "mock_form_123",
        "page_id": "mock_page_456",
        "ad_id": "mock_ad_789",
    }


async def fetch_ad_account_insights(
    ad_account_id: str,
    access_token: str,
    date_start: str,
    date_end: str,
    level: str = "campaign",
    max_pages: int = 10,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> tuple[list[dict] | None, str | None]:
    """
    Fetch ad insights (spend, impressions, etc.) from Meta Marketing API.

    Args:
        ad_account_id: Meta Ad Account ID (format: act_XXXXX)
        access_token: User/system access token with ads_read permission
        date_start: Start date (YYYY-MM-DD)
        date_end: End date (YYYY-MM-DD)
        level: Breakdown level (campaign, adset, ad)
        max_pages: Maximum number of pages to fetch (default 10)
        time_increment: Time granularity in days (1, 7, 28, etc.)
        breakdowns: Optional breakdown dimensions (region, country, dma, etc.)

    Returns:
        (data, error) tuple - data is list of insight objects
    """
    if settings.META_TEST_MODE:
        return _mock_insights_data(
            date_start,
            date_end,
            time_increment=time_increment,
            breakdowns=breakdowns,
        ), None

    if not access_token:
        return None, "No access token provided"

    if not ad_account_id:
        return None, "No ad account ID provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{ad_account_id}/insights"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": "campaign_id,campaign_name,spend,impressions,reach,clicks,actions",
        "level": level,
        "time_range": f'{{"since":"{date_start}","until":"{date_end}"}}',
        "limit": 100,  # Request max per page
    }
    if time_increment:
        params["time_increment"] = time_increment
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)

    all_data = []
    pages_fetched = 0

    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            while url and pages_fetched < max_pages:
                resp = await client.get(
                    url, params=params if pages_fetched == 0 else None
                )

                if resp.status_code != 200:
                    error_body = resp.text[:500]
                    return None, f"Meta API {resp.status_code}: {error_body}"

                data = resp.json()
                all_data.extend(data.get("data", []))
                pages_fetched += 1

                # Check for next page
                paging = data.get("paging", {})
                url = paging.get("next")
                params = None  # Next page URL includes all params

            return all_data, None

    except httpx.TimeoutException:
        return None, "Meta API timeout"
    except httpx.ConnectError:
        return None, "Meta API connection failed"
    except Exception as e:
        return None, f"Meta API error: {str(e)[:200]}"


def _mock_insights_data(
    date_start: str,
    date_end: str,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> list[dict]:
    """Return mock insights data for test mode."""
    breakdowns = breakdowns or []
    return [
        {
            "campaign_id": "camp_001",
            "campaign_name": "Surrogacy Leads - CA",
            "spend": "1250.50",
            "impressions": "45000",
            "reach": "32000",
            "clicks": "850",
            "actions": [
                {"action_type": "lead", "value": "42"},
                {"action_type": "link_click", "value": "850"},
            ],
            "date_start": date_start,
            "date_stop": date_end,
            **({"region": "California"} if "region" in breakdowns else {}),
            **({"country": "US"} if "country" in breakdowns else {}),
        },
        {
            "campaign_id": "camp_002",
            "campaign_name": "Surrogacy Leads - TX",
            "spend": "980.25",
            "impressions": "38000",
            "reach": "28000",
            "clicks": "620",
            "actions": [
                {"action_type": "lead", "value": "35"},
                {"action_type": "link_click", "value": "620"},
            ],
            "date_start": date_start,
            "date_stop": date_end,
            **({"region": "Texas"} if "region" in breakdowns else {}),
            **({"country": "US"} if "country" in breakdowns else {}),
        },
        {
            "campaign_id": "camp_003",
            "campaign_name": "Surrogacy Leads - FL",
            "spend": "875.00",
            "impressions": "31000",
            "reach": "24000",
            "clicks": "510",
            "actions": [
                {"action_type": "lead", "value": "28"},
                {"action_type": "link_click", "value": "510"},
            ],
            "date_start": date_start,
            "date_stop": date_end,
            **({"region": "Florida"} if "region" in breakdowns else {}),
            **({"country": "US"} if "country" in breakdowns else {}),
        },
    ]
