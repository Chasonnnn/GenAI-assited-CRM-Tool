"""Apply the unlanded candidate only in a disposable pytest process."""


def pytest_configure(config):
    from phase_filter_candidate import _stage_filter

    from app.services import record_scope_service

    record_scope_service._stage_filter = _stage_filter
