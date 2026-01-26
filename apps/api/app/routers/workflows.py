"""Workflow API router - REST endpoints for automation workflows."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_current_session,
    require_csrf_header,
)
from app.schemas.auth import UserSession
from app.db.enums import WorkflowTriggerType
from app.services import surrogate_service, workflow_service, workflow_access
from app.services.workflow_engine import engine
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowRead,
    WorkflowListItem,
    WorkflowStats,
    WorkflowOptions,
    ExecutionRead,
    ExecutionListResponse,
    UserWorkflowPreferenceRead,
    UserWorkflowPreferenceUpdate,
    WorkflowTestRequest,
    WorkflowTestResponse,
)


router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
    # No default permission - individual endpoints check based on scope
)


# =============================================================================
# Workflow CRUD
# =============================================================================


@router.get("", response_model=list[WorkflowListItem])
def list_workflows(
    scope: Literal["org", "personal"] | None = Query(default=None),
    enabled_only: bool = False,
    trigger_type: WorkflowTriggerType | None = None,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    List workflows for the organization.

    With manage_automation permission: sees all org + all personal workflows.
    Without: sees org workflows (read-only) + own personal workflows.

    Args:
        scope: Filter by scope ('org' or 'personal'). If omitted, shows all visible.
    """
    has_manage = workflow_access.has_manage_permission(db, session)
    workflows = workflow_service.list_workflows(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        has_manage_permission=has_manage,
        scope_filter=scope,
        enabled_only=enabled_only,
        trigger_type=trigger_type,
    )
    return [
        workflow_service.to_workflow_list_item(
            db, w, can_edit=workflow_access.can_edit(db, session, w)
        )
        for w in workflows
    ]


