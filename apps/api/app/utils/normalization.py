"""Data normalization utilities for consistent data quality."""

import re
import unicodedata
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

MASS_EDIT_RACE_FILTER_KEYS: tuple[str, ...] = (
    "american_indian_or_alaska_native",
    "asian",
    "black_or_african_american",
    "hispanic_or_latino",
    "native_hawaiian_or_other_pacific_islander",
    "white",
    "other_please_specify",
)

RACE_KEY_ALIASES = {
    "american_indian_alaska_native": "american_indian_or_alaska_native",
    "black_african_american": "black_or_african_american",
    "native_hawaiian_or_pacific_islander": "native_hawaiian_or_other_pacific_islander",
    "native_hawaiian_or_other_pacific_islanders": "native_hawaiian_or_other_pacific_islander",
    "other": "other_please_specify",
    "other_please_specified": "other_please_specify",
}

RACE_LABEL_OVERRIDES = {
    "american_indian_or_alaska_native": "American Indian or Alaska Native",
    "asian": "Asian",
    "black_or_african_american": "Black or African American",
    "hispanic_or_latino": "Hispanic or Latino",
    "native_hawaiian_or_other_pacific_islander": "Native Hawaiian or Other Pacific Islander",
    "white": "White",
    "other_please_specify": "Other (please specify)",
    "not_hispanic_or_latino": "Not Hispanic or Latino",
}

LOWERCASE_TITLE_WORDS = {"or", "and", "of", "the", "a", "an", "in", "on", "to", "for"}


def format_race_label(race: Optional[str]) -> Optional[str]:
    """Normalize race labels for display without mutating stored values."""
    if not race:
        return None
    trimmed = race.strip()
    if not trimmed:
        return None

    normalized_key = normalize_race_key(trimmed)
    if not normalized_key:
        return None
    override = RACE_LABEL_OVERRIDES.get(normalized_key)
    if override:
        return override

    normalized = re.sub(r"[_-]+", " ", trimmed.lower())
    words = []
    for index, word in enumerate(normalized.split()):
        if index > 0 and word in LOWERCASE_TITLE_WORDS:
            words.append(word)
        elif word:
            words.append(f"{word[0].upper()}{word[1:]}")
    return " ".join(words)


def normalize_race_key(race: Optional[str]) -> Optional[str]:
    """Normalize a race input into a stable key used by filters and display helpers."""
    if not race:
        return None
    trimmed = race.strip()
    if not trimmed:
        return None

    normalized_key = re.sub(r"[^a-z0-9]+", "_", trimmed.lower()).strip("_")
    if not normalized_key:
        return None

    return RACE_KEY_ALIASES.get(normalized_key, normalized_key)


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


def _strip_accents(value: str) -> str:
    """Remove diacritics for accent-insensitive matching."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def normalize_search_text(value: Optional[str]) -> Optional[str]:
    """
    Normalize free-text for search matching.

    - Strip accents
    - Lowercase
    - Collapse whitespace
    """
    if not value:
        return None
    collapsed = " ".join(value.split())
    if not collapsed:
        return None
    return _strip_accents(collapsed).lower()


def normalize_identifier(value: Optional[str]) -> Optional[str]:
    """
    Normalize identifier-like strings (numbers/short codes) for search.

    - Remove whitespace
    - Lowercase
    """
    if not value:
        return None
    collapsed = re.sub(r"\s+", "", value)
    if not collapsed:
        return None
    return collapsed.lower()


def extract_email_domain(email: Optional[str]) -> Optional[str]:
    """
    Extract lowercased email domain for ops filtering.

    Expects a normalized email, but will normalize if needed.
    """
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        return None
    return normalized.split("@", 1)[1]


def extract_phone_last4(phone: Optional[str]) -> Optional[str]:
    """
    Extract last 4 digits from a normalized phone number.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    return digits[-4:] if len(digits) >= 4 else digits
