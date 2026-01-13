"""Meta Graph API client for Lead Ads integration.

Handles:
- Webhook signature verification (HMAC-SHA256)
- Lead data fetching with appsecret_proof
- Field data normalization for form variations
- Test mode with mock data
"""

import hmac
import hashlib
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.types import JsonObject


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
) -> tuple[JsonObject | None, str | None]:
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


def normalize_field_data(field_data_list: list[JsonObject]) -> JsonObject:
    """
    Normalize Meta field_data array to dict with standard keys.

    Handles common field name variations across different forms:
    - phone_number, mobile_phone, phone, cell_phone → phone
    - full_name, name, first_name + last_name → full_name
    - email, email_address → email
    - state, us_state → state
    """
    result: JsonObject = {}

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


def _mock_lead_data(leadgen_id: str) -> JsonObject:
    """Return mock data for test mode."""
    return {
        "id": leadgen_id,
        "created_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
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
) -> tuple[list[JsonObject] | None, str | None]:
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
) -> list[JsonObject]:
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


# =============================================================================
# Field Data Processing
# =============================================================================


def extract_field_data_raw(field_data_list: list[JsonObject]) -> JsonObject:
    """
    Extract field_data preserving multi-select arrays.

    Returns dict with values as arrays when multiple values present.
    Used for field_data_raw storage and form analysis.
    """
    result: JsonObject = {}
    for field in field_data_list:
        name = field.get("name", "").lower().replace(" ", "_")
        values = field.get("values", [])
        # Preserve array if multiple values, else single value
        result[name] = values if len(values) > 1 else (values[0] if values else None)
    return result


# =============================================================================
# Hierarchy Fetch Functions (Campaigns, AdSets, Ads)
# =============================================================================


async def fetch_campaigns(
    ad_account_id: str,
    access_token: str,
    updated_since: datetime | None = None,
    fields: str = "id,name,objective,status,updated_time",
    max_pages: int = 50,
) -> tuple[list[JsonObject] | None, str | None]:
    """
    Fetch campaigns from Meta Marketing API.

    Args:
        ad_account_id: Meta Ad Account ID (format: act_XXXXX)
        access_token: System access token with ads_read permission
        updated_since: Only fetch campaigns updated after this time (delta sync)
        fields: Fields to retrieve
        max_pages: Maximum number of pages to fetch

    Returns:
        (data, error) tuple - data is list of campaign objects
    """
    if settings.META_TEST_MODE:
        return _mock_campaigns_data(), None

    if not access_token:
        return None, "No access token provided"

    if not ad_account_id:
        return None, "No ad account ID provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{ad_account_id}/campaigns"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": fields,
        "limit": 100,
    }
    if updated_since:
        # Use filtering for delta sync
        params["filtering"] = (
            f'[{{"field":"updated_time","operator":"GREATER_THAN",'
            f'"value":"{int(updated_since.timestamp())}"}}]'
        )

    return await _fetch_paginated(url, params, max_pages)


async def fetch_adsets(
    ad_account_id: str,
    access_token: str,
    updated_since: datetime | None = None,
    fields: str = "id,name,campaign_id,targeting,status,updated_time",
    max_pages: int = 50,
) -> tuple[list[JsonObject] | None, str | None]:
    """
    Fetch ad sets from Meta Marketing API.

    Args:
        ad_account_id: Meta Ad Account ID
        access_token: System access token
        updated_since: Only fetch adsets updated after this time (delta sync)
        fields: Fields to retrieve
        max_pages: Maximum number of pages to fetch

    Returns:
        (data, error) tuple - data is list of adset objects
    """
    if settings.META_TEST_MODE:
        return _mock_adsets_data(), None

    if not access_token:
        return None, "No access token provided"

    if not ad_account_id:
        return None, "No ad account ID provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{ad_account_id}/adsets"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": fields,
        "limit": 100,
    }
    if updated_since:
        params["filtering"] = (
            f'[{{"field":"updated_time","operator":"GREATER_THAN",'
            f'"value":"{int(updated_since.timestamp())}"}}]'
        )

    return await _fetch_paginated(url, params, max_pages)


async def fetch_ads(
    ad_account_id: str,
    access_token: str,
    updated_since: datetime | None = None,
    fields: str = "id,name,adset_id,campaign_id,status,updated_time",
    max_pages: int = 100,
) -> tuple[list[JsonObject] | None, str | None]:
    """
    Fetch ads from Meta Marketing API.

    Args:
        ad_account_id: Meta Ad Account ID
        access_token: System access token
        updated_since: Only fetch ads updated after this time (delta sync)
        fields: Fields to retrieve
        max_pages: Maximum number of pages to fetch

    Returns:
        (data, error) tuple - data is list of ad objects
    """
    if settings.META_TEST_MODE:
        return _mock_ads_data(), None

    if not access_token:
        return None, "No access token provided"

    if not ad_account_id:
        return None, "No ad account ID provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{ad_account_id}/ads"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": fields,
        "limit": 100,
    }
    if updated_since:
        params["filtering"] = (
            f'[{{"field":"updated_time","operator":"GREATER_THAN",'
            f'"value":"{int(updated_since.timestamp())}"}}]'
        )

    return await _fetch_paginated(url, params, max_pages)


