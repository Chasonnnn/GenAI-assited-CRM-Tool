"""AI workflow generation routes."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_ai_enabled, require_permission, require_csrf_header
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.schemas.auth import UserSession
from app.services.ai_provider import ChatMessage
from app.services.ai_response_validation import parse_json_object, validate_model
from app.services.ai_prompt_registry import get_prompt
from app.utils.sse import format_sse, sse_preamble, STREAM_HEADERS

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
    "/workflows/generate/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def generate_workflow_stream(
    request: Request,
    body: GenerateWorkflowRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> StreamingResponse:
    """Stream workflow generation via SSE."""
    from app.services import ai_workflow_service, ai_settings_service
    from app.services.ai_workflow_service import GeneratedWorkflow

    if body.scope == "org":
        from app.services import permission_service

        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
        ):
            raise HTTPException(status_code=403, detail="Missing permission: manage_automation")

    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        async def _disabled_events() -> AsyncIterator[str]:
            yield sse_preamble()
            yield format_sse("start", {"status": "thinking"})
            response = GenerateWorkflowResponse(
                success=False,
                explanation="AI is not enabled for this organization",
            )
            yield format_sse("done", response.model_dump())

        return StreamingResponse(
            _disabled_events(),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    if ai_settings_service.is_consent_required(settings):
        async def _consent_events() -> AsyncIterator[str]:
            yield sse_preamble()
            yield format_sse("start", {"status": "thinking"})
            response = GenerateWorkflowResponse(
                success=False,
                explanation="AI consent not accepted",
            )
            yield format_sse("done", response.model_dump())

        return StreamingResponse(
            _consent_events(),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    provider = ai_settings_service.get_ai_provider_for_settings(
        settings, session.org_id, user_id=session.user_id
    )
    if not provider:
        message = (
            "Vertex AI configuration is incomplete"
            if settings.provider == "vertex_wif"
            else "AI API key not configured"
        )

        async def _missing_events() -> AsyncIterator[str]:
            yield sse_preamble()
            yield format_sse("start", {"status": "thinking"})
            response = GenerateWorkflowResponse(
                success=False,
                explanation=message,
            )
            yield format_sse("done", response.model_dump())

        return StreamingResponse(
            _missing_events(),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    context = ai_workflow_service._get_context_for_prompt(
        db,
        session.org_id,
        anonymize_pii=settings.anonymize_pii,
        scope=body.scope,
        owner_user_id=session.user_id,
    )
    prompt_template = get_prompt("workflow_generation")
    prompt = prompt_template.render_user(
        triggers=context["triggers"],
        actions=context["actions"],
        templates=context["templates"],
        users=context["users"],
        stages=context["stages"],
        user_input=body.description,
    )

    messages = [
        ChatMessage(role="system", content=prompt_template.system),
        ChatMessage(role="user", content=prompt),
    ]

    async def event_generator() -> AsyncIterator[str]:
        yield sse_preamble()
        yield format_sse("start", {"status": "thinking"})
        content = ""
        try:
            async for chunk in provider.stream_chat(messages=messages, temperature=0.3):
                if chunk.text:
                    content += chunk.text
                    yield format_sse("delta", {"text": chunk.text})
        except asyncio.CancelledError:
            return
        except Exception as exc:
            ai_workflow_service._create_workflow_generation_alert(
                db, session.org_id, str(exc), type(exc).__name__
            )
            response = GenerateWorkflowResponse(
                success=False,
                explanation=f"Error generating workflow: {str(exc)}",
            )
            yield format_sse("done", response.model_dump())
            return

        try:
            workflow_data = parse_json_object(content)
            workflow_model = validate_model(GeneratedWorkflow, workflow_data)
            if not workflow_model:
                raise json.JSONDecodeError("Invalid workflow JSON", content, 0)

            validation_result = ai_workflow_service.validate_workflow(
                db,
                session.org_id,
                workflow_model,
                scope=body.scope,
                owner_user_id=session.user_id if body.scope == "personal" else None,
            )

            if not validation_result.valid:
                response = GenerateWorkflowResponse(
                    success=False,
                    workflow=workflow_model.model_dump(),
                    explanation="Generated workflow has validation errors",
                    validation_errors=validation_result.errors,
                    warnings=validation_result.warnings,
                )
                yield format_sse("done", response.model_dump())
                return

            response = GenerateWorkflowResponse(
                success=True,
                workflow=workflow_model.model_dump(),
                explanation="Workflow generated successfully. Please review before saving.",
                warnings=validation_result.warnings,
            )
            yield format_sse("done", response.model_dump())
        except json.JSONDecodeError as exc:
            ai_workflow_service._create_workflow_generation_alert(
                db, session.org_id, str(exc), "JSONDecodeError"
            )
            response = GenerateWorkflowResponse(
                success=False,
                explanation=f"Failed to parse AI response as JSON: {str(exc)}",
            )
            yield format_sse("done", response.model_dump())
        except Exception as exc:
            ai_workflow_service._create_workflow_generation_alert(
                db, session.org_id, str(exc), type(exc).__name__
            )
            response = GenerateWorkflowResponse(
                success=False,
                explanation=f"Error generating workflow: {str(exc)}",
            )
            yield format_sse("done", response.model_dump())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
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
