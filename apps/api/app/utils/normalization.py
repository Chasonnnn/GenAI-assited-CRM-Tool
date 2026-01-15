"""Data normalization utilities for consistent data quality."""

import re
from typing import Optional


# =============================================================================
# US States (including DC and territories)
# =============================================================================

US_STATES = {
    # Full names to codes
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    # DC and territories
    "district of columbia": "DC",
    "washington dc": "DC",
    "dc": "DC",
    "puerto rico": "PR",
    "guam": "GU",
    "virgin islands": "VI",
    "american samoa": "AS",
    "northern mariana islands": "MP",
    # Common variations
    "cali": "CA",
    "ny": "NY",
    "tx": "TX",
    "fla": "FL",
    "penn": "PA",
}

# Valid 2-letter codes
VALID_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
    "PR",
    "GU",
    "VI",
    "AS",
    "MP",
}


def normalize_state(state: Optional[str]) -> Optional[str]:
    """
    Normalize state input to 2-letter uppercase code.

    Args:
        state: Raw state input (can be full name, abbreviation, or variation)

    Returns:
        2-letter state code or None if empty

    Raises:
        ValueError: If state is not a recognized US state
    """
    if not state:
        return None

    normalized = state.strip().lower()

    # Try mapping first (handles full names and variations)
    if normalized in US_STATES:
        return US_STATES[normalized]

    # Try as 2-letter code
    upper = normalized.upper()
    if upper in VALID_STATE_CODES:
        return upper

    raise ValueError(
        f"Invalid state '{state}'. Use 2-letter code (e.g., CA) or full name (e.g., California)."
    )


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone to E.164 format (+15551234567).

    Accepts:
    - 10 digits: 5551234567 → +15551234567
    - 11 digits starting with 1: 15551234567 → +15551234567
    - Already E.164: +15551234567 → +15551234567

    Args:
        phone: Raw phone input

    Returns:
        E.164 formatted phone or None if empty

    Raises:
        ValueError: If phone is not a valid US phone number
    """
    if not phone:
        return None

    # Strip all non-digits except leading +
    cleaned = phone.strip()
    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned[1:])
        if digits.startswith("1") and len(digits) == 11:
            return f"+{digits}"
    else:
        digits = re.sub(r"\D", "", cleaned)

    # Validate and format
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"

    raise ValueError(f"Invalid phone number '{phone}'. Use 10-digit US format (e.g., 5551234567).")


def normalize_email(email: Optional[str]) -> Optional[str]:
    """
    Normalize email to lowercase.

    Args:
        email: Raw email input

    Returns:
        Lowercased email or None if empty
    """
    if not email:
        return None
    return email.strip().lower()


def normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize name by stripping whitespace and collapsing multiple spaces.

    Args:
        name: Raw name input

    Returns:
        Cleaned name or None if empty
    """
    if not name:
        return None
    # Strip leading/trailing whitespace and collapse internal spaces
    return " ".join(name.split())
