"""AI Assistant API router.

Endpoints for AI settings, chat, and actions.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_current_session,
    require_ai_enabled,
    require_all_permissions,
    require_csrf_header,
    require_permission,
)
from app.core.encryption import encrypt_value
from app.core.permissions import PermissionKey as P
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import SurrogateActivityType, JobStatus, JobType, Role
from app.schemas.auth import UserSession
from app.services import (
    ai_chat_service,
    ai_service,
    ai_settings_service,
    surrogate_service,
    ip_service,
    job_service,
    match_service,
    note_service,
    oauth_service,
    task_service,
    user_service,
)
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_prompt_schemas import (
    AIDashboardAnalysisOutput,
    AIDraftEmailOutput,
    AISurrogateSummaryOutput,
)
from app.services.ai_response_validation import (
    parse_json_object,
    validate_model,
)

# Rate limiting
from app.core.rate_limit import limiter

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

CONSENT_TEXT = """
By enabling the AI Assistant, you acknowledge that:

1. Surrogate data (names, contact info, notes) will be sent to a third-party AI provider 
   (OpenAI or Google Gemini) for processing.

2. If "Anonymize PII" is enabled (default), personal identifiers will be stripped 
   before sending to the AI and restored in responses.

3. Data sent to AI providers is subject to their data processing policies. 
   OpenAI and Google do not train on API data.

4. AI responses are suggestions only. Staff must verify accuracy before acting.

