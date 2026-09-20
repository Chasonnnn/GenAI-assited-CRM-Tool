"""Template API router - REST endpoints for workflow templates."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.template import (
    TEMPLATE_CATEGORIES,
    TemplateCreate,
    TemplateFromWorkflow,
    TemplateListItem,
    TemplateRead,
    UseTemplateRequest,
)
from app.schemas.workflow import WorkflowRead
from app.services import template_service, workflow_access, workflow_service

router = APIRouter(
    prefix="/templates",
    tags=["Templates"],
    dependencies=[Depends(require_permission(POLICIES["automation"].default))],
)


def _uses_messaging(actions: list[dict] | None) -> bool:
    return any(action.get("action_type") == "send_message" for action in actions or [])


def _require_messaging_admin(session: UserSession) -> None:
    from app.db.enums import Role

    if session.role not in {Role.ADMIN, Role.DEVELOPER}:
        raise HTTPException(
            status_code=403,
            detail="Messaging workflows require an organization admin or developer",
        )


def _require_subject_access(db: Session, session: UserSession, subject_type: str | None) -> None:
    if not workflow_access.can_view_subject(db, session, subject_type):
        raise HTTPException(status_code=403, detail="Missing permission: view_donors")


def _require_subject_edit_access(
    db: Session,
    session: UserSession,
    subject_type: str | None,
) -> None:
    if not workflow_access.can_edit_subject(db, session, subject_type):
        raise HTTPException(status_code=403, detail="Missing permission: edit_donors")


@router.get("", response_model=list[TemplateListItem])
def list_templates(
    category: str | None = None,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    """List available templates (global + org-specific)."""
    templates = template_service.list_templates(
        db=db,
        org_id=session.org_id,
        category=category,
    )

    can_view_donor = workflow_access.can_view_subject(db, session, "donor")
    effective_subjects = (
        {}
        if can_view_donor
        else template_service.get_templates_effective_subject_types(
            db, session.org_id, templates
        )
    )
    result = []
    for t in templates:
        if (
            not can_view_donor
            and effective_subjects[t.id] in workflow_access.DONOR_SUBJECT_TYPES
        ):
            continue
        item = TemplateListItem.model_validate(t)
        result.append(item)
    return result


@router.get("/categories")
def get_template_categories() -> object:
    """Get available template categories."""
    return {"categories": TEMPLATE_CATEGORIES}


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    """Get a template by ID."""
    template = template_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    effective_subject = template_service.get_template_effective_subject_type(
        db, session.org_id, template
    )
    _require_subject_access(db, session, effective_subject)

    result = TemplateRead.model_validate(template)

    # Add creator name if available
    if template.created_by:
        result.created_by_name = template.created_by.display_name

    return result


@router.post("", response_model=TemplateRead, dependencies=[Depends(require_csrf_header)])
def create_template(
    data: TemplateCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    """Create a new org-specific template."""
    effective_subject = template_service.resolve_effective_template_subject_type(
        db,
        session.org_id,
        subject_type=data.subject_type,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config,
    )
    _require_subject_access(db, session, effective_subject)
    _require_subject_edit_access(db, session, effective_subject)
    try:
        template = template_service.create_template(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            name=data.name,
            description=data.description,
            category=data.category,
            subject_type=data.subject_type,
            trigger_type=data.trigger_type,
            trigger_config=data.trigger_config,
            conditions=[c.model_dump() if hasattr(c, "model_dump") else c for c in data.conditions],
            condition_logic=data.condition_logic,
            actions=data.actions,
            icon=data.icon,
        )
        return TemplateRead.model_validate(template)
    except ValueError as e:
        detail = str(e)
        status_code = 409 if "already exists" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/from-workflow",
    response_model=TemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def create_template_from_workflow(
    data: TemplateFromWorkflow,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    """Create a template from an existing workflow."""
    workflow = workflow_service.get_workflow(db, data.workflow_id, session.org_id)
    if workflow is not None:
        workflow_subject = workflow_service.get_workflow_effective_subject_type(db, workflow)
        if not workflow_access.can_view(db, session, workflow, workflow_subject):
            raise HTTPException(status_code=403, detail="Cannot view this workflow")
        _require_subject_edit_access(db, session, workflow_subject)
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
        detail = str(e)
        if detail == "Workflow not found":
            raise HTTPException(status_code=404, detail=detail)
        status_code = 409 if "already exists" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/{template_id}/use",
    response_model=WorkflowRead,
    dependencies=[Depends(require_csrf_header)],
)
def use_template(
    template_id: UUID,
    data: UseTemplateRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    """Create a workflow from a template.

    - scope='org': Creates an organization workflow (requires manage_automation permission)
    - scope='personal': Creates a personal workflow owned by the current user
    """
    # Check permissions based on scope
    if data.scope == "org" and not workflow_access.has_manage_permission(db, session):
        raise HTTPException(
            status_code=403,
            detail="Cannot create org workflows without manage_automation permission",
        )

    template = template_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        trigger_config = template_service.resolve_template_trigger_config(
            db, session.org_id, template, data.trigger_form_id
        )
        actions = template_service.merge_action_overrides(
            template.actions, getattr(data, "action_overrides", None)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    effective_subject_type = template_service.get_template_effective_subject_type(
        db,
        session.org_id,
        template,
        trigger_config=trigger_config,
    )
    _require_subject_access(db, session, effective_subject_type)
    _require_subject_edit_access(db, session, effective_subject_type)
    if _uses_messaging(actions):
        _require_messaging_admin(session)

    try:
        workflow = template_service.use_template(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            template_id=template_id,
            workflow_name=data.name,
            workflow_description=data.description,
            is_enabled=data.is_enabled,
            action_overrides=getattr(data, "action_overrides", None),
            scope=data.scope,
            trigger_form_id=data.trigger_form_id,
        )

        # Build response with creator name
        result = WorkflowRead.model_validate(workflow)
        if workflow.created_by:
            result.created_by_name = workflow.created_by.display_name
        return result
    except ValueError as e:
        detail = str(e)
        status_code = 404 if detail == "Template not found" else 400
        raise HTTPException(status_code=status_code, detail=detail)


@router.delete("/{template_id}", dependencies=[Depends(require_csrf_header)])
def delete_template(
    template_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> object:
    """Delete an org-specific template (cannot delete global templates)."""
    template = template_service.get_template(db, template_id, session.org_id)
    if (
        template is None
        or template.is_global
        or template.organization_id != session.org_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Template not found or cannot delete global template",
        )
    effective_subject = template_service.get_template_effective_subject_type(
        db, session.org_id, template
    )
    _require_subject_access(db, session, effective_subject)
    _require_subject_edit_access(db, session, effective_subject)
    deleted = template_service.delete_template(db, session.org_id, template_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Template not found or cannot delete global template",
        )
    return {"message": "Template deleted"}
