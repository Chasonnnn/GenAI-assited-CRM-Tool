from app.core.stage_definitions import (
    DEFAULT_STAGE_ORDER,
    STAGE_TYPE_MAP,
    get_default_stage_defs,
    get_protected_system_stage_keys,
)
from app.schemas.pipeline_semantics import default_pipeline_feature_config, default_stage_semantics


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
        ("pending_docusign", "Pending-DocuSign"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("ready_to_match", "Ready to Match"),
        ("matched", "Matched"),
        ("medical_clearance_passed", "Medical Clearance Passed"),
        ("legal_clearance_passed", "Legal Clearance Passed"),
        ("transfer_cycle", "Transfer Cycle Initiated"),
        ("second_hcg_confirmed", "Second hCG confirmed"),
        ("heartbeat_confirmed", "Heartbeat Confirmed"),
        ("life_insurance_application_started", "Life Insurance Application Started"),
        ("ob_care_established", "OB Care Established"),
        ("pbo_process_started", "PBO Process Started"),
        ("anatomy_scanned", "Anatomy Scanned"),
        ("delivered", "Delivered"),
        ("on_hold", "On-Hold"),
        ("cold_leads", "Cold Leads"),
        ("lost", "Lost"),
        ("disqualified", "Disqualified"),
    ]

    stage_defs = get_default_stage_defs()

    assert [(stage["stage_key"], stage["label"]) for stage in stage_defs] == expected_stages


def test_stage_type_map_matches_default_surrogate_stage_defs() -> None:
    stage_defs = get_default_stage_defs()

    assert STAGE_TYPE_MAP == {stage["slug"]: stage["stage_type"] for stage in stage_defs}


def test_new_surrogate_platform_stages_use_expected_default_semantics() -> None:
    pending_docusign = default_stage_semantics("pending_docusign", "intake")
    assert pending_docusign["capabilities"]["counts_as_contacted"] is True
    assert pending_docusign["capabilities"]["eligible_for_matching"] is False
    assert pending_docusign["capabilities"]["locks_match_state"] is False
    assert pending_docusign["capabilities"]["shows_pregnancy_tracking"] is False
    assert pending_docusign["capabilities"]["tracks_interview_outcome"] is False
    assert pending_docusign["terminal_outcome"] == "none"
    assert pending_docusign["integration_bucket"] == "qualified"

    life_insurance = default_stage_semantics(
        "life_insurance_application_started",
        "post_approval",
    )
    assert life_insurance["capabilities"]["locks_match_state"] is True
    assert life_insurance["capabilities"]["shows_pregnancy_tracking"] is True
    assert life_insurance["capabilities"]["requires_delivery_details"] is False
    assert life_insurance["terminal_outcome"] == "none"
    assert life_insurance["integration_bucket"] == "converted"

    pbo_process = default_stage_semantics("pbo_process_started", "post_approval")
    assert pbo_process["capabilities"]["locks_match_state"] is True
    assert pbo_process["capabilities"]["shows_pregnancy_tracking"] is True
    assert pbo_process["capabilities"]["requires_delivery_details"] is False
    assert pbo_process["terminal_outcome"] == "none"
    assert pbo_process["integration_bucket"] == "converted"

    cold_leads = default_stage_semantics("cold_leads", "terminal")
    assert cold_leads["capabilities"]["counts_as_contacted"] is False
    assert cold_leads["capabilities"]["locks_match_state"] is False
    assert cold_leads["terminal_outcome"] == "none"
    assert cold_leads["integration_bucket"] == "none"


def test_default_surrogate_journey_mappings_cover_new_platform_stages_conservatively() -> None:
    feature_config = default_pipeline_feature_config()
    milestones = {
        milestone["slug"]: milestone["mapped_stage_keys"]
        for milestone in feature_config["journey"]["milestones"]
    }

    assert "pending_docusign" in milestones["screening_interviews"]
    assert "life_insurance_application_started" in milestones["ongoing_care"]
    assert "pbo_process_started" in milestones["ongoing_care"]
    assert all(
        "cold_leads" not in mapped_stage_keys for mapped_stage_keys in milestones.values()
    )


def test_cold_leads_is_not_a_protected_surrogate_system_stage() -> None:
    protected_stage_keys = get_protected_system_stage_keys()

    assert "cold_leads" not in protected_stage_keys
    assert {"lost", "disqualified"}.issubset(protected_stage_keys)