5. A usage log tracks all AI interactions for compliance and auditing.
""".strip()


# ============================================================================
# Request/Response Models
# ============================================================================


class VertexWIFConfig(BaseModel):
    project_id: str | None = None
    location: str | None = None
    audience: str | None = None
    service_account_email: str | None = None


class AISettingsResponse(BaseModel):
    """AI settings for display (with masked key)."""

    is_enabled: bool
    provider: str
    model: str | None
    api_key_masked: str | None
    vertex_wif: VertexWIFConfig | None = None
    context_notes_limit: int
    conversation_history_limit: int
    # Privacy fields
    anonymize_pii: bool
    consent_accepted_at: str | None
    consent_required: bool
    # Version control
    current_version: int | None = None


class AISettingsUpdate(BaseModel):
    """Update AI settings."""

    is_enabled: bool | None = None
    provider: str | None = Field(None, pattern="^(openai|gemini|vertex_wif)$")
    api_key: str | None = None
    model: str | None = None
    vertex_wif: VertexWIFConfig | None = None
    context_notes_limit: int | None = Field(None, ge=1, le=20)
    conversation_history_limit: int | None = Field(None, ge=5, le=50)
    anonymize_pii: bool | None = None
    expected_version: int | None = Field(None, description="Required for optimistic locking")


class TestKeyRequest(BaseModel):
    """Test an API key."""

    provider: str = Field(..., pattern="^(openai|gemini)$")
    api_key: str


class TestKeyResponse(BaseModel):
    """API key test result."""

    valid: bool


class ConsentResponse(BaseModel):
    """Consent info."""

    consent_text: str
    consent_accepted_at: str | None
    consent_accepted_by: str | None


class ChatRequest(BaseModel):
    """Send a chat message.

    entity_type and entity_id are optional for global chat mode.
    When provided, context is injected for that specific entity.
    """

    entity_type: str | None = Field(None, pattern="^(case|surrogate|task|global)$")
    entity_id: uuid.UUID | None = None
    message: str = Field(..., min_length=1, max_length=10000)


class ChatResponseModel(BaseModel):
    """Chat response."""

    content: str
    proposed_actions: list[dict[str, Any]]
    tokens_used: dict[str, Any]
    conversation_id: str | None = None
    assistant_message_id: str | None = None


class ChatJobResponse(BaseModel):
    job_id: str
    status: str


class ChatJobStatusResponse(BaseModel):
    job_id: str
    status: str
    error: str | None = None
    result: ChatResponseModel | None = None


# ============================================================================
# Settings Endpoints (Manager Only)
# ============================================================================


@router.get("/settings", response_model=AISettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> AISettingsResponse:
    """Get AI settings for the organization."""
    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id, session.user_id)

    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=settings.model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        vertex_wif=VertexWIFConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
            audience=settings.vertex_audience,
            service_account_email=settings.vertex_service_account_email,
        )
        if settings.provider == "vertex_wif"
        else None,
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_required=ai_settings_service.is_consent_required(settings),
        current_version=settings.current_version,
    )


@router.patch(
    "/settings",
    response_model=AISettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_settings(
    update: AISettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> AISettingsResponse:
    """Update AI settings for the organization. Creates version snapshot."""
    from app.services import version_service

    try:
        settings = ai_settings_service.update_ai_settings(
            db,
            session.org_id,
            session.user_id,
            is_enabled=update.is_enabled,
            provider=update.provider,
            api_key=update.api_key,
            model=update.model,
            vertex_project_id=update.vertex_wif.project_id if update.vertex_wif else None,
            vertex_location=update.vertex_wif.location if update.vertex_wif else None,
            vertex_audience=update.vertex_wif.audience if update.vertex_wif else None,
            vertex_service_account_email=update.vertex_wif.service_account_email
            if update.vertex_wif
            else None,
            context_notes_limit=update.context_notes_limit,
            conversation_history_limit=update.conversation_history_limit,
            anonymize_pii=update.anonymize_pii,
            expected_version=update.expected_version,
        )
    except version_service.VersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {e.expected}, got {e.actual}",
        )
    changed_fields = [
        field
        for field, value in {
            "is_enabled": update.is_enabled,
            "provider": update.provider,
            "api_key": update.api_key,
            "model": update.model,
            "vertex_wif": update.vertex_wif,
            "context_notes_limit": update.context_notes_limit,
            "conversation_history_limit": update.conversation_history_limit,
            "anonymize_pii": update.anonymize_pii,
        }.items()
        if value is not None
    ]
    if changed_fields:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="ai",
            changes={"fields": changed_fields},
            request=request,
        )
        if update.api_key is not None:
            audit_service.log_api_key_rotated(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                provider=update.provider or settings.provider,
                request=request,
            )
        db.commit()

    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=settings.model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        vertex_wif=VertexWIFConfig(
            project_id=settings.vertex_project_id,
            location=settings.vertex_location,
            audience=settings.vertex_audience,
            service_account_email=settings.vertex_service_account_email,
        )
        if settings.provider == "vertex_wif"
        else None,
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_required=ai_settings_service.is_consent_required(settings),
        current_version=settings.current_version,
    )


@router.post(
    "/settings/test",
    response_model=TestKeyResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def test_api_key(
    request: TestKeyRequest,
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> TestKeyResponse:
    """Test if an API key is valid."""
    valid = await ai_settings_service.test_api_key(request.provider, request.api_key)
    return TestKeyResponse(valid=valid)


# ============================================================================
# Consent Endpoints (Manager Only)
# ============================================================================


@router.get("/consent", response_model=ConsentResponse)
def get_consent(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> ConsentResponse:
    """Get consent text and status."""
    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id, session.user_id)

    return ConsentResponse(
        consent_text=CONSENT_TEXT,
        consent_accepted_at=settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        consent_accepted_by=str(settings.consent_accepted_by)
        if settings.consent_accepted_by
        else None,
    )


@router.post("/consent/accept", dependencies=[Depends(require_csrf_header)])
def accept_consent(
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_SETTINGS_MANAGE)),
) -> dict[str, Any]:
    """Accept the AI data processing consent."""
    settings = ai_settings_service.accept_consent(db, session.org_id, session.user_id)
    from app.services import audit_service

    audit_service.log_consent_accepted(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        request=request,
    )
    db.commit()

    return {
        "accepted": True,
        "accepted_at": settings.consent_accepted_at.isoformat()
        if settings.consent_accepted_at
        else None,
        "accepted_by": str(settings.consent_accepted_by) if settings.consent_accepted_by else None,
    }


# ============================================================================
# Chat Endpoints
# ============================================================================


@router.post(
    "/chat",
    response_model=ChatResponseModel,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("60/minute")
def chat(
    request: Request,  # Required by limiter
    body: ChatRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ChatResponseModel:
    """Send a message to the AI assistant.

    Requires: use_ai_assistant permission
    """
    # Check consent before allowing chat
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. An admin must accept the data processing consent before using AI.",
        )

    # Determine entity type and ID - support global mode
    entity_type = body.entity_type or "global"
    entity_id = body.entity_id

    # For global mode, use a special "global" entity ID based on user
    if entity_type == "global" or entity_id is None:
        entity_type = "global"
        # Use user_id as entity_id for global conversations
        entity_id = session.user_id

    # Check if user has access to the entity
    if entity_type in ("case", "surrogate"):
        surrogate = surrogate_service.get_surrogate(db, session.org_id, entity_id)
        if not surrogate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Surrogate not found",
            )
        # Use centralized surrogate access check (owner-based + permissions)
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )
    elif entity_type == "task":
        # Users can only access tasks they own or are assigned to
        task = task_service.get_task(db, entity_id, session.org_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        # Check if user owns or is assigned to the task
        if (
            task.created_by_user_id != session.user_id
            and task.assigned_to_user_id != session.user_id
        ):
            # Allow admins to access any task in their org
            is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
            if not is_manager:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this task",
                )

    # Get user's connected integrations
    integrations = oauth_service.get_user_integrations(db, session.user_id)
    user_integrations = [i.integration_type for i in integrations]

    # Process chat
    response = ai_chat_service.chat(
        db,
        session.org_id,
        session.user_id,
        entity_type,
        entity_id,
        body.message,
        user_integrations,
    )

    return ChatResponseModel(
        content=response["content"],
        proposed_actions=response["proposed_actions"],
        tokens_used=response["tokens_used"],
        conversation_id=response.get("conversation_id"),
        assistant_message_id=response.get("assistant_message_id"),
    )


@router.post(
    "/chat/async",
    response_model=ChatJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("60/minute")
def chat_async(
    request: Request,  # Required by limiter
    body: ChatRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ChatJobResponse:
    """Queue a chat message for async processing."""
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. An admin must accept the data processing consent before using AI.",
        )

    entity_type = body.entity_type or "global"
    entity_id = body.entity_id

    if entity_type == "global" or entity_id is None:
        entity_type = "global"
        entity_id = session.user_id

    if entity_type in ("case", "surrogate"):
        surrogate = surrogate_service.get_surrogate(db, session.org_id, entity_id)
        if not surrogate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Surrogate not found",
            )
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )
    elif entity_type == "task":
        task = task_service.get_task(db, entity_id, session.org_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        if (
            task.created_by_user_id != session.user_id
            and task.assigned_to_user_id != session.user_id
        ):
            is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
            if not is_manager:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this task",
                )

    job = job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.AI_CHAT,
        payload={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "message_encrypted": encrypt_value(body.message),
            "user_id": str(session.user_id),
        },
    )

    return ChatJobResponse(job_id=str(job.id), status=job.status)


@router.get("/chat/jobs/{job_id}", response_model=ChatJobStatusResponse)
def get_chat_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ChatJobStatusResponse:
    """Get async chat job status."""
    job = job_service.get_job(db, job_id, session.org_id)
    if not job or job.job_type != JobType.AI_CHAT.value:
        raise HTTPException(status_code=404, detail="Chat job not found")

    result_payload = None
    payload = job.payload or {}
    if job.status == JobStatus.COMPLETED.value:
        result = payload.get("result") or {}
        if result:
            result_payload = ChatResponseModel(
                content=result.get("content", ""),
                proposed_actions=result.get("proposed_actions", []),
                tokens_used=result.get("tokens_used", {}),
                conversation_id=result.get("conversation_id"),
                assistant_message_id=result.get("assistant_message_id"),
            )

    return ChatJobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        error=job.last_error,
        result=result_payload,
    )


@router.get("/conversations/{entity_type}/{entity_id}")
def get_conversation(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> dict[str, Any]:
    """Get conversation history for an entity."""
    # Validate entity access before fetching conversations
    if entity_type in ("case", "surrogate"):
        surrogate = surrogate_service.get_surrogate(db, session.org_id, entity_id)
        if not surrogate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Surrogate not found",
            )
        # Use centralized surrogate access check (owner-based + permissions)
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )
    elif entity_type == "task":
        task = task_service.get_task(db, entity_id, session.org_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )
        # Check if user owns or is assigned to the task
        if (
            task.created_by_user_id != session.user_id
            and task.assigned_to_user_id != session.user_id
        ):
            is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
            if not is_manager:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this task",
                )

    conversations = ai_chat_service.get_user_conversations(
        db, session.user_id, entity_type, entity_id
    )

    if not conversations:
        return {"messages": []}

    # Get the most recent conversation
    conversation = conversations[0]
    messages = ai_chat_service.get_conversation_messages(db, conversation.id)

    formatted_messages = []
    for msg in messages:
        # Build proposed_actions with approval_id from action_approvals
        proposed_actions = None
        if msg.proposed_actions:
            proposed_actions = []
            for i, action in enumerate(msg.proposed_actions):
                # Find matching approval by action_index
                approval = next(
                    (a for a in (msg.action_approvals or []) if a.action_index == i),
                    None,
                )
                proposed_actions.append(
                    {
                        "approval_id": str(approval.id) if approval else None,
                        "action_type": action.get("type", "unknown"),
                        "action_data": action,
                        "status": approval.status if approval else "unknown",
                    }
                )

        formatted_messages.append(
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "proposed_actions": proposed_actions,
                "created_at": msg.created_at.isoformat(),
                "action_approvals": [
                    {
                        "id": str(a.id),
                        "action_index": a.action_index,
                        "action_type": a.action_type,
                        "status": a.status,
                    }
                    for a in msg.action_approvals
                ]
                if msg.action_approvals
                else None,
            }
        )

    return {
        "conversation_id": str(conversation.id),
        "messages": formatted_messages,
    }


@router.get("/conversations/global")
@limiter.limit("120/minute")
def get_global_conversation(
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> dict[str, Any]:
    """Get global conversation history for the current user.

    Global conversations use entity_type='global' and entity_id=user_id.
    """
    conversations = ai_chat_service.get_user_conversations(
        db, session.user_id, "global", session.user_id
    )

    if not conversations:
        return {"messages": []}

    # Get the most recent conversation
    conversation = conversations[0]
    messages = ai_chat_service.get_conversation_messages(db, conversation.id)

    formatted_messages = []
    for msg in messages:
        # Build proposed_actions with approval_id from action_approvals
        proposed_actions = None
        if msg.proposed_actions:
            proposed_actions = []
            for i, action in enumerate(msg.proposed_actions):
                approval = next(
                    (a for a in (msg.action_approvals or []) if a.action_index == i),
                    None,
                )
                proposed_actions.append(
                    {
                        "approval_id": str(approval.id) if approval else None,
                        "action_type": action.get("type", "unknown"),
                        "action_data": action,
                        "status": approval.status if approval else "unknown",
                    }
                )

        formatted_messages.append(
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "proposed_actions": proposed_actions,
                "created_at": msg.created_at.isoformat(),
            }
        )

    return {
        "conversation_id": str(conversation.id),
        "messages": formatted_messages,
    }


@router.get("/conversations/{entity_type}/{entity_id}/all")
def get_all_conversations(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_CONVERSATIONS_VIEW_ALL)),
) -> dict[str, Any]:
    """Get all users' conversations for an entity (developer only, for audit)."""
    conversations = ai_service.list_conversations_for_entity(
        db=db,
        org_id=session.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return {
        "conversations": [
            {
                "id": str(c.id),
                "user_id": str(c.user_id),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in conversations
        ]
    }


# ============================================================================
# Action Approval Endpoints
# ============================================================================


class ActionApprovalResponse(BaseModel):
    """Response for action approval."""

    success: bool
    action_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


@router.post(
    "/actions/{approval_id}/approve",
    response_model=ActionApprovalResponse,
    dependencies=[Depends(require_csrf_header)],
)
def approve_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_APPROVE_ACTIONS)),
) -> ActionApprovalResponse:
    """Approve and execute a proposed action.

    Requires: approve_ai_actions permission (plus action-specific permissions)
    """
    from app.services.ai_action_executor import execute_action

    # Get the approval with related data
    approval, message, conversation = ai_service.get_approval_with_conversation(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")

    # Get conversation to verify org access
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify user owns this conversation or has admin role
    is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
    if conversation.user_id != session.user_id and not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to approve this action")

    # Re-check surrogate access before executing actions
    if conversation.entity_type in ("surrogate", "case"):
        surrogate = surrogate_service.get_surrogate(db, session.org_id, conversation.entity_id)
        if not surrogate:
            raise HTTPException(status_code=404, detail="Surrogate not found")
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )

    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already processed (status: {approval.status})",
        )

    # Get user's permissions for action-specific checks
    from app.services import permission_service

    user_permissions = permission_service.get_effective_permissions(
        db, session.org_id, session.user_id, session.role.value
    )

    # Execute the action with permission checks
    result = execute_action(
        db=db,
        approval=approval,
        user_id=session.user_id,
        org_id=session.org_id,
        entity_id=conversation.entity_id,
        user_permissions=user_permissions,
    )

    # Surrogate activity log for AI-generated actions (surrogate context only)
    if result.get("success") and conversation.entity_type == "surrogate":
        from app.services import activity_service, pipeline_service

        surrogate_id = conversation.entity_id
        details_base = {
            "source": "ai",
            "approval_id": str(approval.id),
            "action_type": approval.action_type,
        }

        if approval.action_type == "add_note":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.NOTE_ADDED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "note_id": result.get("note_id"),
                },
            )
        elif approval.action_type == "send_email":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.EMAIL_SENT,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "provider": "gmail",
                },
            )
        elif approval.action_type == "update_status":
            old_stage_id = result.get("old_stage_id")
            new_stage_id = result.get("new_stage_id")
            old_label = None
            new_label = None
            if old_stage_id:
                old_stage = pipeline_service.get_stage_by_id(db, uuid.UUID(old_stage_id))
                old_label = old_stage.label if old_stage else None
            if new_stage_id:
                new_stage = pipeline_service.get_stage_by_id(db, uuid.UUID(new_stage_id))
                new_label = new_stage.label if new_stage else None

            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.STATUS_CHANGED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "from": old_label,
                    "to": new_label,
                },
            )
        elif approval.action_type == "create_task":
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.TASK_CREATED,
                actor_user_id=session.user_id,
                details={
                    **details_base,
                    "task_id": result.get("task_id"),
                    "title": result.get("title"),
                },
            )

    # Audit log - only log approved if actually successful
    from app.services import audit_service

    if result.get("success"):
        audit_service.log_ai_action_approved(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            approval_id=approval.id,
            action_type=approval.action_type,
        )
    else:
        error_code = result.get("error_code")
        if error_code == "permission_denied":
            audit_service.log_ai_action_denied(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                approval_id=approval.id,
                action_type=approval.action_type,
                reason=result.get("error"),
            )
        else:
            audit_service.log_ai_action_failed(
                db=db,
                org_id=session.org_id,
                user_id=session.user_id,
                approval_id=approval.id,
                action_type=approval.action_type,
                error=result.get("error"),
            )

    db.commit()

    return ActionApprovalResponse(
        success=result.get("success", False),
        action_type=approval.action_type,
        status=approval.status,
        result=result if result.get("success") else None,
        error=result.get("error") if not result.get("success") else None,
    )


