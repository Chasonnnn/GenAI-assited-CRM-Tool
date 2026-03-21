"""Validation, dependency, and preview helpers for pipeline changes."""

from __future__ import annotations

from typing import Any

from app.core.stage_definitions import canonicalize_stage_key
from app.schemas.pipeline_semantics import PipelineFeatureConfig
from app.services import pipeline_semantics_service

VALID_STAGE_CATEGORIES = {"intake", "post_approval", "paused", "terminal"}


def normalize_stage_category(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "intake"


def normalize_stage_key(value: str | None) -> str | None:
    normalized = canonicalize_stage_key(str(value or "").strip())
    return normalized or None


def _replace_stage_keys(values: list[str], remap_by_key: dict[str, str | None]) -> list[str]:
    replaced: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_stage_key(value)
        replacement = remap_by_key.get(normalized, normalized)
        if replacement and replacement not in seen:
            seen.add(replacement)
            replaced.append(replacement)
    return replaced


def apply_feature_config_stage_remaps(
    feature_config: PipelineFeatureConfig,
    remap_by_key: dict[str, str | None],
) -> PipelineFeatureConfig:
    if not remap_by_key:
        return feature_config
    return feature_config.model_copy(
        update={
            "journey": feature_config.journey.model_copy(
                update={
                    "milestones": [
                        milestone.model_copy(
                            update={
                                "mapped_stage_keys": _replace_stage_keys(
                                    milestone.mapped_stage_keys,
                                    remap_by_key,
                                )
                            }
                        )
                        for milestone in feature_config.journey.milestones
                    ]
                }
            ),
            "analytics": feature_config.analytics.model_copy(
                update={
                    "funnel_stage_keys": _replace_stage_keys(
                        feature_config.analytics.funnel_stage_keys,
                        remap_by_key,
                    )
                }
            ),
            "role_visibility": {
                role: rule.model_copy(
                    update={"stage_keys": _replace_stage_keys(rule.stage_keys, remap_by_key)}
                )
                for role, rule in feature_config.role_visibility.items()
            },
            "role_mutation": {
                role: rule.model_copy(
                    update={"stage_keys": _replace_stage_keys(rule.stage_keys, remap_by_key)}
                )
                for role, rule in feature_config.role_mutation.items()
            },
        }
    )


def normalize_stage_drafts(
    stages: list[dict[str, Any]],
    *,
    existing_stage_by_id: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    existing_stage_by_id = existing_stage_by_id or {}
    errors: list[str] = []
    auto_fixes: list[str] = []
    normalized_stages: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_slugs: set[str] = set()

    if not stages:
        return [], ["A pipeline must keep at least one stage."], []

    for index, raw_stage in enumerate(stages, start=1):
        stage_id = str(raw_stage.get("id") or "").strip() or None
        existing_stage = existing_stage_by_id.get(stage_id) if stage_id else None
        raw_slug = str(raw_stage.get("slug") or "").strip().lower()
        stage_key = normalize_stage_key(raw_stage.get("stage_key") or raw_slug)
        if existing_stage is not None:
            existing_stage_key = normalize_stage_key(getattr(existing_stage, "stage_key", None))
            if (
                raw_stage.get("stage_key") is not None
                and stage_key is not None
                and existing_stage_key is not None
                and stage_key != existing_stage_key
            ):
                errors.append(
                    f"Stage key for '{getattr(existing_stage, 'label', stage_id)}' is immutable."
                )
            stage_key = existing_stage_key or stage_key

        category = normalize_stage_category(raw_stage.get("category") or raw_stage.get("stage_type"))
        if category not in VALID_STAGE_CATEGORIES:
            errors.append(f"Invalid stage category '{category}' for stage '{raw_slug or stage_key or index}'.")

        if not raw_slug:
            errors.append(f"Stage {index} is missing a slug.")
        if not stage_key:
            errors.append(f"Stage {index} is missing an immutable stage key.")

        if raw_slug:
            if raw_slug in seen_slugs:
                errors.append(f"Duplicate stage slug '{raw_slug}'.")
            seen_slugs.add(raw_slug)
        if stage_key:
            if stage_key in seen_keys:
                errors.append(f"Duplicate stage key '{stage_key}'.")
            seen_keys.add(stage_key)

        declared_order = raw_stage.get("order")
        if declared_order != index:
            auto_fixes.append("Stage order normalized to match the draft order.")

        normalized_stages.append(
            {
                "id": getattr(existing_stage, "id", None) or raw_stage.get("id"),
                "stage_key": stage_key,
                "slug": raw_slug,
                "label": str(raw_stage.get("label") or "").strip() or raw_slug or stage_key,
                "color": str(raw_stage.get("color") or "#6B7280").strip() or "#6B7280",
                "order": index,
                "category": category,
                "stage_type": category,
                "is_active": bool(raw_stage.get("is_active", True)),
                "semantics": pipeline_semantics_service.get_stage_semantics(
                    {
                        "stage_key": stage_key,
                        "slug": raw_slug,
                        "stage_type": category,
                        "semantics": raw_stage.get("semantics"),
                    }
                ).model_dump(mode="json"),
            }
        )

    return normalized_stages, list(dict.fromkeys(errors)), list(dict.fromkeys(auto_fixes))


def validate_guarded_invariants(
    stages: list[dict[str, Any]],
    feature_config: PipelineFeatureConfig,
) -> None:
    pause_stage_keys = [
        stage["stage_key"]
        for stage in stages
        if stage.get("is_active", True)
        and pipeline_semantics_service.get_stage_semantics(stage).pause_behavior
        == "resume_previous_stage"
    ]
    if len(pause_stage_keys) != 1:
        raise ValueError("Exactly one active pause stage must use resume_previous_stage")

    delivery_stage_keys = [
        stage["stage_key"]
        for stage in stages
        if stage.get("is_active", True)
        and pipeline_semantics_service.stage_has_capability(stage, "requires_delivery_details")
    ]
    if len(delivery_stage_keys) > 1:
        raise ValueError("At most one active stage can require delivery details")

    for stage in stages:
        if not stage.get("is_active", True):
            continue
        semantics = pipeline_semantics_service.get_stage_semantics(stage)
        stage_type = stage.get("stage_type")
        if (
            stage_type == "terminal"
            and semantics.terminal_outcome == "none"
            and not semantics.capabilities.requires_delivery_details
        ):
            raise ValueError("Terminal stages must declare a terminal outcome")
        if semantics.pause_behavior != "none" and stage_type != "paused":
            raise ValueError("Only paused stages can use pause behavior")
        if semantics.pause_behavior != "none" and semantics.terminal_outcome != "none":
            raise ValueError("A stage cannot be both paused and terminal")
        if (
            semantics.capabilities.requires_delivery_details
            and semantics.terminal_outcome != "none"
        ):
            raise ValueError("A delivery stage cannot also be a terminal lost/disqualified stage")

    active_stage_keys = {stage["stage_key"] for stage in stages if stage.get("is_active", True)}
    for milestone in feature_config.journey.milestones:
        missing_keys = [stage_key for stage_key in milestone.mapped_stage_keys if stage_key not in active_stage_keys]
        if missing_keys:
            raise ValueError(
                f"Journey milestone '{milestone.slug}' references missing stages: {', '.join(missing_keys)}"
            )
    missing_funnel_keys = [
        stage_key
        for stage_key in feature_config.analytics.funnel_stage_keys
        if stage_key not in active_stage_keys
    ]
    if missing_funnel_keys:
        raise ValueError(
            f"Analytics funnel references missing stages: {', '.join(missing_funnel_keys)}"
        )


def build_impact_report(
    before_stages: list[dict[str, Any]],
    after_stages: list[dict[str, Any]],
    before_feature_config: PipelineFeatureConfig,
    after_feature_config: PipelineFeatureConfig,
) -> list[str]:
    impact: set[str] = set()
    before_by_key = {stage["stage_key"]: stage for stage in before_stages}
    after_by_key = {stage["stage_key"]: stage for stage in after_stages}

    all_keys = set(before_by_key) | set(after_by_key)
    for stage_key in all_keys:
        before = before_by_key.get(stage_key)
        after = after_by_key.get(stage_key)
        if before is None or after is None:
            impact.update({"journey", "analytics", "integrations", "intelligent_suggestions"})
            continue
        if before.get("order") != after.get("order"):
            impact.update({"ui_gating", "analytics"})
        if before.get("label") != after.get("label"):
            impact.update({"analytics", "journey", "integrations"})
        if before.get("semantics") != after.get("semantics"):
            after_semantics = pipeline_semantics_service.get_stage_semantics(after)
            before_semantics = pipeline_semantics_service.get_stage_semantics(before)
            if before_semantics.integration_bucket != after_semantics.integration_bucket:
                impact.add("integrations")
            if before_semantics.analytics_bucket != after_semantics.analytics_bucket:
                impact.add("analytics")
            if before_semantics.suggestion_profile_key != after_semantics.suggestion_profile_key:
                impact.add("intelligent_suggestions")
            if before_semantics.capabilities != after_semantics.capabilities:
                impact.update({"ui_gating", "analytics"})
            if (
                before_semantics.pause_behavior != after_semantics.pause_behavior
                or before_semantics.terminal_outcome != after_semantics.terminal_outcome
            ):
                impact.update({"journey", "ui_gating", "analytics"})

    if before_feature_config.journey != after_feature_config.journey:
        impact.add("journey")
    if before_feature_config.analytics != after_feature_config.analytics:
        impact.add("analytics")
    if before_feature_config.role_visibility != after_feature_config.role_visibility:
        impact.add("role_visibility")
    if before_feature_config.role_mutation != after_feature_config.role_mutation:
        impact.add("role_mutation")
    return sorted(impact)


def build_pipeline_change_preview(
    *,
    dependency_graph: dict[str, Any],
    before_stages: list[dict[str, Any]],
    after_stages: list[dict[str, Any]],
    before_feature_config: PipelineFeatureConfig,
    after_feature_config: PipelineFeatureConfig,
    remaps: list[dict[str, Any]] | None = None,
    normalization_errors: list[str] | None = None,
    safe_auto_fixes: list[str] | None = None,
) -> dict[str, Any]:
    remap_by_key = {
        normalize_stage_key(item.get("removed_stage_key")): normalize_stage_key(
            item.get("target_stage_key")
        )
        for item in remaps or []
        if normalize_stage_key(item.get("removed_stage_key"))
    }
    validation_errors = list(normalization_errors or [])
    try:
        validate_guarded_invariants(after_stages, after_feature_config)
    except ValueError as exc:
        validation_errors.append(str(exc))

    after_stage_keys = {
        stage["stage_key"]
        for stage in after_stages
        if stage.get("is_active", True) and stage.get("stage_key")
    }
    before_stage_keys = {
        stage["stage_key"]
        for stage in before_stages
        if stage.get("is_active", True) and stage.get("stage_key")
    }
    removed_stage_keys = sorted(before_stage_keys - after_stage_keys)

    dependency_by_key = {
        stage["stage_key"]: stage for stage in dependency_graph.get("stages", []) if stage.get("stage_key")
    }
    required_remaps: list[dict[str, Any]] = []
    blocking_issues: list[str] = []

    for stage_key in removed_stage_keys:
        dependency = dependency_by_key.get(stage_key, {})
        reasons: list[str] = []
        if int(dependency.get("surrogate_count") or 0) > 0:
            reasons.append("active_surrogates")
        if dependency.get("intelligent_suggestion_rules"):
            reasons.append("intelligent_suggestions")
        if dependency.get("integration_refs"):
            reasons.append("integrations")
        if not reasons:
            continue

        target_stage_key = remap_by_key.get(stage_key)
        if not target_stage_key:
            blocking_issues.append(
                f"Stage '{dependency.get('label') or stage_key}' requires a remap target before removal."
            )
            required_remaps.append(
                {
                    "stage_key": stage_key,
                    "label": dependency.get("label") or stage_key,
                    "surrogate_count": int(dependency.get("surrogate_count") or 0),
                    "reasons": reasons,
                }
            )
            continue
        if target_stage_key not in after_stage_keys:
            blocking_issues.append(
                f"Remap target '{target_stage_key}' for removed stage '{dependency.get('label') or stage_key}' is not active in the draft."
            )

    if not after_stage_keys:
        blocking_issues.append("A pipeline must keep at least one active stage.")

    return {
        "impact_areas": build_impact_report(
            before_stages,
            after_stages,
            before_feature_config,
            after_feature_config,
        ),
        "validation_errors": list(dict.fromkeys(validation_errors)),
        "blocking_issues": list(dict.fromkeys(blocking_issues)),
        "required_remaps": required_remaps,
        "safe_auto_fixes": list(dict.fromkeys(safe_auto_fixes or [])),
        "dependency_graph": dependency_graph,
    }
