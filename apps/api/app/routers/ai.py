"""AI Assistant API router.

Endpoints for AI settings, chat, and actions.
"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_session, require_roles
from app.db.enums import Role
from app.db.models import Case, UserIntegration, AIConversation
from app.schemas.auth import UserSession
from app.services import ai_settings_service, ai_chat_service

router = APIRouter(prefix="/ai", tags=["AI"])


# ============================================================================
# Constants
# ============================================================================

CONSENT_TEXT = """
By enabling the AI Assistant, you acknowledge that:

1. Case data (names, contact info, notes) will be sent to a third-party AI provider 
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

class AISettingsResponse(BaseModel):
    """AI settings for display (with masked key)."""
    is_enabled: bool
    provider: str
    model: str | None
    api_key_masked: str | None
    context_notes_limit: int
    conversation_history_limit: int
    # Privacy fields
    anonymize_pii: bool
    consent_accepted_at: str | None
    consent_required: bool


class AISettingsUpdate(BaseModel):
    """Update AI settings."""
    is_enabled: bool | None = None
    provider: str | None = Field(None, pattern="^(openai|gemini)$")
    api_key: str | None = None
    model: str | None = None
    context_notes_limit: int | None = Field(None, ge=1, le=20)
    conversation_history_limit: int | None = Field(None, ge=5, le=50)
    anonymize_pii: bool | None = None


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
    """Send a chat message."""
    entity_type: str = Field(..., pattern="^(case)$")  # Only case for now
    entity_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=10000)


class ChatResponseModel(BaseModel):
    """Chat response."""
    content: str
    proposed_actions: list[dict[str, Any]]
    tokens_used: dict[str, Any]


# ============================================================================
# Settings Endpoints (Manager Only)
# ============================================================================

@router.get("/settings", response_model=AISettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> AISettingsResponse:
    """Get AI settings for the organization."""
    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id)
    
    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=settings.model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat() if settings.consent_accepted_at else None,
        consent_required=ai_settings_service.is_consent_required(settings),
    )


