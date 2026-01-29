"""Import detection service for CSV analysis.

Provides smart detection of:
- File encoding (BOM detection, UTF-8/UTF-16 try, charset_normalizer fallback)
- Delimiter detection (csv.Sniffer + frequency analysis)
- Column analysis (pattern matching, semantic matching, data-type inference)

Features:
- Three-layer matching: exact/alias, keyword-based, fuzzy (for unmatched only)
- Learning from corrections: org-specific overrides from previous imports
- Confidence scoring for all suggestions
- Transformation recommendations based on data patterns
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING

from app.services.import_transformers import get_suggested_transformer

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

    from app.db.models.surrogates import ImportMappingCorrection


# =============================================================================
# Types & Constants
# =============================================================================


class ConfidenceLevel(str, Enum):
    """Confidence level for column suggestions."""

    HIGH = "high"  # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"  # 0.2 - 0.5
    NONE = "none"  # < 0.2

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        elif score >= 0.2:
            return cls.LOW
        return cls.NONE


@dataclass
class DetectionResult:
    """Result of file format detection."""

    encoding: str
    delimiter: str
    has_header: bool
    row_count: int
    headers: list[str]
    sample_rows: list[list[str]]  # First 5 rows of data


@dataclass
class ColumnSuggestion:
    """Column mapping suggestion with confidence."""

    csv_column: str
    suggested_field: str | None
    confidence: float
    confidence_level: ConfidenceLevel
    transformation: str | None
    sample_values: list[str]
    reason: str
    warnings: list[str] = field(default_factory=list)
    default_action: str | None = None  # 'ignore', 'metadata', etc.
    needs_inversion: bool = False  # For inverted boolean questions


# =============================================================================
# Exact & Alias Column Mapping
# =============================================================================

# Maps normalized CSV column names to Surrogate fields
EXACT_COLUMN_MAPPING: dict[str, str] = {
    # Name variations
    "full_name": "full_name",
    "fullname": "full_name",
    "name": "full_name",
    "full name": "full_name",
    # Email variations
    "email": "email",
    "email_address": "email",
    "emailaddress": "email",
    "e_mail": "email",
    "e-mail": "email",
    # Phone variations
    "phone": "phone",
    "phone_number": "phone",
    "phonenumber": "phone",
    "mobile": "phone",
    "cell": "phone",
    "telephone": "phone",
    # State variations
    "state": "state",
    "st": "state",
    "province": "state",
    # Date of birth variations
    "date_of_birth": "date_of_birth",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "birthdate": "date_of_birth",
    "birthday": "date_of_birth",
    # Race
    "race": "race",
    "ethnicity": "race",
    "race_ethnicity": "race",
    # Height
    "height": "height_ft",
    "height_ft": "height_ft",
    "height_feet": "height_ft",
    # Weight
    "weight": "weight_lb",
    "weight_lb": "weight_lb",
    "weight_lbs": "weight_lb",
    # Eligibility booleans
    "is_age_eligible": "is_age_eligible",
    "age_eligible": "is_age_eligible",
    "is_citizen_or_pr": "is_citizen_or_pr",
    "citizen": "is_citizen_or_pr",
    "has_child": "has_child",
    "is_non_smoker": "is_non_smoker",
    "non_smoker": "is_non_smoker",
    "has_surrogate_experience": "has_surrogate_experience",
    "surrogate_experience": "has_surrogate_experience",
    # Delivery counts
    "num_deliveries": "num_deliveries",
    "deliveries": "num_deliveries",
    "num_csections": "num_csections",
    "c_sections": "num_csections",
    "csections": "num_csections",
    # Source
    "source": "source",
    "lead_source": "source",
    # Created time variations
    "created_at": "created_at",
    "created_time": "created_at",
    "submission_time": "created_at",
    "submitted_at": "created_at",
    "submitted_time": "created_at",
    "date_submitted": "created_at",
    "time_submitted": "created_at",
    "lead_created_time": "created_at",
    "lead_submitted_at": "created_at",
}


# =============================================================================
# Keyword-Based Semantic Patterns
# =============================================================================

# Maps keywords found in column names to target fields
KEYWORD_PATTERNS: dict[str, list[str]] = {
    "num_deliveries": [
        "deliver",
        "birth",
        "kids",
        "children",
        "babies",
        "how many.*kids",
        "how many.*children",
    ],
    "num_csections": ["c-section", "csection", "cesarean"],
    "is_non_smoker": [
        "smoke",
        "nicotine",
        "tobacco",
        "cigarette",
        "vape",
        "marijuana",
        "cannabis",
        "drugs",
    ],
    "is_age_eligible": ["age", "21", "36", "between.*age", "age.*eligible"],
    "is_citizen_or_pr": [
        "citizen",
        "permanent resident",
        "legal status",
        "us resident",
        "legal.*reside",
    ],
    "has_child": ["have.*child", "given birth", "raised.*child", "mom", "mother", "parent"],
    "has_surrogate_experience": [
        "surrogate before",
        "been.*surrogate",
        "previous surrogate",
        "surrogate.*experience",
    ],
    "height_ft": ["height", "tall", "how tall"],
    "weight_lb": ["weight", "weigh", "how much.*weigh"],
    "race": ["race", "ethnicity"],
    "date_of_birth": ["birth", "born", "dob"],
    "email": ["email", "e-mail"],
    "phone": ["phone", "mobile", "cell", "contact number"],
    "full_name": ["full.*name", "your name"],
    "state": ["state", "where.*live", "location"],
    "created_at": [
        "submitted",
        "submission",
        "created",
        "timestamp",
        "lead time",
        "time submitted",
        "date submitted",
    ],
}

# Patterns that should BLOCK mapping to certain fields (guards)
MAPPING_GUARDS: dict[str, dict[str, object]] = {
    "num_csections": {
        "block_patterns": ["more than 2", ">2", "greater than 2", "more than two"],
        "suggest_instead": "custom.c_sections_gt_2",
        "reason": "This is a boolean (yes/no), not a count",
    },
}

# Questions that need inverted boolean logic
# "Do you smoke?" = yes means is_non_smoker = False
INVERTED_PATTERNS: dict[str, list[str]] = {
    "is_non_smoker": ["do you smoke", "are you.*smoker", "use.*tobacco", "use.*nicotine"],
}


# =============================================================================
# Pre-defined Custom Field Suggestions
# =============================================================================

# When these patterns are detected, suggest creating a custom field
CUSTOM_FIELD_SUGGESTIONS: dict[str, dict[str, object]] = {
    "section_8_assistance": {
        "patterns": ["section 8", "government assistance", "housing assistance"],
        "field_type": "boolean",
        "label": "Section 8 Assistance",
    },
    "criminal_history": {
        "patterns": ["criminal", "crime", "committed.*crime", "felony", "misdemeanor"],
        "field_type": "boolean",
        "label": "Criminal History",
    },
    "c_sections_gt_2": {
        "patterns": ["more than 2 c-sections", ">2 c-sections", "more than two c-sections"],
        "field_type": "boolean",
        "label": "More than 2 C-Sections",
    },
}


# Meta/Facebook tracking columns (suggest ignore or metadata)
META_TRACKING_PATTERNS: list[str] = [
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "campaign_id",
    "campaign_name",
    "form_id",
    "form_name",
    "meta_",
    "fb_",
    "created_time",
    "platform",
    "is_organic",
]


# =============================================================================
# Fuzzy Matching (Fallback for typos/abbreviations)
# =============================================================================

# Higher threshold to reduce false positives
FUZZY_MATCH_THRESHOLD = 0.85
FUZZY_MIN_LENGTH = 4  # Skip very short column names

# Stop-list for ambiguous short words
FUZZY_STOP_LIST = {"id", "name", "type", "status", "state", "date", "time", "value", "data"}

# Canonical names for fuzzy matching - ONLY for fields in AVAILABLE_IMPORT_FIELDS
# Maps field name -> list of human-readable variants
CANONICAL_NAMES: dict[str, list[str]] = {
    "full_name": ["full name", "fullname", "complete name"],
    "email": ["email address", "e-mail address", "emal", "emial", "e mail"],
    "phone": ["phone number", "telephone", "mobile number", "cell phone", "fone"],
    "date_of_birth": ["date of birth", "birth date", "birthday", "dob date"],
    "state": ["state province", "province"],
    "race": ["race ethnicity", "ethnicity"],
    "height_ft": ["height feet", "height in feet"],
    "weight_lb": ["weight pounds", "weight lbs"],
    "source": ["lead source", "source name", "referral source", "agency name"],
    "created_at": ["created time", "submission time", "submitted at"],
    "is_age_eligible": ["age eligible", "age eligibility"],
    "is_citizen_or_pr": ["citizen permanent resident", "citizenship status"],
    "has_child": ["has children", "have children", "parenting experience"],
    "is_non_smoker": ["non smoker", "nonsmoker", "smoking status"],
    "has_surrogate_experience": ["surrogate experience", "prior surrogacy"],
    "num_deliveries": ["number deliveries", "delivery count", "birth count"],
    "num_csections": ["number csections", "cesarean count"],
}


def fuzzy_match_column(
    column: str, allowed_fields: list[str] | None = None
) -> tuple[str | None, float]:
    """
    Match column name using string similarity.

    Returns (field, score) or (None, 0.0).
    Only considers fields in allowed_fields AND CANONICAL_NAMES.
    Only use as fallback AFTER keyword matching fails.
    """
    normalized = column.lower().strip().replace("_", " ").replace("-", " ")

    # Skip short or ambiguous names
    if len(normalized) < FUZZY_MIN_LENGTH:
        return None, 0.0
    if normalized in FUZZY_STOP_LIST:
        return None, 0.0

    fields_to_check = allowed_fields if allowed_fields else list(CANONICAL_NAMES.keys())

    best_match: str | None = None
    best_score = 0.0

    for field_name, variants in CANONICAL_NAMES.items():
        # MUST be in allowed_fields to avoid dead matches
        if field_name not in fields_to_check:
            continue
        for variant in variants:
            score = SequenceMatcher(None, normalized, variant).ratio()
            if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                best_score = score
                best_match = field_name

    return best_match, best_score


# =============================================================================
# Encoding Detection
# =============================================================================


def detect_encoding(content: bytes) -> str:
    """
    Detect file encoding using a chain of methods.

    Order:
    1. Check BOM (UTF-8-BOM, UTF-16-LE/BE)
    2. Try UTF-8 decode (most common)
    3. Try UTF-16 decode
    4. Fallback to charset_normalizer

    Args:
        content: Raw file bytes

    Returns:
        Detected encoding string
    """
    # Check for BOM
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if content.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if content.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # Try UTF-8 first (most common)
    try:
        content.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Try UTF-16
    try:
        content.decode("utf-16")
        return "utf-16"
    except UnicodeDecodeError:
        pass

    # Fallback to charset_normalizer (transitive dep of requests)
    try:
        from charset_normalizer import from_bytes

        result = from_bytes(content)
        best = result.best()
        if best:
            return best.encoding
    except ImportError:
        pass

    # Last resort: latin-1 (accepts any byte sequence)
    return "latin-1"


# =============================================================================
# Delimiter Detection
# =============================================================================


def detect_delimiter(content: str) -> str:
    """
    Detect CSV delimiter using csv.Sniffer and frequency analysis.

    Args:
        content: Decoded file content

    Returns:
        Detected delimiter character
    """
    # Use first 8KB for sniffing
    sample = content[:8192]

    # Try csv.Sniffer first
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        pass

    # Fallback: frequency analysis
    # Count potential delimiters in first few lines
    lines = sample.split("\n")[:5]
    delimiter_counts = {",": 0, "\t": 0, ";": 0, "|": 0}

    for line in lines:
        for delim in delimiter_counts:
            delimiter_counts[delim] += line.count(delim)

    # Return most frequent that appears consistently
    best = ","
    best_count = 0
    for delim, count in delimiter_counts.items():
        if count > best_count:
            best = delim
            best_count = count

    return best


# =============================================================================
# Column Analysis
# =============================================================================


def normalize_column_name(col: str) -> str:
    """Normalize column name for matching."""
    # Remove common question prefixes/suffixes
    normalized = col.lower().strip()
    # Replace separators with underscores
    normalized = re.sub(r"[\s\-/]+", "_", normalized)
    # Remove trailing punctuation
    normalized = normalized.rstrip("?:_")
    return normalized


def get_sample_values(rows: list[list[str]], col_idx: int, max_samples: int = 5) -> list[str]:
    """Extract sample values for a column."""
    samples = []
    for row in rows:
        if col_idx < len(row):
            value = row[col_idx].strip()
            if value and value not in samples:
                samples.append(value)
                if len(samples) >= max_samples:
                    break
    return samples


def check_mapping_guard(column: str, field: str) -> tuple[bool, str | None, str | None]:
    """
    Check if a mapping should be blocked by a guard.

    Returns:
        (should_block, suggested_field, reason)
    """
    if field in MAPPING_GUARDS:
        guard = MAPPING_GUARDS[field]
        patterns = guard.get("block_patterns", [])
        for pattern in patterns:
            if re.search(pattern, column, re.IGNORECASE):
                return (
                    True,
                    str(guard.get("suggest_instead")),
                    str(guard.get("reason")),
                )
    return False, None, None


def check_inverted_pattern(column: str, field: str) -> bool:
    """Check if the column question needs inverted boolean logic."""
    if field in INVERTED_PATTERNS:
        for pattern in INVERTED_PATTERNS[field]:
            if re.search(pattern, column, re.IGNORECASE):
                return True
    return False


def infer_data_type(samples: list[str]) -> dict[str, object]:
    """
    Analyze sample values to infer data type and suggest transformations.

    Returns dict with:
    - type: 'date', 'phone', 'boolean', 'number', 'text'
    - confidence: 0-1
    - transformation: suggested transformer name
    """
    if not samples:
        return {"type": "text", "confidence": 0.5, "transformation": None}

    # Check for dates (MM/DD/YYYY, YYYY-MM-DD, ISO timestamps)
    date_patterns = [
        r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}$",  # MM/DD/YYYY
        r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$",  # YYYY-MM-DD
        r"^\d{4}-\d{2}-\d{2}T",  # ISO timestamp
    ]
    date_matches = 0
    for sample in samples:
        for pattern in date_patterns:
            if re.match(pattern, sample.strip()):
                date_matches += 1
                break

    if date_matches >= len(samples) * 0.8:
        return {"type": "date", "confidence": 0.9, "transformation": "date_flexible"}

    # Check for phone numbers
    phone_pattern = r"^[\d\s\-\(\)\+\.]{10,}$"
    phone_matches = sum(1 for s in samples if re.match(phone_pattern, s.strip()))
    if phone_matches >= len(samples) * 0.8:
        return {"type": "phone", "confidence": 0.85, "transformation": "phone_normalize"}

    # Check for boolean values
    bool_values = {"yes", "no", "y", "n", "true", "false", "1", "0", "on", "off"}
    bool_matches = sum(1 for s in samples if s.strip().lower() in bool_values)
    if bool_matches >= len(samples) * 0.8:
        return {"type": "boolean", "confidence": 0.9, "transformation": "boolean_flexible"}

    # Check for numbers
    try:
        num_matches = sum(1 for s in samples if s.strip() and Decimal(s.strip()))
        if num_matches >= len(samples) * 0.8:
            return {"type": "number", "confidence": 0.85, "transformation": None}
    except Exception:
        pass

    return {"type": "text", "confidence": 0.5, "transformation": None}


def is_meta_tracking_column(column: str) -> bool:
    """Check if a column is likely Meta/Facebook tracking data."""
    normalized = column.lower().replace(" ", "_").replace("-", "_")
    for pattern in META_TRACKING_PATTERNS:
        if pattern in normalized:
            return True
    return False


def suggest_custom_field(column: str) -> dict[str, object] | None:
    """Check if a column should suggest creating a custom field."""
    for key, config in CUSTOM_FIELD_SUGGESTIONS.items():
        patterns = config.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, column, re.IGNORECASE):
                return {
                    "key": key,
                    "label": config.get("label"),
                    "field_type": config.get("field_type"),
                }
    return None


def analyze_column(
    column: str,
    col_idx: int,
    sample_rows: list[list[str]],
    allowed_fields: list[str] | None = None,
) -> ColumnSuggestion:
    """
    Analyze a single column and generate a mapping suggestion.

    Uses three-layer matching:
    1. Exact/alias matching
    2. Keyword-based semantic matching
    3. Fuzzy matching (only for unmatched, as fallback for typos)

    AI-powered matching is handled separately (opt-in).
    """
    normalized = normalize_column_name(column)
    samples = get_sample_values(sample_rows, col_idx)
    warnings: list[str] = []

    # Layer 1: Exact/alias matching
    if normalized in EXACT_COLUMN_MAPPING:
        target_field = EXACT_COLUMN_MAPPING[normalized]

        # Check for mapping guards
        blocked, alt_field, block_reason = check_mapping_guard(column, target_field)
        if blocked:
            warnings.append(block_reason or "")
            default_action = "custom" if (alt_field or "").startswith("custom.") else None
            return ColumnSuggestion(
                csv_column=column,
                suggested_field=alt_field,
                confidence=0.7,
                confidence_level=ConfidenceLevel.MEDIUM,
                transformation=None,
                sample_values=samples,
                reason=f"Blocked: {block_reason}. Consider {alt_field}",
                warnings=warnings,
                default_action=default_action,
            )

        transformation = get_suggested_transformer(target_field)
        needs_inversion = check_inverted_pattern(column, target_field)
        if needs_inversion and transformation == "boolean_flexible":
            transformation = "boolean_inverted"

        return ColumnSuggestion(
            csv_column=column,
            suggested_field=target_field,
            confidence=0.98,
            confidence_level=ConfidenceLevel.HIGH,
            transformation=transformation,
            sample_values=samples,
            reason="Exact column name match",
            needs_inversion=needs_inversion,
        )

    # Layer 2: Keyword-based semantic matching
    best_match: str | None = None
    best_score = 0.0
    match_reason = ""

    for target_field, keywords in KEYWORD_PATTERNS.items():
        for keyword in keywords:
            if re.search(keyword, column, re.IGNORECASE):
                # Score based on keyword specificity
                score = 0.75 + (len(keyword) / 50)  # Longer patterns = more specific
                if score > best_score:
                    # Check mapping guard
                    blocked, alt_field, block_reason = check_mapping_guard(column, target_field)
                    if blocked:
                        warnings.append(block_reason or "")
                        best_match = alt_field if alt_field else None
                        best_score = 0.5
                        match_reason = f"Blocked: {block_reason}"
                    else:
                        best_match = target_field
                        best_score = min(score, 0.9)
                        match_reason = f"Semantic match: keyword '{keyword}' found"

    if best_match:
        transformation = get_suggested_transformer(best_match)
        needs_inversion = check_inverted_pattern(column, best_match)
        if needs_inversion and transformation == "boolean_flexible":
            transformation = "boolean_inverted"

        default_action = "custom" if best_match.startswith("custom.") else None

        return ColumnSuggestion(
            csv_column=column,
            suggested_field=best_match,
            confidence=best_score,
            confidence_level=ConfidenceLevel.from_score(best_score),
            transformation=transformation,
            sample_values=samples,
            reason=match_reason,
            warnings=warnings,
            needs_inversion=needs_inversion,
            default_action=default_action,
        )

    # Layer 3: Fuzzy matching (ONLY if no keyword match found)
    fields = allowed_fields or list(CANONICAL_NAMES.keys())
    fuzzy_field, fuzzy_score = fuzzy_match_column(column, fields)
    if fuzzy_field:
        # Check mapping guard (same as exact/keyword)
        blocked, alt_field, block_reason = check_mapping_guard(column, fuzzy_field)
        if blocked:
            warnings.append(block_reason or "")
            return ColumnSuggestion(
                csv_column=column,
                suggested_field=alt_field,
                confidence=0.5,
                confidence_level=ConfidenceLevel.MEDIUM,
                transformation=None,
                sample_values=samples,
                reason=f"Fuzzy match blocked: {block_reason}",
                warnings=warnings,
                default_action="custom" if (alt_field or "").startswith("custom.") else None,
            )

        transformation = get_suggested_transformer(fuzzy_field)
        needs_inversion = check_inverted_pattern(column, fuzzy_field)
        if needs_inversion and transformation == "boolean_flexible":
            transformation = "boolean_inverted"

        return ColumnSuggestion(
            csv_column=column,
            suggested_field=fuzzy_field,
            confidence=fuzzy_score,
            confidence_level=ConfidenceLevel.from_score(fuzzy_score),
            transformation=transformation,
            sample_values=samples,
            reason=f"Similar column name match ({int(fuzzy_score * 100)}% similarity)",
            needs_inversion=needs_inversion,
        )

    # Check if it's Meta tracking data
    if is_meta_tracking_column(column):
        return ColumnSuggestion(
            csv_column=column,
            suggested_field=None,
            confidence=0.1,
            confidence_level=ConfidenceLevel.NONE,
            transformation=None,
            sample_values=samples,
            reason="Meta/Facebook tracking column - recommend ignore or metadata",
            default_action="ignore",
        )

    # Check for custom field suggestion
    custom_suggestion = suggest_custom_field(column)
    if custom_suggestion:
        return ColumnSuggestion(
            csv_column=column,
            suggested_field=f"custom.{custom_suggestion['key']}",
            confidence=0.6,
            confidence_level=ConfidenceLevel.MEDIUM,
            transformation="boolean_flexible"
            if custom_suggestion["field_type"] == "boolean"
            else None,
            sample_values=samples,
            reason=f"Suggests creating custom field: {custom_suggestion['label']}",
        )

    # Try data-type inference as fallback
    type_info = infer_data_type(samples)
    if type_info["type"] != "text" and type_info["confidence"] >= 0.8:
        return ColumnSuggestion(
            csv_column=column,
            suggested_field=None,
            confidence=0.3,
            confidence_level=ConfidenceLevel.LOW,
            transformation=type_info.get("transformation"),
            sample_values=samples,
            reason=f"Data type detected: {type_info['type']}",
            default_action="metadata",
        )

    # No match found
    return ColumnSuggestion(
        csv_column=column,
        suggested_field=None,
        confidence=0.0,
        confidence_level=ConfidenceLevel.NONE,
        transformation=None,
        sample_values=samples,
        reason="No matching field found",
        default_action="ignore",
    )


def analyze_columns(
    headers: list[str],
    sample_rows: list[list[str]],
    *,
    allowed_fields: list[str] | None = None,
) -> list[ColumnSuggestion]:
    """
    Analyze all columns and generate mapping suggestions.

    Args:
        headers: List of CSV column headers
        sample_rows: First N rows of data for type inference
        allowed_fields: List of allowed field names (for fuzzy matching filtering)

    Returns:
        List of ColumnSuggestion for each header
    """
    suggestions = []
    allowed = set(allowed_fields) if allowed_fields else None
    for idx, header in enumerate(headers):
        suggestion = analyze_column(header, idx, sample_rows, allowed_fields)
        # Post-filter: if suggestion is for a field not in allowed, reset
        if allowed is not None and suggestion.suggested_field:
            # Allow custom. fields through, only filter standard fields
            if not suggestion.suggested_field.startswith("custom."):
                if suggestion.suggested_field not in allowed:
                    suggestion = ColumnSuggestion(
                        csv_column=suggestion.csv_column,
                        suggested_field=None,
                        confidence=0.0,
                        confidence_level=ConfidenceLevel.NONE,
                        transformation=None,
                        sample_values=suggestion.sample_values,
                        reason="Field not available for this import type",
                        default_action="ignore",
                    )
        suggestions.append(suggestion)
    return suggestions


# =============================================================================
# Learning from Corrections
# =============================================================================


def get_org_corrections(db: Session, org_id: UUID) -> dict[str, ImportMappingCorrection]:
    """
    Load all corrections for an org, keyed by normalized column name.

    Returns:
        Dict of {normalized_column_name: ImportMappingCorrection}
    """
    from app.db.models.surrogates import ImportMappingCorrection

    corrections = (
        db.query(ImportMappingCorrection)
        .filter(ImportMappingCorrection.organization_id == org_id)
        .all()
    )
    return {c.column_name_normalized: c for c in corrections}


def analyze_column_with_learning(
    column: str,
    col_idx: int,
    sample_rows: list[list[str]],
    org_corrections: dict[str, ImportMappingCorrection],
    allowed_fields: list[str] | None = None,
) -> ColumnSuggestion:
    """
    Enhanced analyze_column that checks org corrections first.

    Priority order:
    1. Learned corrections (highest priority)
    2. Exact/alias match
    3. Keyword match
    4. Fuzzy match
    5. Custom field/data-type inference
    """
    normalized = normalize_column_name(column)
    samples = get_sample_values(sample_rows, col_idx)

    # Layer 0: Check learned corrections FIRST (highest priority)
    if correction := org_corrections.get(normalized):
        # Confidence increases with usage (0.7 base + 0.05 per use, max 0.95)
        confidence = min(0.95, 0.7 + (correction.times_used * 0.05))
        transformation = correction.corrected_transformation
        if not transformation and correction.corrected_field:
            if not correction.corrected_field.startswith("custom."):
                transformation = get_suggested_transformer(correction.corrected_field)

        return ColumnSuggestion(
            csv_column=column,
            suggested_field=correction.corrected_field if correction.corrected_field else None,
            confidence=confidence,
            confidence_level=ConfidenceLevel.from_score(confidence),
            transformation=transformation,
            sample_values=samples,
            reason=f"Learned from {correction.times_used} previous import(s)",
            default_action=correction.corrected_action,
        )

    # Fall back to normal analysis (layers 1-4)
    return analyze_column(column, col_idx, sample_rows, allowed_fields)


def analyze_columns_with_learning(
    db: Session,
    org_id: UUID,
    headers: list[str],
    sample_rows: list[list[str]],
    allowed_fields: list[str] | None = None,
) -> list[ColumnSuggestion]:
    """
    Analyze all columns with org-specific learned corrections.

    Args:
        db: Database session
        org_id: Organization ID
        headers: List of CSV column headers
        sample_rows: First N rows of data for type inference
        allowed_fields: List of allowed field names

    Returns:
        List of ColumnSuggestion for each header
    """
    org_corrections = get_org_corrections(db, org_id)

    suggestions = []
    allowed = set(allowed_fields) if allowed_fields else None
    for idx, header in enumerate(headers):
        if org_corrections:
            suggestion = analyze_column_with_learning(
                header, idx, sample_rows, org_corrections, allowed_fields
            )
        else:
            suggestion = analyze_column(header, idx, sample_rows, allowed_fields)

        # Post-filter: if suggestion is for a field not in allowed, reset
        if allowed is not None and suggestion.suggested_field:
            if not suggestion.suggested_field.startswith("custom."):
                if suggestion.suggested_field not in allowed:
                    suggestion = ColumnSuggestion(
                        csv_column=suggestion.csv_column,
                        suggested_field=None,
                        confidence=0.0,
                        confidence_level=ConfidenceLevel.NONE,
                        transformation=None,
                        sample_values=suggestion.sample_values,
                        reason="Field not available for this import type",
                        default_action="ignore",
                    )
        suggestions.append(suggestion)

    return suggestions


# =============================================================================
# Full Detection Pipeline
# =============================================================================


def detect_file_format(content: bytes) -> DetectionResult:
    """
    Detect file format and parse content.

    Combines encoding detection, delimiter detection, and header analysis.

    Args:
        content: Raw file bytes

    Returns:
        DetectionResult with all detection info
    """
    # Detect encoding
    encoding = detect_encoding(content)

    # Decode content
    try:
        decoded = content.decode(encoding)
    except UnicodeDecodeError:
        # Fallback to latin-1
        decoded = content.decode("latin-1")
        encoding = "latin-1"

    # Detect delimiter
    delimiter = detect_delimiter(decoded)

    # Parse CSV
    reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
    rows = list(reader)

    if not rows:
        return DetectionResult(
            encoding=encoding,
            delimiter=delimiter,
            has_header=False,
            row_count=0,
            headers=[],
            sample_rows=[],
        )

    # Assume first row is header
    headers = rows[0]
    if headers and headers[0].startswith("\ufeff"):
        headers[0] = headers[0].lstrip("\ufeff")
    data_rows = rows[1:]

    # Get sample rows (first 5)
    sample_rows = data_rows[:5]

    return DetectionResult(
        encoding=encoding,
        delimiter=delimiter,
        has_header=True,
        row_count=len(data_rows),
        headers=headers,
        sample_rows=sample_rows,
    )


def full_column_analysis(content: bytes) -> tuple[DetectionResult, list[ColumnSuggestion]]:
    """
    Full detection and analysis pipeline.

    Args:
        content: Raw file bytes

    Returns:
        Tuple of (DetectionResult, list[ColumnSuggestion])
    """
    detection = detect_file_format(content)
    suggestions = analyze_columns(detection.headers, detection.sample_rows)
    return detection, suggestions


# =============================================================================
# Available Surrogate Fields
# =============================================================================

# All fields that can be mapped from CSV
AVAILABLE_SURROGATE_FIELDS = [
    # Required
    "full_name",
    "email",
    # Contact
    "phone",
    "state",
    # Demographics
    "date_of_birth",
    "race",
    "height_ft",
    "weight_lb",
    # Eligibility
    "is_age_eligible",
    "is_citizen_or_pr",
    "has_child",
    "is_non_smoker",
    "has_surrogate_experience",
    "num_deliveries",
    "num_csections",
    # Source
    "source",
    # Timestamps
    "created_at",
]

# CSV import fields (may include fields also used in Meta lead mapping)
AVAILABLE_IMPORT_FIELDS = list(dict.fromkeys([*AVAILABLE_SURROGATE_FIELDS, "created_at"]))