@router.post("/actions/{approval_id}/reject", dependencies=[Depends(require_csrf_header)])
def reject_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Reject a proposed action."""
    # Get the approval with related data
    approval, message, conversation = ai_service.get_approval_with_conversation(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")

    # Get conversation to verify org access
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify user owns this conversation or has admin role
    is_manager = session.role in (Role.ADMIN, Role.CASE_MANAGER, Role.DEVELOPER)
    if conversation.user_id != session.user_id and not is_manager:
        raise HTTPException(status_code=403, detail="Not authorized to reject this action")

    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action already processed (status: {approval.status})",
        )

    # Mark as rejected
    approval.status = "rejected"
    approval.executed_at = datetime.now(timezone.utc)

    # Audit log
    from app.services import audit_service

    audit_service.log_ai_action_rejected(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        approval_id=approval.id,
        action_type=approval.action_type,
    )

    db.commit()

    return {
        "success": True,
        "action_type": approval.action_type,
        "status": "rejected",
    }


@router.get("/actions/pending")
def get_pending_actions(
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> dict[str, Any]:
    """Get all pending actions for the current user."""
    approvals = ai_service.list_pending_actions(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )

    return {
        "pending_actions": [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "action_payload": a.action_payload,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ]
    }


# ============================================================================
# Usage Analytics Endpoints (Manager Only)
# ============================================================================


@router.get("/usage/summary")
def get_usage_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get organization usage summary."""
    from app.services import ai_usage_service

    return ai_usage_service.get_org_usage_summary(db, session.org_id, days)