@router.patch("/settings", response_model=AISettingsResponse)
def update_settings(
    update: AISettingsUpdate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> AISettingsResponse:
    """Update AI settings for the organization."""
    settings = ai_settings_service.update_ai_settings(
        db,
        session.org_id,
        is_enabled=update.is_enabled,
        provider=update.provider,
        api_key=update.api_key,
        model=update.model,
        context_notes_limit=update.context_notes_limit,
        conversation_history_limit=update.conversation_history_limit,
        anonymize_pii=update.anonymize_pii,
    )
    
    return AISettingsResponse(
        is_enabled=settings.is_enabled,
        provider=settings.provider,
        model=settings.model,
        api_key_masked=ai_settings_service.mask_api_key(settings.api_key_encrypted),
        context_notes_limit=settings.context_notes_limit or 5,
        conversation_history_limit=settings.conversation_history_limit or 10,
        anonymize_pii=settings.anonymize_pii,
        consent_accepted_at=settings.consent_accepted_at.isoformat() if settings.consent_accepted_at else None,
        consent_required=ai_settings_service.is_consent_required(settings),
    )


@router.post("/settings/test", response_model=TestKeyResponse)
async def test_api_key(
    request: TestKeyRequest,
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> ConsentResponse:
    """Get consent text and status."""
    settings = ai_settings_service.get_or_create_ai_settings(db, session.org_id)
    
    return ConsentResponse(
        consent_text=CONSENT_TEXT,
        consent_accepted_at=settings.consent_accepted_at.isoformat() if settings.consent_accepted_at else None,
        consent_accepted_by=str(settings.consent_accepted_by) if settings.consent_accepted_by else None,
    )


@router.post("/consent/accept")
def accept_consent(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> dict[str, Any]:
    """Accept the AI data processing consent."""
    settings = ai_settings_service.accept_consent(db, session.org_id, session.user_id)
    
    return {
        "accepted": True,
        "accepted_at": settings.consent_accepted_at.isoformat() if settings.consent_accepted_at else None,
        "accepted_by": str(settings.consent_accepted_by) if settings.consent_accepted_by else None,
    }


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.post("/chat", response_model=ChatResponseModel)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> ChatResponseModel:
    """Send a message to the AI assistant."""
    # Check consent before allowing chat
    settings = ai_settings_service.get_ai_settings(db, session.org_id)
    if settings and ai_settings_service.is_consent_required(settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI consent not accepted. A manager must accept the data processing consent before using AI.",
        )
    
    # Check if user has access to the entity
    if request.entity_type == "case":
        case = db.query(Case).filter(
            Case.id == request.entity_id,
            Case.organization_id == session.org_id
        ).first()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found",
            )
    
    # Get user's connected integrations
    integrations = db.query(UserIntegration.integration_type).filter(
        UserIntegration.user_id == session.user_id
    ).all()
    user_integrations = [i[0] for i in integrations]
    
    # Process chat
    response = ai_chat_service.chat(
        db,
        session.org_id,
        session.user_id,
        request.entity_type,
        request.entity_id,
        request.message,
        user_integrations,
    )
    
    return ChatResponseModel(
        content=response["content"],
        proposed_actions=response["proposed_actions"],
        tokens_used=response["tokens_used"],
    )


@router.get("/conversations/{entity_type}/{entity_id}")
def get_conversation(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Get conversation history for an entity."""
    conversations = ai_chat_service.get_user_conversations(
        db, session.user_id, entity_type, entity_id
    )
    
    if not conversations:
        return {"messages": []}
    
    # Get the most recent conversation
    conversation = conversations[0]
    messages = ai_chat_service.get_conversation_messages(db, conversation.id)
    
    return {
        "conversation_id": str(conversation.id),
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "proposed_actions": msg.proposed_actions,
                "created_at": msg.created_at.isoformat(),
                "action_approvals": [
                    {
                        "id": str(a.id),
                        "action_index": a.action_index,
                        "action_type": a.action_type,
                        "status": a.status,
                    }
                    for a in msg.action_approvals
                ] if msg.action_approvals else None,
            }
            for msg in messages
        ],
    }


@router.get("/conversations/{entity_type}/{entity_id}/all")
def get_all_conversations(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
) -> dict[str, Any]:
    """Get all users' conversations for an entity (developer only, for audit)."""
    conversations = db.query(AIConversation).filter(
        AIConversation.organization_id == session.org_id,
        AIConversation.entity_type == entity_type,
        AIConversation.entity_id == entity_id
    ).order_by(AIConversation.updated_at.desc()).all()
    
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


@router.post("/actions/{approval_id}/approve", response_model=ActionApprovalResponse)
def approve_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> ActionApprovalResponse:
    """Approve and execute a proposed action."""
    from app.db.models import AIActionApproval, AIMessage, AIConversation
    from app.services.ai_action_executor import execute_action
    
    # Get the approval with related data
    approval = db.query(AIActionApproval).filter(AIActionApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Get conversation to verify org access
    message = db.query(AIMessage).filter(AIMessage.id == approval.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    conversation = db.query(AIConversation).filter(AIConversation.id == message.conversation_id).first()
    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Action already processed (status: {approval.status})"
        )
    
    # Execute the action
    result = execute_action(
        db=db,
        approval=approval,
        user_id=session.user_id,
        org_id=session.org_id,
        entity_id=conversation.entity_id,
    )
    
    db.commit()
    
    return ActionApprovalResponse(
        success=result.get("success", False),
        action_type=approval.action_type,
        status=approval.status,
        result=result if result.get("success") else None,
        error=result.get("error") if not result.get("success") else None,
    )


@router.post("/actions/{approval_id}/reject")
def reject_action(
    approval_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Reject a proposed action."""
    from app.db.models import AIActionApproval, AIMessage, AIConversation
    
    # Get the approval with related data
    approval = db.query(AIActionApproval).filter(AIActionApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # Get conversation to verify org access
    message = db.query(AIMessage).filter(AIMessage.id == approval.message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    conversation = db.query(AIConversation).filter(AIConversation.id == message.conversation_id).first()
    if not conversation or conversation.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check status
    if approval.status != "pending":
        raise HTTPException(
            status_code=400, 
            detail=f"Action already processed (status: {approval.status})"
        )
    
    # Mark as rejected
    approval.status = "rejected"
    approval.executed_at = datetime.utcnow()
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
    session: UserSession = Depends(get_current_session),
) -> dict[str, Any]:
    """Get all pending actions for the current user."""
    from app.db.models import AIActionApproval, AIMessage, AIConversation
    
    query = db.query(AIActionApproval).join(
        AIMessage, AIActionApproval.message_id == AIMessage.id
    ).join(
        AIConversation, AIMessage.conversation_id == AIConversation.id
    ).filter(
        AIConversation.user_id == session.user_id,
        AIConversation.organization_id == session.org_id,
        AIActionApproval.status == "pending"
    )
    
    if entity_type:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)
    
    approvals = query.order_by(AIActionApproval.created_at.desc()).all()
    
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
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> dict[str, Any]:
    """Get organization usage summary."""
    from app.services import ai_usage_service
    
    return ai_usage_service.get_org_usage_summary(db, session.org_id, days)


@router.get("/usage/by-model")
def get_usage_by_model(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> dict[str, Any]:
    """Get usage breakdown by AI model."""
    from app.services import ai_usage_service
    
    return {"models": ai_usage_service.get_usage_by_model(db, session.org_id, days)}


@router.get("/usage/daily")
def get_daily_usage(
    days: int = 30,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
) -> dict[str, Any]:
    """Get daily usage breakdown."""
    from app.services import ai_usage_service
    
    return {"daily": ai_usage_service.get_daily_usage(db, session.org_id, days)}


@router.get("/usage/top-users")
def get_top_users(
    days: int = 30,
    limit: int = 10,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.MANAGER, Role.DEVELOPER])),
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
