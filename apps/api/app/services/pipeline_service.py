"""Pipeline service - manage org-configurable case pipelines."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.stage_definitions import canonicalize_stage_key, get_default_stage_defs
from app.db.models import Pipeline, PipelineStage, Surrogate
from app.services import version_service
from app.utils.presentation import humanize_identifier

ENTITY_TYPE = "pipeline"


def _normalize_slug(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_stage_key(value: str | None) -> str:
    return canonicalize_stage_key(value)


def _pipeline_payload(pipeline: Pipeline) -> dict:
    """Extract versionable payload from pipeline."""
    return {
        "name": pipeline.name,
        "is_default": pipeline.is_default,
        "stages": [
            {
                "stage_key": stage.stage_key,
                "slug": stage.slug,
                "label": stage.label,
                "color": stage.color,
                "order": stage.order,
                "stage_type": stage.stage_type,
                "is_active": stage.is_active,
            }
            for stage in pipeline.stages
        ],
    }


def get_or_create_default_pipeline(
    db: Session,
    org_id: UUID,
    user_id: UUID | None = None,
) -> Pipeline:
    """
    Get the default pipeline for an org, creating if not exists.

    Called on first access to ensure every org has a pipeline.
    Creates initial version snapshot.
    """
    pipeline = (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
            Pipeline.is_default.is_(True),
        )
        .first()
    )

    if not pipeline:
        pipeline = Pipeline(
            organization_id=org_id,
            name="Default",
            is_default=True,
            current_version=1,
        )
        db.add(pipeline)
        db.flush()

        # Create default stage rows
        stage_defs = get_default_stage_defs()
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
                    is_intake_stage=stage["stage_type"] == "intake",
                    is_active=True,
                )
                for stage in stage_defs
            ]
        )
        db.flush()

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

    sync_missing_stages(db, pipeline, user_id)
    return pipeline


def get_pipeline(db: Session, org_id: UUID, pipeline_id: UUID) -> Pipeline | None:
    """Get pipeline by ID (org-scoped)."""
    return (
        db.query(Pipeline)
        .filter(
            Pipeline.id == pipeline_id,
            Pipeline.organization_id == org_id,
        )
        .first()
    )


def list_pipelines(db: Session, org_id: UUID) -> list[Pipeline]:
    """List all pipelines for an org."""
    return (
        db.query(Pipeline)
        .filter(
            Pipeline.organization_id == org_id,
        )
        .order_by(Pipeline.is_default.desc(), Pipeline.name)
        .all()
    )


def sync_missing_stages(
    db: Session,
    pipeline: Pipeline,
    user_id: UUID | None = None,
) -> int:
    """
    Add missing default stages to an existing pipeline.

    Compares existing stages against DEFAULT_STAGE_ORDER and adds any missing ones.
    Returns count of stages added.
    """
    # Get existing stage slugs
    existing_stage_keys = {s.stage_key for s in pipeline.stages if not s.deleted_at}

    # Find missing stage keys
    default_defs = get_default_stage_defs()
    missing = [
        d
        for d in default_defs
        if _normalize_stage_key(d.get("stage_key") or d["slug"]) not in existing_stage_keys
    ]

    if not missing:
        return 0

    # Get max order from existing stages
    max_order = max((s.order for s in pipeline.stages), default=0)

    # Add missing stages
    for i, stage_def in enumerate(missing):
        db.add(
            PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=_normalize_stage_key(stage_def.get("stage_key") or stage_def["slug"]),
                slug=stage_def["slug"],
                label=stage_def["label"],
                color=stage_def["color"],
                order=max_order + i + 1,  # Append after existing
                stage_type=stage_def["stage_type"],
                is_intake_stage=stage_def["stage_type"] == "intake",
                is_active=True,
            )
        )

    db.flush()
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


def create_pipeline(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    name: str,
    stages: list[dict] | None = None,
) -> Pipeline:
    """
    Create a new non-default pipeline with initial version.

    Uses default stages if not provided.
    """
    pipeline = Pipeline(
        organization_id=org_id,
        name=name,
        is_default=False,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stage_defs = stages or get_default_stage_defs()
    db.add_all(
        [
            PipelineStage(
                pipeline_id=pipeline.id,
                stage_key=_normalize_stage_key(stage.get("stage_key") or stage["slug"]),
                slug=stage["slug"],
                label=stage["label"],
                color=stage["color"],
                order=stage.get("order", i + 1),
                stage_type=stage.get("stage_type", "intake"),
                is_intake_stage=stage.get(
                    "is_intake_stage", stage.get("stage_type", "intake") == "intake"
                ),
                is_active=stage.get("is_active", True),
            )
            for i, stage in enumerate(stage_defs)
        ]
    )
    db.flush()

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
            stage.stage_type = stage_data.get("stage_type", stage.stage_type)
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
                stage_type=stage_data.get("stage_type", "intake"),
                is_intake_stage=stage_data.get("stage_type", "intake") == "intake",
                is_active=stage_data.get("is_active", True),
            )
            db.add(stage)

    # Soft-deactivate stages not present in payload
    for stage_key, stage in existing_by_key.items():
        if stage_key not in payload_stage_keys and stage.is_active:
            stage.is_active = False
            stage.deleted_at = datetime.now(timezone.utc)
            stage.updated_at = datetime.now(timezone.utc)

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
            PipelineStage.stage_key == normalized_key,
        )
        .first()
    )


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
) -> list[UUID]:
    """Resolve a mixed list of stage keys/slugs into stage IDs for an org pipeline."""
    if not refs:
        return []

    if pipeline_id is None:
        pipeline = get_or_create_default_pipeline(db, org_id)
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
    user_id: UUID | None = None,
) -> PipelineStage:
    """
    Create a new pipeline stage.

    stage_key and stage_type are immutable after creation.
    Slug is editable via update_stage.
    Raises ValueError if slug/stage_key already exists or stage_type is invalid.
    """
    normalized_slug = _normalize_slug(slug)
    stage_key = _normalize_stage_key(normalized_slug)
    if not normalized_slug:
        raise ValueError("Slug cannot be empty")

    # Validate stage_type
    if stage_type not in ("intake", "post_approval", "terminal"):
        raise ValueError(f"Invalid stage_type: {stage_type}")

    # Validate slug uniqueness
    if not validate_stage_slug(db, pipeline_id, normalized_slug):
        raise ValueError(f"Slug '{normalized_slug}' already exists or is invalid")

    # Validate stage_key uniqueness (immutable semantic key)
    existing_key = get_stage_by_key(db, pipeline_id, stage_key)
    if existing_key:
        raise ValueError(f"Stage key '{stage_key}' already exists in this pipeline")

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
        is_intake_stage=stage_type == "intake",
        is_active=True,
    )
    db.add(stage)
    db.flush()
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline:
        pipeline.stages.append(stage)
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
    user_id: UUID | None = None,
) -> PipelineStage:
    """
    Update stage slug, label, color, or order.

    stage_key and stage_type are immutable.
    Syncs case status_label when label changes.
    """
    label_changed = False

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

    stage.updated_at = datetime.now(timezone.utc)
    pipeline = db.query(Pipeline).filter(Pipeline.id == stage.pipeline_id).first()
    if pipeline:
        _bump_pipeline_version(db, pipeline, user_id, f"Updated stage {stage.stage_key}")
    db.commit()
    db.refresh(stage)

    # Sync case labels if label changed
    if label_changed:
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

    # Validate migrate_to stage
    target = get_stage_by_id(db, migrate_to_stage_id)
    if not target:
        raise ValueError("Target stage not found")
    if not target.is_active:
        raise ValueError("Target stage is not active")
    if target.pipeline_id != stage.pipeline_id:
        raise ValueError("Target stage must be in the same pipeline")

    # Migrate cases
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

    # Soft-delete stage
    stage.is_active = False
    stage.deleted_at = datetime.now(timezone.utc)
    stage.updated_at = datetime.now(timezone.utc)

    pipeline = db.query(Pipeline).filter(Pipeline.id == stage.pipeline_id).first()
    if pipeline:
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
        stage_map[stage_id].order = i + 1

    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline:
        _bump_pipeline_version(db, pipeline, user_id, "Reordered stages")
    db.commit()
    return get_stages(db, pipeline_id)


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
