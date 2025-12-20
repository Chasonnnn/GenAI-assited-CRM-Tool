"""AI Chat service.

Handles AI conversations with context injection and action parsing.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

import nh3
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AIConversation, AIMessage, AIActionApproval, AIEntitySummary, 
    AIUsageLog, Case, EntityNote, Task, UserIntegration
)
from app.services.ai_provider import ChatMessage, ChatResponse
from app.services import ai_settings_service
from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_text

logger = logging.getLogger(__name__)


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are an AI assistant for a surrogacy agency CRM called CareFlow. You help staff manage cases efficiently.

## Available Actions
When you want to propose an action, output it as JSON in an <action> tag. You can propose multiple actions.

Action types:
- send_email: Draft an email (requires user's Gmail to be connected)
- create_task: Create a follow-up task
- add_note: Add a note to the case
- update_status: Suggest a status change

Example action format:
<action>
{"type": "send_email", "to": "email@example.com", "subject": "Following up", "body": "Hi..."}
</action>

<action>
{"type": "create_task", "title": "Follow up with Sarah", "due_date": "2024-12-20", "description": "Check on application status"}
</action>

## Guidelines
- Be concise and professional
- Always propose actions for approval, never auto-execute
- Don't provide legal or medical advice
- Keep responses focused on the current case context
"""


def _build_dynamic_context(
    case: Case, 
    notes: list[EntityNote], 
    tasks: list[Task], 
    user_integrations: list[str],
    anonymize: bool = False,
    pii_mapping: PIIMapping | None = None,
) -> str:
    """Build dynamic context string for the current case.
    
    If anonymize=True and pii_mapping is provided, PII will be replaced with placeholders.
    """
    # Get values, anonymize if needed
    # Case uses full_name, not first_name/last_name
    full_name = case.full_name or ""
    email = case.email or "N/A"
    phone = case.phone or "N/A"
    
    if anonymize and pii_mapping:
        if full_name:
            full_name = pii_mapping.add_name(full_name)
        if email != "N/A":
            email = pii_mapping.add_email(email)
        if phone != "N/A":
            phone = pii_mapping.add_phone(phone)
    
    status_value = case.status_label or "N/A"
    source_value = case.source if isinstance(case.source, str) else case.source.value
    
    lines = [
        f"## Current Case Context",
        f"- Case #: {case.case_number}",
        f"- Name: {full_name}",
        f"- Status: {status_value}",
        f"- Email: {email}",
        f"- Phone: {phone}",
        f"- State: {case.state or 'N/A'}",
    ]
    
    if case.date_of_birth:
        lines.append(f"- Date of Birth: {case.date_of_birth}")
    if case.source:
        lines.append(f"- Source: {source_value}")
    if case.last_contacted_at:
        lines.append(f"- Last Contacted: {case.last_contacted_at.strftime('%Y-%m-%d')} via {case.last_contact_method or 'unknown'}")
    
    # Add notes (plain text, limited)
    if notes:
        lines.append("\n## Recent Notes")
        # Build known names list for anonymization (use full_name)
        known_names = []
        if case.full_name:
            known_names.append(case.full_name)
            # Split into first/last for matching
            parts = case.full_name.split()
            known_names.extend(parts)
        
        for note in notes[:5]:  # Limit to 5 notes
            plain_text = nh3.clean(note.content, tags=set())  # Strip HTML
            truncated = plain_text[:200] + "..." if len(plain_text) > 200 else plain_text
            
            # Anonymize note content if enabled
            if anonymize and pii_mapping:
                truncated = anonymize_text(truncated, pii_mapping, known_names)
            
            lines.append(f"- [{note.created_at.strftime('%Y-%m-%d')}] {truncated}")
    
    # Add tasks (Task uses is_completed, not status)
    pending_tasks = [t for t in tasks if not t.is_completed]
    if pending_tasks:
        lines.append("\n## Pending Tasks")
        for task in pending_tasks[:3]:
            due = f" (due {task.due_date.strftime('%Y-%m-%d')})" if task.due_date else ""
            lines.append(f"- {task.title}{due}")
    
    # Add user integrations
    lines.append("\n## Your Connected Integrations")
    if "gmail" in user_integrations:
        lines.append("- ✓ Gmail (can send emails)")
    else:
        lines.append("- ✗ Gmail not connected (can only draft emails)")
    if "zoom" in user_integrations:
        lines.append("- ✓ Zoom (can create meetings)")
    
    return "\n".join(lines)