@router.get("/usage/by-model")
def get_usage_by_model(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get usage breakdown by AI model."""
    from app.services import ai_usage_service

    return {"models": ai_usage_service.get_usage_by_model(db, session.org_id, days)}


@router.get("/usage/daily")
def get_daily_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get daily usage breakdown."""
    from app.services import ai_usage_service

    return {"daily": ai_usage_service.get_daily_usage(db, session.org_id, days)}


@router.get("/usage/top-users")
def get_top_users(
    days: int = 30,
    limit: int = 10,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USAGE_VIEW)),
) -> dict[str, Any]:
    """Get top users by AI usage."""
    from app.services import ai_usage_service

    return {"users": ai_usage_service.get_top_users(db, session.org_id, days, limit)}


@router.get("/usage/me")
def get_my_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Get current user's AI usage."""
    from app.services import ai_usage_service

    return ai_usage_service.get_user_usage_summary(db, session.user_id, days)


# ============================================================================
# Focused AI Endpoints (One-shot operations, no conversation history)
# ============================================================================


class SummarizeSurrogateRequest(BaseModel):
    """Request to summarize a surrogate."""

    surrogate_id: uuid.UUID


class SummarizeSurrogateResponse(BaseModel):
    """Surrogate summary response."""

    surrogate_number: str
    full_name: str
    summary: str
    current_status: str
    key_dates: dict[str, Any]
    pending_tasks: list[dict[str, Any]]
    recent_activity: str
    suggested_next_steps: list[str]


class EmailType(str, Enum):
    """Types of emails that can be drafted."""

    FOLLOW_UP = "follow_up"
    STATUS_UPDATE = "status_update"
    MEETING_REQUEST = "meeting_request"
    DOCUMENT_REQUEST = "document_request"
    INTRODUCTION = "introduction"


