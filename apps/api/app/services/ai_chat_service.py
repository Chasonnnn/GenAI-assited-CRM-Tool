"""AI Chat service.

Handles AI conversations with context injection and action parsing.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone, date

import nh3
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    AIConversation,
    AIMessage,
    AIActionApproval,
    AIUsageLog,
    AIEntitySummary,
    Surrogate,
    EntityNote,
    Task,
    UserIntegration,
)
from app.db.enums import TaskType
from app.services.ai_provider import ChatMessage, ChatResponse
from app.services import ai_settings_service
from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_text
from app.types import JsonObject

logger = logging.getLogger(__name__)

LEGACY_SURROGATE_ENTITY_TYPE = "case"
SURROGATE_ENTITY_TYPE = "surrogate"


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are an AI assistant for a surrogacy agency CRM called CareFlow. You help staff manage surrogates efficiently.

## Available Actions
When you want to propose an action, output it as JSON in an <action> tag. You can propose multiple actions.

Action types:
- send_email: Draft an email (requires user's Gmail to be connected)
- create_task: Create a follow-up task
- add_note: Add a note to the surrogate
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
- Keep responses focused on the current surrogate context
"""

GLOBAL_SYSTEM_PROMPT = """You are an AI assistant for a surrogacy agency CRM called CareFlow. You help staff manage surrogates efficiently.

You are in GLOBAL mode - no specific surrogate is selected. You can:
- Answer general questions about workflows and processes
- Help draft messages that the user can copy/paste
- Suggest next steps based on information the user provides
- Help parse emails or notes the user pastes to extract relevant information
- Answer questions about team performance and conversion metrics (if data is provided below)

If the user pastes an email or describes a situation, you can help:
1. Identify if it relates to an existing surrogate (ask for the person's name or surrogate number)
2. Suggest what tasks should be created
3. Draft responses
4. Recommend next steps

When answering performance questions:
- Identify top performers (high conversion rates) and those who may need support (low conversion rates)
- Consider both volume (total surrogates) and efficiency (conversion rate)
- Application submitted count represents successful outcomes; Lost represents unsuccessful outcomes
- Conversion rate = (application_submitted / total surrogates) * 100

## Guidelines
- Be concise and professional
- If you need a specific surrogate context to take action, ask the user to open that surrogate
- Don't provide legal or medical advice
- You cannot execute actions without surrogate context
"""

TASK_SYSTEM_PROMPT = """You are an AI assistant for a surrogacy agency CRM called CareFlow. You help staff manage tasks efficiently.

You are viewing a specific TASK. You can:
- Answer questions about this task
- Suggest updates or notes to add
- Help break down the task into sub-tasks
- Parse schedules provided by the user into actionable tasks

## Schedule Parsing

When a user provides a medication schedule, exam schedule, or appointment list:
1. Parse each item for: date, time (if specified), and description
2. For each item, propose a `create_task` action with:
   - title: Brief description (e.g., "Take Prenatal Vitamins")
   - due_date: Parsed date in YYYY-MM-DD format
   - due_time: Parsed time in HH:MM format (24h), or null if not specified
   - description: Full details from the schedule
3. Ask user to confirm before creating tasks
4. Handle recurring items by creating individual tasks for a reasonable period (up to 7 days for daily items)

Example input: "Prenatal vitamins daily at 9am for the next 7 days"
→ Propose 7 individual create_task actions, one for each day

Example action:
<action>
{"type": "create_task", "title": "Take Prenatal Vitamins", "due_date": "2024-12-21", "due_time": "09:00", "description": "Daily prenatal vitamins"}
</action>

## Guidelines
- Be concise and professional
- Always propose actions for approval, never auto-execute
- Don't provide legal or medical advice
- Keep responses focused on the current task context
"""

ENTITY_SUMMARY_TTL_MINUTES = 10


