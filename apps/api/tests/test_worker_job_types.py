from app.db.enums import JobType


def test_parse_worker_job_types_filters_invalid():
    from app.worker import parse_worker_job_types

    result = parse_worker_job_types("send_email, campaign_send, nope")
    assert result == [JobType.SEND_EMAIL.value, JobType.CAMPAIGN_SEND.value]


def test_parse_worker_job_types_empty_returns_none():
    from app.worker import parse_worker_job_types

    assert parse_worker_job_types("") is None


def test_parse_worker_job_types_invalid_returns_empty():
    from app.worker import parse_worker_job_types

    assert parse_worker_job_types("nope") == []
