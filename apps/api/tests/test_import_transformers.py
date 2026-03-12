from decimal import Decimal

from app.services.import_transformers import transform_height_flexible, transform_int_flexible


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


def test_transform_height_flexible_interprets_spelled_out_feet_inches() -> None:
    result = transform_height_flexible("5 feet 4 inches")
    assert result.success is True
    assert result.value == Decimal("5.3")


def test_transform_height_flexible_interprets_three_digit_feet_inches_shorthand() -> None:
    result = transform_height_flexible("411")
    assert result.success is True
    assert result.value == Decimal("4.9")


def test_transform_height_flexible_interprets_feet_units_without_inches_units() -> None:
    result = transform_height_flexible("5ft 6")
    assert result.success is True
    assert result.value == Decimal("5.5")


def test_transform_height_flexible_interprets_quote_before_feet_unit() -> None:
    result = transform_height_flexible('4"ft 11')
    assert result.success is True
    assert result.value == Decimal("4.9")


def test_transform_height_flexible_interprets_curly_quote_before_feet_unit() -> None:
    result = transform_height_flexible("4”ft 11")
    assert result.success is True
    assert result.value == Decimal("4.9")


def test_transform_height_flexible_interprets_inline_inch_suffix() -> None:
    result = transform_height_flexible("5'3inch")
    assert result.success is True
    assert result.value == Decimal("5.3")


def test_transform_height_flexible_interprets_label_prefixed_dash_separated_feet_inches() -> None:
    result = transform_height_flexible("Height: 4-5")
    assert result.success is True
    assert result.value == Decimal("4.4")


def test_transform_height_flexible_interprets_label_prefixed_total_inches() -> None:
    result = transform_height_flexible("Height: 67 inches")
    assert result.success is True
    assert result.value == Decimal("5.6")


def test_transform_height_flexible_interprets_label_prefixed_short_inches_height() -> None:
    result = transform_height_flexible("Height: 5-1")
    assert result.success is True
    assert result.value == Decimal("5.1")


def test_transform_int_flexible_interprets_common_word_counts() -> None:
    assert transform_int_flexible("No").value == 0
    assert transform_int_flexible("One").value == 1
    assert transform_int_flexible("Five").value == 5


def test_transform_int_flexible_extracts_wordy_delivery_count() -> None:
    result = transform_int_flexible("Two vaginal deliveries")
    assert result.success is True
    assert result.value == 2


def test_transform_int_flexible_extracts_label_prefixed_weight() -> None:
    result = transform_int_flexible("Weight: 160 lbs")
    assert result.success is True
    assert result.value == 160
