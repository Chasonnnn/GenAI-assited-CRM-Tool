"""Pipeline service - manage org-configurable case pipelines.

v1: Display-only customization of existing CaseStatus values.
Each stage maps to a CaseStatus enum with custom label, color, and order.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import CaseStatus
from app.db.models import Pipeline


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


def get_or_create_default_pipeline(db: Session, org_id: UUID) -> Pipeline:
    """
    Get the default pipeline for an org, creating if not exists.
    
    Called on first access to ensure every org has a pipeline.
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
        )
        db.add(pipeline)
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
) -> Pipeline:
    """
    Update pipeline stage configuration.
    
    Validates that all stages reference valid CaseStatus values.
    Raises ValueError if invalid status found.
    """
    # Validate stages
    valid_statuses = {s.value for s in CaseStatus}
    for stage in stages:
        if stage.get("status") not in valid_statuses:
            raise ValueError(f"Invalid status: {stage.get('status')}")
    
    pipeline.stages = stages
    db.commit()
    db.refresh(pipeline)
    return pipeline


def create_pipeline(
    db: Session,
    org_id: UUID,
    name: str,
    stages: list[dict] | None = None,
) -> Pipeline:
    """
    Create a new non-default pipeline.
    
    Uses default stages if not provided.
    """
    pipeline = Pipeline(
        organization_id=org_id,
        name=name,
        is_default=False,
        stages=stages or get_default_stages(),
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


def delete_pipeline(db: Session, pipeline: Pipeline) -> bool:
    """
    Delete a pipeline.
    
    Cannot delete the default pipeline.
    """
    if pipeline.is_default:
        return False
    
    db.delete(pipeline)
    db.commit()
    return True
