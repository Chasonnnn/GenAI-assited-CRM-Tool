"""Template API router - REST endpoints for workflow templates."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_csrf_header
from app.schemas.auth import UserSession
from app.services import template_service
from app.schemas.template import (
    TemplateCreate,
    TemplateFromWorkflow,
    TemplateRead,
    TemplateListItem,
    UseTemplateRequest,
    TEMPLATE_CATEGORIES,
)
from app.schemas.workflow import WorkflowRead


router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=list[TemplateListItem])
def list_templates(
    category: str | None = None,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """List available templates (global + org-specific)."""
    templates = template_service.list_templates(
        db=db,
        org_id=session.org_id,
        category=category,
    )
    
    result = []
    for t in templates:
        item = TemplateListItem.model_validate(t)
        result.append(item)
    return result


@router.get("/categories")
def get_template_categories():
    """Get available template categories."""
    return {"categories": TEMPLATE_CATEGORIES}


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """Get a template by ID."""
    template = template_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    result = TemplateRead.model_validate(template)
    
    # Add creator name if available
    if template.created_by:
        result.created_by_name = template.created_by.display_name
    
    return result


@router.post("", response_model=TemplateRead, dependencies=[Depends(require_csrf_header)])
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """Create a new org-specific template."""
    template = template_service.create_template(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=data.name,
        description=data.description,
        category=data.category,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
        conditions=[c.model_dump() if hasattr(c, 'model_dump') else c for c in data.conditions],
        condition_logic=data.condition_logic,
        actions=data.actions,
        icon=data.icon,
    )
    return TemplateRead.model_validate(template)


@router.post("/from-workflow", response_model=TemplateRead, dependencies=[Depends(require_csrf_header)])
def create_template_from_workflow(
    data: TemplateFromWorkflow,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """Create a template from an existing workflow."""
    try:
        template = template_service.create_template_from_workflow(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            workflow_id=data.workflow_id,
            name=data.name,
            description=data.description,
            category=data.category,
        )
        return TemplateRead.model_validate(template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{template_id}/use", response_model=WorkflowRead, dependencies=[Depends(require_csrf_header)])
def use_template(
    template_id: UUID,
    data: UseTemplateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """Create a workflow from a template."""
    try:
        workflow = template_service.use_template(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            template_id=template_id,
            workflow_name=data.name,
            workflow_description=data.description,
            is_enabled=data.is_enabled,
        )
        
        # Build response with creator name
        result = WorkflowRead.model_validate(workflow)
        if workflow.created_by:
            result.created_by_name = workflow.created_by.display_name
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{template_id}", dependencies=[Depends(require_csrf_header)])
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission("manage_automation")),
):
    """Delete an org-specific template (cannot delete global templates)."""
    deleted = template_service.delete_template(db, session.org_id, template_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Template not found or cannot delete global template"
        )
    return {"message": "Template deleted"}