def _build_performance_context(
    db: Session,
    organization_id: uuid.UUID,
) -> str:
    """Build performance data context for global mode."""
    from app.services import analytics_service

    try:
        # Get performance data (last 90 days by default)
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        data = analytics_service.get_cached_performance_by_user(
            db=db,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            mode="cohort",
        )

        if not data or not data.get("data"):
            return "\n## Team Performance\nNo performance data available."

        lines = [
            "\n## Team Performance (Last 90 Days)",
            "Mode: Cohort (surrogates created in the period)",
            "",
            "| Team Member | Surrogates | Contacted | Qualified | Matched | Application Submitted | Lost | Conv. Rate |",
            "|-------------|-------|-----------|-----------|---------|---------|------|------------|",
        ]

        for user in data["data"]:
            if user["total_surrogates"] > 0:
                lines.append(
                    f"| {user['user_name']} | {user['total_surrogates']} | {user['contacted']} | "
                    f"{user['qualified']} | {user['matched']} | {user['application_submitted']} | "
                    f"{user['lost']} | {user['conversion_rate']}% |"
                )

        # Add unassigned if any
        unassigned = data.get("unassigned", {})
        if unassigned.get("total_surrogates", 0) > 0:
            lines.append(
                f"| Unassigned | {unassigned['total_surrogates']} | {unassigned['contacted']} | "
                f"{unassigned['qualified']} | {unassigned['matched']} | {unassigned['application_submitted']} | "
                f"{unassigned['lost']} | - |"
            )

        # Add summary
        total_surrogates = sum(u["total_surrogates"] for u in data["data"])
        total_submitted = sum(u["application_submitted"] for u in data["data"])
        avg_conversion = (
            round(total_submitted / total_surrogates * 100, 1) if total_surrogates > 0 else 0
        )

        lines.append("")
        lines.append(
            f"**Summary**: {total_surrogates} total surrogates, {total_submitted} submitted, {avg_conversion}% team avg conversion rate"
        )

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to build performance context: {e}")
        return "\n## Team Performance\nUnable to load performance data."


def _should_fetch_performance(message: str) -> bool:
    """Return True when the user asks about team performance metrics."""
    if not message:
        return False
    text = message.lower()
    keywords = (
        "performance",
        "conversion",
        "conversion rate",
        "convert",
        "application_submitted",
        "matched",
        "lost",
        "assigned",
        "surrogates",
        "team",
        "top performer",
        "needs support",
        "underperform",
    )
    return any(term in text for term in keywords)


def _build_dynamic_context(
    surrogate: Surrogate,
    notes: list[EntityNote],
    tasks: list[Task],
    user_integrations: list[str],
    anonymize: bool = False,
    pii_mapping: PIIMapping | None = None,
    include_integrations: bool = True,
) -> str:
    """Build dynamic context string for the current surrogate.

    If anonymize=True and pii_mapping is provided, PII will be replaced with placeholders.
    """
    # Get values, anonymize if needed
    # Surrogate uses full_name, not first_name/last_name
    full_name = surrogate.full_name or ""
    email = surrogate.email or "N/A"
    phone = surrogate.phone or "N/A"

    if anonymize and pii_mapping:
        if full_name:
            full_name = pii_mapping.add_name(full_name)
        if email != "N/A":
            email = pii_mapping.add_email(email)
        if phone != "N/A":
            phone = pii_mapping.add_phone(phone)

    status_value = surrogate.status_label or "N/A"
    source_value = surrogate.source if isinstance(surrogate.source, str) else surrogate.source.value

    lines = [
        "## Current Surrogate Context",
        f"- Surrogate #: {surrogate.surrogate_number}",
        f"- Name: {full_name}",
        f"- Status: {status_value}",
        f"- Email: {email}",
        f"- Phone: {phone}",
        f"- State: {surrogate.state or 'N/A'}",
    ]

    if surrogate.date_of_birth:
        lines.append(f"- Date of Birth: {surrogate.date_of_birth}")
    if surrogate.source:
        lines.append(f"- Source: {source_value}")
    if surrogate.last_contacted_at:
        lines.append(
            f"- Last Contacted: {surrogate.last_contacted_at.strftime('%Y-%m-%d')} via {surrogate.last_contact_method or 'unknown'}"
        )

    # Add notes (plain text, limited)
    if notes:
        lines.append("\n## Recent Notes")
        # Build known names list for anonymization (use full_name)
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            # Split into first/last for matching
            parts = surrogate.full_name.split()
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
    if include_integrations:
        lines.append("\n## Your Connected Integrations")
        if "gmail" in user_integrations:
            lines.append("- ✓ Gmail (can send emails)")
        else:
            lines.append("- ✗ Gmail not connected (can only draft emails)")
        if "zoom" in user_integrations:
            lines.append("- ✓ Zoom (can create meetings)")

    return "\n".join(lines)


