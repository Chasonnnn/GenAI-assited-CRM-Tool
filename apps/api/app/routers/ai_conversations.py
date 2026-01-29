"""AI conversation history routes."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import Role
from app.schemas.auth import UserSession

router = APIRouter()


@router.get("/conversations/{entity_type}/{entity_id}")
def get_conversation(
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> dict[str, Any]:
    """Get conversation history for an entity."""
    from app.services import ai_chat_service, surrogate_service, task_service

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
    from app.services import ai_chat_service

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
    from app.services import ai_service

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
