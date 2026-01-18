from app.db.enums import IntendedParentStatus, SurrogateSource
from scripts import seed_mock_data


def test_seed_surrogate_sources_match_enum() -> None:
    allowed = {source.value for source in SurrogateSource}
    assert set(seed_mock_data.SURROGATE_SOURCES).issubset(allowed)


def test_seed_intended_parent_statuses_match_enum() -> None:
    allowed = {status.value for status in IntendedParentStatus}
    assert set(seed_mock_data.IP_STATUSES).issubset(allowed)
