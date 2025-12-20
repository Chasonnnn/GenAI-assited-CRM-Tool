"""Pipeline service - manage org-configurable case pipelines.

v2: With version control integration
- Creates version snapshot on every change
- Optimistic locking via expected_version
- Rollback support with audit trail

v2.1: PipelineStage CRUD
- Stage rows instead of JSON
- Immutable slug/stage_type
- Soft-delete with migration

Each stage maps to a CaseStatus enum with custom label, color, and order.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import CaseStatus
from app.db.models import Pipeline, PipelineStage, Case
from app.services import version_service


# Default stage colors (matching typical CRM conventions)
DEFAULT_COLORS = {
    # Stage A: Intake Pipeline (blues/greens)
    CaseStatus.NEW_UNREAD: "#3B82F6",  # Blue
    CaseStatus.CONTACTED: "#06B6D4",  # Cyan
    CaseStatus.QUALIFIED: "#10B981",  # Green
    CaseStatus.APPLIED: "#84CC16",  # Lime
    CaseStatus.FOLLOWUP_SCHEDULED: "#A855F7",  # Purple
    CaseStatus.APPLICATION_SUBMITTED: "#8B5CF6",  # Violet
    CaseStatus.UNDER_REVIEW: "#F59E0B",  # Amber
    CaseStatus.APPROVED: "#22C55E",  # Green
    CaseStatus.PENDING_HANDOFF: "#F97316",  # Orange
    CaseStatus.DISQUALIFIED: "#EF4444",  # Red
    # Stage B: Post-Approval (darker shades)
    CaseStatus.PENDING_MATCH: "#0EA5E9",  # Sky
    CaseStatus.MEDS_STARTED: "#14B8A6",  # Teal
    CaseStatus.EXAM_PASSED: "#059669",  # Emerald
    CaseStatus.EMBRYO_TRANSFERRED: "#0D9488",  # Teal
    CaseStatus.DELIVERED: "#16A34A",  # Green (success)
    # Pseudo-statuses
    CaseStatus.ARCHIVED: "#6B7280",  # Gray
    CaseStatus.RESTORED: "#9CA3AF",  # Gray light
}

ENTITY_TYPE = "pipeline"


def get_default_stages() -> list[dict]:
    """
    Generate default pipeline stages from CaseStatus enum.
    
    Returns a list of stage configs matching all CaseStatus values.
    """
    stages = []
    order = 1
    
    # Generate from enum (order follows enum definition)
    for status in CaseStatus:
        # Skip pseudo-statuses for default display
        if status in (CaseStatus.ARCHIVED, CaseStatus.RESTORED):
            continue
        
        stages.append({
            "status": status.value,
            "label": status.value.replace("_", " ").title(),  # "new_unread" -> "New Unread"
            "color": DEFAULT_COLORS.get(status, "#6B7280"),
            "order": order,
            "visible": True,
        })
        order += 1
    
    return stages


def _pipeline_payload(pipeline: Pipeline) -> dict:
    """Extract versionable payload from pipeline."""
    return {
        "name": pipeline.name,
        "is_default": pipeline.is_default,
        "stages": pipeline.stages,
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
            stages=get_default_stages(),
            current_version=1,
        )
        db.add(pipeline)
        db.flush()
        
        # Create initial version snapshot
        version_service.create_version(
            db=db,
            org_id=org_id,
            entity_type=ENTITY_TYPE,
            entity_id=pipeline.id,
            payload=_pipeline_payload(pipeline),
            created_by_user_id=user_id or pipeline.organization_id,  # Fallback for system
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


def update_pipeline_stages(
    db: Session,
    pipeline: Pipeline,
    stages: list[dict],
    user_id: UUID,
    expected_version: int | None = None,
    comment: str | None = None,
) -> Pipeline:
    """
    Update pipeline stage configuration with version control.
    
    Args:
        expected_version: If provided, checks for conflicts (409 on mismatch)
        comment: Optional comment for the version
    
    Validates that all stages reference valid CaseStatus values.
    Raises ValueError if invalid status found.
    Raises VersionConflictError if expected_version doesn't match.
    """
    # Optimistic locking
    if expected_version is not None:
        version_service.check_version(pipeline.current_version, expected_version)
    
    # Validate stages
    valid_statuses = {s.value for s in CaseStatus}
    for stage in stages:
        if stage.get("status") not in valid_statuses:
            raise ValueError(f"Invalid status: {stage.get('status')}")
    
    # Update pipeline
    pipeline.stages = stages
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
        comment=comment or "Updated stages",
    )
    
    db.commit()
    db.refresh(pipeline)
    return pipeline


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
        stages=stages or get_default_stages(),
        current_version=1,
    )
    db.add(pipeline)
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
    pipeline.stages = payload.get("stages", pipeline.stages)
    pipeline.current_version = new_version.version
    pipeline.updated_at = datetime.now(timezone.utc)
    
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
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session,
    stage: PipelineStage,
    label: str | None = None,
    color: str | None = None,
    order: int | None = None,
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
    
    db.commit()
    return migrated


def reorder_stages(
    db: Session,
    pipeline_id: UUID,
    ordered_stage_ids: list[UUID],
) -> list[PipelineStage]:
    """
    Reorder stages by providing an ordered list of stage IDs.
    
    Normalizes order values to 1, 2, 3...
    Only active stages can be reordered.
    """
    stages = get_stages(db, pipeline_id)
    stage_map = {s.id: s for s in stages}
    
    # Validate all IDs are valid active stages
    for i, stage_id in enumerate(ordered_stage_ids):
        if stage_id not in stage_map:
            raise ValueError(f"Stage ID {stage_id} not found or not active")
        stage_map[stage_id].order = i + 1
    
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
