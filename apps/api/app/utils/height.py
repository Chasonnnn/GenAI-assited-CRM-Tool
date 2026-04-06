"""Shared helpers for canonical surrogate height handling."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import Float, cast, func
from sqlalchemy.sql.elements import ColumnElement


INCHES_PER_FOOT = Decimal("12")
HEIGHT_CANONICAL_QUANTUM = Decimal("0.01")
WHOLE_INCH_QUANTUM = Decimal("1")


def _coerce_decimal(value: Decimal | float | int | str) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Height must be numeric") from exc


def height_ft_to_total_inches(value: Decimal | float | int | str | None) -> int | None:
    """Convert decimal feet to the nearest whole inch."""
    if value is None:
        return None

    decimal_value = _coerce_decimal(value)
    return int(
        (decimal_value * INCHES_PER_FOOT).quantize(
            WHOLE_INCH_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
    )


def total_inches_to_height_ft(total_inches: int | Decimal | None) -> Decimal | None:
    """Convert whole inches to canonical decimal feet."""
    if total_inches is None:
        return None

    decimal_inches = Decimal(str(total_inches))
    if decimal_inches < 0:
        raise ValueError("Height inches must be non-negative")

    return (decimal_inches / INCHES_PER_FOOT).quantize(
        HEIGHT_CANONICAL_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def canonicalize_height_ft(value: Decimal | float | int | str | None) -> Decimal | None:
    """Normalize decimal feet to the canonical exact-to-the-inch representation."""
    total_inches = height_ft_to_total_inches(value)
    if total_inches is None:
        return None
    return total_inches_to_height_ft(total_inches)


def height_ft_to_total_inches_expr(value_expr: ColumnElement[object]) -> ColumnElement[float]:
    """SQL expression version of the canonical rounded-inch conversion."""
    return cast(func.round(cast(value_expr, Float) * 12.0), Float)