def _build_integrations_context(user_integrations: list[str]) -> str:
    lines = ["## Your Connected Integrations"]
    if "gmail" in user_integrations:
        lines.append("- ✓ Gmail (can send emails)")
    else:
        lines.append("- ✗ Gmail not connected (can only draft emails)")
    if "zoom" in user_integrations:
        lines.append("- ✓ Zoom (can create meetings)")
    return "\n".join(lines)


def _get_or_update_entity_summary(
    db: Session,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    summary_text: str,
) -> AIEntitySummary:
    now = datetime.now(timezone.utc)
    summary = (
        db.query(AIEntitySummary)
        .filter(
            AIEntitySummary.organization_id == organization_id,
            AIEntitySummary.entity_type == entity_type,
            AIEntitySummary.entity_id == entity_id,
        )
        .first()
    )
    if summary:
        summary.summary_text = summary_text
        summary.updated_at = now
        return summary

    summary = AIEntitySummary(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        summary_text=summary_text,
        notes_plain_text=None,
        updated_at=now,
    )
    db.add(summary)
    return summary


def _get_cached_entity_summary(
    db: Session,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> str | None:
    summary = (
        db.query(AIEntitySummary)
        .filter(
            AIEntitySummary.organization_id == organization_id,
            AIEntitySummary.entity_type == entity_type,
            AIEntitySummary.entity_id == entity_id,
        )
        .first()
    )
    if not summary:
        return None
    if summary.updated_at < datetime.now(timezone.utc) - timedelta(
        minutes=ENTITY_SUMMARY_TTL_MINUTES
    ):
        return None
    return summary.summary_text


def _parse_actions(content: str) -> list[JsonObject]:
    """Extract action JSON from <action> tags in AI response."""
    actions = []
    pattern = r"<action>\s*(.*?)\s*</action>"
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        try:
            action = json.loads(match)
            if isinstance(action, dict) and "type" in action:
                actions.append(action)
        except json.JSONDecodeError:
            logger.warning("Failed to parse action JSON from AI response")

    return actions


def _clean_content(content: str) -> str:
    """Remove action tags from content for display."""
    return re.sub(r"<action>.*?</action>", "", content, flags=re.DOTALL).strip()


def _normalize_entity_type(entity_type: str) -> str:
    if entity_type == LEGACY_SURROGATE_ENTITY_TYPE:
        return SURROGATE_ENTITY_TYPE
    return entity_type


def _resolve_entity_types(entity_type: str) -> list[str]:
    normalized = _normalize_entity_type(entity_type)
    if normalized == SURROGATE_ENTITY_TYPE:
        return [SURROGATE_ENTITY_TYPE, LEGACY_SURROGATE_ENTITY_TYPE]
    return [normalized]


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
    normalized_entity_type = _normalize_entity_type(entity_type)
    entity_types = _resolve_entity_types(entity_type)
    conversation = (
        db.query(AIConversation)
        .filter(
            AIConversation.organization_id == organization_id,
            AIConversation.user_id == user_id,
            AIConversation.entity_type.in_(entity_types),
            AIConversation.entity_id == entity_id,
        )
        .first()
    )

    if conversation:
        return conversation

    conversation = AIConversation(
        organization_id=organization_id,
        user_id=user_id,
        entity_type=normalized_entity_type,
        entity_id=entity_id,
    )
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        conversation = (
            db.query(AIConversation)
            .filter(
                AIConversation.organization_id == organization_id,
                AIConversation.user_id == user_id,
                AIConversation.entity_type == entity_type,
                AIConversation.entity_id == entity_id,
            )
            .first()
        )
        if conversation:
            return conversation
        raise
    db.refresh(conversation)
    return conversation


def get_conversation_history(
    db: Session,
    conversation_id: uuid.UUID,
    limit: int = 10,
) -> list[AIMessage]:
    """Get recent messages in a conversation."""
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    messages.reverse()  # Oldest first
    return messages


def get_surrogate_context(
    db: Session,
    surrogate_id: uuid.UUID,
    organization_id: uuid.UUID,
    notes_limit: int = 5,
) -> tuple[Surrogate | None, list[EntityNote], list[Task]]:
    """Load surrogate with notes and tasks for context."""
    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.id == surrogate_id,
            Surrogate.organization_id == organization_id,
        )
        .first()
    )
    if not surrogate:
        return None, [], []

    # Get notes via EntityNote (entity_type='surrogate')
    notes = (
        db.query(EntityNote)
        .filter(
            EntityNote.entity_type == "surrogate",
            EntityNote.entity_id == surrogate_id,
            EntityNote.organization_id == organization_id,
        )
        .order_by(EntityNote.created_at.desc())
        .limit(notes_limit)
        .all()
    )

    # Get tasks (Task uses surrogate_id, not entity_type/entity_id)
    tasks = (
        db.query(Task)
        .filter(
            Task.surrogate_id == surrogate_id,
            Task.organization_id == organization_id,
            Task.task_type != TaskType.WORKFLOW_APPROVAL.value,
        )
        .all()
    )

    return surrogate, notes, tasks