class DraftEmailRequest(BaseModel):
    """Request to draft an email."""

    surrogate_id: uuid.UUID
    email_type: EmailType
    additional_context: str | None = None


class DraftEmailResponse(BaseModel):
    """Draft email response."""

    subject: str
    body: str
    recipient_email: str
    recipient_name: str
    email_type: str


class AnalyzeDashboardResponse(BaseModel):
    """Dashboard analytics response."""

    insights: list[str]
    surrogate_volume_trend: str
    bottlenecks: list[dict[str, Any]]
    recommendations: list[str]
    stats: dict[str, Any]


# Email type prompts
EMAIL_PROMPTS = {
    EmailType.FOLLOW_UP: """Draft a professional follow-up email to check in with the applicant. 
The tone should be warm and supportive. Ask how they're doing and if they have any questions.""",
    EmailType.STATUS_UPDATE: """Draft a status update email informing the applicant about their surrogate progress.
Be clear about current status, what's been completed, and what to expect next.""",
    EmailType.MEETING_REQUEST: """Draft an email requesting a meeting or phone call with the applicant.
Suggest a few time options and explain what you'd like to discuss.""",
    EmailType.DOCUMENT_REQUEST: """Draft an email requesting missing or additional documents from the applicant.
Be specific about what documents are needed and why they're important.""",
    EmailType.INTRODUCTION: """Draft an introduction email to share with intended parents about this surrogate candidate.
Highlight key qualifications and background while being professional and respectful of privacy.""",
}


@router.post(
    "/summarize-surrogate",
    response_model=SummarizeSurrogateResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("30/minute")
async def summarize_surrogate(
    request: Request,
    body: SummarizeSurrogateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> SummarizeSurrogateResponse:
    """Generate a comprehensive summary of a surrogate using AI.

    Requires: use_ai_assistant permission
    """
    from app.services import ai_settings_service
    from app.services.ai_provider import ChatMessage, get_provider
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data
    from app.services.ai_usage_service import log_usage

    # Check AI is enabled and consent accepted
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI is not enabled for this organization",
        )
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted",
        )

    # Load surrogate with context
    surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
    check_surrogate_access(
        surrogate=surrogate,
        user_role=session.role,
        user_id=session.user_id,
        db=db,
        org_id=session.org_id,
    )

    # Load notes and tasks
    notes = note_service.list_notes_limited(
        db=db,
        org_id=session.org_id,
        entity_type="case",
        entity_id=surrogate.id,
        limit=10,
    )
    tasks = task_service.list_open_tasks_for_surrogate(
        db=db,
        surrogate_id=surrogate.id,
        org_id=session.org_id,
        limit=10,
    )

    # Build context
    notes_text = (
        "\n".join([f"- [{n.created_at.strftime('%Y-%m-%d')}] {n.content[:200]}" for n in notes])
        or "No notes yet"
    )
    tasks_text = (
        "\n".join([f"- {t.title} (due: {t.due_date or 'not set'})" for t in tasks])
        or "No pending tasks"
    )

    context = f"""Surrogate #{surrogate.surrogate_number}
Name: {surrogate.full_name}
Email: {surrogate.email}
Status: {surrogate.status_label}
Created: {surrogate.created_at.strftime("%Y-%m-%d")}

Recent Notes:
{notes_text}

Pending Tasks:
{tasks_text}"""

    pii_mapping = PIIMapping() if settings.anonymize_pii else None
    if settings.anonymize_pii and pii_mapping:
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        context = anonymize_text(context, pii_mapping, known_names)

    prompt = get_prompt("surrogate_summary").render_user(context=context)

    # Call AI
    api_key = ai_settings_service.get_decrypted_key(settings)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="AI API key not configured"
        )

    provider = get_provider(settings.provider, api_key, settings.model)

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("surrogate_summary").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.3,
    )

    parsed_model = validate_model(AISurrogateSummaryOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "summary": response.content[:500],
            "recent_activity": "See notes above",
            "suggested_next_steps": ["Review case details", "Follow up with applicant"],
        }

    if settings.anonymize_pii and pii_mapping:
        parsed = rehydrate_data(parsed, pii_mapping)

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    # Build key dates
    key_dates = {
        "created": surrogate.created_at.isoformat() if surrogate.created_at else None,
        "updated": surrogate.updated_at.isoformat() if surrogate.updated_at else None,
    }

    # Build pending tasks list
    pending_tasks = [
        {
            "id": str(t.id),
            "title": t.title,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        }
        for t in tasks
    ]

    return SummarizeSurrogateResponse(
        surrogate_number=surrogate.surrogate_number,
        full_name=surrogate.full_name,
        summary=parsed.get("summary", "Unable to generate summary"),
        current_status=surrogate.status_label,
        key_dates=key_dates,
        pending_tasks=pending_tasks,
        recent_activity=parsed.get("recent_activity", "No recent activity"),
        suggested_next_steps=parsed.get("suggested_next_steps", []),
    )


