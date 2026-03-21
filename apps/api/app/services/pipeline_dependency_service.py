"""Dependency graph helpers for pipeline lifecycle changes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.stage_definitions import canonicalize_stage_key
from app.db.models import (
    AutomationWorkflow,
    Campaign,
    IntendedParent,
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
        "campaign_refs": [],
        "workflow_refs": [],
    }


def _stage_ref_matches(stage: PipelineStage, value: Any) -> bool:
    if value is None:
        return False
    if str(value) == str(stage.id):
        return True
    return _normalize_stage_key(str(value)) == stage.stage_key


def _workflow_values_reference_stage(stage: PipelineStage, value: Any) -> bool:
    if isinstance(value, list):
        return any(_workflow_values_reference_stage(stage, item) for item in value)
    return _stage_ref_matches(stage, value)


def _workflow_reference_paths(workflow: AutomationWorkflow, stage: PipelineStage) -> list[str]:
    refs: set[str] = set()
    trigger_config = workflow.trigger_config if isinstance(workflow.trigger_config, dict) else {}
    if _stage_ref_matches(stage, trigger_config.get("from_stage_id")) or _stage_ref_matches(
        stage, trigger_config.get("from_stage_key")
    ) or _stage_ref_matches(stage, trigger_config.get("from_status")):
        refs.add("trigger.from_stage")
    if _stage_ref_matches(stage, trigger_config.get("to_stage_id")) or _stage_ref_matches(
        stage, trigger_config.get("to_stage_key")
    ) or _stage_ref_matches(stage, trigger_config.get("to_status")):
        refs.add("trigger.to_stage")

    for condition in workflow.conditions or []:
        if not isinstance(condition, dict) or condition.get("field") != "stage_id":
            continue
        if _workflow_values_reference_stage(stage, condition.get("value")) or _workflow_values_reference_stage(
            stage, condition.get("stage_key")
        ) or _workflow_values_reference_stage(stage, condition.get("stage_keys")):
            refs.add("condition.stage_id")

    for action in workflow.actions or []:
        if not isinstance(action, dict):
            continue
        action_type = action.get("action_type")
        if action_type == "update_status" and _stage_ref_matches(stage, action.get("stage_id")):
            refs.add("action.update_status")
            continue
        if (
            action_type == "update_field"
            and action.get("field") == "stage_id"
            and (
                _stage_ref_matches(stage, action.get("value"))
                or _stage_ref_matches(stage, action.get("value_stage_key"))
            )
        ):
            refs.add("action.update_field.stage_id")

    return sorted(refs)


def _campaign_reference_modes(campaign: Campaign, stage: PipelineStage) -> list[str]:
    criteria = campaign.filter_criteria if isinstance(campaign.filter_criteria, dict) else {}
    refs: set[str] = set()
    for value in criteria.get("stage_ids") or []:
        if str(value) == str(stage.id):
            refs.add("stage_ids")
            break
    for value in criteria.get("stage_keys") or []:
        if _normalize_stage_key(str(value)) == stage.stage_key:
            refs.add("stage_keys")
            break
    for value in criteria.get("stage_slugs") or []:
        if _stage_ref_matches(stage, value):
            refs.add("stage_slugs")
            break
    return sorted(refs)


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

    if pipeline.entity_type == "intended_parent":
        surrogate_counts = dict(
            db.query(IntendedParent.stage_id, func.count(IntendedParent.id))
            .filter(
                IntendedParent.organization_id == pipeline.organization_id,
                IntendedParent.is_archived.is_(False),
                IntendedParent.stage_id.is_not(None),
            )
            .group_by(IntendedParent.stage_id)
            .all()
        )
    else:
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

    if pipeline.entity_type == "surrogate":
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
    if pipeline.entity_type == "surrogate":
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

    campaigns = (
        db.query(Campaign)
        .filter(
            Campaign.organization_id == pipeline.organization_id,
            Campaign.recipient_type
            == ("case" if pipeline.entity_type == "surrogate" else "intended_parent"),
            Campaign.status.in_(("draft", "scheduled")),
        )
        .all()
    )
    for campaign in campaigns:
        for stage in stages:
            if not stage.stage_key or stage.stage_key not in stage_map:
                continue
            reference_modes = _campaign_reference_modes(campaign, stage)
            if reference_modes:
                stage_map[stage.stage_key]["campaign_refs"].append(
                    {
                        "id": str(campaign.id),
                        "name": campaign.name,
                        "status": campaign.status,
                        "reference_modes": reference_modes,
                    }
                )

    workflows = (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == pipeline.organization_id)
        .all()
    )
    for workflow in workflows:
        for stage in stages:
            if not stage.stage_key or stage.stage_key not in stage_map:
                continue
            reference_paths = _workflow_reference_paths(workflow, stage)
            if reference_paths:
                stage_map[stage.stage_key]["workflow_refs"].append(
                    {
                        "id": str(workflow.id),
                        "name": workflow.name,
                        "scope": workflow.scope,
                        "is_enabled": bool(workflow.is_enabled),
                        "reference_paths": reference_paths,
                    }
                )

    ordered_entries = [
        stage_map[stage.stage_key]
        for stage in sorted(stages, key=lambda item: item.order)
        if stage.stage_key in stage_map
    ]
    return {
        "pipeline_id": pipeline.id,
        "entity_type": pipeline.entity_type,
        "version": pipeline.current_version,
        "stages": ordered_entries,
    }
