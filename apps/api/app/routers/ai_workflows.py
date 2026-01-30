"""AI workflow generation routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_ai_enabled, require_permission, require_csrf_header
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.schemas.auth import UserSession

router = APIRouter()
logger = logging.getLogger(__name__)


class GenerateWorkflowRequest(BaseModel):
    """Request to generate a workflow from natural language."""

    description: str = Field(..., min_length=10, max_length=2000)
    scope: str = Field(default="personal", pattern="^(personal|org)$")


class GenerateWorkflowResponse(BaseModel):
    """Response from workflow generation."""

    success: bool
    workflow: dict[str, Any] | None = None
    explanation: str | None = None
    validation_errors: list[str] = []
    warnings: list[str] = []


class ValidateWorkflowRequest(BaseModel):
    """Request to validate a workflow configuration."""

    workflow: dict[str, Any]
    scope: str = Field(default="personal", pattern="^(personal|org)$")


class ValidateWorkflowResponse(BaseModel):
    """Response from workflow validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class SaveWorkflowRequest(BaseModel):
    """Request to save an approved workflow."""

    workflow: dict[str, Any]
    scope: str = Field(default="personal", pattern="^(personal|org)$")


class SaveWorkflowResponse(BaseModel):
    """Response from workflow save."""

    success: bool
    workflow_id: str | None = None
    error: str | None = None


@router.post(
    "/workflows/generate",
    response_model=GenerateWorkflowResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
def generate_workflow(
    request: Request,
    body: GenerateWorkflowRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> GenerateWorkflowResponse:
    """
    Generate a workflow configuration from natural language description.

    The generated workflow is returned for user review before saving.
    Restricted to Manager/Developer roles for safety.
    """
    from app.services import ai_workflow_service

    if body.scope == "org":
        from app.services import permission_service

        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
        ):
            raise HTTPException(status_code=403, detail="Missing permission: manage_automation")

    result = ai_workflow_service.generate_workflow(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        description=body.description,
        scope=body.scope,
    )

    return GenerateWorkflowResponse(
        success=result.success,
        workflow=result.workflow.model_dump() if result.workflow else None,
        explanation=result.explanation,
        validation_errors=result.validation_errors,
        warnings=result.warnings,
    )


@router.post(
    "/workflows/validate",
    response_model=ValidateWorkflowResponse,
    dependencies=[Depends(require_csrf_header)],
)
def validate_workflow(
    body: ValidateWorkflowRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ValidateWorkflowResponse:
    """
    Validate a workflow configuration.

    Used to check if an AI-generated or user-modified workflow is valid
    before saving.
    """
    from app.services import ai_workflow_service
    from app.services.ai_workflow_service import GeneratedWorkflow

    try:
        workflow = GeneratedWorkflow(**body.workflow)
    except Exception as e:
        return ValidateWorkflowResponse(
            valid=False,
            errors=[f"Invalid workflow format: {str(e)}"],
        )

    if body.scope == "org":
        from app.services import permission_service

        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
        ):
            raise HTTPException(status_code=403, detail="Missing permission: manage_automation")

    result = ai_workflow_service.validate_workflow(
        db,
        session.org_id,
        workflow,
        scope=body.scope,
        owner_user_id=session.user_id if body.scope == "personal" else None,
    )

    return ValidateWorkflowResponse(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post(
    "/workflows/save",
    response_model=SaveWorkflowResponse,
    dependencies=[Depends(require_csrf_header)],
)
def save_ai_workflow(
    body: SaveWorkflowRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> SaveWorkflowResponse:
    """
    Save an approved AI-generated workflow.

    The workflow must pass validation before saving.
    Created workflows are disabled by default for safety.
    """
    from app.services import ai_workflow_service, audit_service
    from app.services.ai_workflow_service import GeneratedWorkflow

    try:
        workflow_data = GeneratedWorkflow(**body.workflow)
    except Exception as e:
        return SaveWorkflowResponse(
            success=False,
            error=f"Invalid workflow format: {str(e)}",
        )

    if body.scope == "org":
        from app.services import permission_service

        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
        ):
            raise HTTPException(status_code=403, detail="Missing permission: manage_automation")

    try:
        saved = ai_workflow_service.save_workflow(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            workflow=workflow_data,
            scope=body.scope,
        )

        # Audit log for AI-generated workflow
        audit_service.log_ai_workflow_created(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            workflow_id=saved.id,
            workflow_name=saved.name,
        )

        db.commit()

        return SaveWorkflowResponse(
            success=True,
            workflow_id=str(saved.id),
        )

    except ValueError as e:
        return SaveWorkflowResponse(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to save AI workflow: {e}")
        return SaveWorkflowResponse(
            success=False,
            error="Failed to save workflow",
        )
