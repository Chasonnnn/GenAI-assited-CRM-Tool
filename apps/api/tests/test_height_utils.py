from decimal import Decimal

from app.utils.height import canonicalize_height_ft, height_ft_to_total_inches


def test_canonicalize_height_ft_preserves_displayed_inches_for_legacy_decimal_values() -> None:
    assert canonicalize_height_ft(Decimal("5.3")) == Decimal("5.33")
    assert canonicalize_height_ft(Decimal("4.8")) == Decimal("4.83")


def test_height_ft_to_total_inches_rounds_to_nearest_inch_for_legacy_and_canonical_values() -> None:
    assert height_ft_to_total_inches(Decimal("4.8")) == 58
    assert height_ft_to_total_inches(Decimal("4.92")) == 59
