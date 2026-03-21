"""Dependency graph helpers for pipeline lifecycle changes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.stage_definitions import canonicalize_stage_key
from app.db.models import (
    MetaCrmDatasetSettings,
    OrgIntelligentSuggestionRule,
    Pipeline,
    PipelineStage,
    Surrogate,
    ZapierWebhookSettings,
)
from app.services import pipeline_semantics_service, pipeline_service


def _normalize_stage_key(value: str | None) -> str | None:
    normalized = canonicalize_stage_key(str(value or "").strip())
    return normalized or None


def _empty_dependency_entry(stage: PipelineStage) -> dict[str, Any]:
    return {
        "stage_id": stage.id,
        "stage_key": stage.stage_key,
        "slug": stage.slug,
        "label": stage.label,
        "category": stage.stage_type,
        "stage_type": stage.stage_type,
        "is_active": stage.is_active,
        "surrogate_count": 0,
        "journey_milestone_slugs": [],
        "analytics_funnel": False,
        "intelligent_suggestion_rules": [],
        "integration_refs": [],
        "role_visibility_roles": [],
        "role_mutation_roles": [],
    }


def build_pipeline_dependency_graph(
    db: Session,
    pipeline: Pipeline,
) -> dict[str, Any]:
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    stage_map = {
        stage.stage_key: _empty_dependency_entry(stage)
        for stage in stages
        if stage.stage_key
    }

    surrogate_counts = dict(
        db.query(Surrogate.stage_id, func.count(Surrogate.id))
        .filter(
            Surrogate.organization_id == pipeline.organization_id,
            Surrogate.is_archived.is_(False),
            Surrogate.stage_id.is_not(None),
        )
        .group_by(Surrogate.stage_id)
        .all()
    )
    for stage in stages:
        if stage.stage_key in stage_map:
            stage_map[stage.stage_key]["surrogate_count"] = int(surrogate_counts.get(stage.id, 0))

    for milestone in feature_config.journey.milestones:
        for stage_key in milestone.mapped_stage_keys:
            normalized = _normalize_stage_key(stage_key)
            if normalized in stage_map:
                stage_map[normalized]["journey_milestone_slugs"].append(milestone.slug)

    for stage_key in feature_config.analytics.funnel_stage_keys:
        normalized = _normalize_stage_key(stage_key)
        if normalized in stage_map:
            stage_map[normalized]["analytics_funnel"] = True

    for role, rule in feature_config.role_visibility.items():
        for stage_key in rule.stage_keys:
            normalized = _normalize_stage_key(stage_key)
            if normalized in stage_map:
                stage_map[normalized]["role_visibility_roles"].append(role)

    for role, rule in feature_config.role_mutation.items():
        for stage_key in rule.stage_keys:
            normalized = _normalize_stage_key(stage_key)
            if normalized in stage_map:
                stage_map[normalized]["role_mutation_roles"].append(role)

    rules = (
        db.query(OrgIntelligentSuggestionRule)
        .filter(OrgIntelligentSuggestionRule.organization_id == pipeline.organization_id)
        .all()
    )
    for rule in rules:
        stage = pipeline_service.resolve_stage(db, pipeline.id, rule.stage_slug)
        normalized = stage.stage_key if stage else _normalize_stage_key(rule.stage_slug)
        if normalized in stage_map:
            stage_map[normalized]["intelligent_suggestion_rules"].append(
                {
                    "id": str(rule.id),
                    "name": rule.name,
                    "enabled": bool(rule.enabled),
                }
            )

    integration_refs: dict[str, set[str]] = defaultdict(set)
    zapier_settings = (
        db.query(ZapierWebhookSettings)
        .filter(ZapierWebhookSettings.organization_id == pipeline.organization_id)
        .first()
    )
    if zapier_settings and isinstance(zapier_settings.outbound_event_mapping, list):
        for item in zapier_settings.outbound_event_mapping:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_stage_key(item.get("stage_key") or item.get("stage_slug"))
            if normalized:
                integration_refs[normalized].add("zapier_outbound")

    meta_settings = (
        db.query(MetaCrmDatasetSettings)
        .filter(MetaCrmDatasetSettings.organization_id == pipeline.organization_id)
        .first()
    )
    if meta_settings and isinstance(meta_settings.event_mapping, list):
        for item in meta_settings.event_mapping:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_stage_key(item.get("stage_key") or item.get("stage_slug"))
            if normalized:
                integration_refs[normalized].add("meta_crm_dataset")

    for stage_key, refs in integration_refs.items():
        if stage_key in stage_map:
            stage_map[stage_key]["integration_refs"] = sorted(refs)

    ordered_entries = [
        stage_map[stage.stage_key]
        for stage in sorted(stages, key=lambda item: item.order)
        if stage.stage_key in stage_map
    ]
    return {
        "pipeline_id": pipeline.id,
        "version": pipeline.current_version,
        "stages": ordered_entries,
    }
