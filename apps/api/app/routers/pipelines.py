"""Pipelines router - API endpoints for org pipeline configuration.

v2: With version control
- current_version field for optimistic locking
- Version history endpoint
- Rollback endpoint (Developer-only)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES

from app.schemas.auth import UserSession
from app.services import pipeline_service, version_service

router = APIRouter(
    prefix="/settings/pipelines",
    tags=["Pipelines"],
    dependencies=[Depends(require_permission(POLICIES["pipelines"].default))],
)


# =============================================================================
# Schemas
# =============================================================================


class PipelineRead(BaseModel):
    """Pipeline response with version info."""

    id: UUID
    name: str
    is_default: bool
    stages: list["StageRead"]
    current_version: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    """Request to create a new pipeline."""

    name: str = Field(min_length=1, max_length=100)
    stages: list["StageCreate"] | None = None  # Uses defaults if not provided


class PipelineUpdate(BaseModel):
    """Request to update pipeline name."""

    name: str | None = Field(None, min_length=1, max_length=100)
    expected_version: int | None = None  # For optimistic locking
    comment: str | None = None  # Version comment


class PipelineVersionRead(BaseModel):
    """Version history entry."""

    id: UUID
    version: int
    created_by_user_id: UUID | None
    comment: str | None
    created_at: str


class RollbackRequest(BaseModel):
    """Request to rollback to a specific version."""

    target_version: int


# v2.1 Stage schemas
class StageRead(BaseModel):
    """Stage response."""

    id: UUID
    slug: str
    label: str
    color: str
    order: int
    stage_type: str
    is_active: bool

    model_config = {"from_attributes": True}


class StageCreate(BaseModel):
    """Request to create a new stage."""

    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    stage_type: str = Field(pattern=r"^(intake|post_approval|terminal)$")
    order: int | None = None  # Auto-calculated if not provided
    expected_version: int | None = None  # Optional optimistic locking


class StageUpdate(BaseModel):
    """Request to update a stage (slug/stage_type immutable)."""

    label: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    order: int | None = None
    expected_version: int | None = None  # Optional optimistic locking


class StageDelete(BaseModel):
    """Request to delete a stage with case migration."""

    migrate_to_stage_id: UUID
    expected_version: int | None = None  # Optional optimistic locking


class StageReorder(BaseModel):
    """Request to reorder stages."""

    ordered_stage_ids: list[UUID]
    expected_version: int | None = None  # Optional optimistic locking


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.get("", response_model=list[PipelineRead])
def list_pipelines(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    List all pipelines for the organization.

    Creates default pipeline if none exists.
    Requires: Manager+ role
    """
    # Ensure default exists
    pipeline_service.get_or_create_default_pipeline(db, session.org_id, session.user_id)

    pipelines = pipeline_service.list_pipelines(db, session.org_id)

    return [
        PipelineRead(
            id=p.id,
            name=p.name,
            is_default=p.is_default,
            stages=pipeline_service.get_stages(db, p.id),
            current_version=p.current_version,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in pipelines
    ]


@router.get("/default", response_model=PipelineRead)
def get_default_pipeline(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Get the default pipeline (creates if not exists).

    Requires: Authenticated user
    """
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, session.org_id, session.user_id
    )

    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline_service.get_stages(db, pipeline.id),
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(
    pipeline_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get a specific pipeline by ID."""
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline_service.get_stages(db, pipeline.id),
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=PipelineRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_pipeline(
    data: PipelineCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Create a new non-default pipeline.

    Uses default stages if not provided.
    Creates initial version snapshot.
    Requires: Manager+ role
    """
    stages = [s.model_dump() for s in data.stages] if data.stages else None

    pipeline = pipeline_service.create_pipeline(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=data.name,
        stages=stages,
    )

    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline_service.get_stages(db, pipeline.id),
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.post("/default/sync-stages", dependencies=[Depends(require_csrf_header)])
def sync_default_pipeline_stages(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Sync missing stages to the default pipeline.

    Adds any stages from DEFAULT_STAGE_ORDER that don't exist yet.
    Useful when the stage definitions have been expanded.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, session.org_id, session.user_id
    )
    added_count = pipeline_service.sync_missing_stages(db, pipeline, session.user_id)

    return {
        "synced": True,
        "stages_added": added_count,
        "current_version": pipeline.current_version,
    }


@router.patch(
    "/{pipeline_id}",
    response_model=PipelineRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_pipeline(
    pipeline_id: UUID,
    data: PipelineUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Update pipeline name and/or stages.

    Creates new version snapshot.
    Supports optimistic locking via expected_version (returns 409 on conflict).
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Check optimistic locking for any update
    if data.expected_version is not None:
        try:
            version_service.check_version(
                pipeline.current_version, data.expected_version
            )
        except version_service.VersionConflictError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Version conflict: expected {e.expected}, got {e.actual}",
            )

    if data.name is not None:
        # Name-only update also needs versioning
        pipeline_service.update_pipeline_name(
            db=db,
            pipeline=pipeline,
            name=data.name,
            user_id=session.user_id,
            comment=data.comment or "Renamed",
        )
    else:
        raise HTTPException(status_code=400, detail="No updates provided")

    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline_service.get_stages(db, pipeline.id),
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.delete(
    "/{pipeline_id}", status_code=204, dependencies=[Depends(require_csrf_header)]
)
def delete_pipeline(
    pipeline_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Delete a pipeline.

    Cannot delete the default pipeline.
    Version history is retained for audit.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    if pipeline.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete the default pipeline"
        )

    pipeline_service.delete_pipeline(db, pipeline)
    return None


# =============================================================================
# Version Control Endpoints (Developer-only)
# =============================================================================


@router.get("/{pipeline_id}/versions", response_model=list[PipelineVersionRead])
def get_pipeline_versions(
    pipeline_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Get version history for a pipeline.

    Returns versions newest first.
    Requires: Developer role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    versions = pipeline_service.get_pipeline_versions(
        db, session.org_id, pipeline_id, limit
    )

    return [
        PipelineVersionRead(
            id=v.id,
            version=v.version,
            created_by_user_id=v.created_by_user_id,
            comment=v.comment,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post(
    "/{pipeline_id}/rollback",
    response_model=PipelineRead,
    dependencies=[Depends(require_csrf_header)],
)
def rollback_pipeline(
    pipeline_id: UUID,
    data: RollbackRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Rollback pipeline to a previous version.

    Creates a NEW version with the old payload (never rewrites history).
    Emits audit event with before/after version links.
    Requires: Developer role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    updated, error = pipeline_service.rollback_pipeline(
        db=db,
        pipeline=pipeline,
        target_version=data.target_version,
        user_id=session.user_id,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    # Audit log the rollback
    from app.services import audit_service
    from app.db.enums import AuditEventType

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.CONFIG_ROLLED_BACK,
        actor_user_id=session.user_id,
        target_type="pipeline",
        target_id=pipeline_id,
        details={
            "target_version": data.target_version,
            "new_version": updated.current_version,
        },
    )
    db.commit()

    return PipelineRead(
        id=updated.id,
        name=updated.name,
        is_default=updated.is_default,
        stages=pipeline_service.get_stages(db, updated.id, include_inactive=True),
        current_version=updated.current_version,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
    )


# =============================================================================
# Stage CRUD Endpoints (v2.1)
# =============================================================================


@router.get("/{pipeline_id}/stages", response_model=list[StageRead])
async def list_stages(
    pipeline_id: UUID,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    List all stages for a pipeline.

    Stages are ordered by 'order' field.
    Use include_inactive=true to include soft-deleted stages.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")

    return pipeline_service.get_stages(db, pipeline_id, include_inactive)


@router.post("/{pipeline_id}/stages", response_model=StageRead, status_code=201)
async def create_stage(
    pipeline_id: UUID,
    data: StageCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """
    Create a new stage in a pipeline.

    Slug and stage_type are immutable after creation.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    if data.expected_version is not None:
        try:
            version_service.check_version(
                pipeline.current_version, data.expected_version
            )
        except version_service.VersionConflictError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Version conflict: expected {e.expected}, got {e.actual}",
            )

    try:
        stage = pipeline_service.create_stage(
            db=db,
            pipeline_id=pipeline_id,
            slug=data.slug,
            label=data.label,
            color=data.color,
            stage_type=data.stage_type,
            order=data.order,
            user_id=session.user_id,
        )
        return stage
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{pipeline_id}/stages/reorder", response_model=list[StageRead])
async def reorder_stages(
    pipeline_id: UUID,
    data: StageReorder,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """
    Reorder stages by providing a list of stage IDs in desired order.

    Order values are normalized to 1, 2, 3...
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")

    try:
        return pipeline_service.reorder_stages(
            db=db,
            pipeline_id=pipeline_id,
            ordered_stage_ids=data.ordered_stage_ids,
            user_id=session.user_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/{pipeline_id}/stages/{stage_id}", response_model=StageRead)
async def update_stage(
    pipeline_id: UUID,
    stage_id: UUID,
    data: StageUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """
    Update a stage's label, color, or order.

    Slug and stage_type are IMMUTABLE and cannot be changed.
    When label changes, all cases using this stage update their status_label.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    if data.expected_version is not None:
        try:
            version_service.check_version(
                pipeline.current_version, data.expected_version
            )
        except version_service.VersionConflictError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Version conflict: expected {e.expected}, got {e.actual}",
            )

    stage = pipeline_service.get_stage_by_id(db, stage_id)
    if not stage or stage.pipeline_id != pipeline_id:
        raise HTTPException(404, "Stage not found")
    if not stage.is_active:
        raise HTTPException(400, "Cannot update an inactive stage")

    return pipeline_service.update_stage(
        db=db,
        stage=stage,
        label=data.label,
        color=data.color,
        order=data.order,
        user_id=session.user_id,
    )


@router.delete("/{pipeline_id}/stages/{stage_id}")
async def delete_stage(
    pipeline_id: UUID,
    stage_id: UUID,
    data: StageDelete,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """
    Soft-delete a stage and migrate cases to another stage.

    All cases currently in this stage will be moved to migrate_to_stage_id.
    History rows are preserved pointing to this stage.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    if data.expected_version is not None:
        try:
            version_service.check_version(
                pipeline.current_version, data.expected_version
            )
        except version_service.VersionConflictError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Version conflict: expected {e.expected}, got {e.actual}",
            )

    stage = pipeline_service.get_stage_by_id(db, stage_id)
    if not stage or stage.pipeline_id != pipeline_id:
        raise HTTPException(404, "Stage not found")
    if not stage.is_active:
        raise HTTPException(400, "Stage is already deleted")

    # Count active stages to prevent deleting last one
    active_count = len(pipeline_service.get_stages(db, pipeline_id))
    if active_count <= 1:
        raise HTTPException(400, "Cannot delete the last remaining stage")

    try:
        migrated = pipeline_service.delete_stage(
            db=db,
            stage=stage,
            migrate_to_stage_id=data.migrate_to_stage_id,
            user_id=session.user_id,
        )
        return {"deleted": True, "migrated_cases": migrated}
    except ValueError as e:
        raise HTTPException(400, str(e))

