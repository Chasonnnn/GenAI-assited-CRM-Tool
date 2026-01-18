from app.core.stage_definitions import DEFAULT_STAGE_ORDER, get_default_stage_defs


def test_application_submitted_before_interview_scheduled() -> None:
    assert DEFAULT_STAGE_ORDER.index("application_submitted") < DEFAULT_STAGE_ORDER.index(
        "interview_scheduled"
    )


def test_default_stage_defs_follow_default_order() -> None:
    stage_defs = get_default_stage_defs()
    assert [stage["slug"] for stage in stage_defs] == DEFAULT_STAGE_ORDER
