"""Build form-aware eligibility checklist payloads for surrogates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.models import FormSubmission, Surrogate
from app.schemas.surrogate import SurrogateEligibilityChecklistItem
from app.services import form_submission_service
from app.utils.journey_timing import (
    JOURNEY_TIMING_FIELD_KEY_ALIASES,
    JOURNEY_TIMING_LABEL_ALIASES,
    get_journey_timing_preference_label,
    normalize_journey_timing_preference,
    normalize_journey_timing_text,
)


ChecklistValueType = Literal["boolean", "text", "number"]


@dataclass(frozen=True)
class ChecklistSpec:
    key: str
    label: str
    type: ChecklistValueType
    legacy_visible_without_submission: bool = True
    alias_field_keys: tuple[str, ...] = field(default_factory=tuple)
    alias_labels: tuple[str, ...] = field(default_factory=tuple)


CHECKLIST_SPECS: tuple[ChecklistSpec, ...] = (
    ChecklistSpec("is_age_eligible", "Age Eligible (21-36)", "boolean"),
    ChecklistSpec("is_citizen_or_pr", "US Citizen or PR", "boolean"),
    ChecklistSpec("has_child", "Has Child", "boolean"),
    ChecklistSpec("is_non_smoker", "Non-Smoker", "boolean"),
    ChecklistSpec("has_surrogate_experience", "Prior Surrogate Experience", "boolean"),
    ChecklistSpec(
        "journey_timing_preference",
        "Journey Timing",
        "text",
        legacy_visible_without_submission=False,
        alias_field_keys=JOURNEY_TIMING_FIELD_KEY_ALIASES,
        alias_labels=JOURNEY_TIMING_LABEL_ALIASES,
    ),
    ChecklistSpec("num_deliveries", "Deliveries", "number"),
    ChecklistSpec("num_csections", "C-sections", "number"),
)


@dataclass
class SubmissionChecklistContext:
    submission: FormSubmission
    fields_by_key: dict[str, Any]
    visible_field_keys: set[str]
    mapping_by_surrogate_field: dict[str, list[str]]
    answers: dict[str, Any]


def build_eligibility_checklist(
    db: Session,
    surrogate: Surrogate,
) -> list[SurrogateEligibilityChecklistItem]:
    submission = form_submission_service.get_latest_submission_for_surrogate(
        db=db,
        org_id=surrogate.organization_id,
        surrogate_id=surrogate.id,
    )
    submission_context = _build_submission_context(db, submission)

    items: list[SurrogateEligibilityChecklistItem] = []
    for spec in CHECKLIST_SPECS:
        structured_value = getattr(surrogate, spec.key, None)
        fallback_value, asked_in_submission = _resolve_submission_value(spec, submission_context)
        has_structured_value = structured_value not in (None, "")
        resolved_value = structured_value if has_structured_value else fallback_value

        if not _should_include_item(
            spec=spec,
            submission_context=submission_context,
            asked_in_submission=asked_in_submission,
            has_structured_value=has_structured_value,
            resolved_value=resolved_value,
        ):
            continue

        items.append(
            SurrogateEligibilityChecklistItem(
                key=spec.key,
                label=spec.label,
                type=spec.type,
                value=resolved_value,
                display_value=_format_display_value(spec, resolved_value),
            )
        )

    return items


def _build_submission_context(
    db: Session, submission: FormSubmission | None
) -> SubmissionChecklistContext | None:
    if not submission or not submission.schema_snapshot:
        return None

    try:
        schema = form_submission_service.parse_schema(submission.schema_snapshot)
        fields_by_key = form_submission_service.flatten_fields(schema)
    except Exception:
        return None

    answers = submission.answers_json or {}
    visible_field_keys = {
        key
        for key, field in fields_by_key.items()
        if form_submission_service._is_field_visible(field, answers, fields_by_key)
        or answers.get(key) not in (None, "", [])
    }

    mapping_by_surrogate_field: dict[str, list[str]] = {}
    for mapping in form_submission_service._get_submission_mappings(db, submission):
        field_key = mapping.get("field_key")
        surrogate_field = mapping.get("surrogate_field")
        if not field_key or not surrogate_field or field_key not in visible_field_keys:
            continue
        mapping_by_surrogate_field.setdefault(surrogate_field, []).append(field_key)

    return SubmissionChecklistContext(
        submission=submission,
        fields_by_key=fields_by_key,
        visible_field_keys=visible_field_keys,
        mapping_by_surrogate_field=mapping_by_surrogate_field,
        answers=answers,
    )


def _resolve_submission_value(
    spec: ChecklistSpec, context: SubmissionChecklistContext | None
) -> tuple[bool | str | int | None, bool]:
    if context is None:
        return None, False

    matching_field_keys = list(context.mapping_by_surrogate_field.get(spec.key, []))
    if not matching_field_keys and spec.alias_field_keys:
        alias_key_set = {normalize_journey_timing_text(value) for value in spec.alias_field_keys}
        alias_label_set = {normalize_journey_timing_text(value) for value in spec.alias_labels}
        for field_key in context.visible_field_keys:
            field = context.fields_by_key[field_key]
            if normalize_journey_timing_text(field_key) in alias_key_set:
                matching_field_keys.append(field_key)
                continue
            if normalize_journey_timing_text(field.label) in alias_label_set:
                matching_field_keys.append(field_key)

    asked_in_submission = len(matching_field_keys) > 0
    for field_key in matching_field_keys:
        raw_value = context.answers.get(field_key)
        coerced_value = _coerce_checklist_value(spec, raw_value)
        if coerced_value not in (None, ""):
            return coerced_value, asked_in_submission

    return None, asked_in_submission


def _should_include_item(
    *,
    spec: ChecklistSpec,
    submission_context: SubmissionChecklistContext | None,
    asked_in_submission: bool,
    has_structured_value: bool,
    resolved_value: bool | str | int | None,
) -> bool:
    if has_structured_value:
        return True

    if submission_context is None:
        if spec.type == "boolean":
            return spec.legacy_visible_without_submission
        if spec.type == "number":
            return spec.legacy_visible_without_submission and resolved_value is not None
        return resolved_value is not None

    return asked_in_submission


def _coerce_checklist_value(spec: ChecklistSpec, raw_value: Any) -> bool | str | int | None:
    if raw_value in (None, "", []):
        return None

    if spec.key == "journey_timing_preference":
        return normalize_journey_timing_preference(raw_value)

    try:
        coerced = form_submission_service._coerce_surrogate_value(spec.key, raw_value)
    except ValueError:
        return None
    if isinstance(coerced, bool | int | str):
        return coerced
    return coerced


def _format_display_value(spec: ChecklistSpec, value: bool | str | int | None) -> str:
    if spec.type == "boolean":
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "-"

    if value in (None, ""):
        return "-"

    if spec.key == "journey_timing_preference" and isinstance(value, str):
        return get_journey_timing_preference_label(value)

    return str(value)
