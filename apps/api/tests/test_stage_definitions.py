from app.core.stage_definitions import DEFAULT_STAGE_ORDER, get_default_stage_defs


def test_application_submitted_before_interview_scheduled() -> None:
    assert DEFAULT_STAGE_ORDER.index("application_submitted") < DEFAULT_STAGE_ORDER.index(
        "interview_scheduled"
    )


def test_default_stage_defs_follow_default_order() -> None:
    stage_defs = get_default_stage_defs()
    assert [stage["slug"] for stage in stage_defs] == DEFAULT_STAGE_ORDER


def test_on_hold_stage_is_positioned_before_terminal_outcomes() -> None:
    assert DEFAULT_STAGE_ORDER.index("on_hold") < DEFAULT_STAGE_ORDER.index("lost")
    assert DEFAULT_STAGE_ORDER.index("on_hold") < DEFAULT_STAGE_ORDER.index("disqualified")


def test_on_hold_stage_uses_paused_type_and_muted_brick_color() -> None:
    stage_defs = {stage["slug"]: stage for stage in get_default_stage_defs()}

    assert stage_defs["on_hold"]["stage_type"] == "paused"
    assert stage_defs["on_hold"]["color"] == "#B4536A"
