"""Import transformation engine for CSV data normalization.

Provides registered transformers that convert raw CSV values into
normalized formats suitable for the Surrogate model.

Features:
- date_flexible: Parses multiple date formats (MM/DD/YYYY, YYYY-MM-DD, ISO)
- height_flexible: Parses height formats ("5'4", "5.6", "5ft 2in", inches)
- state_normalize: Normalizes to 2-letter state codes
- phone_normalize: Normalizes to E.164 format
- boolean_flexible: Parses yes/no/true/false/1/0
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, TypeAlias

from app.utils.normalization import normalize_phone, normalize_state


# =============================================================================
# Types
# =============================================================================

TransformResult: TypeAlias = tuple[Any, list[str]]  # (value, warnings)
TransformerFn: TypeAlias = Callable[[str], TransformResult]


@dataclass
class TransformOutput:
    """Result of a transformation operation."""

    value: Any
    success: bool
    warnings: list[str]
    error: str | None = None


# =============================================================================
# Date Transformer
# =============================================================================

# Common date format patterns to try
DATE_PATTERNS = [
    # MM/DD/YYYY (US format)
    (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", "MM/DD/YYYY"),
    # MM-DD-YYYY
    (r"^(\d{1,2})-(\d{1,2})-(\d{4})$", "MM-DD-YYYY"),
    # YYYY-MM-DD (ISO)
    (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "YYYY-MM-DD"),
    # YYYY/MM/DD
    (r"^(\d{4})/(\d{1,2})/(\d{1,2})$", "YYYY/MM/DD"),
    # DD/MM/YYYY (European - less common in US context, lower priority)
    # This is handled as ambiguous when month <= 12
]


def is_date_ambiguous(month: int, day: int) -> bool:
    """Check if a date could be interpreted as MM/DD or DD/MM."""
    return month <= 12 and day <= 12 and month != day


def transform_date_flexible(raw_value: str) -> TransformOutput:
    """
    Parse date from various formats.

    Supported formats:
    - MM/DD/YYYY, MM-DD-YYYY (US standard)
    - YYYY-MM-DD, YYYY/MM/DD (ISO)
    - ISO 8601 timestamps (2025-11-19T17:10:38-08:00)

    Returns date object and warnings for ambiguous dates.
    """
    value = raw_value.strip()
    if not value:
        return TransformOutput(value=None, success=True, warnings=[])

    warnings: list[str] = []

    # Try ISO 8601 timestamp first (from Meta exports)
    try:
        # Handle timezone-aware ISO format: 2025-11-19T17:10:38-08:00
        if "T" in value:
            # Parse ISO timestamp, extract date
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return TransformOutput(value=dt.date(), success=True, warnings=[])
    except ValueError:
        pass

    # Try standard date formats
    # US format: MM/DD/YYYY or MM-DD-YYYY
    match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", value)
    if match:
        part1, part2, year = int(match.group(1)), int(match.group(2)), int(match.group(3))

        # Assume US format (MM/DD/YYYY) as default
        month, day = part1, part2

        # Check for ambiguity
        if is_date_ambiguous(part1, part2):
            warnings.append(
                f"Date '{value}' is ambiguous (could be {part1}/{part2}/{year} or {part2}/{part1}/{year}). "
                f"Interpreting as MM/DD/YYYY (US format)."
            )

        # Validate the date
        try:
            result_date = date(year, month, day)
            return TransformOutput(value=result_date, success=True, warnings=warnings)
        except ValueError:
            # Maybe it's actually DD/MM/YYYY?
            try:
                result_date = date(year, part2, part1)
                warnings.append(f"Interpreted '{value}' as DD/MM/YYYY format.")
                return TransformOutput(value=result_date, success=True, warnings=warnings)
            except ValueError:
                return TransformOutput(
                    value=None,
                    success=False,
                    warnings=[],
                    error=f"Invalid date: {value}",
                )

    # Try ISO format: YYYY-MM-DD or YYYY/MM/DD
    match = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", value)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            result_date = date(year, month, day)
            return TransformOutput(value=result_date, success=True, warnings=[])
        except ValueError:
            return TransformOutput(
                value=None,
                success=False,
                warnings=[],
                error=f"Invalid date: {value}",
            )

    return TransformOutput(
        value=None,
        success=False,
        warnings=[],
        error=f"Unrecognized date format: {value}",
    )


# =============================================================================
# Height Transformer
# =============================================================================


def transform_height_flexible(raw_value: str) -> TransformOutput:
    """
    Parse height from various formats to decimal feet.

    Supported formats:
    - "5'4" or "5'4\"" (feet and inches)
    - "5 ft 4 in" or "5ft 4in" (spelled out)
    - "5.4" or "5.33" (decimal feet)
    - "64" (total inches, if > 36)

    Returns decimal feet (e.g., 5.33 for 5'4").
    """
    value = raw_value.strip()
    if not value:
        return TransformOutput(value=None, success=True, warnings=[])

    warnings: list[str] = []

    # Pattern: 5'4" or 5'4 or 5' 4" or 5' 4
    match = re.match(r"^(\d+)\s*['\u2019]?\s*(\d+)\s*\"?\s*$", value)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        if inches >= 12:
            warnings.append(f"Inches value {inches} >= 12, may be incorrect")
        decimal_feet = Decimal(str(feet)) + Decimal(str(inches)) / Decimal("12")
        return TransformOutput(
            value=decimal_feet.quantize(Decimal("0.1")),
            success=True,
            warnings=warnings,
        )

    # Pattern: 5ft 4in or 5 ft 4 in
    match = re.match(r"^(\d+)\s*ft\.?\s*(\d+)\s*in\.?\s*$", value, re.IGNORECASE)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        if inches >= 12:
            warnings.append(f"Inches value {inches} >= 12, may be incorrect")
        decimal_feet = Decimal(str(feet)) + Decimal(str(inches)) / Decimal("12")
        return TransformOutput(
            value=decimal_feet.quantize(Decimal("0.1")),
            success=True,
            warnings=warnings,
        )

    # Pattern: 5ft (feet only)
    match = re.match(r"^(\d+)\s*ft\.?\s*$", value, re.IGNORECASE)
    if match:
        feet = int(match.group(1))
        return TransformOutput(
            value=Decimal(str(feet)),
            success=True,
            warnings=warnings,
        )

    # Pattern: 5' (feet only with apostrophe)
    match = re.match(r"^(\d+)\s*['\u2019]\s*$", value)
    if match:
        feet = int(match.group(1))
        return TransformOutput(
            value=Decimal(str(feet)),
            success=True,
            warnings=warnings,
        )

    # Pattern: decimal feet (5.4, 5.33, etc.)
    try:
        decimal_value = Decimal(value)
        # Sanity check: reasonable height range 3-8 feet
        if Decimal("3") <= decimal_value <= Decimal("8"):
            return TransformOutput(
                value=decimal_value.quantize(Decimal("0.1")),
                success=True,
                warnings=[],
            )
        # If > 36, treat as total inches
        elif decimal_value > Decimal("36"):
            feet_from_inches = decimal_value / Decimal("12")
            if Decimal("3") <= feet_from_inches <= Decimal("8"):
                warnings.append(f"Interpreted '{value}' as inches, converted to feet")
                return TransformOutput(
                    value=feet_from_inches.quantize(Decimal("0.1")),
                    success=True,
                    warnings=warnings,
                )
        # Value seems unreasonable
        return TransformOutput(
            value=None,
            success=False,
            warnings=[],
            error=f"Height value '{value}' out of reasonable range (3-8 feet)",
        )
    except InvalidOperation:
        pass

    return TransformOutput(
        value=None,
        success=False,
        warnings=[],
        error=f"Unrecognized height format: {value}",
    )


# =============================================================================
# State Transformer
# =============================================================================


def transform_state_normalize(raw_value: str) -> TransformOutput:
    """
    Normalize state to 2-letter code.

    Uses the existing normalize_state utility but wraps errors.
    """
    value = raw_value.strip()
    if not value:
        return TransformOutput(value=None, success=True, warnings=[])

    try:
        normalized = normalize_state(value)
        return TransformOutput(value=normalized, success=True, warnings=[])
    except ValueError as e:
        return TransformOutput(
            value=None,
            success=False,
            warnings=[],
            error=str(e),
        )


# =============================================================================
# Phone Transformer
# =============================================================================


def transform_phone_normalize(raw_value: str) -> TransformOutput:
    """
    Normalize phone to E.164 format.

    Uses the existing normalize_phone utility but wraps errors.
    """
    value = raw_value.strip()
    if not value:
        return TransformOutput(value=None, success=True, warnings=[])

    try:
        normalized = normalize_phone(value)
        return TransformOutput(value=normalized, success=True, warnings=[])
    except ValueError as e:
        return TransformOutput(
            value=None,
            success=False,
            warnings=[],
            error=str(e),
        )


# =============================================================================
# Boolean Transformer
# =============================================================================

# Values that should parse to True
TRUE_VALUES = {
    "yes",
    "y",
    "true",
    "t",
    "1",
    "on",
    "si",  # Spanish
    "oui",  # French
    "✓",
    "✔",
    "x",  # Often used as a checkmark
}

# Values that should parse to False
FALSE_VALUES = {
    "no",
    "n",
    "false",
    "f",
    "0",
    "off",
    "",
    "none",
    "null",
    "na",
    "n/a",
}


def transform_boolean_flexible(raw_value: str) -> TransformOutput:
    """
    Parse boolean from various text representations.

    Recognizes:
    - yes/no, y/n
    - true/false, t/f
    - 1/0
    - on/off
    - Checkmarks (✓, ✔, x)
    """
    value = raw_value.strip().lower()

    if not value:
        return TransformOutput(value=None, success=True, warnings=[])

    if value in TRUE_VALUES:
        return TransformOutput(value=True, success=True, warnings=[])

    if value in FALSE_VALUES:
        return TransformOutput(value=False, success=True, warnings=[])

    return TransformOutput(
        value=None,
        success=False,
        warnings=[],
        error=f"Unrecognized boolean value: '{raw_value}'",
    )


# =============================================================================
# Inverted Boolean Transformer
# =============================================================================


def transform_boolean_inverted(raw_value: str) -> TransformOutput:
    """
    Parse boolean with inverted logic.

    Used for questions like "Do you smoke?" that need to map to is_non_smoker.
    "Yes" to smoking means is_non_smoker=False.
    """
    result = transform_boolean_flexible(raw_value)
    if result.success and result.value is not None:
        result.value = not result.value
    return result


# =============================================================================
# Transformer Registry
# =============================================================================

TRANSFORMERS: dict[str, Callable[[str], TransformOutput]] = {
    "date_flexible": transform_date_flexible,
    "height_flexible": transform_height_flexible,
    "state_normalize": transform_state_normalize,
    "phone_normalize": transform_phone_normalize,
    "boolean_flexible": transform_boolean_flexible,
    "boolean_inverted": transform_boolean_inverted,
}


def get_transformer(name: str) -> Callable[[str], TransformOutput] | None:
    """Get a transformer by name."""
    return TRANSFORMERS.get(name)


def transform_value(transformer_name: str, raw_value: str) -> TransformOutput:
    """
    Apply a named transformer to a value.

    Args:
        transformer_name: Name of the transformer to use
        raw_value: Raw string value from CSV

    Returns:
        TransformOutput with value, success flag, warnings, and optional error
    """
    transformer = TRANSFORMERS.get(transformer_name)
    if not transformer:
        return TransformOutput(
            value=raw_value,  # Return original if no transformer
            success=True,
            warnings=[f"Unknown transformer: {transformer_name}"],
        )
    return transformer(raw_value)


# =============================================================================
# Field-to-Transformer Mapping
# =============================================================================

# Auto-suggest transformers based on target field
FIELD_TRANSFORMERS: dict[str, str] = {
    "date_of_birth": "date_flexible",
    "height_ft": "height_flexible",
    "state": "state_normalize",
    "phone": "phone_normalize",
    "is_age_eligible": "boolean_flexible",
    "is_citizen_or_pr": "boolean_flexible",
    "has_child": "boolean_flexible",
    "is_non_smoker": "boolean_flexible",  # May need inversion based on question
    "has_surrogate_experience": "boolean_flexible",
    # Insurance info
    "insurance_phone": "phone_normalize",
    "insurance_subscriber_dob": "date_flexible",
    # Clinic info
    "clinic_state": "state_normalize",
    "clinic_phone": "phone_normalize",
    # Monitoring clinic
    "monitoring_clinic_state": "state_normalize",
    "monitoring_clinic_phone": "phone_normalize",
    # OB
    "ob_state": "state_normalize",
    "ob_phone": "phone_normalize",
    # Delivery hospital
    "delivery_hospital_state": "state_normalize",
    "delivery_hospital_phone": "phone_normalize",
    # Pregnancy tracking
    "pregnancy_start_date": "date_flexible",
    "pregnancy_due_date": "date_flexible",
    "actual_delivery_date": "date_flexible",
}


def get_suggested_transformer(field_name: str) -> str | None:
    """Get the suggested transformer for a surrogate field."""
    return FIELD_TRANSFORMERS.get(field_name)
