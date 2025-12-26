"""Pipeline service - manage org-configurable case pipelines.

v2: With version control integration
- Creates version snapshot on every change
- Optimistic locking via expected_version
- Rollback support with audit trail

v2.1: PipelineStage CRUD
- Stage rows instead of JSON
- Immutable slug/stage_type
- Soft-delete with migration

Stages are stored as PipelineStage rows with immutable slugs.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Pipeline, PipelineStage, Case
from app.services import version_service


# Default stage colors (matching typical CRM conventions)
DEFAULT_COLORS = {
    # Stage A: Intake Pipeline (blues/greens)
    "new_unread": "#3B82F6",  # Blue
    "contacted": "#06B6D4",  # Cyan
    "qualified": "#10B981",  # Green
    "applied": "#84CC16",  # Lime
    "followup_scheduled": "#A855F7",  # Purple
    "application_submitted": "#8B5CF6",  # Violet
    "under_review": "#F59E0B",  # Amber
    "approved": "#22C55E",  # Green
    "pending_handoff": "#F97316",  # Orange
    "disqualified": "#EF4444",  # Red
    # Stage B: Post-Approval (darker shades)
    "pending_match": "#0EA5E9",  # Sky
    "matched": "#6366F1",  # Indigo
    "meds_started": "#14B8A6",  # Teal
    "exam_passed": "#059669",  # Emerald
    "embryo_transferred": "#0D9488",  # Teal
    "delivered": "#16A34A",  # Green (success)
}

ENTITY_TYPE = "pipeline"


STAGE_TYPE_MAP = {
    "new_unread": "intake",
    "contacted": "intake",
    "qualified": "intake",
    "applied": "intake",
    "followup_scheduled": "intake",
    "application_submitted": "intake",
    "under_review": "intake",
    "approved": "intake",
    "pending_handoff": "intake",
    "pending_match": "post_approval",
    "matched": "post_approval",
    "meds_started": "post_approval",
    "exam_passed": "post_approval",
    "embryo_transferred": "post_approval",
    "disqualified": "terminal",
    "delivered": "terminal",
}

DEFAULT_STAGE_ORDER = [
    "new_unread",
    "contacted",
    "qualified",
    "applied",
    "followup_scheduled",
    "application_submitted",
    "under_review",
    "approved",
    "pending_handoff",
    "pending_match",
    "matched",
    "meds_started",
    "exam_passed",
    "embryo_transferred",
    "disqualified",
    "delivered",
]


def get_default_stage_defs() -> list[dict]:
    """Generate default pipeline stage definitions."""
    stages = []
    for order, slug in enumerate(DEFAULT_STAGE_ORDER, start=1):
        stages.append({
            "slug": slug,
            "label": slug.replace("_", " ").title(),
            "color": DEFAULT_COLORS.get(slug, "#6B7280"),
            "order": order,
            "stage_type": STAGE_TYPE_MAP.get(slug, "intake"),
        })
    return stages


def _pipeline_payload(pipeline: Pipeline) -> dict:
    """Extract versionable payload from pipeline."""
    return {
        "name": pipeline.name,
        "is_default": pipeline.is_default,
        "stages": [
            {
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
    pipeline = db.query(Pipeline).filter(
        Pipeline.organization_id == org_id,
        Pipeline.is_default == True,
    ).first()
    
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
        db.add_all([
            PipelineStage(
                pipeline_id=pipeline.id,
                slug=stage["slug"],
                label=stage["label"],
                color=stage["color"],
                order=stage["order"],
                stage_type=stage["stage_type"],
                is_active=True,
            )
            for stage in stage_defs
        ])
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


def get_pipeline(db: Session, org_id: UUID, pipeline_id: UUID) -> Pipeline | None:
    """Get pipeline by ID (org-scoped)."""
    return db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == org_id,
    ).first()


def list_pipelines(db: Session, org_id: UUID) -> list[Pipeline]:
    """List all pipelines for an org."""
    return db.query(Pipeline).filter(
        Pipeline.organization_id == org_id,
    ).order_by(Pipeline.is_default.desc(), Pipeline.name).all()


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
    existing_slugs = {s.slug for s in pipeline.stages if not s.deleted_at}
    
    # Find missing slugs
    default_defs = get_default_stage_defs()
    missing = [d for d in default_defs if d["slug"] not in existing_slugs]
    
    if not missing:
        return 0
    
    # Get max order from existing stages
    max_order = max((s.order for s in pipeline.stages), default=0)
    
    # Add missing stages
    for i, stage_def in enumerate(missing):
        db.add(PipelineStage(
            pipeline_id=pipeline.id,
            slug=stage_def["slug"],
            label=stage_def["label"],
            color=stage_def["color"],
            order=max_order + i + 1,  # Append after existing
            stage_type=stage_def["stage_type"],
            is_active=True,
        ))
    
    # Update pipeline version
    pipeline.current_version += 1
    pipeline.updated_at = datetime.now(timezone.utc)
    
    # Create version snapshot if user provided
    if user_id:
        version_service.create_version(
            db=db,
            org_id=pipeline.organization_id,
            entity_type=ENTITY_TYPE,
            entity_id=pipeline.id,
            payload=_pipeline_payload(pipeline),
            created_by_user_id=user_id,
            comment=f"Added {len(missing)} missing stages",
        )
    
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
    pipeline.current_version += 1
    pipeline.updated_at = datetime.now(timezone.utc)
    
    # Create version snapshot
    version_service.create_version(
        db=db,
        org_id=pipeline.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=pipeline.id,
        payload=_pipeline_payload(pipeline),
        created_by_user_id=user_id,
        comment=comment or "Renamed",
    )
    
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
    db.add_all([
        PipelineStage(
            pipeline_id=pipeline.id,
            slug=stage["slug"],
            label=stage["label"],
            color=stage["color"],
            order=stage.get("order", i + 1),
            stage_type=stage.get("stage_type", "intake"),
            is_active=stage.get("is_active", True),
        )
        for i, stage in enumerate(stage_defs)
    ])
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
    pipeline.current_version += 1
    pipeline.updated_at = datetime.now(timezone.utc)
    version_service.create_version(
        db=db,
        org_id=pipeline.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=pipeline.id,
        payload=_pipeline_payload(pipeline),
        created_by_user_id=user_id,
        comment=comment,
    )


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

    # Reconcile stage rows by slug
    payload_stages = payload.get("stages", [])
    existing = {s.slug: s for s in pipeline.stages}
    payload_slugs = set()

    for stage_data in payload_stages:
        slug = stage_data.get("slug")
        if not slug:
            continue
        payload_slugs.add(slug)

        stage = existing.get(slug)
        if stage:
            stage.label = stage_data.get("label", stage.label)
            stage.color = stage_data.get("color", stage.color)
            stage.order = stage_data.get("order", stage.order)
            stage.stage_type = stage_data.get("stage_type", stage.stage_type)
            stage.is_active = stage_data.get("is_active", stage.is_active)
            stage.updated_at = datetime.now(timezone.utc)
            if not stage.is_active and stage.deleted_at is None:
                stage.deleted_at = datetime.now(timezone.utc)
        else:
            stage = PipelineStage(
                pipeline_id=pipeline.id,
                slug=slug,
                label=stage_data.get("label", slug.replace("_", " ").title()),
                color=stage_data.get("color", "#6B7280"),
                order=stage_data.get("order", len(existing) + 1),
                stage_type=stage_data.get("stage_type", "intake"),
                is_active=stage_data.get("is_active", True),
            )
            db.add(stage)

    # Soft-deactivate stages not present in payload
    for slug, stage in existing.items():
        if slug not in payload_slugs and stage.is_active:
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
        query = query.filter(PipelineStage.is_active == True)
    return query.order_by(PipelineStage.order).all()


def get_stage_by_id(db: Session, stage_id: UUID) -> PipelineStage | None:
    """Get a stage by ID."""
    return db.query(PipelineStage).filter(PipelineStage.id == stage_id).first()


def get_stage_by_slug(db: Session, pipeline_id: UUID, slug: str) -> PipelineStage | None:
    """Get a stage by slug (unique per pipeline)."""
    return db.query(PipelineStage).filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.slug == slug,
    ).first()


def validate_stage_slug(db: Session, pipeline_id: UUID, slug: str) -> bool:
    """Check if slug is valid (unique per pipeline, not empty)."""
    if not slug or len(slug) > 50:
        return False
    existing = get_stage_by_slug(db, pipeline_id, slug)
    return existing is None


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
    
    Slug and stage_type are immutable after creation.
    Raises ValueError if slug already exists or stage_type is invalid.
    """
    # Validate stage_type
    if stage_type not in ("intake", "post_approval", "terminal"):
        raise ValueError(f"Invalid stage_type: {stage_type}")
    
    # Validate slug uniqueness
    if not validate_stage_slug(db, pipeline_id, slug):
        raise ValueError(f"Slug '{slug}' already exists or is invalid")
    
    # Auto-calculate order if not provided
    if order is None:
        max_order = db.query(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline_id,
        ).count()
        order = max_order + 1
    
    stage = PipelineStage(
        pipeline_id=pipeline_id,
        slug=slug,
        label=label,
        color=color,
        stage_type=stage_type,
        order=order,
        is_active=True,
    )
    db.add(stage)
    db.flush()
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline:
        pipeline.stages.append(stage)
        _bump_pipeline_version(db, pipeline, user_id, f"Added stage {slug}")
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session,
    stage: PipelineStage,
    label: str | None = None,
    color: str | None = None,
    order: int | None = None,
    user_id: UUID | None = None,
) -> PipelineStage:
    """
    Update stage label, color, or order.
    
    Slug and stage_type are IMMUTABLE - any attempt to change them is ignored.
    Syncs case status_label when label changes.
    """
    label_changed = False
    
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
        _bump_pipeline_version(db, pipeline, user_id, f"Updated stage {stage.slug}")
    db.commit()
    db.refresh(stage)
    
    # Sync case labels if label changed
    if label_changed:
        sync_case_labels(db, stage.id, stage.label)
    
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
    migrated = db.query(Case).filter(Case.stage_id == stage.id).update({
        Case.stage_id: migrate_to_stage_id,
        Case.status_label: target.label,
    })
    
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


def sync_case_labels(db: Session, stage_id: UUID, new_label: str) -> int:
    """
    Sync Case.status_label when a stage's label changes.
    
    History snapshots are NOT updated (frozen at change time).
    Returns number of cases updated.
    """
    updated = db.query(Case).filter(Case.stage_id == stage_id).update({
        Case.status_label: new_label,
    })
    db.commit()
    return updated


def validate_case_stage(
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
    return db.query(PipelineStage).filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.is_active == True,
    ).order_by(PipelineStage.order).first()
