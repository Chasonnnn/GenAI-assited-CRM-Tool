"""Pipelines router - API endpoints for org pipeline configuration.

v2: With version control
- current_version field for optimistic locking
- Version history endpoint
- Rollback endpoint (Developer-only)
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_roles
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import pipeline_service, version_service

router = APIRouter(prefix="/settings/pipelines", tags=["Pipelines"])


# =============================================================================
# Schemas
# =============================================================================

class PipelineStage(BaseModel):
    """Single pipeline stage configuration."""
    status: str  # Must match a CaseStatus value
    label: str  # Display label
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")  # Hex color
    order: int = Field(ge=1)
    visible: bool = True


class PipelineRead(BaseModel):
    """Pipeline response with version info."""
    id: UUID
    name: str
    is_default: bool
    stages: list[dict[str, Any]]
    current_version: int
    created_at: str
    updated_at: str
    
    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    """Request to create a new pipeline."""
    name: str = Field(min_length=1, max_length=100)
    stages: list[PipelineStage] | None = None  # Uses defaults if not provided


class PipelineUpdate(BaseModel):
    """Request to update pipeline stages."""
    name: str | None = Field(None, min_length=1, max_length=100)
    stages: list[PipelineStage] | None = None
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


# =============================================================================
# CRUD Endpoints
# =============================================================================

@router.get("", response_model=list[PipelineRead])
def list_pipelines(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
            stages=p.stages,
            current_version=p.current_version,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in pipelines
    ]


@router.get("/default", response_model=PipelineRead)
def get_default_pipeline(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
):
    """
    Get the default pipeline (creates if not exists).
    
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_or_create_default_pipeline(db, session.org_id, session.user_id)
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(
    pipeline_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
):
    """Get a specific pipeline by ID."""
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.post("", response_model=PipelineRead, status_code=201, dependencies=[Depends(require_csrf_header)])
def create_pipeline(
    data: PipelineCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
        stages=pipeline.stages,
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.patch("/{pipeline_id}", response_model=PipelineRead, dependencies=[Depends(require_csrf_header)])
def update_pipeline(
    pipeline_id: UUID,
    data: PipelineUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    
    if data.stages is not None:
        stages = [s.model_dump() for s in data.stages]
        try:
            pipeline_service.update_pipeline_stages(
                db=db,
                pipeline=pipeline,
                stages=stages,
                user_id=session.user_id,
                expected_version=data.expected_version,
                comment=data.comment,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except version_service.VersionConflictError as e:
            raise HTTPException(status_code=409, detail=f"Version conflict: expected {e.expected}, got {e.actual}")
    elif data.name is not None:
        pipeline.name = data.name
        db.commit()
        db.refresh(pipeline)
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
        current_version=pipeline.current_version,
        created_at=pipeline.created_at.isoformat(),
        updated_at=pipeline.updated_at.isoformat(),
    )


@router.delete("/{pipeline_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_pipeline(
    pipeline_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
        raise HTTPException(status_code=400, detail="Cannot delete the default pipeline")
    
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
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
):
    """
    Get version history for a pipeline.
    
    Returns versions newest first.
    Requires: Developer role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    versions = pipeline_service.get_pipeline_versions(db, session.org_id, pipeline_id, limit)
    
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


@router.post("/{pipeline_id}/rollback", response_model=PipelineRead, dependencies=[Depends(require_csrf_header)])
def rollback_pipeline(
    pipeline_id: UUID,
    data: RollbackRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
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
        stages=updated.stages,
        current_version=updated.current_version,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
    )
