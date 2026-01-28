"""AI-powered column mapping service for CSV imports.

Provides semantic analysis of unmatched columns using LLM.
Always opt-in (user must click "Get AI Help").

Features:
- Analyzes column names and sample data semantically
- Suggests mappings with confidence scores and reasoning
- Handles question-style columns from Meta/Typeform
- Respects org's ai_enabled flag
- Masks PII before sending to AI

PII Hygiene:
- Mask emails: user@example.com → u***@e***.com
- Mask phones: +15551234567 → ***-***-4567
- Cap samples to 3-5 values per column
- Never send free-text PII (notes, addresses) to AI
"""

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.ai_provider import AIProvider, ChatMessage
from app.services.ai_settings_service import get_ai_provider_for_org
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_prompt_schemas import AIImportMappingSuggestion
from app.services.ai_response_validation import parse_json_array, validate_model_list
from app.services.import_detection_service import (
    AVAILABLE_SURROGATE_FIELDS,
    ColumnSuggestion,
    ConfidenceLevel,
)
from app.services.import_transformers import get_suggested_transformer


logger = logging.getLogger(__name__)


# =============================================================================
# PII Masking
# =============================================================================


def mask_email(email: str) -> str:
    """Mask email for AI prompt: user@example.com → u***@e***.com"""
    if "@" not in email:
        return email

    local, domain = email.split("@", 1)
    domain_parts = domain.split(".")

    masked_local = local[0] + "***" if local else "***"
    masked_domain = domain_parts[0][0] + "***" if domain_parts else "***"
    masked_tld = domain_parts[-1] if len(domain_parts) > 1 else "com"

    return f"{masked_local}@{masked_domain}.{masked_tld}"


def mask_phone(phone: str) -> str:
    """Mask phone for AI prompt: +15551234567 → ***-***-4567"""
    # Extract digits only
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return f"***-***-{digits[-4:]}"
    return "***"


def looks_like_email(value: str) -> bool:
    """Check if value looks like an email."""
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", value))


def looks_like_phone(value: str) -> bool:
    """Check if value looks like a phone number."""
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 10


def mask_sample_value(value: str) -> str:
    """Mask PII in sample value if detected."""
    if looks_like_email(value):
        return mask_email(value)
    if looks_like_phone(value):
        return mask_phone(value)
    return value


def mask_samples(samples: list[str], max_samples: int = 3) -> list[str]:
    """Mask PII in sample values and limit count."""
    return [mask_sample_value(s) for s in samples[:max_samples]]


# =============================================================================
# AI Prompt Construction
# =============================================================================


def build_mapping_prompt(
    unmatched_columns: list[dict[str, object]],
    available_fields: list[str],
) -> str:
    """
    Build the AI prompt for column mapping analysis.

    Args:
        unmatched_columns: List of dicts with 'column' and 'samples' keys
        available_fields: List of available Surrogate fields

    Returns:
        Prompt string for the AI
    """
    columns_text = "\n".join(
        f'{i + 1}. "{col["column"]}" - samples: {col["samples"]}'
        for i, col in enumerate(unmatched_columns)
    )

    fields_text = ", ".join(available_fields)

    prompt = get_prompt("import_mapping")
    return prompt.render_user(fields_text=fields_text, columns_text=columns_text)


# =============================================================================
# AI Response Parsing
# =============================================================================


@dataclass
class AIMappingSuggestion:
    """Parsed AI suggestion for a column."""

    column: str
    suggested_field: str | None
    confidence: float
    transformation: str | None
    invert: bool
    reasoning: str
    action: str  # 'map', 'metadata', 'custom', 'ignore'
    custom_field: dict | None = None


def parse_ai_response(response_text: str) -> list[AIMappingSuggestion]:
    """
    Parse the AI response JSON into structured suggestions.

    Handles common JSON issues (markdown code blocks, etc.)
    """
    data = parse_json_array(response_text)
    if data is None:
        logger.warning("AI response is not a list")
        return []

    validated = validate_model_list(AIImportMappingSuggestion, data)
    suggestions: list[AIMappingSuggestion] = []
    for item in validated:
        suggestions.append(
            AIMappingSuggestion(
                column=item.column,
                suggested_field=item.suggested_field,
                confidence=float(item.confidence),
                transformation=item.transformation,
                invert=bool(item.invert),
                reasoning=item.reasoning,
                action=item.action,
                custom_field=item.custom_field,
            )
        )

    return suggestions