async def fetch_page_leadgen_forms(
    page_id: str,
    access_token: str,
    fields: str = "id,name,questions",
    max_pages: int = 20,
) -> tuple[list[JsonObject] | None, str | None]:
    """
    Fetch lead gen forms from a Meta Page.

    NOTE: This uses PAGE access tokens, not ad account tokens.
    Ad accounts don't have permission to access page leadgen_forms.

    Args:
        page_id: Meta Page ID
        access_token: Page access token (NOT ad account token)
        fields: Fields to retrieve
        max_pages: Maximum number of pages to fetch

    Returns:
        (data, error) tuple - data is list of form objects
    """
    if settings.META_TEST_MODE:
        return _mock_forms_data(page_id), None

    if not access_token:
        return None, "No access token provided"

    if not page_id:
        return None, "No page ID provided"

    proof = compute_appsecret_proof(access_token)
    url = f"{_graph_base()}/{page_id}/leadgen_forms"
    params = {
        "access_token": access_token,
        "appsecret_proof": proof,
        "fields": fields,
        "limit": 50,
    }

    return await _fetch_paginated(url, params, max_pages)


async def _fetch_paginated(
    url: str,
    params: dict,
    max_pages: int,
) -> tuple[list[JsonObject] | None, str | None]:
    """Generic paginated fetch helper."""
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


# =============================================================================
# Mock Data for Test Mode
# =============================================================================


def _mock_campaigns_data() -> list[JsonObject]:
    """Return mock campaigns for test mode."""
    return [
        {
            "id": "camp_001",
            "name": "Surrogacy Leads - California",
            "objective": "LEAD_GENERATION",
            "status": "ACTIVE",
            "updated_time": "2026-01-10T12:00:00+0000",
        },
        {
            "id": "camp_002",
            "name": "Surrogacy Leads - Texas",
            "objective": "LEAD_GENERATION",
            "status": "ACTIVE",
            "updated_time": "2026-01-10T12:00:00+0000",
        },
        {
            "id": "camp_003",
            "name": "Surrogacy Awareness",
            "objective": "REACH",
            "status": "PAUSED",
            "updated_time": "2026-01-05T12:00:00+0000",
        },
    ]


def _mock_adsets_data() -> list[JsonObject]:
    """Return mock adsets for test mode."""
    return [
        {
            "id": "adset_001",
            "name": "CA - Women 25-35",
            "campaign_id": "camp_001",
            "status": "ACTIVE",
            "targeting": {"geo_locations": {"regions": [{"key": "CA"}]}},
            "updated_time": "2026-01-10T12:00:00+0000",
        },
        {
            "id": "adset_002",
            "name": "TX - Women 25-35",
            "campaign_id": "camp_002",
            "status": "ACTIVE",
            "targeting": {"geo_locations": {"regions": [{"key": "TX"}]}},
            "updated_time": "2026-01-10T12:00:00+0000",
        },
    ]


def _mock_ads_data() -> list[JsonObject]:
    """Return mock ads for test mode."""
    return [
        {
            "id": "ad_001",
            "name": "CA Lead Ad - Video",
            "adset_id": "adset_001",
            "campaign_id": "camp_001",
            "status": "ACTIVE",
            "updated_time": "2026-01-10T12:00:00+0000",
        },
        {
            "id": "ad_002",
            "name": "CA Lead Ad - Image",
            "adset_id": "adset_001",
            "campaign_id": "camp_001",
            "status": "ACTIVE",
            "updated_time": "2026-01-10T12:00:00+0000",
        },
        {
            "id": "ad_003",
            "name": "TX Lead Ad - Video",
            "adset_id": "adset_002",
            "campaign_id": "camp_002",
            "status": "ACTIVE",
            "updated_time": "2026-01-10T12:00:00+0000",
        },
    ]


def _mock_forms_data(page_id: str) -> list[JsonObject]:
    """Return mock forms for test mode."""
    return [
        {
            "id": "form_001",
            "name": "Surrogacy Application - Standard",
            "questions": [
                {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
                {"key": "email", "type": "EMAIL", "label": "Email"},
                {"key": "phone_number", "type": "PHONE", "label": "Phone"},
                {"key": "state", "type": "CUSTOM", "label": "State of Residence"},
            ],
        },
        {
            "id": "form_002",
            "name": "Surrogacy Application - Extended",
            "questions": [
                {"key": "full_name", "type": "FULL_NAME", "label": "Full Name"},
                {"key": "email", "type": "EMAIL", "label": "Email"},
                {"key": "phone_number", "type": "PHONE", "label": "Phone"},
                {"key": "date_of_birth", "type": "DATE_OF_BIRTH", "label": "DOB"},
                {"key": "state", "type": "CUSTOM", "label": "State of Residence"},
                {"key": "has_child", "type": "CUSTOM", "label": "Have you given birth?"},
            ],
        },
    ]
