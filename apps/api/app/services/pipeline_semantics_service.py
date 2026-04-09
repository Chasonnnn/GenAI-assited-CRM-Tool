"""Pipeline semantics resolver and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.pipeline_stage_colors import resolve_stage_color
from app.core.stage_definitions import canonicalize_stage_key, get_stage_protection_metadata
from app.db.models import Pipeline, PipelineStage
from app.schemas.pipeline_semantics import (
    PipelineFeatureConfig,
    RoleStageRule,
    StageCapabilityKey,
    StageSemantics,
    normalize_feature_config,
    normalize_stage_semantics,
)


@dataclass(frozen=True)
class PipelineSemanticsStageSnapshot:
    id: UUID
    stage_key: str
    slug: str
    label: str
    color: str
    order: int
    category: str
    stage_type: str
    is_active: bool
    semantics: StageSemantics


@dataclass(frozen=True)
class PipelineSemanticsSnapshot:
    pipeline_id: UUID
    entity_type: str
    version: int
    feature_config: PipelineFeatureConfig
    stages: list[PipelineSemanticsStageSnapshot]
    stage_by_id: dict[UUID, PipelineSemanticsStageSnapshot]
    stage_by_key: dict[str, PipelineSemanticsStageSnapshot]


def get_stage_semantics(stage: PipelineStage | dict[str, Any] | None) -> StageSemantics:
    if not stage:
        return normalize_stage_semantics("", "intake", None)
    if isinstance(stage, dict):
        stage_key = canonicalize_stage_key(
            str(stage.get("stage_key") or stage.get("slug") or "").strip()
        )
        stage_type = str(stage.get("stage_type") or "intake")
        semantics = stage.get("semantics")
        return normalize_stage_semantics(
            stage_key,
            stage_type,
            semantics if isinstance(semantics, dict) else None,
            stage.get("entity_type"),
        )

    return normalize_stage_semantics(
        stage.stage_key or stage.slug,
        stage.stage_type,
        stage.semantics if isinstance(stage.semantics, dict) else None,
        getattr(getattr(stage, "pipeline", None), "entity_type", None),
    )


def get_pipeline_feature_config(pipeline: Pipeline | dict[str, Any]) -> PipelineFeatureConfig:
    if isinstance(pipeline, dict):
        payload = pipeline.get("feature_config")
        entity_type = pipeline.get("entity_type")
    else:
        payload = pipeline.feature_config
        entity_type = pipeline.entity_type
    return normalize_feature_config(payload if isinstance(payload, dict) else None, entity_type)


def stage_has_capability(
    stage: PipelineStage | dict[str, Any] | None,
    capability: StageCapabilityKey,
) -> bool:
    return bool(get_stage_semantics(stage).capabilities.model_dump().get(capability))


def get_first_active_stage_with_capability(
    snapshot: PipelineSemanticsSnapshot,
    capability: StageCapabilityKey,
) -> PipelineSemanticsStageSnapshot | None:
    for stage in snapshot.stages:
        if stage.is_active and stage.semantics.capabilities.model_dump().get(capability):
            return stage
    return None


def get_stage_integration_bucket(stage: PipelineStage | dict[str, Any] | None) -> str:
    return get_stage_semantics(stage).integration_bucket


def get_stage_terminal_outcome(stage: PipelineStage | dict[str, Any] | None) -> str:
    return get_stage_semantics(stage).terminal_outcome


def get_pipeline_semantics_snapshot(
    db: Session,
    pipeline_or_id: Pipeline | UUID,
) -> PipelineSemanticsSnapshot:
    pipeline: Pipeline | None
    if isinstance(pipeline_or_id, Pipeline):
        pipeline = pipeline_or_id
    else:
        pipeline = (
            db.query(Pipeline)
            .options(selectinload(Pipeline.stages))
            .filter(Pipeline.id == pipeline_or_id)
            .first()
        )
    if not pipeline:
        raise ValueError("Pipeline not found")

    feature_config = get_pipeline_feature_config(pipeline)
    ordered_stages = sorted(pipeline.stages, key=lambda stage: stage.order)
    stages = [
        PipelineSemanticsStageSnapshot(
            id=stage.id,
            stage_key=canonicalize_stage_key(stage.stage_key or stage.slug),
            slug=stage.slug,
            label=stage.label,
            color=resolve_stage_color(
                color=stage.color,
                label=stage.label,
                slug=stage.slug,
                stage_key=stage.stage_key,
                stage_type=stage.stage_type,
                order=stage.order,
                is_locked=stage.is_locked,
            ),
            order=stage.order,
            category=stage.stage_type,
            stage_type=stage.stage_type,
            is_active=stage.is_active,
            semantics=get_stage_semantics(stage),
        )
        for stage in ordered_stages
    ]
    return PipelineSemanticsSnapshot(
        pipeline_id=pipeline.id,
        entity_type=pipeline.entity_type,
        version=pipeline.current_version,
        feature_config=feature_config,
        stages=stages,
        stage_by_id={stage.id: stage for stage in stages},
        stage_by_key={stage.stage_key: stage for stage in stages},
    )


def role_rule_matches_stage(
    stage: PipelineStage | dict[str, Any],
    rule: RoleStageRule | None,
) -> bool:
    if not rule:
        return False
    stage_key = canonicalize_stage_key(
        str(stage.get("stage_key") or stage.get("slug") or "").strip()
        if isinstance(stage, dict)
        else stage.stage_key or stage.slug
    )
    stage_type = str(stage.get("stage_type") or "") if isinstance(stage, dict) else stage.stage_type
    if stage_type and stage_type in rule.stage_types:
        return True
    if stage_key and stage_key in rule.stage_keys:
        return True
    return any(stage_has_capability(stage, capability) for capability in rule.capabilities)


def can_role_access_stage(
    role: str | None,
    stage: PipelineStage | dict[str, Any],
    *,
    feature_config: PipelineFeatureConfig,
    mutation: bool = False,
) -> bool:
    if not role:
        return True
    rules = feature_config.role_mutation if mutation else feature_config.role_visibility
    rule = rules.get(role)
    if rule is None:
        return True
    return role_rule_matches_stage(stage, rule)


def serialize_stage_snapshot(
    stage: PipelineSemanticsStageSnapshot,
    entity_type: str | None = None,
) -> dict[str, Any]:
    return {
        "id": stage.id,
        "stage_key": stage.stage_key,
        "slug": stage.slug,
        "label": stage.label,
        "color": stage.color,
        "order": stage.order,
        "category": stage.category,
        "stage_type": stage.stage_type,
        "is_active": stage.is_active,
        "semantics": stage.semantics.model_dump(mode="json"),
        **get_stage_protection_metadata(stage.stage_key, entity_type),
    }


def serialize_pipeline_semantics_snapshot(snapshot: PipelineSemanticsSnapshot) -> dict[str, Any]:
    return {
        "pipeline_id": snapshot.pipeline_id,
        "entity_type": snapshot.entity_type,
        "version": snapshot.version,
        "feature_config": snapshot.feature_config.model_dump(mode="json"),
        "stages": [
            serialize_stage_snapshot(stage, snapshot.entity_type) for stage in snapshot.stages
        ],
    }