@router.post(
    "/draft-email",
    response_model=DraftEmailResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("30/minute")
async def draft_email(
    request: Request,
    body: DraftEmailRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> DraftEmailResponse:
    """Draft an email for a case using AI.

    Requires: use_ai_assistant permission
    """
    from app.services import ai_settings_service
    from app.services.ai_provider import ChatMessage, get_provider
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data
    from app.services.ai_usage_service import log_usage

    # Check AI is enabled
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI is not enabled")
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI consent not accepted")

    # Load surrogate
    surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
    check_surrogate_access(
        surrogate=surrogate,
        user_role=session.role,
        user_id=session.user_id,
        db=db,
        org_id=session.org_id,
    )

    # Get user name for signature
    user = user_service.get_user_by_id(db, session.user_id)
    if user:
        sender_name = user.signature_name or user.display_name
    else:
        sender_name = "Your Case Manager"

    # Build email prompt
    email_instruction = EMAIL_PROMPTS[body.email_type]
    additional_context = body.additional_context or ""
    pii_mapping = PIIMapping() if settings.anonymize_pii else None
    recipient_name = surrogate.full_name
    recipient_email = surrogate.email
    if settings.anonymize_pii and pii_mapping:
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        if recipient_name:
            recipient_name = pii_mapping.add_name(recipient_name)
        if recipient_email:
            recipient_email = pii_mapping.add_email(recipient_email)
        if additional_context:
            additional_context = anonymize_text(additional_context, pii_mapping, known_names)

    additional = f"\nAdditional context: {additional_context}" if additional_context else ""

    prompt = get_prompt("email_draft").render_user(
        email_instruction=email_instruction,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        surrogate_status=surrogate.status_label,
        additional_context=additional,
        sender_name=sender_name,
    )

    # Call AI
    api_key = ai_settings_service.get_decrypted_key(settings)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="AI API key not configured"
        )

    provider = get_provider(settings.provider, api_key, settings.model)

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("email_draft").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.5,
    )

    parsed_model = validate_model(AIDraftEmailOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "subject": "Following up on your application",
            "body": response.content,
        }

    if settings.anonymize_pii and pii_mapping:
        parsed = rehydrate_data(parsed, pii_mapping)

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    return DraftEmailResponse(
        subject=parsed.get("subject", "Following up"),
        body=parsed.get("body", ""),
        recipient_email=surrogate.email,
        recipient_name=surrogate.full_name,
        email_type=body.email_type.value,
    )


@router.post(
    "/analyze-dashboard",
    response_model=AnalyzeDashboardResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def analyze_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_all_permissions([P.AI_USE, P.REPORTS_VIEW])),
) -> AnalyzeDashboardResponse:
    """Analyze dashboard data and provide AI-powered insights."""
    from app.services import ai_settings_service
    from app.services.ai_provider import ChatMessage, get_provider
    from app.services.ai_usage_service import log_usage

    # Check AI is enabled
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if not settings or not settings.is_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI is not enabled")
    if ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted",
        )

    # Gather dashboard stats
    now = datetime.now(timezone.utc)

    surrogate_stats = surrogate_service.get_surrogate_stats(db, session.org_id)
    total_surrogates = surrogate_stats["total"]
    status_summary = surrogate_stats["by_status"]
    surrogates_this_week = surrogate_stats["this_week"]
    surrogates_last_week = surrogate_stats["last_week"]
    overdue_tasks = task_service.count_overdue_tasks(db, session.org_id, now.date())

    # Build stats summary
    stats = {
        "total_active_surrogates": total_surrogates,
        "surrogates_this_week": surrogates_this_week,
        "surrogates_last_week": surrogates_last_week,
        "overdue_tasks": overdue_tasks,
        "status_breakdown": status_summary,
    }

    # Determine trend
    if surrogates_this_week > surrogates_last_week:
        trend = f"Increasing ({surrogates_this_week} this week vs {surrogates_last_week} last week)"
    elif surrogates_this_week < surrogates_last_week:
        trend = f"Decreasing ({surrogates_this_week} this week vs {surrogates_last_week} last week)"
    else:
        trend = f"Stable ({surrogates_this_week} surrogates this week)"

    # Identify bottlenecks
    bottlenecks = []
    for status_name, count in status_summary.items():
        if count > total_surrogates * 0.3:  # More than 30% in one status
            bottlenecks.append(
                {
                    "status": status_name,
                    "count": count,
                    "percentage": round(count / total_surrogates * 100, 1)
                    if total_surrogates > 0
                    else 0,
                }
            )

    # Call AI for insights
    api_key = ai_settings_service.get_decrypted_key(settings)
    if not api_key:
        # Return basic analysis without AI
        return AnalyzeDashboardResponse(
            insights=[f"You have {total_surrogates} active surrogates"],
            surrogate_volume_trend=trend,
            bottlenecks=bottlenecks,
            recommendations=["Configure AI API key for detailed insights"],
            stats=stats,
        )

    prompt = get_prompt("dashboard_analysis").render_user(
        total_surrogates=total_surrogates,
        surrogates_this_week=surrogates_this_week,
        surrogates_last_week=surrogates_last_week,
        overdue_tasks=overdue_tasks,
        status_summary=status_summary,
    )

    provider = get_provider(settings.provider, api_key, settings.model)

    response = await provider.chat(
        [
            ChatMessage(role="system", content=get_prompt("dashboard_analysis").system),
            ChatMessage(role="user", content=prompt),
        ],
        temperature=0.4,
    )

    parsed_model = validate_model(AIDashboardAnalysisOutput, parse_json_object(response.content))
    if parsed_model:
        parsed = parsed_model.model_dump()
    else:
        parsed = {
            "insights": [response.content[:200]],
            "recommendations": ["Review case statuses regularly"],
        }

    log_usage(
        db=db,
        organization_id=session.org_id,
        user_id=session.user_id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )

    return AnalyzeDashboardResponse(
        insights=parsed.get("insights", []),
        surrogate_volume_trend=trend,
        bottlenecks=bottlenecks,
        recommendations=parsed.get("recommendations", []),
        stats=stats,
    )


# ============================================================================
# AI Workflow Generation Endpoints
# ============================================================================


class GenerateWorkflowRequest(BaseModel):
    """Request to generate a workflow from natural language."""

    description: str = Field(..., min_length=10, max_length=2000)


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