@router.get("/options", response_model=WorkflowOptions)
def get_workflow_options(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get available options for workflow builder UI."""
    return workflow_service.get_workflow_options(db, session.org_id)


@router.get("/stats", response_model=WorkflowStats)
def get_workflow_stats(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get workflow statistics for dashboard."""
    return workflow_service.get_workflow_stats(db, session.org_id)


# =============================================================================
# Org-wide Execution Dashboard (Manager+Dev only)
# =============================================================================


@router.get("/executions")
def list_org_executions(
    status: str | None = None,
    workflow_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    List all workflow executions for the organization.

    Manager/Developer only. Shows all executions across the org.
    """
    if not workflow_access.has_manage_permission(db, session):
        raise HTTPException(status_code=403, detail="Cannot view org executions")

    offset = (page - 1) * per_page
    items, total = workflow_service.list_org_executions(
        db=db,
        org_id=session.org_id,
        status=status,
        workflow_id=workflow_id,
        limit=per_page,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/executions/stats")
def get_execution_stats(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get execution statistics for the dashboard (last 24h)."""
    if not workflow_access.has_manage_permission(db, session):
        raise HTTPException(status_code=403, detail="Cannot view org execution stats")
    return workflow_service.get_execution_stats(db, session.org_id)


@router.post("", response_model=WorkflowRead, dependencies=[Depends(require_csrf_header)])
def create_workflow(
    data: WorkflowCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Create a new workflow.

    - Org workflows: require manage_automation permission
    - Personal workflows: any authenticated user can create
    """
    if not workflow_access.can_create(db, session, data.scope):
        raise HTTPException(
            status_code=403,
            detail="Cannot create org workflows without manage_automation permission",
        )

    try:
        workflow = workflow_service.create_workflow(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
        )
        return workflow_service.to_workflow_read(db, workflow, can_edit=True)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get a workflow by ID."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_view(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot view this workflow")
    return workflow_service.to_workflow_read(
        db, workflow, can_edit=workflow_access.can_edit(db, session, workflow)
    )


@router.patch(
    "/{workflow_id}",
    response_model=WorkflowRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Update a workflow."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_edit(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot edit this workflow")

    try:
        workflow = workflow_service.update_workflow(
            db=db,
            workflow=workflow,
            user_id=session.user_id,
            data=data,
        )
        return workflow_service.to_workflow_read(db, workflow, can_edit=True)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/{workflow_id}", dependencies=[Depends(require_csrf_header)])
def delete_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Delete a workflow."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_delete(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot delete this workflow")

    workflow_service.delete_workflow(db, workflow)
    return {"message": "Workflow deleted"}


@router.post(
    "/{workflow_id}/toggle",
    response_model=WorkflowRead,
    dependencies=[Depends(require_csrf_header)],
)
def toggle_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Toggle a workflow's enabled state."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_toggle(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot toggle this workflow")

    workflow = workflow_service.toggle_workflow(db, workflow, session.user_id)
    return workflow_service.to_workflow_read(db, workflow, can_edit=True)


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowRead,
    dependencies=[Depends(require_csrf_header)],
)
def duplicate_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """
    Duplicate a workflow.

    - Duplicating an org workflow requires manage_automation permission
    - Duplicating a personal workflow creates a personal copy owned by the current user
    """
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_duplicate(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot duplicate this workflow")

    # If duplicating an org workflow, keep it as org if user has permission
    # Otherwise, create a personal copy
    new_scope = None
    if workflow.scope == "org" and not workflow_access.has_manage_permission(db, session):
        new_scope = "personal"

    new_workflow = workflow_service.duplicate_workflow(db, workflow, session.user_id, new_scope)
    return workflow_service.to_workflow_read(db, new_workflow, can_edit=True)


# =============================================================================
# Workflow Testing (Dry Run)
# =============================================================================


@router.post(
    "/{workflow_id}/test",
    response_model=WorkflowTestResponse,
    dependencies=[Depends(require_csrf_header)],
)
def test_workflow(
    workflow_id: UUID,
    request: WorkflowTestRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Test a workflow against an entity (dry run)."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_view(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot view this workflow")

    # Get entity
    entity = surrogate_service.get_surrogate(db, session.org_id, request.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Evaluate conditions
    conditions_evaluated = []
    for condition in workflow.conditions:
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        entity_value = getattr(entity, field, None)

        result = engine._evaluate_condition(operator, entity_value, value)
        conditions_evaluated.append(
            {
                "field": field,
                "operator": operator,
                "expected": value,
                "actual": str(entity_value),
                "result": result,
            }
        )

    logic = workflow.condition_logic
    if logic == "AND":
        conditions_matched = (
            all(c["result"] for c in conditions_evaluated) if conditions_evaluated else True
        )
    else:
        conditions_matched = (
            any(c["result"] for c in conditions_evaluated) if conditions_evaluated else True
        )

    # Preview actions
    actions_preview = []
    for action in workflow.actions:
        action_type = action.get("action_type")
        description = f"{action_type}: "

        if action_type == "send_email":
            description += f"Send template {action.get('template_id')}"
        elif action_type == "create_task":
            description += f"Create task '{action.get('title')}'"
        elif action_type == "assign_surrogate":
            description += f"Assign to {action.get('owner_type')}:{action.get('owner_id')}"
        elif action_type == "send_notification":
            description += f"Notify: {action.get('title')}"
        elif action_type == "update_field":
            description += f"Set {action.get('field')} = {action.get('value')}"
        elif action_type == "add_note":
            description += f"Add note: {action.get('content', '')[:50]}..."

        actions_preview.append(
            {
                "action_type": action_type,
                "description": description,
            }
        )

    return WorkflowTestResponse(
        would_trigger=True,  # We're testing directly
        conditions_matched=conditions_matched,
        conditions_evaluated=conditions_evaluated,
        actions_preview=actions_preview,
    )


# =============================================================================
# Execution History
# =============================================================================


@router.get("/{workflow_id}/executions", response_model=ExecutionListResponse)
def list_executions(
    workflow_id: UUID,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get execution history for a workflow."""
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow_access.can_view(db, session, workflow):
        raise HTTPException(status_code=403, detail="Cannot view this workflow")

    items, total = workflow_service.list_executions(db, workflow_id, limit, offset)
    return ExecutionListResponse(
        items=[ExecutionRead.model_validate(e) for e in items],
        total=total,
    )


# =============================================================================
# User Preferences
# =============================================================================


@router.get("/me/preferences", response_model=list[UserWorkflowPreferenceRead])
def get_my_preferences(
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get current user's workflow preferences."""
    prefs = workflow_service.get_user_preferences(db, session.user_id, session.org_id)

    result = []
    for pref in prefs:
        workflow = workflow_service.get_workflow(db, pref.workflow_id, session.org_id)
        if workflow:
            result.append(
                UserWorkflowPreferenceRead(
                    id=pref.id,
                    workflow_id=pref.workflow_id,
                    workflow_name=workflow.name,
                    is_opted_out=pref.is_opted_out,
                )
            )
    return result


@router.patch(
    "/me/preferences/{workflow_id}",
    response_model=UserWorkflowPreferenceRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_my_preference(
    workflow_id: UUID,
    data: UserWorkflowPreferenceUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Update user's preference for a workflow (opt in/out)."""
    # Verify workflow exists and is in user's org
    workflow = workflow_service.get_workflow(db, workflow_id, session.org_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Users can only opt out of workflows they created OR their own preferences
    # They cannot disable org-level workflows globally
    pref = workflow_service.update_user_preference(
        db=db,
        user_id=session.user_id,
        workflow_id=workflow_id,
        is_opted_out=data.is_opted_out,
    )

    return UserWorkflowPreferenceRead(
        id=pref.id,
        workflow_id=pref.workflow_id,
        workflow_name=workflow.name,
        is_opted_out=pref.is_opted_out,
    )
