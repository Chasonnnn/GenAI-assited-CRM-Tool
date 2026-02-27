import pytest

from app.services import meta_capi


@pytest.mark.parametrize(
    "status,expected",
    [
        ("contacted", meta_capi.META_STATUS_INTAKE),
        ("pre_qualified", meta_capi.META_STATUS_INTAKE),
        ("interview_scheduled", meta_capi.META_STATUS_INTAKE),
        ("application_submitted", meta_capi.META_STATUS_QUALIFIED),
        ("approved", meta_capi.META_STATUS_QUALIFIED),
        ("ready_to_match", meta_capi.META_STATUS_QUALIFIED),
        ("delivered", meta_capi.META_STATUS_QUALIFIED),
        ("disqualified", meta_capi.META_STATUS_DISQUALIFIED),
        ("lost", meta_capi.META_STATUS_LOST),
    ],
)
def test_map_case_status_to_meta_status(status, expected):
    assert meta_capi.map_surrogate_status_to_meta_status(status) == expected


@pytest.mark.parametrize(
    "status",
    ["new_unread", "archived", "restored", ""],
)
def test_map_case_status_to_meta_status_unknown(status):
    assert meta_capi.map_surrogate_status_to_meta_status(status) is None


@pytest.mark.parametrize(
    "from_status,to_status,expected",
    [
        ("new_unread", "contacted", True),
        ("contacted", "pre_qualified", False),
        ("pre_qualified", "application_submitted", True),
        ("application_submitted", "under_review", False),
        ("approved", "ready_to_match", False),
        ("contacted", "disqualified", True),
        ("disqualified", "ready_to_match", True),
        ("", "contacted", True),
        ("archived", "restored", False),
    ],
)
def test_should_send_capi_event(from_status, to_status, expected):
    assert meta_capi.should_send_capi_event(from_status, to_status) is expected