def get_task_context(
    db: Session,
    task_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> tuple[Task | None, Surrogate | None]:
    """Load task with optional related surrogate for context."""
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
        .options(joinedload(Task.surrogate))
        .first()
    )

    if not task:
        return None, None

    return task, task.surrogate


def _build_task_context(
    task: Task,
    surrogate: Surrogate | None,
    user_integrations: list[str],
) -> str:
    """Build dynamic context string for the current task."""
    lines = [
        "## Current Task Context",
        f"- Title: {task.title}",
        f"- Type: {task.task_type}",
        f"- Status: {'Completed' if task.is_completed else 'Open'}",
    ]

    if task.description:
        desc = task.description[:300] + "..." if len(task.description) > 300 else task.description
        lines.append(f"- Description: {desc}")
    if task.due_date:
        lines.append(f"- Due Date: {task.due_date}")
    if task.due_time:
        lines.append(f"- Due Time: {task.due_time}")
    if task.priority:
        lines.append(f"- Priority: {task.priority}")

    if surrogate:
        lines.append("\n## Related Surrogate")
        lines.append(f"- Surrogate #: {surrogate.surrogate_number}")
        lines.append(f"- Name: {surrogate.full_name or 'N/A'}")
        lines.append(f"- Status: {surrogate.status_label or 'N/A'}")

    # Add user integrations
    lines.append("\n## Your Connected Integrations")
    if "gmail" in user_integrations:
        lines.append("- ✓ Gmail (can send emails)")
    else:
        lines.append("- ✗ Gmail not connected (can only draft emails)")
    if "zoom" in user_integrations:
        lines.append("- ✓ Zoom (can create meetings)")

    return "\n".join(lines)


def get_user_integrations(db: Session, user_id: uuid.UUID) -> list[str]:
    """Get list of connected integration types for a user."""
    integrations = (
        db.query(UserIntegration.integration_type).filter(UserIntegration.user_id == user_id).all()
    )
    return [i[0] for i in integrations]