class ValidateWorkflowResponse(BaseModel):
    """Response from workflow validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []


class SaveWorkflowRequest(BaseModel):
    """Request to save an approved workflow."""

    workflow: dict[str, Any]


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
    session: UserSession = Depends(require_all_permissions([P.AI_USE, P.AUTOMATION_MANAGE])),
) -> GenerateWorkflowResponse:
    """
    Generate a workflow configuration from natural language description.

    The generated workflow is returned for user review before saving.
    Restricted to Manager/Developer roles for safety.
    """
    from app.services import ai_workflow_service

    result = ai_workflow_service.generate_workflow(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        description=body.description,
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
    session: UserSession = Depends(require_all_permissions([P.AI_USE, P.AUTOMATION_MANAGE])),
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

    result = ai_workflow_service.validate_workflow(db, session.org_id, workflow)

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
    session: UserSession = Depends(require_all_permissions([P.AI_USE, P.AUTOMATION_MANAGE])),
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

    try:
        saved = ai_workflow_service.save_workflow(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            workflow=workflow_data,
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


# ============================================================================
# Schedule Parsing Endpoints
# ============================================================================


class ParseScheduleRequest(BaseModel):
    """Request to parse a schedule text."""

    text: str = Field(..., min_length=1, max_length=10000)
    # At least one entity ID must be provided
    surrogate_id: uuid.UUID | None = None
    intended_parent_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    user_timezone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_id(cls, values):
        if isinstance(values, dict) and not values.get("surrogate_id") and values.get("case_id"):
            values["surrogate_id"] = values["case_id"]
        return values

    @model_validator(mode="after")
    def _validate_entity_ids(self):
        if not any([self.surrogate_id, self.intended_parent_id, self.match_id]):
            raise ValueError(
                "At least one of surrogate_id, intended_parent_id, or match_id must be provided"
            )
        return self


class ParseScheduleResponse(BaseModel):
    """Response with proposed tasks."""

    proposed_tasks: list[dict]
    warnings: list[str]
    assumed_timezone: str
    assumed_reference_date: str


@router.post(
    "/parse-schedule",
    response_model=ParseScheduleResponse,
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("10/minute")
async def parse_schedule(
    request: Request,
    body: ParseScheduleRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> ParseScheduleResponse:
    """
    Parse schedule text using AI and extract task proposals.

    At least one of surrogate_id, intended_parent_id, or match_id must be provided.
    User reviews and approves before tasks are created.
    """
    from app.services.schedule_parser import parse_schedule_text

    # Enforce AI consent (consistent with /chat)
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. An admin must accept the data processing consent before using AI.",
        )

    # Verify entity exists and belongs to org
    entity_type = None
    entity_id = None
    known_names: list[str] = []

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
        # Enforce surrogate access (owner/role-based)
        check_surrogate_access(
            surrogate=surrogate,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        entity_type = "case"
        entity_id = surrogate_id
    elif body.intended_parent_id:
        parent = ip_service.get_intended_parent(db, body.intended_parent_id, session.org_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intended parent not found",
            )
        if parent.full_name:
            known_names.append(parent.full_name)
            known_names.extend(parent.full_name.split())
        entity_type = "intended_parent"
        entity_id = body.intended_parent_id
    elif body.match_id:
        match = match_service.get_match(db, body.match_id, session.org_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        # Enforce access to the associated surrogate
        if match.surrogate_id:
            surrogate = surrogate_service.get_surrogate(db, session.org_id, match.surrogate_id)
            if surrogate:
                check_surrogate_access(
                    surrogate=surrogate,
                    user_role=session.role,
                    user_id=session.user_id,
                    db=db,
                    org_id=session.org_id,
                )
                if surrogate.full_name:
                    known_names.append(surrogate.full_name)
                    known_names.extend(surrogate.full_name.split())
        entity_type = "match"
        entity_id = body.match_id

    # Log metadata only (no PII from schedule text)
    logger.info(
        f"Parse schedule request: user={session.user_id}, "
        f"entity_type={entity_type}, entity_id={entity_id}, text_len={len(body.text)}"
    )

    # Parse using AI
    result = await parse_schedule_text(
        db=db,
        org_id=session.org_id,
        text=body.text,
        user_timezone=body.user_timezone,
        known_names=known_names or None,
    )

    return ParseScheduleResponse(
        proposed_tasks=[task.model_dump() for task in result.proposed_tasks],
        warnings=result.warnings,
        assumed_timezone=result.assumed_timezone,
        assumed_reference_date=result.assumed_reference_date.isoformat(),
    )


class BulkTaskItem(BaseModel):
    """A single task to create."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    due_date: str | None = None  # ISO format
    due_time: str | None = None  # HH:MM format
    task_type: str = "other"
    dedupe_key: str | None = None


class BulkTaskCreateRequest(BaseModel):
    """Request to create multiple tasks."""

    request_id: uuid.UUID  # Idempotency key
    # At least one entity ID must be provided
    surrogate_id: uuid.UUID | None = None
    intended_parent_id: uuid.UUID | None = None
    match_id: uuid.UUID | None = None
    tasks: list[BulkTaskItem] = Field(..., min_length=1, max_length=50)

    @model_validator(mode="before")
    @classmethod
    def _normalize_case_id(cls, values):
        if isinstance(values, dict) and not values.get("surrogate_id") and values.get("case_id"):
            values["surrogate_id"] = values["case_id"]
        return values

    @model_validator(mode="after")
    def _validate_entity_ids(self):
        if not any([self.surrogate_id, self.intended_parent_id, self.match_id]):
            raise ValueError(
                "At least one of surrogate_id, intended_parent_id, or match_id must be provided"
            )
        return self


class BulkTaskCreateResponse(BaseModel):
    """Response from bulk task creation."""

    success: bool
    created: list[dict]  # [{task_id, title}]
    error: str | None = None


