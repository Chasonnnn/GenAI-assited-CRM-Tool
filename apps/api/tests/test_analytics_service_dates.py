from datetime import date, datetime, timezone


def test_normalize_date_bounds_inclusive_end():
    from app.services import analytics_service

    start_dt, end_dt = analytics_service._normalize_date_bounds(
        date(2024, 1, 1),
        date(2024, 1, 31),
    )

    assert start_dt == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert end_dt == datetime(2024, 2, 1, tzinfo=timezone.utc)


def test_normalize_date_bounds_none_returns_none():
    from app.services import analytics_service

    start_dt, end_dt = analytics_service._normalize_date_bounds(None, None)

    assert start_dt is None
    assert end_dt is None
