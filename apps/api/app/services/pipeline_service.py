"""Pipeline service - manage org-configurable case pipelines.

v2: With version control integration
- Creates version snapshot on every change
- Optimistic locking via expected_version
- Rollback support with audit trail

Each stage maps to a CaseStatus enum with custom label, color, and order.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import CaseStatus
from app.db.models import Pipeline
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