def ai_suggestion_to_column_suggestion(
    ai_suggestion: AIMappingSuggestion,
    original_samples: list[str],
) -> ColumnSuggestion:
    """Convert AI suggestion to ColumnSuggestion format."""
    # Determine confidence level
    confidence_level = ConfidenceLevel.from_score(ai_suggestion.confidence)

    # Handle transformation
    transformation = ai_suggestion.transformation
    if ai_suggestion.invert and not transformation:
        transformation = "boolean_inverted"
    elif ai_suggestion.suggested_field and not transformation:
        # Get default transformer for field
        transformation = get_suggested_transformer(ai_suggestion.suggested_field)

    # Handle custom field suggestion
    suggested_field = ai_suggestion.suggested_field
    if ai_suggestion.action == "custom" and ai_suggestion.custom_field:
        suggested_field = f"custom.{ai_suggestion.custom_field.get('key', 'unknown')}"

    # Determine default action
    default_action = None
    if ai_suggestion.action in ("metadata", "ignore"):
        default_action = ai_suggestion.action

    return ColumnSuggestion(
        csv_column=ai_suggestion.column,
        suggested_field=suggested_field,
        confidence=ai_suggestion.confidence,
        confidence_level=confidence_level,
        transformation=transformation,
        sample_values=original_samples,
        reason=f"AI: {ai_suggestion.reasoning}",
        needs_inversion=ai_suggestion.invert,
        default_action=default_action,
    )


# =============================================================================
# Main Service Functions
# =============================================================================


def is_ai_available(db: Session, org_id: UUID) -> bool:
    """Check if AI is enabled and configured for the organization."""
    from app.db.models import Organization

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or not org.ai_enabled:
        return False

    provider = get_ai_provider_for_org(db, org_id)
    return provider is not None


async def ai_suggest_mappings(
    db: Session,
    org_id: UUID,
    unmatched_columns: list[ColumnSuggestion],
) -> list[ColumnSuggestion]:
    """
    Use AI to suggest mappings for unmatched columns.

    This is an opt-in feature - only called when user clicks "Get AI Help".

    Args:
        db: Database session
        org_id: Organization ID
        unmatched_columns: List of ColumnSuggestion with no confident mapping

    Returns:
        Updated list of ColumnSuggestion with AI recommendations
    """
    # Get AI provider
    provider = get_ai_provider_for_org(db, org_id)
    if not provider:
        logger.warning(f"AI not available for org {org_id}")
        return unmatched_columns

    # Prepare data for AI (with PII masking)
    columns_for_ai = []
    original_samples_map = {}  # column -> original samples

    for col in unmatched_columns:
        original_samples_map[col.csv_column] = col.sample_values
        masked_samples = mask_samples(col.sample_values)
        columns_for_ai.append(
            {
                "column": col.csv_column,
                "samples": masked_samples,
            }
        )

    # Build prompt
    prompt = build_mapping_prompt(columns_for_ai, AVAILABLE_SURROGATE_FIELDS)

    # Call AI
    messages = [
        ChatMessage(role="system", content=get_prompt("import_mapping").system),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.chat(
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent mapping
            max_tokens=2000,
        )

        logger.info(
            f"AI mapping response for org {org_id}: "
            f"{response.prompt_tokens} prompt tokens, "
            f"{response.completion_tokens} completion tokens"
        )

    except Exception as e:
        logger.error(f"AI request failed for org {org_id}: {e}")
        # Return original suggestions with error note
        for col in unmatched_columns:
            col.reason = f"{col.reason} (AI unavailable: {str(e)[:50]})"
        return unmatched_columns

    # Parse AI response
    ai_suggestions = parse_ai_response(response.content)

    # Create mapping of column -> AI suggestion
    ai_map = {s.column: s for s in ai_suggestions}

    # Update suggestions with AI recommendations
    updated_suggestions = []
    for col in unmatched_columns:
        if col.csv_column in ai_map:
            ai_suggestion = ai_map[col.csv_column]
            updated = ai_suggestion_to_column_suggestion(
                ai_suggestion,
                original_samples_map.get(col.csv_column, []),
            )
            updated_suggestions.append(updated)
        else:
            # AI didn't return suggestion for this column
            col.reason = f"{col.reason} (AI: no suggestion)"
            updated_suggestions.append(col)

    return updated_suggestions


async def ai_analyze_single_column(
    provider: AIProvider,
    column_name: str,
    samples: list[str],
) -> AIMappingSuggestion | None:
    """
    Analyze a single column with AI.

    Useful for re-analyzing a specific column after user edits.
    """
    masked_samples = mask_samples(samples)
    prompt = build_mapping_prompt(
        [{"column": column_name, "samples": masked_samples}],
        AVAILABLE_SURROGATE_FIELDS,
    )

    messages = [ChatMessage(role="user", content=prompt)]

    try:
        response = await provider.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=500,
        )

        suggestions = parse_ai_response(response.content)
        return suggestions[0] if suggestions else None

    except Exception as e:
        logger.error(f"AI single column analysis failed: {e}")
        return None
