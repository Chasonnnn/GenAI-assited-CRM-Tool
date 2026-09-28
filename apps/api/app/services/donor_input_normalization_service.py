"""Lenient normalization for incoming donor records from Meta, Zapier, and CRM forms.

Mirrors ``surrogate_input_normalization_service``: invalid optional values are dropped
and reported by field name, while the identity fields stay hard requirements.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.donor import DonorCreate, normalize_donor_source
from app.schemas.donor_profile import DonorProfileFields
from app.services.surrogate_input_normalization_service import coerce_surrogate_field_value
from app.utils.normalization import normalize_email, normalize_name

REQUIRED_DONOR_CREATE_FIELDS = frozenset({"full_name", "email"})
DONOR_CREATE_INPUT_FIELDS = ("full_name", "email", "phone", "state", "education")
# Donor profile fields that intake mappings may set when the donor is created.
DONOR_INTAKE_PROFILE_FIELDS = ("date_of_birth", "race", "height_ft", "weight_lb")
DONOR_INTAKE_FIELDS = (*DONOR_CREATE_INPUT_FIELDS, *DONOR_INTAKE_PROFILE_FIELDS)


@dataclass(frozen=True)
class DonorIntakeInput:
    create: DonorCreate
    profile: dict[str, Any] = field(default_factory=dict)
    dropped_fields: list[str] = field(default_factory=list)


def _coerce(field_name: str, value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    # Donor intake fields share names and formats with surrogate fields, so they use
    # the same transformers (phone, state, flexible dates, height, integers).
    return coerce_surrogate_field_value(field_name, value)


def _source(value: Any, fallback_source: str) -> str:
    try:
        return normalize_donor_source(value) or fallback_source
    except ValueError:
        return fallback_source


def _validate_dropping_invalid[ModelT: BaseModel](
    model: type[ModelT],
    values: dict[str, Any],
    *,
    required_fields: frozenset[str],
) -> tuple[ModelT, set[str]]:
    try:
        return model(**values), set()
    except ValidationError as exc:
        invalid_fields: set[str] = set()
        for error in exc.errors():
            location = error.get("loc") or ()
            field_name = location[0] if location else None
            if not isinstance(field_name, str) or field_name not in values:
                raise
            if field_name in required_fields:
                raise
            invalid_fields.add(field_name)
        sanitized = {key: value for key, value in values.items() if key not in invalid_fields}
        return model(**sanitized), invalid_fields


def build_donor_create_from_payload(
    payload: Mapping[str, Any],
    *,
    donor_type: str,
    fallback_source: str,
    required_fields: frozenset[str] = REQUIRED_DONOR_CREATE_FIELDS,
) -> DonorIntakeInput:
    """Build DonorCreate plus intake profile values from mapped incoming data.

    Invalid optional values are dropped and listed in ``dropped_fields``. Invalid or
    missing required fields raise. An unknown source becomes ``fallback_source``.
    """
    dropped: set[str] = set()
    create_values: dict[str, Any] = {}
    profile_values: dict[str, Any] = {}
    for field_name in DONOR_INTAKE_FIELDS:
        if field_name not in payload:
            continue
        try:
            value = _coerce(field_name, payload[field_name])
        except ValueError:
            if field_name in required_fields:
                raise
            dropped.add(field_name)
            continue
        if value is None:
            continue
        if field_name in DONOR_INTAKE_PROFILE_FIELDS:
            profile_values[field_name] = value
        else:
            create_values[field_name] = value

    full_name = create_values.get("full_name")
    if isinstance(full_name, str):
        create_values["full_name"] = normalize_name(full_name) or full_name.strip()
    email = create_values.get("email")
    if isinstance(email, str):
        create_values["email"] = normalize_email(email) or email.strip()

    create, invalid_create = _validate_dropping_invalid(
        DonorCreate,
        {
            **create_values,
            "donor_type": donor_type,
            "source": _source(payload.get("source"), fallback_source),
        },
        required_fields=required_fields | {"donor_type", "source"},
    )
    profile, invalid_profile = _validate_dropping_invalid(
        DonorProfileFields,
        profile_values,
        required_fields=frozenset(),
    )
    dropped |= invalid_create | invalid_profile
    return DonorIntakeInput(
        create=create,
        profile={
            field_name: getattr(profile, field_name)
            for field_name in DONOR_INTAKE_PROFILE_FIELDS
            if field_name in profile_values and field_name not in invalid_profile
        },
        dropped_fields=sorted(dropped),
    )
