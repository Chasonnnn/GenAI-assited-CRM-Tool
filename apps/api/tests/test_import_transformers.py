from decimal import Decimal

from app.services.import_transformers import transform_height_flexible


def test_transform_height_flexible_interprets_feet_inches_shorthand() -> None:
    result = transform_height_flexible("5.6")
    assert result.success is True
    assert result.value == Decimal("5.5")


def test_transform_height_flexible_interprets_feet_inches_shorthand_with_unit() -> None:
    result = transform_height_flexible("5.6 ft")
    assert result.success is True
    assert result.value == Decimal("5.5")


def test_transform_height_flexible_keeps_decimal_feet_for_long_fraction() -> None:
    result = transform_height_flexible("5.33")
    assert result.success is True
    assert result.value == Decimal("5.3")


def test_transform_height_flexible_interprets_space_separated_feet_inches() -> None:
    result = transform_height_flexible("5 6")
    assert result.success is True
    assert result.value == Decimal("5.5")


def test_transform_height_flexible_interprets_space_separated_feet_inches_rounded() -> None:
    result = transform_height_flexible("5 7")
    assert result.success is True
    assert result.value == Decimal("5.6")


def test_transform_height_flexible_interprets_feet_only_integer() -> None:
    result = transform_height_flexible("5")
    assert result.success is True
    assert result.value == Decimal("5.0")


def test_transform_height_flexible_interprets_feet_only_integer_with_trailing_space() -> None:
    result = transform_height_flexible("5 ")
    assert result.success is True
    assert result.value == Decimal("5.0")
