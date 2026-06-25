"""Shared normalization for incoming surrogate records from external sources."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import UnionType
from typing import Any, Mapping, Union, get_args, get_origin

from pydantic import EmailStr, ValidationError

from app.schemas.surrogate import SurrogateCreate, SurrogateUpdate
from app.services.import_transformers import get_suggested_transformer, transform_value
from app.utils.journey_timing import normalize_journey_timing_preference
from app.utils.normalization import normalize_email, normalize_name


REQUIRED_SURROGATE_CREATE_FIELDS = frozenset({"full_name", "email"})


def _unwrap_annotation(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    if origin in (UnionType, Union):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return _unwrap_annotation(args[0])
        return annotation
    origin_name = str(origin)
    if "Annotated" in origin_name:
        args = get_args(annotation)
        if args:
            return _unwrap_annotation(args[0])
    return annotation


def _surrogate_field_type_from_annotation(annotation: Any) -> str | None:
    base = _unwrap_annotation(annotation)
    if base is bool:
        return "bool"
    if base is int:
        return "int"
    if base is Decimal:
        return "decimal"
    if base is date:
        return "date"
    if base is EmailStr:
        return "str"
    if base is str:
        return "str"
    if isinstance(base, type):
        if issubclass(base, bool):
            return "bool"
        if issubclass(base, int):
            return "int"
        if issubclass(base, Decimal):
            return "decimal"
        if issubclass(base, date):
            return "date"
        if issubclass(base, EmailStr):
            return "str"
        if issubclass(base, str):
            return "str"
    return None


def _build_surrogate_field_types() -> dict[str, str]:
    field_types: dict[str, str] = {}
    for model in (SurrogateCreate, SurrogateUpdate):
        for field_name, model_field in model.model_fields.items():
            field_type = _surrogate_field_type_from_annotation(model_field.annotation)
            if field_type:
                field_types[field_name] = field_type
    return field_types


SURROGATE_FIELD_TYPES: dict[str, str] = _build_surrogate_field_types()


def coerce_surrogate_field_value(surrogate_field: str, value: Any) -> Any:
    """Normalize one mapped value into the shape expected by SurrogateCreate/Update."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None

    if surrogate_field == "journey_timing_preference":
        normalized = normalize_journey_timing_preference(value)
        if normalized is None:
            raise ValueError(f"Invalid journey timing for {surrogate_field}")
        return normalized

    transformer_name = get_suggested_transformer(surrogate_field)
    if transformer_name:
        transformed = transform_value(transformer_name, str(value))
        if transformed.success:
            return transformed.value
        raise ValueError(
            transformed.error or f"Invalid value for {surrogate_field}: {value}"
        )

    field_type = SURROGATE_FIELD_TYPES.get(surrogate_field)
    if field_type == "str":
        return str(value)
    if field_type == "bool":
        return _parse_bool(value)
    if field_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer for {surrogate_field}") from exc
    if field_type == "decimal":
        try:
            return Decimal(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid decimal for {surrogate_field}") from exc
    if field_type == "date":
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"Invalid date for {surrogate_field}") from exc
        raise ValueError(f"Invalid date for {surrogate_field}")
    return value


def normalize_surrogate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize mapped incoming data while ignoring unsupported surrogate fields."""
    normalized: dict[str, Any] = {}
    for field_name, value in payload.items():
        if field_name not in SURROGATE_FIELD_TYPES:
            continue
        normalized[field_name] = coerce_surrogate_field_value(field_name, value)

    full_name = normalized.get("full_name")
    if isinstance(full_name, str):
        normalized["full_name"] = normalize_name(full_name) or full_name.strip()
    email = normalized.get("email")
    if isinstance(email, str):
        normalized["email"] = normalize_email(email) or email.strip()

    return normalized


def _normalize_surrogate_payload_lenient(
    payload: Mapping[str, Any],
    *,
    required_fields: frozenset[str],
) -> tuple[dict[str, Any], list[str]]:
    normalized: dict[str, Any] = {}
    dropped: list[str] = []
    for field_name, value in payload.items():
        if field_name not in SURROGATE_FIELD_TYPES:
            continue
        try:
            normalized[field_name] = coerce_surrogate_field_value(field_name, value)
        except ValueError:
            if field_name in required_fields:
                raise
            dropped.append(field_name)

    full_name = normalized.get("full_name")
    if isinstance(full_name, str):
        normalized["full_name"] = normalize_name(full_name) or full_name.strip()
    email = normalized.get("email")
    if isinstance(email, str):
        normalized["email"] = normalize_email(email) or email.strip()

    return normalized, sorted(dropped)


def build_surrogate_create_from_payload(
    payload: Mapping[str, Any],
    *,
    lenient: bool = False,
    required_fields: frozenset[str] = REQUIRED_SURROGATE_CREATE_FIELDS,
) -> tuple[SurrogateCreate, list[str]]:
    """
    Build SurrogateCreate from mapped incoming data.

    Strict mode raises on any invalid mapped value. Lenient mode drops invalid optional
    fields, but required identity fields remain hard failures.
    """
    if not lenient:
        normalized = normalize_surrogate_payload(payload)
        return SurrogateCreate(**normalized), []

    normalized, coercion_dropped_fields = _normalize_surrogate_payload_lenient(
        payload,
        required_fields=required_fields,
    )
    try:
        return SurrogateCreate(**normalized), coercion_dropped_fields
    except ValidationError as exc:
        invalid_fields: set[str] = set()
        has_required_error = False
        for err in exc.errors():
            loc = err.get("loc") or []
            field = loc[0] if loc else None
            if not isinstance(field, str):
                continue
            if field in required_fields:
                has_required_error = True
            elif field in normalized:
                invalid_fields.add(field)

        if has_required_error or not invalid_fields:
            raise

        sanitized = dict(normalized)
        for field in invalid_fields:
            sanitized.pop(field, None)

        return SurrogateCreate(**sanitized), sorted(
            {*coercion_dropped_fields, *invalid_fields}
        )


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes", "1", "y"}:
            return True
        if cleaned in {"false", "no", "0", "n"}:
            return False
    raise ValueError("Invalid boolean value")
