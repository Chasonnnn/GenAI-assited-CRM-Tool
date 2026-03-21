from app.core.stage_definitions import DEFAULT_STAGE_ORDER, STAGE_TYPE_MAP, get_default_stage_defs


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


def test_default_stage_defs_match_recommended_platform_labels() -> None:
    expected_stages = [
        ("new_unread", "New Unread"),
        ("contacted", "Contacted"),
        ("pre_qualified", "Pre-Qualified"),
        ("application_submitted", "Application Submitted"),
        ("interview_scheduled", "Interview Scheduled"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("ready_to_match", "Ready to Match"),
        ("matched", "Matched"),
        ("medical_clearance_passed", "Medical Clearance Passed"),
        ("legal_clearance_passed", "Legal Clearance Passed"),
        ("transfer_cycle", "Transfer Cycle Initiated"),
        ("second_hcg_confirmed", "Second hCG confirmed"),
        ("heartbeat_confirmed", "Heartbeat Confirmed"),
        ("ob_care_established", "OB Care Established"),
        ("anatomy_scanned", "Anatomy Scanned"),
        ("delivered", "Delivered"),
        ("on_hold", "On-Hold"),
        ("lost", "Lost"),
        ("disqualified", "Disqualified"),
    ]

    stage_defs = get_default_stage_defs()

    assert [(stage["stage_key"], stage["label"]) for stage in stage_defs] == expected_stages


def test_stage_type_map_matches_default_surrogate_stage_defs() -> None:
    stage_defs = get_default_stage_defs()

    assert STAGE_TYPE_MAP == {stage["slug"]: stage["stage_type"] for stage in stage_defs}
