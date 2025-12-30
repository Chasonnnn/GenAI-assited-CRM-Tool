import pytest

from app.services import meta_capi


@pytest.mark.parametrize(
    "status,expected",
    [
        ("contacted", meta_capi.META_STATUS_INTAKE),
        ("qualified", meta_capi.META_STATUS_INTAKE),
        ("applied", meta_capi.META_STATUS_INTAKE),
        ("followup_scheduled", meta_capi.META_STATUS_INTAKE),
        ("application_submitted", meta_capi.META_STATUS_QUALIFIED),
        ("approved", meta_capi.META_STATUS_QUALIFIED),
        ("pending_match", meta_capi.META_STATUS_QUALIFIED),
        ("delivered", meta_capi.META_STATUS_QUALIFIED),
        ("disqualified", meta_capi.META_STATUS_DISQUALIFIED),
        ("lost", meta_capi.META_STATUS_LOST),
    ],
)
def test_map_case_status_to_meta_status(status, expected):
    assert meta_capi.map_case_status_to_meta_status(status) == expected


@pytest.mark.parametrize(
    "status",
    ["new_unread", "archived", "restored", ""],
)
def test_map_case_status_to_meta_status_unknown(status):
    assert meta_capi.map_case_status_to_meta_status(status) is None


@pytest.mark.parametrize(
    "from_status,to_status,expected",
    [
        ("new_unread", "contacted", True),
        ("contacted", "qualified", False),
        ("qualified", "application_submitted", True),
        ("application_submitted", "under_review", False),
        ("approved", "pending_handoff", False),
        ("contacted", "disqualified", True),
        ("disqualified", "pending_match", True),
        ("", "contacted", True),
        ("archived", "restored", False),
    ],
)
def test_should_send_capi_event(from_status, to_status, expected):
    assert meta_capi.should_send_capi_event(from_status, to_status) is expected
