"""Pipelines router - API endpoints for org pipeline configuration."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_roles
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import pipeline_service

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
    """Pipeline response."""
    id: UUID
    name: str
    is_default: bool
    stages: list[dict[str, Any]]
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


# =============================================================================
# Endpoints
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
    pipeline_service.get_or_create_default_pipeline(db, session.org_id)
    
    pipelines = pipeline_service.list_pipelines(db, session.org_id)
    
    return [
        PipelineRead(
            id=p.id,
            name=p.name,
            is_default=p.is_default,
            stages=p.stages,
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
    pipeline = pipeline_service.get_or_create_default_pipeline(db, session.org_id)
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
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
    Requires: Manager+ role
    """
    stages = [s.model_dump() for s in data.stages] if data.stages else None
    
    pipeline = pipeline_service.create_pipeline(
        db=db,
        org_id=session.org_id,
        name=data.name,
        stages=stages,
    )
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
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
    
    Validates that all stages reference valid CaseStatus values.
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if data.name is not None:
        pipeline.name = data.name
    
    if data.stages is not None:
        stages = [s.model_dump() for s in data.stages]
        try:
            pipeline_service.update_pipeline_stages(db, pipeline, stages)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        db.commit()
        db.refresh(pipeline)
    
    return PipelineRead(
        id=pipeline.id,
        name=pipeline.name,
        is_default=pipeline.is_default,
        stages=pipeline.stages,
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
    Requires: Manager+ role
    """
    pipeline = pipeline_service.get_pipeline(db, session.org_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if pipeline.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default pipeline")
    
    pipeline_service.delete_pipeline(db, pipeline)
    return None