async def chat_async(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    message: str,
    user_integrations: list[str] | None = None,
) -> JsonObject:
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
            "content": "AI is not configured for this organization. Please ask an admin to enable AI in settings.",
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

    normalized_entity_type = _normalize_entity_type(entity_type)

    # Get or create conversation
    conversation = get_or_create_conversation(
        db, organization_id, user_id, normalized_entity_type, entity_id
    )

    # Load context based on entity type
    surrogate = None
    system_prompt = SYSTEM_PROMPT
    dynamic_context = ""

    if normalized_entity_type == SURROGATE_ENTITY_TYPE:
        cached_summary = _get_cached_entity_summary(
            db, organization_id, SURROGATE_ENTITY_TYPE, entity_id
        )
        if cached_summary:
            surrogate = (
                db.query(Surrogate)
                .filter(
                    Surrogate.id == entity_id,
                    Surrogate.organization_id == organization_id,
                )
                .first()
            )
            if not surrogate:
                return {
                    "content": "Surrogate not found.",
                    "proposed_actions": [],
                    "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
                }
            summary_text = cached_summary
        else:
            surrogate, notes, tasks = get_surrogate_context(
                db=db,
                surrogate_id=entity_id,
                organization_id=organization_id,
                notes_limit=notes_limit,
            )
            if not surrogate:
                return {
                    "content": "Surrogate not found.",
                    "proposed_actions": [],
                    "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
                }
            summary_text = _build_dynamic_context(
                surrogate,
                notes,
                tasks,
                user_integrations,
                anonymize=False,
                pii_mapping=None,
                include_integrations=False,
            )
            _get_or_update_entity_summary(
                db,
                organization_id,
                SURROGATE_ENTITY_TYPE,
                entity_id,
                summary_text,
            )

        dynamic_context = summary_text + "\n\n" + _build_integrations_context(user_integrations)
        if should_anonymize and pii_mapping:
            known_names = []
            if surrogate.full_name:
                known_names.append(surrogate.full_name)
                known_names.extend(surrogate.full_name.split())
            dynamic_context = anonymize_text(dynamic_context, pii_mapping, known_names)
    elif normalized_entity_type == "task":
        task, related_surrogate = get_task_context(db, entity_id, organization_id)
        if not task:
            return {
                "content": "Task not found.",
                "proposed_actions": [],
                "tokens_used": {"prompt": 0, "completion": 0, "total": 0},
            }
        system_prompt = TASK_SYSTEM_PROMPT
        dynamic_context = _build_task_context(task, related_surrogate, user_integrations)
    elif normalized_entity_type == "global":
        # Global mode - use simplified prompt with performance data
        system_prompt = GLOBAL_SYSTEM_PROMPT
        integrations_ctx = f"User's connected integrations: {', '.join(user_integrations) if user_integrations else 'none'}"
        performance_ctx = ""
        if _should_fetch_performance(message):
            performance_ctx = _build_performance_context(db, organization_id)
        dynamic_context = integrations_ctx + ("\n" + performance_ctx if performance_ctx else "")
    else:
        dynamic_context = "No context available for this entity type."

    # Anonymize user message if enabled
    anonymized_message = message
    if should_anonymize and pii_mapping and surrogate:
        known_names = []
        if surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        anonymized_message = anonymize_text(message, pii_mapping, known_names)

    # Build messages for AI
    history = get_conversation_history(db, conversation.id, history_limit)

    ai_messages = [
        ChatMessage(role="system", content=system_prompt + "\n\n" + dynamic_context),
    ]

    # Add conversation history (anonymize if PII anonymization is enabled)
    for msg in history:
        content = msg.content
        if should_anonymize and pii_mapping and surrogate:
            known_names = []
            if surrogate.full_name:
                known_names.append(surrogate.full_name)
                known_names.extend(surrogate.full_name.split())
            content = anonymize_text(content, pii_mapping, known_names)
        ai_messages.append(ChatMessage(role=msg.role, content=content))

    # Add current user message (anonymized if enabled)
    ai_messages.append(ChatMessage(role="user", content=anonymized_message))

    # Call AI provider
    try:
        response: ChatResponse = await provider.chat(ai_messages)
    except Exception as e:
        logger.exception(f"AI provider error: {e}")
        # Create system alert for AI provider error
        try:
            from app.services import alert_service
            from app.db.enums import AlertType, AlertSeverity

            alert_service.create_or_update_alert(
                db=db,
                org_id=organization_id,
                alert_type=AlertType.AI_PROVIDER_ERROR,
                severity=AlertSeverity.ERROR,
                title="AI provider error",
                message=str(e)[:500],
                integration_key="ai_chat",
                error_class=type(e).__name__,
            )
        except Exception as alert_err:
            logger.warning(f"Failed to create AI provider alert: {alert_err}")
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
            approval_responses.append(
                {
                    "approval_id": str(approval.id),
                    "action_type": approval.action_type,
                    "action_data": approval.action_payload,  # Map to frontend field name
                    "status": approval.status,
                }
            )

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
    conversation.updated_at = datetime.now(timezone.utc)

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
        "conversation_id": str(conversation.id),
        "assistant_message_id": str(assistant_message.id),
    }


def chat(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    message: str,
    user_integrations: list[str] | None = None,
) -> JsonObject:
    """Synchronous wrapper for chat_async (used by API routes)."""
    return asyncio.run(
        chat_async(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            user_integrations=user_integrations,
        )
    )


def get_user_conversations(
    db: Session,
    user_id: uuid.UUID,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[AIConversation]:
    """Get conversations for a user."""
    query = db.query(AIConversation).filter(AIConversation.user_id == user_id)

    if entity_type:
        query = query.filter(AIConversation.entity_type.in_(_resolve_entity_types(entity_type)))
    if entity_id:
        query = query.filter(AIConversation.entity_id == entity_id)

    return query.order_by(AIConversation.updated_at.desc()).all()


def get_conversation_messages(
    db: Session,
    conversation_id: uuid.UUID,
) -> list[AIMessage]:
    """Get all messages in a conversation with action approvals."""
    return (
        db.query(AIMessage)
        .options(joinedload(AIMessage.action_approvals))
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at)
        .all()
    )
