"""Pipeline service - manage org-configurable stage pipelines."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.stage_definitions import (
    INTENDED_PARENT_PIPELINE_ENTITY,
    SURROGATE_PIPELINE_ENTITY,
    canonicalize_stage_key,
    get_default_stage_defs,
    get_protected_system_stage_defs,
    get_stage_protection,
    get_stage_protection_metadata,
    get_system_stage_key,
    normalize_pipeline_entity_type,
)
from app.db.models import (
    AutomationWorkflow,
    Campaign,
    IntendedParent,
    MetaCrmDatasetSettings,
    OrgIntelligentSuggestionRule,
    Pipeline,
    PipelineStage,
    StatusChangeRequest,
    Surrogate,
    ZapierWebhookSettings,
)
from app.schemas.pipeline_semantics import (
    PipelineFeatureConfig,
    default_pipeline_feature_config,
    default_stage_semantics,
)
from app.services import pipeline_change_service, pipeline_semantics_service, version_service
from app.utils.presentation import humanize_identifier

ENTITY_TYPE = "pipeline"
VALID_STAGE_TYPES = {"intake", "post_approval", "paused", "terminal"}


def _normalize_slug(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_stage_key(value: str | None) -> str:
    return canonicalize_stage_key(value)


def _normalize_pipeline_entity_type(value: str | None) -> str:
    return normalize_pipeline_entity_type(value)


def get_stage_semantic_key(stage: PipelineStage | None) -> str | None:
    """Return the canonical stage key for a stage instance."""
    if not stage:
        return None
    return _normalize_stage_key(stage.stage_key or stage.slug)


def normalize_stage_ref(value: str | None) -> str | None:
    """Normalize a stage key or slug reference to its canonical stage key."""
    normalized = _normalize_stage_key(value)
    return normalized or None


def stage_matches_key(stage: PipelineStage | None, stage_key: str | None) -> bool:
    """Return whether a stage represents the requested semantic stage key."""
    normalized_target = normalize_stage_ref(stage_key)
    if not normalized_target:
        return False
    return get_stage_semantic_key(stage) == normalized_target


def stage_matches_system_role(
    stage: PipelineStage | None,
    system_role: str | None,
    entity_type: str | None = None,
) -> bool:
    stage_key = get_system_stage_key(entity_type, system_role)
    return stage_matches_key(stage, stage_key)


def _default_stage_position_map(entity_type: str) -> dict[str, int]:
    return {
        _normalize_stage_key(stage_def.get("stage_key") or stage_def["slug"]): index
        for index, stage_def in enumerate(get_default_stage_defs(entity_type))
    }


def _normalize_stage_semantics_payload(
    *,
    entity_type: str,
    stage_key: str,
    slug: str,
    stage_type: str,
    semantics: dict | None,
    stage_label: str,
) -> dict[str, object]:
    normalized_semantics = pipeline_semantics_service.get_stage_semantics(
        {
            "entity_type": entity_type,
            "stage_key": stage_key,
            "slug": slug,
            "stage_type": stage_type,
            "semantics": semantics,
        }
    )
    errors = pipeline_change_service.get_reserved_lifecycle_semantics_errors(
        stage_key=stage_key,
        stage_label=stage_label,
        semantics=normalized_semantics,
        entity_type=entity_type,
    )
    if errors:
        raise ValueError(errors[0])
    return normalized_semantics.model_dump(mode="json")


def _protected_stage_update_errors(
    stage: PipelineStage,
    *,
    entity_type: str,
    slug: str | None = None,
    label: str | None = None,
    color: str | None = None,
    order: int | None = None,
    stage_type: str | None = None,
    semantics: dict | None = None,
) -> list[str]:
    if not get_stage_protection(stage.stage_key, entity_type):
        return []

    attempted_fields: list[str] = []
    if slug is not None and _normalize_slug(slug) != stage.slug:
        attempted_fields.append("slug")
    if label is not None and label != stage.label:
        attempted_fields.append("label")
    if color is not None and color != stage.color:
        attempted_fields.append("color")
    if order is not None and order != stage.order:
        attempted_fields.append("order")
    if (
        stage_type is not None
        and pipeline_change_service.normalize_stage_category(stage_type) != stage.stage_type
    ):
        attempted_fields.append("category")
    if semantics is not None:
        next_semantics = pipeline_semantics_service.get_stage_semantics(
            {
                "entity_type": entity_type,
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "stage_type": stage.stage_type,
                "semantics": semantics,
            }
        ).model_dump(mode="json")
        current_semantics = pipeline_semantics_service.get_stage_semantics(stage).model_dump(
            mode="json"
        )
        if next_semantics != current_semantics:
            attempted_fields.append("semantics")
    return attempted_fields


def _protected_stage_layout_errors(
    pipeline: Pipeline,
    stages: list[dict[str, object]],
) -> list[str]:
    current_protected_stage_keys = [
        stage.stage_key
        for stage in sorted(
            (stage for stage in pipeline.stages if stage.is_active),
            key=lambda stage: stage.order,
        )
        if get_stage_protection(stage.stage_key, pipeline.entity_type)
    ]
    return pipeline_change_service.validate_protected_stage_layout(
        stages,
        entity_type=pipeline.entity_type,
        current_protected_stage_keys=current_protected_stage_keys,
    )


def _protected_stage_draft_errors(
    pipeline: Pipeline,
    stages: list[dict[str, object]],
) -> list[str]:
    errors = _protected_stage_layout_errors(pipeline, stages)
    draft_stage_by_key = {
        str(stage["stage_key"]): stage for stage in stages if stage.get("stage_key")
    }

    for existing_stage in pipeline.stages:
        if not existing_stage.is_active or not get_stage_protection(
            existing_stage.stage_key, pipeline.entity_type
        ):
            continue

        draft_stage = draft_stage_by_key.get(existing_stage.stage_key)
        if draft_stage is None or not draft_stage.get("is_active", True):
            errors.append(
                f"Stage '{existing_stage.label}' is a protected system stage and cannot be removed or deactivated."
            )
            continue

        attempted_fields = _protected_stage_update_errors(
            existing_stage,
            entity_type=pipeline.entity_type,
            slug=str(draft_stage.get("slug") or existing_stage.slug),
            label=str(draft_stage.get("label") or existing_stage.label),
            color=str(draft_stage.get("color") or existing_stage.color),
            stage_type=str(
                draft_stage.get("category")
                or draft_stage.get("stage_type")
                or existing_stage.stage_type
            ),
            semantics=draft_stage.get("semantics")
            if isinstance(draft_stage.get("semantics"), dict)
            else None,
        )
        if attempted_fields:
            errors.append(
                f"Stage '{existing_stage.label}' is a protected system stage and cannot be modified ({', '.join(attempted_fields)})."
            )

    return list(dict.fromkeys(errors))


def _merge_required_stage_defs(stage_defs: list[dict], entity_type: str) -> list[dict]:
    """Ensure required system stages exist in a sensible order."""
    normalized_defs = [dict(stage) for stage in stage_defs]
    existing_keys = {
        _normalize_stage_key(stage.get("stage_key") or stage.get("slug"))
        for stage in normalized_defs
    }
    default_positions = _default_stage_position_map(entity_type)

    for stage_def in get_protected_system_stage_defs(entity_type):
        stage_key = _normalize_stage_key(stage_def.get("stage_key") or stage_def["slug"])
        if stage_key in existing_keys:
            continue
        insert_at = next(
            (
                index
                for index, stage in enumerate(normalized_defs)
                if default_positions.get(
                    _normalize_stage_key(stage.get("stage_key") or stage.get("slug")),
                    float("inf"),
                )
                > default_positions.get(stage_key, float("inf"))
            ),
            len(normalized_defs),
        )
        normalized_defs.insert(insert_at, dict(stage_def))
        existing_keys.add(stage_key)

    for order, stage in enumerate(normalized_defs, start=1):
        stage["order"] = order

    return normalized_defs


def _merge_missing_stage_defs(
    existing_stages: list[PipelineStage],
    missing_defs: list[dict[str, object]],
    entity_type: str,
) -> list[PipelineStage | dict[str, object]]:
    """Insert missing required stages while preserving default protected-stage order."""
    ordered_items: list[PipelineStage | dict[str, object]] = sorted(
        existing_stages,
        key=lambda stage: stage.order,
    )
    default_positions = _default_stage_position_map(entity_type)

    for stage_def in missing_defs:
        stage_key = _normalize_stage_key(stage_def.get("stage_key") or stage_def["slug"])
        insert_at = next(
            (
                index
                for index, stage in enumerate(ordered_items)
                if default_positions.get(
                    _normalize_stage_key(
                        stage.stage_key
                        if isinstance(stage, PipelineStage)
                        else stage.get("stage_key") or stage.get("slug")
                    ),
                    float("inf"),
                )
                > default_positions.get(stage_key, float("inf"))
            ),
            len(ordered_items),
        )
        ordered_items.insert(insert_at, stage_def)

    return ordered_items


def _pipeline_payload(pipeline: Pipeline) -> dict:
    """Extract versionable payload from pipeline."""
    return {
        "name": pipeline.name,
        "entity_type": pipeline.entity_type,
        "is_default": pipeline.is_default,
        "feature_config": pipeline_semantics_service.get_pipeline_feature_config(
            pipeline
        ).model_dump(mode="json"),
        "stages": [
            {
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": stage.order,
                "stage_type": stage.stage_type,
                "is_active": stage.is_active,
                "semantics": pipeline_semantics_service.get_stage_semantics(stage).model_dump(
                    mode="json"
                ),
            }
            for stage in pipeline.stages
        ],
    }


def _serialize_stage(
    stage: PipelineStage,
    entity_type: str | None = None,
) -> dict[str, object]:
    normalized_entity_type = entity_type or getattr(
        getattr(stage, "pipeline", None), "entity_type", None
    )
    return {
        "id": stage.id,
        "stage_key": _normalize_stage_key(stage.stage_key or stage.slug),
        "slug": stage.slug,
        "label": stage.label,
        "color": stage.color,
        "order": stage.order,
        "category": stage.stage_type,
        "stage_type": stage.stage_type,
        "is_active": stage.is_active,
        "semantics": pipeline_semantics_service.get_stage_semantics(stage).model_dump(mode="json"),
        **get_stage_protection_metadata(stage.stage_key or stage.slug, normalized_entity_type),
    }


def _derive_stage_category(stage: PipelineStage) -> str:
    normalized_stage_type = pipeline_change_service.normalize_stage_category(stage.stage_type)
    semantics = pipeline_semantics_service.get_stage_semantics(stage)

    if semantics.pause_behavior != "none":
        return "paused"
    if semantics.terminal_outcome != "none":
        return "terminal"
    if normalized_stage_type in VALID_STAGE_TYPES:
        return normalized_stage_type
    if stage.is_intake_stage:
        return "intake"
    if (
        semantics.capabilities.eligible_for_matching
        or semantics.capabilities.locks_match_state
        or semantics.capabilities.shows_pregnancy_tracking
        or semantics.capabilities.requires_delivery_details
    ):
        return "post_approval"
    return "intake"


def _ensure_pipeline_semantics_defaults(db: Session, pipeline: Pipeline) -> bool:
    dirty = False

    for stage in pipeline.stages:
        normalized_stage_key = _normalize_stage_key(stage.stage_key or stage.slug)
        if stage.stage_key != normalized_stage_key:
            stage.stage_key = normalized_stage_key
            dirty = True
        normalized_stage_type = _derive_stage_category(stage)
        if stage.stage_type != normalized_stage_type:
            stage.stage_type = normalized_stage_type
            dirty = True
        expected_is_intake_stage = stage.stage_type == "intake"
        if stage.is_intake_stage != expected_is_intake_stage:
            stage.is_intake_stage = expected_is_intake_stage
            dirty = True
        normalized_semantics = pipeline_semantics_service.get_stage_semantics(stage).model_dump(
            mode="json"
        )
        if stage.semantics != normalized_semantics:
            stage.semantics = normalized_semantics
            dirty = True

    if not isinstance(pipeline.feature_config, dict) or not pipeline.feature_config:
        normalized_feature_config = pipeline_semantics_service.get_pipeline_feature_config(
            {
                "entity_type": pipeline.entity_type,
                "feature_config": default_pipeline_feature_config(pipeline.entity_type),
            }
        )
    else:
        normalized_feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline)
    normalized_payload = _prune_feature_config_for_stage_defs(
        normalized_feature_config,
        _normalized_stage_defs_for_pipeline(pipeline),
    )
    if normalized_payload != pipeline.feature_config:
        pipeline.feature_config = normalized_payload
        dirty = True

    if dirty:
        db.flush()
    return dirty


def _build_default_feature_config_for_stages(
    stage_defs: list[dict],
    entity_type: str,
) -> dict:
    """Prune default feature config to the semantic stage keys present in a pipeline."""
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {
            "entity_type": entity_type,
            "feature_config": default_pipeline_feature_config(entity_type),
        }
    )
    return _prune_feature_config_for_stage_defs(feature_config, stage_defs)


def _prune_feature_config_for_stage_defs(
    feature_config: PipelineFeatureConfig,
    stage_defs: list[dict[str, object]],
) -> dict[str, object]:
    active_stage_keys = {
        _normalize_stage_key(stage.get("stage_key") or stage.get("slug"))
        for stage in stage_defs
        if stage.get("is_active", True)
    }

    feature_config.journey.milestones = [
        milestone.model_copy(
            update={
                "mapped_stage_keys": [
                    stage_key
                    for stage_key in milestone.mapped_stage_keys
                    if _normalize_stage_key(stage_key) in active_stage_keys
                ]
            }
        )
        for milestone in feature_config.journey.milestones
    ]
    feature_config.analytics.funnel_stage_keys = [
        stage_key
        for stage_key in feature_config.analytics.funnel_stage_keys
        if _normalize_stage_key(stage_key) in active_stage_keys
    ]
    feature_config.analytics.performance_stage_keys = [
        stage_key
        for stage_key in feature_config.analytics.performance_stage_keys
        if _normalize_stage_key(stage_key) in active_stage_keys
    ]
    if (
        _normalize_stage_key(feature_config.analytics.qualification_stage_key)
        not in active_stage_keys
    ):
        feature_config.analytics.qualification_stage_key = (
            feature_config.analytics.performance_stage_keys[0]
            if feature_config.analytics.performance_stage_keys
            else None
        )
    if _normalize_stage_key(feature_config.analytics.conversion_stage_key) not in active_stage_keys:
        feature_config.analytics.conversion_stage_key = (
            feature_config.analytics.performance_stage_keys[-1]
            if feature_config.analytics.performance_stage_keys
            else (
                feature_config.analytics.funnel_stage_keys[-1]
                if feature_config.analytics.funnel_stage_keys
                else None
            )
        )
    feature_config.role_visibility = {
        role: rule.model_copy(
            update={
                "stage_keys": [
                    stage_key
                    for stage_key in rule.stage_keys
                    if _normalize_stage_key(stage_key) in active_stage_keys
                ]
            }
        )
        for role, rule in feature_config.role_visibility.items()
    }
    feature_config.role_mutation = {
        role: rule.model_copy(
            update={
                "stage_keys": [
                    stage_key
                    for stage_key in rule.stage_keys
                    if _normalize_stage_key(stage_key) in active_stage_keys
                ]
            }
        )
        for role, rule in feature_config.role_mutation.items()
    }
    return feature_config.model_dump(mode="json")


def _normalized_stage_defs_for_pipeline(pipeline: Pipeline) -> list[dict[str, object]]:
    return [
        {
            "stage_key": _normalize_stage_key(stage.stage_key or stage.slug),
            "slug": stage.slug,
            "is_active": stage.is_active,
        }
        for stage in pipeline.stages
    ]


def _resolve_custom_stage_insert_order(
    pipeline: Pipeline,
    requested_order: int | None,
) -> int:
    active_stages = sorted(
        (stage for stage in pipeline.stages if stage.is_active),
        key=lambda stage: stage.order,
    )
    if not active_stages:
        return 1

    protected_positions = [
        index + 1
        for index, stage in enumerate(active_stages)
        if get_stage_protection(stage.stage_key or stage.slug, pipeline.entity_type)
    ]
    if len(protected_positions) >= 2:
        min_order = protected_positions[0] + 1
        max_order = protected_positions[-1]
    elif protected_positions:
        min_order = protected_positions[0] + 1
        max_order = len(active_stages) + 1
    else:
        min_order = 1
        max_order = len(active_stages) + 1

    desired_order = requested_order if requested_order is not None else max_order
    return max(min_order, min(desired_order, max_order))


def _insert_stage_at_order(
    pipeline: Pipeline,
    stage: PipelineStage,
    order: int,
) -> None:
    active_stages = sorted(
        (existing_stage for existing_stage in pipeline.stages if existing_stage.is_active),
        key=lambda existing_stage: existing_stage.order,
    )
    insert_at = max(1, min(order, len(active_stages) + 1))
    for existing_stage in active_stages:
        if existing_stage.id == stage.id:
            continue
        if existing_stage.order >= insert_at:
            existing_stage.order += 1
    stage.order = insert_at


def _normalize_existing_stage_orders(pipeline: Pipeline) -> None:
    for order, stage in enumerate(
        sorted(
            (existing_stage for existing_stage in pipeline.stages if existing_stage.is_active),
            key=lambda existing_stage: existing_stage.order,
        ),
        start=1,
    ):
        stage.order = order


def _validate_pipeline_configuration(db: Session, pipeline: Pipeline) -> None:
    db.flush()
    active_stages = sorted(
        (stage for stage in pipeline.stages if stage.is_active),
        key=lambda stage: stage.order,
    )
    layout_errors = _protected_stage_layout_errors(
        pipeline,
        [_serialize_stage(stage, pipeline.entity_type) for stage in active_stages],
    )
    if layout_errors:
        raise ValueError("; ".join(layout_errors))
    feature_config = pipeline_semantics_service.get_pipeline_feature_config(pipeline)
    pipeline_change_service.validate_guarded_invariants(
        [_serialize_stage(stage, pipeline.entity_type) for stage in active_stages],
        feature_config,
        pipeline.entity_type,
    )


def get_or_create_default_pipeline(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
    entity_type: str = SURROGATE_PIPELINE_ENTITY,
) -> Pipeline:
    """
    Get the default pipeline for an org, creating if not exists.

    Called on first access to ensure every org has a pipeline.
    Creates initial version snapshot.
    """
    normalized_entity_type = _normalize_pipeline_entity_type(entity_type)
    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type == normalized_entity_type,
            Pipeline.is_default.is_(True),
        )
        .first()
    )

    if not pipeline:
        pipeline = Pipeline(
            organization_id=org_id,
            entity_type=normalized_entity_type,
            name="Default",
            is_default=True,
            current_version=1,
            feature_config=default_pipeline_feature_config(normalized_entity_type),
        )
        db.add(pipeline)
        db.flush()

        # Create default stage rows
        stage_defs = get_default_stage_defs(normalized_entity_type)
        db.add_all(
            [
                PipelineStage(
                    pipeline_id=pipeline.id,
                    stage_key=_normalize_stage_key(stage.get("stage_key") or stage["slug"]),
                    slug=stage["slug"],
                    label=stage["label"],
                    color=stage["color"],
                    order=stage["order"],
                    stage_type=stage["stage_type"],
                    semantics=default_stage_semantics(
                        _normalize_stage_key(stage.get("stage_key") or stage["slug"]),
                        stage["stage_type"],
                        normalized_entity_type,
                    ),
                    is_intake_stage=stage["stage_type"] == "intake",
                    is_active=True,
                )
                for stage in stage_defs
            ]
        )
        db.flush()
        _validate_pipeline_configuration(db, pipeline)

        # Create initial version snapshot
        version_service.create_version(
            db=db,
            org_id=org_id,
            entity_type=ENTITY_TYPE,
            entity_id=pipeline.id,
            payload=_pipeline_payload(pipeline),
            created_by_user_id=user_id,  # None for system-created
            comment="Initial version",
        )
        db.commit()
        db.refresh(pipeline)
        return pipeline

    legacy_requires_full_default_sync = (
        not isinstance(pipeline.feature_config, dict) or not pipeline.feature_config
    )
    changed = _ensure_pipeline_semantics_defaults(db, pipeline)
    existing_stage_keys = {
        _normalize_stage_key(stage.stage_key or stage.slug)
        for stage in pipeline.stages
        if not stage.deleted_at
    }
    required_stage_defs = (
        get_default_stage_defs(pipeline.entity_type)
        if legacy_requires_full_default_sync
        else get_protected_system_stage_defs(pipeline.entity_type)
    )
    required_stage_keys = {
        _normalize_stage_key(stage_def.get("stage_key") or stage_def["slug"])
        for stage_def in required_stage_defs
    }
    if required_stage_keys - existing_stage_keys:
        sync_missing_stages(db, pipeline, user_id, stage_defs=required_stage_defs)
        db.refresh(pipeline)
        return pipeline

    if changed:
        db.commit()
        db.refresh(pipeline)
    return pipeline


def get_pipeline(
    db: Session,
    org_id: UUID,
    pipeline_id: UUID,
    entity_type: str | None = None,
) -> Pipeline | None:
    """Get pipeline by ID (org-scoped)."""
    query = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == org_id,
    )
    if entity_type:
        query = query.filter(Pipeline.entity_type == _normalize_pipeline_entity_type(entity_type))
    return query.first()


def list_pipelines(
    db: Session,
    org_id: UUID,
    entity_type: str = SURROGATE_PIPELINE_ENTITY,
) -> list[Pipeline]:
    """List all pipelines for an org."""
    return (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.entity_type == _normalize_pipeline_entity_type(entity_type),
        )
        .order_by(Pipeline.is_default.desc(), Pipeline.name)
        .all()
    )


def sync_missing_stages(
    db: Session,
    pipeline: Pipeline,
    user_id: UUID | None = None,
    stage_defs: list[dict[str, object]] | None = None,
) -> int:
    """
    Add missing default stages to an existing pipeline.

    Compares existing stages against DEFAULT_STAGE_ORDER and adds any missing ones.
    Returns count of stages added.
    """
    active_stages = [stage for stage in pipeline.stages if not stage.deleted_at]
    existing_stage_keys = {s.stage_key for s in active_stages}

    # Find missing stage keys
    default_defs = stage_defs or get_protected_system_stage_defs(pipeline.entity_type)
    missing = [
        d
        for d in default_defs
        if _normalize_stage_key(d.get("stage_key") or d["slug"]) not in existing_stage_keys
    ]

    if not missing:
        return 0

    ordered_items = _merge_missing_stage_defs(active_stages, missing, pipeline.entity_type)

    for index, item in enumerate(ordered_items, start=1):
        if isinstance(item, PipelineStage):
            item.order = index
            item.updated_at = datetime.now(timezone.utc)
            continue

        db.add(
            PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=_normalize_stage_key(item.get("stage_key") or item["slug"]),
                slug=item["slug"],
                label=item["label"],
                color=item["color"],
                order=index,
                stage_type=item["stage_type"],
                semantics=default_stage_semantics(
                    _normalize_stage_key(item.get("stage_key") or item["slug"]),
                    item["stage_type"],
                    pipeline.entity_type,
                ),
                is_intake_stage=item["stage_type"] == "intake",
                is_active=True,
            )
        )

    db.flush()
    db.refresh(pipeline)
    _ensure_pipeline_semantics_defaults(db, pipeline)
    _validate_pipeline_configuration(db, pipeline)
    _bump_pipeline_version(db, pipeline, user_id, f"Added {len(missing)} missing stages")

    db.commit()
    db.refresh(pipeline)
    return len(missing)


def update_pipeline_stages(
    db: Session,
    pipeline: Pipeline,
    stages: list[dict],
    user_id: UUID,
    expected_version: int | None = None,
    comment: str | None = None,
) -> Pipeline:
    """Stage updates are handled via /stages endpoints in v2."""
    raise ValueError("Stage updates must use /settings/pipelines/{id}/stages endpoints.")


def update_pipeline_name(
    db: Session,
    pipeline: Pipeline,
    name: str,
    user_id: UUID,
    comment: str | None = None,
) -> Pipeline:
    """
    Update pipeline name with version control.

    Creates version snapshot on name change.
    """
    pipeline.name = name
    _bump_pipeline_version(db, pipeline, user_id, comment or "Renamed")

    db.commit()
    db.refresh(pipeline)
    return pipeline


def update_pipeline_feature_config(
    db: Session,
    pipeline: Pipeline,
    feature_config: dict,
    user_id: UUID,
    comment: str | None = None,
) -> Pipeline:
    """Update pipeline-level feature configuration with version control."""
    pipeline.feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {"entity_type": pipeline.entity_type, "feature_config": feature_config}
    ).model_dump(mode="json")
    _validate_pipeline_configuration(db, pipeline)
    _bump_pipeline_version(db, pipeline, user_id, comment or "Updated pipeline behavior")
    db.commit()
    db.refresh(pipeline)
    return pipeline


def create_pipeline(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    entity_type: str = SURROGATE_PIPELINE_ENTITY,
    stages: list[dict] | None = None,
    feature_config: dict | None = None,
) -> Pipeline:
    """
    Create a new non-default pipeline with initial version.

    Uses default stages if not provided.
    """
    normalized_entity_type = _normalize_pipeline_entity_type(entity_type)
    stage_defs = _merge_required_stage_defs(
        stages or get_default_stage_defs(normalized_entity_type),
        normalized_entity_type,
    )
    pipeline = Pipeline(
        organization_id=org_id,
        entity_type=normalized_entity_type,
        name=name,
        is_default=False,
        current_version=1,
        feature_config=feature_config
        or _build_default_feature_config_for_stages(stage_defs, normalized_entity_type),
    )
    db.add(pipeline)
    db.flush()

    db.add_all(
        [
            PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=_normalize_stage_key(stage.get("stage_key") or stage["slug"]),
                slug=stage["slug"],
                label=stage["label"],
                color=stage["color"],
                order=stage.get("order", i + 1),
                stage_type=stage.get("category") or stage.get("stage_type", "intake"),
                semantics=pipeline_semantics_service.get_stage_semantics(
                    {
                        "entity_type": normalized_entity_type,
                        "stage_key": _normalize_stage_key(stage.get("stage_key") or stage["slug"]),
                        "slug": stage["slug"],
                        "stage_type": stage.get("category") or stage.get("stage_type", "intake"),
                        "semantics": stage.get("semantics"),
                    }
                ).model_dump(mode="json"),
                is_intake_stage=stage.get(
                    "is_intake_stage",
                    (stage.get("category") or stage.get("stage_type", "intake")) == "intake",
                ),
                is_active=stage.get("is_active", True),
            )
            for i, stage in enumerate(stage_defs)
        ]
    )
    db.flush()
    _ensure_pipeline_semantics_defaults(db, pipeline)
    _validate_pipeline_configuration(db, pipeline)

    # Create initial version snapshot
    version_service.create_version(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=pipeline.id,
        payload=_pipeline_payload(pipeline),
        created_by_user_id=user_id,
        comment="Created",
    )

    db.commit()
    db.refresh(pipeline)
    return pipeline


def delete_pipeline(db: Session, pipeline: Pipeline) -> bool:
    """
    Delete a pipeline.

    Cannot delete the default pipeline.
    Note: Versions are retained for audit history.
    """
    if pipeline.is_default:
        return False

    db.delete(pipeline)
    db.commit()
    return True


def _bump_pipeline_version(
    db: Session,
    pipeline: Pipeline,
    user_id: UUID | None,
    comment: str,
) -> None:
    """Create a new pipeline version snapshot after stage changes."""
    db.flush()
    locked_pipeline = (
        db.query(Pipeline)
        .options(selectinload(Pipeline.stages))
        .filter(Pipeline.id == pipeline.id)
        .with_for_update()
        .first()
    )
    if not locked_pipeline:
        return

    version = version_service.create_version(
        db=db,
        org_id=locked_pipeline.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=locked_pipeline.id,
        payload=_pipeline_payload(locked_pipeline),
        created_by_user_id=user_id,
        comment=comment,
    )
    locked_pipeline.current_version = version.version
    locked_pipeline.updated_at = datetime.now(timezone.utc)


# =============================================================================
# Version Control
# =============================================================================


def get_pipeline_versions(
    db: Session,
    org_id: UUID,
    pipeline_id: UUID,
    limit: int = 50,
) -> list:
    """Get version history for a pipeline."""
    return version_service.get_version_history(
        db=db,
        org_id=org_id,
        entity_type=ENTITY_TYPE,
        entity_id=pipeline_id,
        limit=limit,
    )


def rollback_pipeline(
    db: Session,
    pipeline: Pipeline,
    target_version: int,
    user_id: UUID,
) -> tuple[Pipeline | None, str | None]:
    """
    Rollback pipeline to a previous version.

    Creates a NEW version with old payload (never rewrites history).

    Returns:
        (updated_pipeline, error) - error is set if rollback failed
    """
    # Rollback version (creates new version from old payload)
    new_version, error = version_service.rollback_to_version(
        db=db,
        org_id=pipeline.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=pipeline.id,
        target_version=target_version,
        user_id=user_id,
    )

    if error:
        return None, error

    # Get the rolled-back payload and apply to pipeline
    payload = version_service.decrypt_payload(new_version.payload_encrypted)

    pipeline.name = payload.get("name", pipeline.name)
    pipeline.feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {"feature_config": payload.get("feature_config")}
    ).model_dump(mode="json")
    pipeline.current_version = new_version.version
    pipeline.updated_at = datetime.now(timezone.utc)

    # Reconcile stage rows by immutable stage_key (fallback to slug for legacy payloads)
    payload_stages = payload.get("stages", [])
    existing_by_key = {s.stage_key: s for s in pipeline.stages}
    existing_by_slug = {s.slug: s for s in pipeline.stages}
    payload_stage_keys = set()

    for stage_data in payload_stages:
        stage_key = _normalize_stage_key(stage_data.get("stage_key") or stage_data.get("slug"))
        slug = _normalize_slug(stage_data.get("slug") or stage_key)
        if not stage_key or not slug:
            continue
        payload_stage_keys.add(stage_key)

        stage = existing_by_key.get(stage_key) or existing_by_slug.get(slug)
        if stage:
            stage.stage_key = stage_key
            stage.slug = slug
            stage.label = stage_data.get("label", stage.label)
            stage.color = stage_data.get("color", stage.color)
            stage.order = stage_data.get("order", stage.order)
            stage.stage_type = stage_data.get(
                "category",
                stage_data.get("stage_type", stage.stage_type),
            )
            stage.semantics = pipeline_semantics_service.get_stage_semantics(
                {
                    "stage_key": stage_key,
                    "slug": slug,
                    "stage_type": stage_data.get(
                        "category",
                        stage_data.get("stage_type", stage.stage_type),
                    ),
                    "semantics": stage_data.get("semantics"),
                }
            ).model_dump(mode="json")
            stage.is_intake_stage = stage.stage_type == "intake"
            stage.is_active = stage_data.get("is_active", stage.is_active)
            stage.updated_at = datetime.now(timezone.utc)
            if not stage.is_active and stage.deleted_at is None:
                stage.deleted_at = datetime.now(timezone.utc)
        else:
            stage = PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=stage_key,
                slug=slug,
                label=stage_data.get("label", humanize_identifier(slug)),
                color=stage_data.get("color", "#6B7280"),
                order=stage_data.get("order", len(existing_by_key) + 1),
                stage_type=stage_data.get("category", stage_data.get("stage_type", "intake")),
                semantics=pipeline_semantics_service.get_stage_semantics(
                    {
                        "stage_key": stage_key,
                        "slug": slug,
                        "stage_type": stage_data.get(
                            "category",
                            stage_data.get("stage_type", "intake"),
                        ),
                        "semantics": stage_data.get("semantics"),
                    }
                ).model_dump(mode="json"),
                is_intake_stage=stage_data.get(
                    "category",
                    stage_data.get("stage_type", "intake"),
                )
                == "intake",
                is_active=stage_data.get("is_active", True),
            )
            db.add(stage)

    # Soft-deactivate stages not present in payload
    for stage_key, stage in existing_by_key.items():
        if stage_key not in payload_stage_keys and stage.is_active:
            stage.is_active = False
            stage.deleted_at = datetime.now(timezone.utc)
            stage.updated_at = datetime.now(timezone.utc)

    _ensure_pipeline_semantics_defaults(db, pipeline)
    _validate_pipeline_configuration(db, pipeline)

    db.commit()
    db.refresh(pipeline)

    return pipeline, None


# =============================================================================
# Stage CRUD (v2.1 - PipelineStage rows)
# =============================================================================


def get_stages(
    db: Session,
    pipeline_id: UUID,
    include_inactive: bool = False,
) -> list[PipelineStage]:
    """Get all stages for a pipeline, ordered by position."""
    query = db.query(PipelineStage).filter(PipelineStage.pipeline_id == pipeline_id)
    if not include_inactive:
        query = query.filter(PipelineStage.is_active.is_(True))
    return query.order_by(PipelineStage.order).all()


def get_stage_by_id(db: Session, stage_id: UUID) -> PipelineStage | None:
    """Get a stage by ID."""
    return db.query(PipelineStage).filter(PipelineStage.id == stage_id).first()


def get_stage_by_key(db: Session, pipeline_id: UUID, stage_key: str) -> PipelineStage | None:
    """Get a stage by immutable semantic key (unique per pipeline)."""
    normalized_key = _normalize_stage_key(stage_key)
    if not normalized_key:
        return None
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            (PipelineStage.stage_key == normalized_key)
            | ((PipelineStage.stage_key.is_(None)) & (PipelineStage.slug == normalized_key)),
        )
        .order_by((PipelineStage.stage_key == normalized_key).desc())
        .first()
    )


def get_stage_by_system_role(
    db: Session,
    pipeline_id: UUID,
    system_role: str,
    entity_type: str | None = None,
) -> PipelineStage | None:
    resolved_entity_type = entity_type
    if not resolved_entity_type:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        resolved_entity_type = pipeline.entity_type if pipeline else None
    stage_key = get_system_stage_key(resolved_entity_type, system_role)
    if not stage_key:
        return None
    return get_stage_by_key(db, pipeline_id, stage_key)


def get_stage_by_slug(db: Session, pipeline_id: UUID, slug: str) -> PipelineStage | None:
    """Get a stage by slug, with stage_key fallback for dynamic resolution."""
    normalized_slug = _normalize_slug(slug)
    if not normalized_slug:
        return None
    normalized_key = _normalize_stage_key(normalized_slug)
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            (PipelineStage.slug == normalized_slug) | (PipelineStage.stage_key == normalized_key),
        )
        .order_by((PipelineStage.slug == normalized_slug).desc())
        .first()
    )


def resolve_stage(db: Session, pipeline_id: UUID, ref: str | UUID | None) -> PipelineStage | None:
    """
    Resolve a stage by stage ID, stage_key, or slug.

    Resolution order:
    1) stage_id (UUID)
    2) stage_key (canonicalized)
    3) slug
    """
    if ref is None:
        return None

    if isinstance(ref, UUID):
        return (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.id == ref,
            )
            .first()
        )

    ref_str = str(ref).strip()
    if not ref_str:
        return None

    try:
        ref_uuid = UUID(ref_str)
    except ValueError:
        ref_uuid = None

    if ref_uuid is not None:
        stage = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.id == ref_uuid,
            )
            .first()
        )
        if stage:
            return stage

    stage = get_stage_by_key(db, pipeline_id, ref_str)
    if stage:
        return stage
    return get_stage_by_slug(db, pipeline_id, ref_str)


def get_stage_ids_by_keys_or_slugs(
    db: Session,
    org_id: UUID,
    refs: list[str],
    pipeline_id: UUID | None = None,
    entity_type: str = SURROGATE_PIPELINE_ENTITY,
) -> list[UUID]:
    """Resolve a mixed list of stage keys/slugs into stage IDs for an org pipeline."""
    if not refs:
        return []

    if pipeline_id is None:
        pipeline = get_or_create_default_pipeline(db, org_id, entity_type=entity_type)
        pipeline_id = pipeline.id

    stage_ids: list[UUID] = []
    seen: set[UUID] = set()
    for ref in refs:
        stage = resolve_stage(db, pipeline_id, ref)
        if stage and stage.id not in seen:
            seen.add(stage.id)
            stage_ids.append(stage.id)
    return stage_ids


def validate_stage_slug(
    db: Session,
    pipeline_id: UUID,
    slug: str,
    *,
    exclude_stage_id: UUID | None = None,
) -> bool:
    """Check if slug is valid (unique per pipeline, not empty)."""
    normalized_slug = _normalize_slug(slug)
    if not normalized_slug or len(normalized_slug) > 50:
        return False
    query = db.query(PipelineStage).filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.slug == normalized_slug,
    )
    if exclude_stage_id is not None:
        query = query.filter(PipelineStage.id != exclude_stage_id)
    return query.first() is None


def create_stage(
    db: Session,
    pipeline_id: UUID,
    slug: str,
    label: str,
    color: str,
    stage_type: str,
    order: int | None = None,
    semantics: dict | None = None,
    user_id: UUID | None = None,
) -> PipelineStage:
    """
    Create a new pipeline stage.

    stage_key is immutable after creation.
    Slug and category remain editable via update_stage.
    Raises ValueError if slug/stage_key already exists or stage_type is invalid.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    pipeline_entity_type = pipeline.entity_type if pipeline else SURROGATE_PIPELINE_ENTITY

    normalized_slug = _normalize_slug(slug)
    stage_key = _normalize_stage_key(normalized_slug)
    if not normalized_slug:
        raise ValueError("Slug cannot be empty")

    # Validate stage_type
    stage_type = pipeline_change_service.normalize_stage_category(stage_type)
    if stage_type not in VALID_STAGE_TYPES:
        raise ValueError(f"Invalid stage_type: {stage_type}")

    # Validate slug uniqueness
    if not validate_stage_slug(db, pipeline_id, normalized_slug):
        raise ValueError(f"Slug '{normalized_slug}' already exists or is invalid")

    # Validate stage_key uniqueness (immutable semantic key)
    existing_key = get_stage_by_key(db, pipeline_id, stage_key)
    if existing_key:
        raise ValueError(f"Stage key '{stage_key}' already exists in this pipeline")

    if pipeline:
        order = _resolve_custom_stage_insert_order(pipeline, order)
    else:
        # Auto-calculate order if not provided
        if order is None:
            max_order = (
                db.query(PipelineStage)
                .filter(
                    PipelineStage.pipeline_id == pipeline_id,
                )
                .count()
            )
            order = max_order + 1

    stage = PipelineStage(
        pipeline_id=pipeline_id,
        stage_key=stage_key,
        slug=normalized_slug,
        label=label,
        color=color,
        stage_type=stage_type,
        order=order,
        semantics=_normalize_stage_semantics_payload(
            entity_type=pipeline_entity_type,
            stage_key=stage_key,
            slug=normalized_slug,
            stage_type=stage_type,
            semantics=semantics,
            stage_label=label,
        ),
        is_intake_stage=stage_type == "intake",
        is_active=True,
    )
    db.add(stage)
    db.flush()
    if pipeline:
        if all(existing_stage.id != stage.id for existing_stage in pipeline.stages):
            pipeline.stages.append(stage)
        _insert_stage_at_order(pipeline, stage, order)
        _normalize_existing_stage_orders(pipeline)
        _ensure_pipeline_semantics_defaults(db, pipeline)
        _validate_pipeline_configuration(db, pipeline)
        _bump_pipeline_version(db, pipeline, user_id, f"Added stage {normalized_slug}")
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session,
    stage: PipelineStage,
    slug: str | None = None,
    label: str | None = None,
    color: str | None = None,
    order: int | None = None,
    stage_type: str | None = None,
    semantics: dict | None = None,
    user_id: UUID | None = None,
) -> PipelineStage:
    """
    Update stage slug, label, color, or order.

    stage_key is immutable. stage_type/category is editable.
    Syncs case status_label when label changes.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == stage.pipeline_id).first()
    pipeline_entity_type = pipeline.entity_type if pipeline else SURROGATE_PIPELINE_ENTITY

    label_changed = False
    attempted_fields = _protected_stage_update_errors(
        stage,
        entity_type=pipeline_entity_type,
        slug=slug,
        label=label,
        color=color,
        order=order,
        stage_type=stage_type,
        semantics=semantics,
    )
    if attempted_fields:
        raise ValueError(
            f"Stage '{stage.label}' is a protected system stage and cannot be modified ({', '.join(attempted_fields)})."
        )

    if slug is not None:
        normalized_slug = _normalize_slug(slug)
        if not validate_stage_slug(
            db, stage.pipeline_id, normalized_slug, exclude_stage_id=stage.id
        ):
            raise ValueError(f"Slug '{normalized_slug}' already exists or is invalid")
        stage.slug = normalized_slug

    if label is not None and label != stage.label:
        stage.label = label
        label_changed = True

    if color is not None:
        stage.color = color

    if order is not None:
        stage.order = order

    if stage_type is not None:
        normalized_stage_type = pipeline_change_service.normalize_stage_category(stage_type)
        if normalized_stage_type not in VALID_STAGE_TYPES:
            raise ValueError(f"Invalid stage_type: {normalized_stage_type}")
        stage.stage_type = normalized_stage_type
        stage.is_intake_stage = normalized_stage_type == "intake"

    if semantics is not None:
        stage.semantics = _normalize_stage_semantics_payload(
            entity_type=pipeline_entity_type,
            stage_key=stage.stage_key,
            slug=stage.slug,
            stage_type=stage.stage_type,
            semantics=semantics,
            stage_label=stage.label,
        )

    stage.updated_at = datetime.now(timezone.utc)
    if pipeline:
        _ensure_pipeline_semantics_defaults(db, pipeline)
        _validate_pipeline_configuration(db, pipeline)
        _bump_pipeline_version(db, pipeline, user_id, f"Updated stage {stage.stage_key}")
    db.commit()
    db.refresh(stage)

    # Sync case labels if label changed
    if label_changed and pipeline and pipeline.entity_type == SURROGATE_PIPELINE_ENTITY:
        sync_surrogate_labels(db, stage.id, stage.label)

    return stage


def delete_stage(
    db: Session,
    stage: PipelineStage,
    migrate_to_stage_id: UUID,
    user_id: UUID | None = None,
) -> int:
    """
    Soft-delete a stage and migrate cases to another stage.

    Returns the number of cases migrated.
    Raises ValueError if migrate_to is invalid or same stage.
    """
    if stage.id == migrate_to_stage_id:
        raise ValueError("Cannot migrate cases to the same stage")
    pipeline = db.query(Pipeline).filter(Pipeline.id == stage.pipeline_id).first()
    pipeline_entity_type = pipeline.entity_type if pipeline else SURROGATE_PIPELINE_ENTITY
    if get_stage_protection(stage.stage_key, pipeline_entity_type):
        raise ValueError(
            f"Stage '{stage.label}' is a protected system stage and cannot be deleted."
        )

    # Validate migrate_to stage
    target = get_stage_by_id(db, migrate_to_stage_id)
    if not target:
        raise ValueError("Target stage not found")
    if not target.is_active:
        raise ValueError("Target stage is not active")
    if target.pipeline_id != stage.pipeline_id:
        raise ValueError("Target stage must be in the same pipeline")

    migrated = 0
    if pipeline and pipeline.entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
        migrated = (
            db.query(IntendedParent)
            .filter(IntendedParent.stage_id == stage.id)
            .update(
                {
                    IntendedParent.stage_id: migrate_to_stage_id,
                    IntendedParent.status: target.stage_key,
                }
            )
        )
    else:
        migrated = (
            db.query(Surrogate)
            .filter(Surrogate.stage_id == stage.id)
            .update(
                {
                    Surrogate.stage_id: migrate_to_stage_id,
                    Surrogate.status_label: target.label,
                }
            )
        )
        (
            db.query(Surrogate)
            .filter(Surrogate.paused_from_stage_id == stage.id)
            .update({Surrogate.paused_from_stage_id: migrate_to_stage_id})
        )

    pending_request_query = db.query(StatusChangeRequest).filter(
        StatusChangeRequest.organization_id == pipeline.organization_id,
        StatusChangeRequest.entity_type == pipeline_entity_type,
        StatusChangeRequest.status == "pending",
        StatusChangeRequest.target_stage_id == stage.id,
    )
    pending_request_query.update({StatusChangeRequest.target_stage_id: migrate_to_stage_id})

    # Soft-delete stage
    stage.is_active = False
    stage.deleted_at = datetime.now(timezone.utc)
    stage.updated_at = datetime.now(timezone.utc)

    if pipeline:
        _ensure_pipeline_semantics_defaults(db, pipeline)
        _validate_pipeline_configuration(db, pipeline)
        _bump_pipeline_version(db, pipeline, user_id, f"Deleted stage {stage.slug}")

    db.commit()
    return migrated


def reorder_stages(
    db: Session,
    pipeline_id: UUID,
    ordered_stage_ids: list[UUID],
    user_id: UUID | None = None,
) -> list[PipelineStage]:
    """
    Reorder stages by providing an ordered list of stage IDs.

    Normalizes order values to 1, 2, 3...
    Only active stages can be reordered.
    """
    stages = get_stages(db, pipeline_id)
    stage_map = {s.id: s for s in stages}
    active_ids = set(stage_map.keys())
    ordered_ids = list(dict.fromkeys(ordered_stage_ids))
    if set(ordered_ids) != active_ids:
        raise ValueError("ordered_stage_ids must include every active stage exactly once")

    # Validate all IDs are valid active stages
    for i, stage_id in enumerate(ordered_ids):
        if stage_id not in stage_map:
            raise ValueError(f"Stage ID {stage_id} not found or not active")
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    ordered_stage_payload = [
        _serialize_stage(stage_map[stage_id], pipeline.entity_type if pipeline else None)
        for stage_id in ordered_ids
    ]
    layout_errors = pipeline_change_service.validate_protected_stage_layout(
        ordered_stage_payload,
        entity_type=pipeline.entity_type if pipeline else SURROGATE_PIPELINE_ENTITY,
        current_protected_stage_keys=[
            stage.stage_key
            for stage in stages
            if get_stage_protection(
                stage.stage_key,
                pipeline.entity_type if pipeline else SURROGATE_PIPELINE_ENTITY,
            )
        ],
    )
    if layout_errors:
        raise ValueError("; ".join(layout_errors))

    for i, stage_id in enumerate(ordered_ids):
        stage_map[stage_id].order = i + 1
    if pipeline:
        _ensure_pipeline_semantics_defaults(db, pipeline)
        _validate_pipeline_configuration(db, pipeline)
        _bump_pipeline_version(db, pipeline, user_id, "Reordered stages")
    db.commit()
    return get_stages(db, pipeline_id)


def build_recommended_pipeline_draft(pipeline: Pipeline) -> dict[str, object]:
    stage_defs = get_default_stage_defs(pipeline.entity_type)
    stages = []
    for index, stage in enumerate(stage_defs, start=1):
        stage_type = stage.get("stage_type", "intake")
        stage_key = _normalize_stage_key(stage.get("stage_key") or stage["slug"])
        stages.append(
            {
                "stage_key": stage_key,
                "slug": stage["slug"],
                "label": stage["label"],
                "color": stage["color"],
                "order": index,
                "category": stage_type,
                "stage_type": stage_type,
                "is_active": True,
                "semantics": pipeline_semantics_service.get_stage_semantics(
                    {
                        "entity_type": pipeline.entity_type,
                        "stage_key": stage_key,
                        "slug": stage["slug"],
                        "stage_type": stage_type,
                        "semantics": default_stage_semantics(
                            stage_key,
                            stage_type,
                            pipeline.entity_type,
                        ),
                    }
                ).model_dump(mode="json"),
            }
        )
    return {
        "name": pipeline.name,
        "feature_config": default_pipeline_feature_config(pipeline.entity_type),
        "stages": stages,
    }


def build_pipeline_draft_preview(
    db: Session,
    pipeline: Pipeline,
    *,
    name: str | None,
    stages: list[dict[str, object]],
    feature_config: dict[str, object] | None,
    remaps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    from app.services import pipeline_dependency_service

    existing_stage_by_id = {str(stage.id): stage for stage in pipeline.stages}
    normalized_stages, normalization_errors, safe_auto_fixes = (
        pipeline_change_service.normalize_stage_drafts(
            stages,
            existing_stage_by_id=existing_stage_by_id,
            entity_type=pipeline.entity_type,
        )
    )
    normalization_errors = list(normalization_errors) + _protected_stage_draft_errors(
        pipeline,
        normalized_stages,
    )
    remap_by_key = {
        normalize_stage_ref(item.get("removed_stage_key")): normalize_stage_ref(
            item.get("target_stage_key")
        )
        for item in remaps or []
        if normalize_stage_ref(item.get("removed_stage_key"))
    }
    after_feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {
            "entity_type": pipeline.entity_type,
            "feature_config": feature_config or pipeline.feature_config,
        }
    )
    after_feature_config = pipeline_change_service.apply_feature_config_stage_remaps(
        after_feature_config,
        remap_by_key,
    )
    before_stages = [
        _serialize_stage(stage, pipeline.entity_type)
        for stage in pipeline.stages
        if stage.is_active
    ]
    dependency_graph = pipeline_dependency_service.build_pipeline_dependency_graph(db, pipeline)
    preview = pipeline_change_service.build_pipeline_change_preview(
        dependency_graph=dependency_graph,
        before_stages=before_stages,
        after_stages=normalized_stages,
        before_feature_config=pipeline_semantics_service.get_pipeline_feature_config(pipeline),
        after_feature_config=after_feature_config,
        entity_type=pipeline.entity_type,
        remaps=remaps,
        normalization_errors=normalization_errors,
        safe_auto_fixes=safe_auto_fixes,
    )
    preview["draft_name"] = name or pipeline.name
    preview["normalized_stages"] = normalized_stages
    preview["normalized_feature_config"] = after_feature_config.model_dump(mode="json")
    return preview


def _apply_external_stage_remaps(
    db: Session,
    pipeline: Pipeline,
    remap_by_key: dict[str, str | None],
) -> None:
    from app.services import (
        campaign_service,
        meta_crm_dataset_settings_service,
        workflow_service,
        zapier_settings_service,
    )

    if not remap_by_key:
        return

    if pipeline.entity_type == SURROGATE_PIPELINE_ENTITY:
        rules = (
            db.query(OrgIntelligentSuggestionRule)
            .filter(OrgIntelligentSuggestionRule.organization_id == pipeline.organization_id)
            .all()
        )
        for rule in rules:
            normalized_rule_key = normalize_stage_ref(rule.stage_slug)
            if normalized_rule_key in remap_by_key:
                rule.stage_slug = remap_by_key[normalized_rule_key]

        zapier_settings = (
            db.query(ZapierWebhookSettings)
            .filter(ZapierWebhookSettings.organization_id == pipeline.organization_id)
            .first()
        )
        if zapier_settings and isinstance(zapier_settings.outbound_event_mapping, list):
            remapped = []
            for item in zapier_settings.outbound_event_mapping:
                if not isinstance(item, dict):
                    continue
                normalized_key = normalize_stage_ref(
                    item.get("stage_key") or item.get("stage_slug")
                )
                if normalized_key in remap_by_key:
                    target_key = remap_by_key[normalized_key]
                    if not target_key:
                        continue
                    item = {**item, "stage_key": target_key}
                    item.pop("stage_slug", None)
                remapped.append(item)
            zapier_settings.outbound_event_mapping = (
                zapier_settings_service.normalize_event_mapping(
                    remapped,
                    db=db,
                    organization_id=pipeline.organization_id,
                )
            )

        meta_settings = (
            db.query(MetaCrmDatasetSettings)
            .filter(MetaCrmDatasetSettings.organization_id == pipeline.organization_id)
            .first()
        )
        if meta_settings and isinstance(meta_settings.event_mapping, list):
            remapped = []
            for item in meta_settings.event_mapping:
                if not isinstance(item, dict):
                    continue
                normalized_key = normalize_stage_ref(
                    item.get("stage_key") or item.get("stage_slug")
                )
                if normalized_key in remap_by_key:
                    target_key = remap_by_key[normalized_key]
                    if not target_key:
                        continue
                    item = {**item, "stage_key": target_key}
                    item.pop("stage_slug", None)
                remapped.append(item)
            meta_settings.event_mapping = meta_crm_dataset_settings_service.normalize_event_mapping(
                remapped,
                db=db,
                organization_id=pipeline.organization_id,
            )

    campaigns = (
        db.query(Campaign)
        .filter(
            Campaign.organization_id == pipeline.organization_id,
            Campaign.recipient_type
            == ("case" if pipeline.entity_type == SURROGATE_PIPELINE_ENTITY else "intended_parent"),
            Campaign.status.in_(("draft", "scheduled")),
        )
        .all()
    )
    for campaign in campaigns:
        campaign_service.remap_campaign_stage_references(
            db,
            pipeline.organization_id,
            campaign,
            remap_by_key,
        )

    workflows = (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == pipeline.organization_id)
        .all()
    )
    for workflow in workflows:
        workflow_service.remap_workflow_stage_references(
            db,
            pipeline.organization_id,
            workflow,
            remap_by_key,
        )


def apply_pipeline_draft(
    db: Session,
    pipeline: Pipeline,
    *,
    name: str | None,
    stages: list[dict[str, object]],
    feature_config: dict[str, object] | None,
    remaps: list[dict[str, object]] | None,
    user_id: UUID | None,
    comment: str | None = None,
) -> Pipeline:
    preview = build_pipeline_draft_preview(
        db,
        pipeline,
        name=name,
        stages=stages,
        feature_config=feature_config,
        remaps=remaps,
    )
    errors = list(preview["validation_errors"]) + list(preview["blocking_issues"])
    if errors:
        raise ValueError("; ".join(errors))

    draft_stages = list(preview["normalized_stages"])
    next_feature_config = pipeline_semantics_service.get_pipeline_feature_config(
        {
            "entity_type": pipeline.entity_type,
            "feature_config": preview["normalized_feature_config"],
        }
    )
    remap_by_key = {
        normalize_stage_ref(item.get("removed_stage_key")): normalize_stage_ref(
            item.get("target_stage_key")
        )
        for item in remaps or []
        if normalize_stage_ref(item.get("removed_stage_key"))
    }

    existing_stages = get_stages(db, pipeline.id, include_inactive=True)
    existing_by_id = {str(stage.id): stage for stage in existing_stages}
    existing_by_key = {stage.stage_key: stage for stage in existing_stages if stage.stage_key}
    kept_stage_keys: set[str] = set()

    for draft_stage in draft_stages:
        stage_id = str(draft_stage.get("id") or "").strip() or None
        stage_key = str(draft_stage["stage_key"])
        stage = existing_by_id.get(stage_id) if stage_id else None
        if stage is None:
            stage = existing_by_key.get(stage_key)

        if stage is None:
            stage = PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=stage_key,
                slug=str(draft_stage["slug"]),
                label=str(draft_stage["label"]),
                color=str(draft_stage["color"]),
                order=int(draft_stage["order"]),
                stage_type=str(draft_stage["category"]),
                semantics=dict(draft_stage["semantics"]),
                is_intake_stage=str(draft_stage["category"]) == "intake",
                is_active=bool(draft_stage.get("is_active", True)),
            )
            db.add(stage)
            db.flush()
            pipeline.stages.append(stage)
            existing_by_id[str(stage.id)] = stage
            existing_by_key[stage_key] = stage
        else:
            stage.slug = str(draft_stage["slug"])
            stage.label = str(draft_stage["label"])
            stage.color = str(draft_stage["color"])
            stage.order = int(draft_stage["order"])
            stage.stage_type = str(draft_stage["category"])
            stage.semantics = dict(draft_stage["semantics"])
            stage.is_intake_stage = stage.stage_type == "intake"
            stage.is_active = bool(draft_stage.get("is_active", True))
            stage.deleted_at = None if stage.is_active else datetime.now(timezone.utc)
            stage.updated_at = datetime.now(timezone.utc)

        kept_stage_keys.add(stage_key)

    removed_stages = [
        stage
        for stage in existing_stages
        if stage.is_active and stage.stage_key not in kept_stage_keys
    ]
    target_stage_by_key = {
        stage.stage_key: stage
        for stage in existing_by_key.values()
        if stage.stage_key in kept_stage_keys and stage.is_active
    }

    for stage in removed_stages:
        target_stage_key = remap_by_key.get(stage.stage_key)
        target_stage = target_stage_by_key.get(target_stage_key) if target_stage_key else None
        if pipeline.entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
            entity_count = (
                db.query(IntendedParent)
                .filter(
                    IntendedParent.organization_id == pipeline.organization_id,
                    IntendedParent.stage_id == stage.id,
                    IntendedParent.is_archived.is_(False),
                )
                .count()
            )
        else:
            entity_count = (
                db.query(Surrogate)
                .filter(
                    Surrogate.organization_id == pipeline.organization_id,
                    Surrogate.stage_id == stage.id,
                    Surrogate.is_archived.is_(False),
                )
                .count()
            )
        if entity_count > 0 and target_stage is None:
            raise ValueError(
                f"Stage '{stage.label}' still has active records and needs a remap target."
            )
        if entity_count > 0 and target_stage is not None:
            if pipeline.entity_type == INTENDED_PARENT_PIPELINE_ENTITY:
                (
                    db.query(IntendedParent)
                    .filter(
                        IntendedParent.organization_id == pipeline.organization_id,
                        IntendedParent.stage_id == stage.id,
                        IntendedParent.is_archived.is_(False),
                    )
                    .update(
                        {
                            IntendedParent.stage_id: target_stage.id,
                            IntendedParent.status: target_stage.stage_key,
                        }
                    )
                )
            else:
                (
                    db.query(Surrogate)
                    .filter(
                        Surrogate.organization_id == pipeline.organization_id,
                        Surrogate.stage_id == stage.id,
                        Surrogate.is_archived.is_(False),
                    )
                    .update(
                        {
                            Surrogate.stage_id: target_stage.id,
                            Surrogate.status_label: target_stage.label,
                        }
                    )
                )

        if target_stage is not None and pipeline.entity_type != INTENDED_PARENT_PIPELINE_ENTITY:
            (
                db.query(Surrogate)
                .filter(
                    Surrogate.organization_id == pipeline.organization_id,
                    Surrogate.paused_from_stage_id == stage.id,
                )
                .update({Surrogate.paused_from_stage_id: target_stage.id})
            )

        if target_stage is not None:
            (
                db.query(StatusChangeRequest)
                .filter(
                    StatusChangeRequest.organization_id == pipeline.organization_id,
                    StatusChangeRequest.entity_type == pipeline.entity_type,
                    StatusChangeRequest.status == "pending",
                    StatusChangeRequest.target_stage_id == stage.id,
                )
                .update({StatusChangeRequest.target_stage_id: target_stage.id})
            )

        stage.is_active = False
        stage.deleted_at = datetime.now(timezone.utc)
        stage.updated_at = datetime.now(timezone.utc)

    pipeline.name = name or pipeline.name
    pipeline.feature_config = pipeline_change_service.apply_feature_config_stage_remaps(
        next_feature_config,
        remap_by_key,
    ).model_dump(mode="json")

    _apply_external_stage_remaps(db, pipeline, remap_by_key)
    _ensure_pipeline_semantics_defaults(db, pipeline)
    _validate_pipeline_configuration(db, pipeline)
    _bump_pipeline_version(db, pipeline, user_id, comment or "Applied pipeline draft")

    db.commit()
    db.refresh(pipeline)
    return pipeline


def sync_surrogate_labels(db: Session, stage_id: UUID, new_label: str) -> int:
    """
    Sync Surrogate.status_label when a stage's label changes.

    History snapshots are NOT updated (frozen at change time).
    Returns number of surrogates updated.
    """
    updated = (
        db.query(Surrogate)
        .filter(Surrogate.stage_id == stage_id)
        .update(
            {
                Surrogate.status_label: new_label,
            }
        )
    )
    db.commit()
    return updated


def validate_surrogate_stage(
    db: Session,
    pipeline_id: UUID,
    stage_id: UUID,
) -> bool:
    """
    Validate that a stage_id is valid for a pipeline.

    Stage must exist, be active, and belong to the pipeline.
    """
    stage = get_stage_by_id(db, stage_id)
    if not stage:
        return False
    return stage.pipeline_id == pipeline_id and stage.is_active


def get_default_stage(db: Session, pipeline_id: UUID) -> PipelineStage | None:
    """Get the first active stage (usually 'new_unread') as default."""
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.is_active.is_(True),
        )
        .order_by(PipelineStage.order)
        .first()
    )