@router.post(
    "/create-bulk-tasks",
    response_model=BulkTaskCreateResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def create_bulk_tasks(
    body: BulkTaskCreateRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.TASKS_CREATE)),
) -> BulkTaskCreateResponse:
    """
    Create multiple tasks in a single transaction (all-or-nothing).

    Uses request_id for idempotency - same request_id returns cached result.
    Tasks can be linked to case, surrogate, intended parent, or match.
    """
    from datetime import date, time
    from app.db.models import Task, AIBulkTaskRequest
    from app.db.enums import TaskType
    from app.services import activity_service

    existing_request = (
        db.query(AIBulkTaskRequest)
        .filter(
            AIBulkTaskRequest.organization_id == session.org_id,
            AIBulkTaskRequest.user_id == session.user_id,
            AIBulkTaskRequest.request_id == body.request_id,
        )
        .first()
    )
    if existing_request:
        logger.info("Returning cached result for request_id=%s", body.request_id)
        return BulkTaskCreateResponse(**existing_request.response_payload)

    # Verify entity exists and belongs to org
    entity_type = None
    entity_id = None
    match = None
    surrogate_for_access = None

    surrogate_id = body.surrogate_id
    if surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Surrogate not found")
        surrogate_for_access = surrogate
        entity_type = "case"
        entity_id = surrogate_id
    elif body.intended_parent_id:
        parent = ip_service.get_intended_parent(db, body.intended_parent_id, session.org_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Intended parent not found",
            )
        entity_type = "intended_parent"
        entity_id = body.intended_parent_id
    elif body.match_id:
        match = match_service.get_match(db, body.match_id, session.org_id)
        if not match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
        entity_type = "match"
        entity_id = body.match_id

        # Enforce access to the associated surrogate (when present)
        if match.surrogate_id:
            surrogate_for_access = surrogate_service.get_surrogate(
                db, session.org_id, match.surrogate_id
            )

    # Surrogate access enforcement (owner/role-based). For IP-only tasks, there may be no surrogate to check.
    if surrogate_for_access:
        check_surrogate_access(
            surrogate=surrogate_for_access,
            user_role=session.role,
            user_id=session.user_id,
            db=db,
            org_id=session.org_id,
        )

    # All-or-nothing: create all tasks in single transaction
    created_tasks: list[dict] = []

    try:
        for task_item in body.tasks:
            # Parse date
            due_date = None
            if task_item.due_date:
                try:
                    due_date = date.fromisoformat(task_item.due_date)
                except ValueError:
                    raise ValueError(f"Invalid date format: {task_item.due_date}")

            # Parse time
            due_time = None
            if task_item.due_time:
                try:
                    due_time = time.fromisoformat(task_item.due_time)
                except ValueError:
                    raise ValueError(f"Invalid time format: {task_item.due_time}")

            # Parse task type
            try:
                task_type = TaskType(task_item.task_type.lower())
            except ValueError:
                task_type = TaskType.OTHER

            # Resolve entity links for task - Task model only has surrogate_id and intended_parent_id
            task_surrogate_id = surrogate_id
            task_ip_id = body.intended_parent_id

            # If creating from match, link to both case and intended_parent from the match
            if body.match_id and entity_type == "match":
                task_surrogate_id = match.surrogate_id if match else None
                task_ip_id = match.intended_parent_id if match else None

            if not task_surrogate_id and not task_ip_id:
                raise ValueError("Each task must be linked to a surrogate_id or intended_parent_id")

            # Create task with appropriate entity link
            task = Task(
                organization_id=session.org_id,
                surrogate_id=task_surrogate_id,
                intended_parent_id=task_ip_id,
                title=task_item.title,
                description=task_item.description,
                task_type=task_type,
                due_date=due_date,
                due_time=due_time,
                owner_type="user",
                owner_id=session.user_id,
                created_by_user_id=session.user_id,
            )
            db.add(task)
            db.flush()  # Get task ID

            created_tasks.append(
                {
                    "task_id": str(task.id),
                    "title": task.title,
                }
            )

        # Log single case activity for bulk creation (when a case is available)
        surrogate_id_for_activity = None
        if entity_type == "match" and match and match.surrogate_id:
            surrogate_id_for_activity = match.surrogate_id
        elif entity_type == "case" and surrogate_id:
            surrogate_id_for_activity = surrogate_id

        if surrogate_id_for_activity:
            activity_service.log_activity(
                db=db,
                surrogate_id=surrogate_id_for_activity,
                organization_id=session.org_id,
                activity_type=SurrogateActivityType.TASK_CREATED,
                actor_user_id=session.user_id,
                details={
                    "description": f"Created {len(created_tasks)} tasks from AI schedule parsing",
                    "source": "ai",
                    "request_id": str(body.request_id),
                    "task_ids": [t["task_id"] for t in created_tasks],
                    "entity_type": entity_type,
                    "entity_id": str(entity_id) if entity_id else None,
                },
            )

        result = BulkTaskCreateResponse(
            success=True,
            created=created_tasks,
        )

        db.add(
            AIBulkTaskRequest(
                organization_id=session.org_id,
                user_id=session.user_id,
                request_id=body.request_id,
                response_payload=result.model_dump(),
            )
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_request = (
                db.query(AIBulkTaskRequest)
                .filter(
                    AIBulkTaskRequest.organization_id == session.org_id,
                    AIBulkTaskRequest.user_id == session.user_id,
                    AIBulkTaskRequest.request_id == body.request_id,
                )
                .first()
            )
            if existing_request:
                return BulkTaskCreateResponse(**existing_request.response_payload)
            raise

        logger.info(
            f"Created {len(created_tasks)} tasks for {entity_type} {entity_id} "
            f"by user {session.user_id}"
        )

        return result

    except ValueError as e:
        db.rollback()
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error=str(e),
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk task creation failed: {e}")
        return BulkTaskCreateResponse(
            success=False,
            created=[],
            error="Failed to create tasks",
        )
