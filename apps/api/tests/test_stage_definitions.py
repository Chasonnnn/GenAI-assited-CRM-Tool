import pytest

from app.core.stage_definitions import (
    DEFAULT_STAGE_ORDER,
    DEFAULT_STAGE_ORDER_BY_ENTITY,
    EGG_DONOR_PIPELINE_ENTITY,
    SPERM_DONOR_PIPELINE_ENTITY,
    STAGE_TYPE_MAP,
    VALID_PIPELINE_ENTITY_TYPES,
    get_default_stage_defs,
    get_protected_system_stage_keys,
    normalize_pipeline_entity_type,
)
from app.schemas.pipeline_semantics import default_pipeline_feature_config, default_stage_semantics


def test_application_submitted_before_interview_scheduled() -> None:
    assert DEFAULT_STAGE_ORDER.index("application_submitted") < DEFAULT_STAGE_ORDER.index(
        "interview_scheduled"
    )


def test_default_stage_defs_follow_default_order() -> None:
    stage_defs = get_default_stage_defs()
    assert [stage["slug"] for stage in stage_defs] == DEFAULT_STAGE_ORDER


def test_every_default_pipeline_has_unique_stage_keys() -> None:
    for entity_type, stage_keys in DEFAULT_STAGE_ORDER_BY_ENTITY.items():
        assert len(stage_keys) == len(set(stage_keys)), entity_type


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
    new_unread = default_stage_semantics("new_unread", "intake")
    assert new_unread["capabilities"]["counts_as_contacted"] is False
    assert new_unread["terminal_outcome"] == "none"
    assert new_unread["integration_bucket"] == "none"
    assert new_unread["analytics_bucket"] == "new_unread"
    assert new_unread["suggestion_profile_key"] == "new_unread_followup"

    contacted = default_stage_semantics("contacted", "intake")
    assert contacted["capabilities"]["counts_as_contacted"] is True
    assert contacted["terminal_outcome"] == "none"
    assert contacted["integration_bucket"] == "intake"
    assert contacted["analytics_bucket"] == "contacted"
    assert contacted["suggestion_profile_key"] == "contacted_followup"

    pending_docusign = default_stage_semantics("pending_docusign", "intake")
    assert pending_docusign["capabilities"]["counts_as_contacted"] is True
    assert pending_docusign["capabilities"]["eligible_for_matching"] is False
    assert pending_docusign["capabilities"]["locks_match_state"] is False
    assert pending_docusign["capabilities"]["shows_pregnancy_tracking"] is False
    assert pending_docusign["capabilities"]["tracks_interview_outcome"] is False
    assert pending_docusign["terminal_outcome"] == "none"
    assert pending_docusign["integration_bucket"] == "qualified"
    assert pending_docusign["suggestion_profile_key"] is None

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
    assert all("cold_leads" not in mapped_stage_keys for mapped_stage_keys in milestones.values())


def test_cold_leads_is_not_a_protected_surrogate_system_stage() -> None:
    protected_stage_keys = get_protected_system_stage_keys()

    assert "cold_leads" not in protected_stage_keys
    assert {"lost", "disqualified"}.issubset(protected_stage_keys)


def test_egg_donor_pipeline_defaults_follow_the_operational_lifecycle() -> None:
    assert [stage["stage_key"] for stage in get_default_stage_defs(EGG_DONOR_PIPELINE_ENTITY)] == [
        "new",
        "contacted",
        "pre_screening",
        "application_submitted",
        "medical_records_review",
        "psychological_screening",
        "ready_to_match",
        "matched",
        "cycle_in_progress",
        "retrieval_complete",
        "on_hold",
        "disqualified",
        "closed",
    ]


def test_sperm_donor_pipeline_defaults_follow_the_operational_lifecycle() -> None:
    assert [
        stage["stage_key"] for stage in get_default_stage_defs(SPERM_DONOR_PIPELINE_ENTITY)
    ] == [
        "new",
        "contacted",
        "pre_screening",
        "application_submitted",
        "semen_analysis",
        "medical_genetic_screening",
        "available",
        "matched",
        "collection_in_progress",
        "donation_complete",
        "on_hold",
        "disqualified",
        "closed",
    ]


def test_donor_defaults_keep_target_specific_labels_categories_and_system_anchors() -> None:
    egg_defs = {
        stage["stage_key"]: stage for stage in get_default_stage_defs(EGG_DONOR_PIPELINE_ENTITY)
    }
    sperm_defs = {
        stage["stage_key"]: stage
        for stage in get_default_stage_defs(SPERM_DONOR_PIPELINE_ENTITY)
    }

    assert egg_defs["medical_records_review"]["label"] == "Medical Records Review"
    assert egg_defs["cycle_in_progress"]["stage_type"] == "post_approval"
    assert sperm_defs["medical_genetic_screening"]["label"] == "Medical & Genetic Screening"
    assert sperm_defs["available"]["stage_type"] == "post_approval"
    assert egg_defs["on_hold"]["stage_type"] == "paused"
    assert sperm_defs["disqualified"]["stage_type"] == "terminal"
    assert get_protected_system_stage_keys(EGG_DONOR_PIPELINE_ENTITY) == {"new", "closed"}
    assert get_protected_system_stage_keys(SPERM_DONOR_PIPELINE_ENTITY) == {"new", "closed"}


def test_donor_default_semantics_are_target_specific_and_not_surrogate_fallbacks() -> None:
    egg_ready = default_stage_semantics(
        "ready_to_match", "post_approval", EGG_DONOR_PIPELINE_ENTITY
    )
    sperm_available = default_stage_semantics(
        "available", "post_approval", SPERM_DONOR_PIPELINE_ENTITY
    )
    sperm_ready = default_stage_semantics(
        "ready_to_match", "post_approval", SPERM_DONOR_PIPELINE_ENTITY
    )

    assert egg_ready["capabilities"]["eligible_for_matching"] is True
    assert sperm_available["capabilities"]["eligible_for_matching"] is True
    assert sperm_ready["capabilities"]["eligible_for_matching"] is False
    assert egg_ready["capabilities"]["shows_pregnancy_tracking"] is False
    assert sperm_available["suggestion_profile_key"] is None


def test_donor_pipeline_default_definitions_are_independent() -> None:
    egg_defs = get_default_stage_defs(EGG_DONOR_PIPELINE_ENTITY)
    sperm_defs = get_default_stage_defs(SPERM_DONOR_PIPELINE_ENTITY)

    assert egg_defs != sperm_defs
    assert egg_defs is not sperm_defs
    assert egg_defs[0] is not sperm_defs[0]


def test_pipeline_entity_normalization_fails_closed_for_non_empty_unknown_types() -> None:
    assert VALID_PIPELINE_ENTITY_TYPES == {
        "surrogate",
        "intended_parent",
        "egg_donor",
        "sperm_donor",
    }
    assert normalize_pipeline_entity_type(None) == "surrogate"

    with pytest.raises(ValueError, match="Unsupported pipeline entity type"):
        normalize_pipeline_entity_type("egg-donor")
