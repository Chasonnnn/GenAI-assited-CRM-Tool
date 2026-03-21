"""Typed pipeline semantics schema and default builders."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.stage_definitions import (
    INTENDED_PARENT_PIPELINE_ENTITY,
    canonicalize_stage_key,
    normalize_pipeline_entity_type,
)
from app.utils.presentation import humanize_identifier

StageCapabilityKey = Literal[
    "counts_as_contacted",
    "eligible_for_matching",
    "locks_match_state",
    "shows_pregnancy_tracking",
    "requires_delivery_details",
    "tracks_interview_outcome",
]
PauseBehavior = Literal["none", "resume_previous_stage"]
TerminalOutcome = Literal["none", "lost", "disqualified"]
IntegrationBucket = Literal["none", "intake", "qualified", "converted", "lost", "not_qualified"]


class StageCapabilities(BaseModel):
    counts_as_contacted: bool = False
    eligible_for_matching: bool = False
    locks_match_state: bool = False
    shows_pregnancy_tracking: bool = False
    requires_delivery_details: bool = False
    tracks_interview_outcome: bool = False


class StageSemantics(BaseModel):
    capabilities: StageCapabilities = Field(default_factory=StageCapabilities)
    pause_behavior: PauseBehavior = "none"
    terminal_outcome: TerminalOutcome = "none"
    integration_bucket: IntegrationBucket = "none"
    analytics_bucket: str | None = None
    suggestion_profile_key: str | None = None
    requires_reason_on_enter: bool = False


class JourneyMilestoneDefinition(BaseModel):
    slug: str
    label: str
    description: str
    mapped_stage_keys: list[str] = Field(default_factory=list)
    is_soft: bool = False


class JourneyPhaseDefinition(BaseModel):
    slug: str
    label: str
    milestone_slugs: list[str] = Field(default_factory=list)


class JourneyFeatureConfig(BaseModel):
    phases: list[JourneyPhaseDefinition] = Field(default_factory=list)
    milestones: list[JourneyMilestoneDefinition] = Field(default_factory=list)


class AnalyticsFeatureConfig(BaseModel):
    funnel_stage_keys: list[str] = Field(default_factory=list)
    performance_stage_keys: list[str] = Field(default_factory=list)
    qualification_stage_key: str | None = None
    conversion_stage_key: str | None = None


class RoleStageRule(BaseModel):
    stage_types: list[str] = Field(default_factory=list)
    stage_keys: list[str] = Field(default_factory=list)
    capabilities: list[StageCapabilityKey] = Field(default_factory=list)


class PipelineFeatureConfig(BaseModel):
    schema_version: int = 1
    journey: JourneyFeatureConfig = Field(default_factory=JourneyFeatureConfig)
    analytics: AnalyticsFeatureConfig = Field(default_factory=AnalyticsFeatureConfig)
    role_visibility: dict[str, RoleStageRule] = Field(default_factory=dict)
    role_mutation: dict[str, RoleStageRule] = Field(default_factory=dict)


DEFAULT_JOURNEY_MILESTONES = [
    JourneyMilestoneDefinition(
        slug="application_intake",
        label="Application & Intake",
        description="Initial application received and intake process begun.",
        mapped_stage_keys=["new_unread", "contacted", "pre_qualified", "application_submitted"],
    ),
    JourneyMilestoneDefinition(
        slug="screening_interviews",
        label="Screening & Interviews",
        description="Background screening and interviews in progress.",
        mapped_stage_keys=["under_review", "interview_scheduled", "approved"],
    ),
    JourneyMilestoneDefinition(
        slug="approved_matching",
        label="Approved for Matching",
        description="Approved and ready to be matched with intended parents.",
        mapped_stage_keys=["ready_to_match"],
    ),
    JourneyMilestoneDefinition(
        slug="match_confirmed",
        label="Match Confirmed",
        description="Successfully matched with intended parents.",
        mapped_stage_keys=["matched"],
    ),
    JourneyMilestoneDefinition(
        slug="medical_clearance",
        label="Medical Clearance",
        description="Medical screening and clearance completed.",
        mapped_stage_keys=["medical_clearance_passed"],
    ),
    JourneyMilestoneDefinition(
        slug="legal_finalization",
        label="Legal Finalization",
        description="Legal contracts and agreements finalized.",
        mapped_stage_keys=["legal_clearance_passed"],
    ),
    JourneyMilestoneDefinition(
        slug="transfer_pregnancy",
        label="Transfer & Pregnancy Confirmation",
        description="Embryo transfer completed and pregnancy confirmed.",
        mapped_stage_keys=["transfer_cycle", "second_hcg_confirmed", "heartbeat_confirmed"],
    ),
    JourneyMilestoneDefinition(
        slug="ongoing_care",
        label="Ongoing Pregnancy Care",
        description="Regular prenatal care and monitoring in progress.",
        mapped_stage_keys=["ob_care_established", "anatomy_scanned"],
    ),
    JourneyMilestoneDefinition(
        slug="delivery_preparation",
        label="Delivery Preparation",
        description="Final preparations underway as delivery approaches.",
        mapped_stage_keys=[],
        is_soft=True,
    ),
    JourneyMilestoneDefinition(
        slug="delivery",
        label="Delivery",
        description="Baby delivered successfully.",
        mapped_stage_keys=["delivered"],
    ),
]

DEFAULT_JOURNEY_PHASES = [
    JourneyPhaseDefinition(
        slug="getting_started",
        label="Getting Started",
        milestone_slugs=["application_intake", "screening_interviews"],
    ),
    JourneyPhaseDefinition(
        slug="matching_preparation",
        label="Matching & Preparation",
        milestone_slugs=[
            "approved_matching",
            "match_confirmed",
            "medical_clearance",
            "legal_finalization",
        ],
    ),
    JourneyPhaseDefinition(
        slug="pregnancy",
        label="Pregnancy",
        milestone_slugs=["transfer_pregnancy", "ongoing_care"],
    ),
    JourneyPhaseDefinition(
        slug="completion",
        label="Completion",
        milestone_slugs=["delivery_preparation", "delivery"],
    ),
]

DEFAULT_ANALYTICS_FUNNEL_STAGE_KEYS = [
    "new_unread",
    "contacted",
    "pre_qualified",
    "ready_to_match",
    "matched",
    "medical_clearance_passed",
]

DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS = [
    "contacted",
    "pre_qualified",
    "ready_to_match",
    "matched",
    "application_submitted",
    "on_hold",
    "lost",
]
DEFAULT_ANALYTICS_QUALIFICATION_STAGE_KEY = "pre_qualified"
DEFAULT_ANALYTICS_CONVERSION_STAGE_KEY = "application_submitted"

DEFAULT_ROLE_VISIBILITY = {
    "intake_specialist": RoleStageRule(stage_types=["intake", "paused", "terminal"]),
    "case_manager": RoleStageRule(
        stage_types=["post_approval", "paused"],
        stage_keys=["approved", "lost", "disqualified"],
    ),
    "admin": RoleStageRule(stage_types=["intake", "post_approval", "paused", "terminal"]),
    "developer": RoleStageRule(stage_types=["intake", "post_approval", "paused", "terminal"]),
}

DEFAULT_ROLE_MUTATION = {
    "intake_specialist": RoleStageRule(stage_types=["intake", "paused", "terminal"]),
    "case_manager": RoleStageRule(
        stage_types=["post_approval", "paused"],
        stage_keys=["lost", "disqualified"],
    ),
    "admin": RoleStageRule(stage_types=["intake", "post_approval", "paused", "terminal"]),
    "developer": RoleStageRule(stage_types=["intake", "post_approval", "paused", "terminal"]),
}

_SUGGESTION_PROFILE_BY_STAGE_KEY = {
    "new_unread": "new_unread_followup",
    "contacted": "contacted_followup",
    "pre_qualified": "qualified_followup",
    "interview_scheduled": "interview_scheduled_followup",
    "application_submitted": "application_submitted_followup",
    "under_review": "under_review_followup",
    "approved": "approved_followup",
    "ready_to_match": "ready_to_match_followup",
    "matched": "matched_followup",
    "medical_clearance_passed": "medical_clearance_followup",
    "legal_clearance_passed": "legal_clearance_followup",
    "transfer_cycle": "transfer_cycle_followup",
    "second_hcg_confirmed": "second_hcg_followup",
    "heartbeat_confirmed": "heartbeat_followup",
    "ob_care_established": "ob_care_followup",
    "anatomy_scanned": "anatomy_scan_followup",
}


def default_stage_semantics(
    stage_key: str,
    stage_type: str,
    entity_type: str | None = None,
) -> dict[str, Any]:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    normalized_key = canonicalize_stage_key(stage_key)
    if normalized_entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
        capabilities = StageCapabilities(
            eligible_for_matching=normalized_key == "ready_to_match",
            locks_match_state=normalized_key in {"matched", "delivered"},
            requires_delivery_details=normalized_key == "delivered",
        )
        return StageSemantics(
            capabilities=capabilities,
            analytics_bucket=normalized_key if stage_type != "paused" else None,
        ).model_dump(mode="json")

    capabilities = StageCapabilities(
        counts_as_contacted=normalized_key
        in {
            "contacted",
            "pre_qualified",
            "interview_scheduled",
            "application_submitted",
            "under_review",
            "approved",
        },
        eligible_for_matching=normalized_key == "ready_to_match",
        locks_match_state=normalized_key
        in {
            "matched",
            "medical_clearance_passed",
            "legal_clearance_passed",
            "transfer_cycle",
            "second_hcg_confirmed",
            "heartbeat_confirmed",
            "ob_care_established",
            "anatomy_scanned",
            "delivered",
        },
        shows_pregnancy_tracking=normalized_key
        in {
            "heartbeat_confirmed",
            "ob_care_established",
            "anatomy_scanned",
            "delivered",
        },
        requires_delivery_details=normalized_key == "delivered",
        tracks_interview_outcome=normalized_key
        in {"interview_scheduled", "under_review", "approved"},
    )

    if normalized_key == "contacted":
        integration_bucket: IntegrationBucket = "intake"
    elif normalized_key in {
        "pre_qualified",
        "interview_scheduled",
        "application_submitted",
        "under_review",
        "approved",
    }:
        integration_bucket = "qualified"
    elif normalized_key in {
        "ready_to_match",
        "matched",
        "medical_clearance_passed",
        "legal_clearance_passed",
        "transfer_cycle",
        "second_hcg_confirmed",
        "heartbeat_confirmed",
        "ob_care_established",
        "anatomy_scanned",
        "delivered",
    }:
        integration_bucket = "converted"
    elif normalized_key == "lost":
        integration_bucket = "lost"
    elif normalized_key == "disqualified":
        integration_bucket = "not_qualified"
    else:
        integration_bucket = "none"

    terminal_outcome: TerminalOutcome = "none"
    if normalized_key == "lost":
        terminal_outcome = "lost"
    elif normalized_key == "disqualified":
        terminal_outcome = "disqualified"

    return StageSemantics(
        capabilities=capabilities,
        pause_behavior="resume_previous_stage" if normalized_key == "on_hold" else "none",
        terminal_outcome=terminal_outcome,
        integration_bucket=integration_bucket,
        analytics_bucket=normalized_key if stage_type != "paused" else "on_hold",
        suggestion_profile_key=_SUGGESTION_PROFILE_BY_STAGE_KEY.get(normalized_key),
        requires_reason_on_enter=normalized_key == "on_hold",
    ).model_dump(mode="json")


def default_pipeline_feature_config(entity_type: str | None = None) -> dict[str, Any]:
    normalized_entity_type = normalize_pipeline_entity_type(entity_type)
    if normalized_entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
        return PipelineFeatureConfig().model_dump(mode="json")

    return PipelineFeatureConfig(
        journey=JourneyFeatureConfig(
            phases=[phase.model_copy(deep=True) for phase in DEFAULT_JOURNEY_PHASES],
            milestones=[
                milestone.model_copy(deep=True) for milestone in DEFAULT_JOURNEY_MILESTONES
            ],
        ),
        analytics=AnalyticsFeatureConfig(
            funnel_stage_keys=list(DEFAULT_ANALYTICS_FUNNEL_STAGE_KEYS),
            performance_stage_keys=list(DEFAULT_ANALYTICS_PERFORMANCE_STAGE_KEYS),
            qualification_stage_key=DEFAULT_ANALYTICS_QUALIFICATION_STAGE_KEY,
            conversion_stage_key=DEFAULT_ANALYTICS_CONVERSION_STAGE_KEY,
        ),
        role_visibility={
            role: rule.model_copy(deep=True) for role, rule in DEFAULT_ROLE_VISIBILITY.items()
        },
        role_mutation={
            role: rule.model_copy(deep=True) for role, rule in DEFAULT_ROLE_MUTATION.items()
        },
    ).model_dump(mode="json")


def deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_stage_semantics(
    stage_key: str,
    stage_type: str,
    semantics: dict[str, Any] | None,
    entity_type: str | None = None,
) -> StageSemantics:
    default_payload = default_stage_semantics(stage_key, stage_type, entity_type)
    payload = deep_merge_dicts(default_payload, semantics or {})
    return StageSemantics.model_validate(payload)


def normalize_feature_config(
    feature_config: dict[str, Any] | None,
    entity_type: str | None = None,
) -> PipelineFeatureConfig:
    payload = deep_merge_dicts(
        default_pipeline_feature_config(entity_type),
        feature_config or {},
    )
    return PipelineFeatureConfig.model_validate(payload)


def default_custom_stage_label(stage_key: str) -> str:
    return humanize_identifier(canonicalize_stage_key(stage_key))
