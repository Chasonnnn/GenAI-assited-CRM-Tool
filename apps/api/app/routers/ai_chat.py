"""AI chat routes."""

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_db_for_stream,
    require_ai_enabled,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.utils.sse import format_sse, sse_preamble, STREAM_HEADERS

router = APIRouter()
logger = logging.getLogger(__name__)


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


def _prepare_chat_request(
    body: ChatRequest,
    db: Session,
    session: UserSession,
) -> tuple[str, uuid.UUID, list[str]]:
    from app.services import (
        ai_settings_service,
        oauth_service,
        surrogate_service,
        task_service,
    )

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

    integrations = oauth_service.get_user_integrations(db, session.user_id)
    user_integrations = [i.integration_type for i in integrations]

    return entity_type, entity_id, user_integrations


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
    from app.services import (
        ai_chat_service,
    )
    entity_type, entity_id, user_integrations = _prepare_chat_request(body, db, session)

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
    "/chat/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_ai_enabled)],
)
@limiter.limit("60/minute")
async def chat_stream(
    request: Request,  # Required by limiter
    body: ChatRequest,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.AI_USE)),
) -> StreamingResponse:
    """Stream messages from the AI assistant via SSE."""
    from app.services import ai_chat_service

    entity_type, entity_id, user_integrations = _prepare_chat_request(body, db, session)

    org_id = session.org_id
    user_id = session.user_id
    message = body.message

    async def event_generator() -> AsyncIterator[str]:
        yield sse_preamble()
        with get_db_for_stream() as stream_db:
            try:
                async for event in ai_chat_service.stream_chat_async(
                    db=stream_db,
                    organization_id=org_id,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    message=message,
                    user_integrations=user_integrations,
                ):
                    yield format_sse(event["type"], event["data"])
            except Exception as exc:
                logger.exception("AI chat stream failed", exc_info=exc)
                yield format_sse("error", {"message": "Streaming error. Please try again."})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=STREAM_HEADERS)