def _parse_actions(content: str) -> list[dict[str, Any]]:
    """Extract action JSON from <action> tags in AI response."""
    actions = []
    pattern = r'<action>\s*(.*?)\s*</action>'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            action = json.loads(match)
            if isinstance(action, dict) and "type" in action:
                actions.append(action)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse action JSON: {match}")
    
    return actions


def _clean_content(content: str) -> str:
    """Remove action tags from content for display."""
    return re.sub(r'<action>.*?</action>', '', content, flags=re.DOTALL).strip()


# ============================================================================
# Core Chat Functions
# ============================================================================

def get_or_create_conversation(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> AIConversation:
    """Get or create a conversation for a user and entity."""
    conversation = db.query(AIConversation).filter(
        AIConversation.organization_id == organization_id,
        AIConversation.user_id == user_id,
        AIConversation.entity_type == entity_type,
        AIConversation.entity_id == entity_id,
    ).first()
    
    if conversation:
        return conversation
    
    conversation = AIConversation(
        organization_id=organization_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_history(
    db: Session,
    conversation_id: uuid.UUID,
    limit: int = 10,
) -> list[AIMessage]:
    """Get recent messages in a conversation."""
    messages = db.query(AIMessage).filter(
        AIMessage.conversation_id == conversation_id
    ).order_by(AIMessage.created_at.desc()).limit(limit).all()
    
    messages.reverse()  # Oldest first
    return messages


def get_case_context(
    db: Session,
    case_id: uuid.UUID,
    notes_limit: int = 5,
) -> tuple[Case | None, list[EntityNote], list[Task]]:
    """Load case with notes and tasks for context."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return None, [], []
    
    # Get notes via EntityNote (entity_type='case')
    notes = db.query(EntityNote).filter(
        EntityNote.entity_type == "case",
        EntityNote.entity_id == case_id
    ).order_by(EntityNote.created_at.desc()).limit(notes_limit).all()
    
    # Get tasks (Task uses case_id, not entity_type/entity_id)
    tasks = db.query(Task).filter(
        Task.case_id == case_id
    ).all()
    
    return case, notes, tasks


def get_user_integrations(db: Session, user_id: uuid.UUID) -> list[str]:
    """Get list of connected integration types for a user."""
    integrations = db.query(UserIntegration.integration_type).filter(
        UserIntegration.user_id == user_id
    ).all()
    return [i[0] for i in integrations]


def chat(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    message: str,
    user_integrations: list[str] | None = None,
) -> dict[str, Any]:
    """Process a chat message and return AI response.
    
    Returns:
        {
            "content": "AI response text",
            "proposed_actions": [...],  # Optional
            "tokens_used": {...},
        }
    """
    if user_integrations is None:
        user_integrations = get_user_integrations(db, user_id)
    
    # Get AI provider
    provider = ai_settings_service.get_ai_provider_for_org(db, organization_id)
    if not provider:
        return {
            "content": "AI is not configured for this organization. Please ask a manager to enable AI in settings.",
            "proposed_actions": [],
            "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
        }
    
    # Get settings for limits and privacy
    ai_settings = ai_settings_service.get_ai_settings(db, organization_id)
    notes_limit = ai_settings.context_notes_limit or 5
    history_limit = ai_settings.conversation_history_limit or 10
    should_anonymize = ai_settings.anonymize_pii
    
    # Create PII mapping for anonymization/rehydration
    pii_mapping = PIIMapping() if should_anonymize else None
    
    # Get or create conversation
    conversation = get_or_create_conversation(
        db, organization_id, user_id, entity_type, entity_id
    )
    
    # Load context based on entity type
    case = None
    if entity_type == "case":
        case, notes, tasks = get_case_context(db, entity_id, notes_limit)
        if not case:
            return {
                "content": "Case not found.",
                "proposed_actions": [],
                "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
            }
        dynamic_context = _build_dynamic_context(
            case, notes, tasks, user_integrations,
            anonymize=should_anonymize,
            pii_mapping=pii_mapping,
        )
    else:
        dynamic_context = "No context available for this entity type."
    
    # Anonymize user message if enabled
    anonymized_message = message
    if should_anonymize and pii_mapping and case:
        known_names = []
        if case.full_name:
            known_names.append(case.full_name)
            known_names.extend(case.full_name.split())
        anonymized_message = anonymize_text(message, pii_mapping, known_names)
    
    # Build messages for AI
    history = get_conversation_history(db, conversation.id, history_limit)
    
    ai_messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT + "\n\n" + dynamic_context),
    ]
    
    # Add conversation history (anonymize if PII anonymization is enabled)
    for msg in history:
        content = msg.content
        if should_anonymize and pii_mapping and case:
            known_names = []
            if case.full_name:
                known_names.append(case.full_name)
                known_names.extend(case.full_name.split())
            content = anonymize_text(content, pii_mapping, known_names)
        ai_messages.append(ChatMessage(role=msg.role, content=content))
    
    # Add current user message (anonymized if enabled)
    ai_messages.append(ChatMessage(role="user", content=anonymized_message))
    
    # Call AI provider (async, need to run in event loop)
    try:
        response: ChatResponse = asyncio.run(provider.chat(ai_messages))
    except Exception as e:
        logger.exception(f"AI provider error: {e}")
        return {
            "content": f"AI error: {str(e)}",
            "proposed_actions": [],
            "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
        }
    
    # Parse actions from response
    proposed_actions = _parse_actions(response.content)
    clean_content = _clean_content(response.content)
    
    # Rehydrate response with real PII values
    if should_anonymize and pii_mapping:
        clean_content = rehydrate_text(clean_content, pii_mapping)
        # Also rehydrate action payloads
        for action in proposed_actions:
            for key, value in action.items():
                if isinstance(value, str):
                    action[key] = rehydrate_text(value, pii_mapping)
    
    # Save user message
    user_message = AIMessage(
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(user_message)
    
    # Save assistant message
    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=clean_content,
        proposed_actions=proposed_actions if proposed_actions else None,
    )
    db.add(assistant_message)
    db.flush()  # Get assistant_message.id
    
    # Create action approvals for each proposed action
    approval_responses = []
    if proposed_actions:
        for i, action in enumerate(proposed_actions):
            approval = AIActionApproval(
                message_id=assistant_message.id,
                action_index=i,
                action_type=action.get("type", "unknown"),
                action_payload=action,
                status="pending",
            )
            db.add(approval)
            db.flush()  # Get approval.id
            
            # Build response matching frontend ProposedAction type
            approval_responses.append({
                "approval_id": str(approval.id),
                "action_type": approval.action_type,
                "action_data": approval.action_payload,  # Map to frontend field name
                "status": approval.status,
            })
    
    # Log usage
    usage_log = AIUsageLog(
        organization_id=organization_id,
        user_id=user_id,
        conversation_id=conversation.id,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
        estimated_cost_usd=response.estimated_cost_usd,
    )
    db.add(usage_log)
    
    # Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "content": clean_content,
        "proposed_actions": approval_responses,  # Now includes approval_id
        "tokens_used": {
            "prompt": response.prompt_tokens,
            "completion": response.completion_tokens,
            "total": response.total_tokens,
            "estimated_cost_usd": str(response.estimated_cost_usd),
        },
    }


def get_user_conversations(
    db: Session,
    user_id: uuid.UUID,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[AIConversation]:
    """Get conversations for a user."""
    query = db.query(AIConversation).filter(AIConversation.user_id == user_id)
    
    if entity_type:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)
    
    return query.order_by(AIConversation.updated_at.desc()).all()


def get_conversation_messages(
    db: Session,
    conversation_id: uuid.UUID,
) -> list[AIMessage]:
    """Get all messages in a conversation with action approvals."""
    return db.query(AIMessage).options(
        joinedload(AIMessage.action_approvals)
    ).filter(
        AIMessage.conversation_id == conversation_id
    ).order_by(AIMessage.created_at).all()
