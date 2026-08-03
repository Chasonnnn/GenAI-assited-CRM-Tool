"""Admin/developer-only read-only messaging inbox and triage actions."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission, require_roles
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.messaging_inbox import (
    MessagingConversationDetail,
    MessagingConversationLinkRequest,
    MessagingConversationListResponse,
    MessagingReconciliationCaseRead,
    MessagingReconciliationUpdateRequest,
)
from app.services import messaging_inbox_service

router = APIRouter(
    prefix="/messaging",
    tags=["messaging-inbox"],
    dependencies=[Depends(require_roles([Role.ADMIN, Role.DEVELOPER]))],
)


def _not_found(exc: LookupError) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/conversations", response_model=MessagingConversationListResponse)
def list_messaging_conversations(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
    unread: Annotated[bool | None, Query()] = None,
    unlinked: Annotated[bool | None, Query()] = None,
    purpose: Annotated[Literal["operational", "promotional"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessagingConversationListResponse:
    return messaging_inbox_service.list_conversations(
        db,
        organization_id=session.org_id,
        unread=unread,
        unlinked=unlinked,
        purpose=purpose,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/candidates/{surrogate_id}/conversations",
    response_model=MessagingConversationListResponse,
)
def list_candidate_messaging_conversations(
    surrogate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessagingConversationListResponse:
    try:
        return messaging_inbox_service.list_candidate_conversations(
            db,
            organization_id=session.org_id,
            surrogate_id=surrogate_id,
            limit=limit,
            offset=offset,
        )
    except messaging_inbox_service.MessagingInboxEntityNotFound as exc:
        _not_found(exc)
        raise AssertionError("unreachable") from exc


@router.get("/conversations/{conversation_id}", response_model=MessagingConversationDetail)
def get_messaging_conversation(
    conversation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingConversationDetail:
    try:
        return messaging_inbox_service.get_conversation(
            db,
            organization_id=session.org_id,
            conversation_id=conversation_id,
        )
    except messaging_inbox_service.MessagingInboxNotFound as exc:
        _not_found(exc)
        raise AssertionError("unreachable") from exc


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=MessagingConversationDetail,
    dependencies=[Depends(require_csrf_header)],
)
def mark_messaging_conversation_read(
    conversation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingConversationDetail:
    try:
        return messaging_inbox_service.mark_conversation_read(
            db,
            organization_id=session.org_id,
            conversation_id=conversation_id,
        )
    except messaging_inbox_service.MessagingInboxNotFound as exc:
        _not_found(exc)
        raise AssertionError("unreachable") from exc


@router.post(
    "/conversations/{conversation_id}/link",
    response_model=MessagingConversationDetail,
    dependencies=[Depends(require_csrf_header)],
)
def link_messaging_conversation(
    conversation_id: UUID,
    request: MessagingConversationLinkRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingConversationDetail:
    try:
        return messaging_inbox_service.link_conversation(
            db,
            organization_id=session.org_id,
            conversation_id=conversation_id,
            **request.model_dump(),
        )
    except (
        messaging_inbox_service.MessagingInboxNotFound,
        messaging_inbox_service.MessagingInboxEntityNotFound,
    ) as exc:
        _not_found(exc)
        raise AssertionError("unreachable") from exc
    except messaging_inbox_service.MessagingInboxLinkConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch(
    "/reconciliation/{case_id}",
    response_model=MessagingReconciliationCaseRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_messaging_reconciliation_case(
    case_id: UUID,
    request: MessagingReconciliationUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingReconciliationCaseRead:
    try:
        return messaging_inbox_service.update_reconciliation_case(
            db,
            organization_id=session.org_id,
            case_id=case_id,
            **request.model_dump(),
        )
    except messaging_inbox_service.MessagingInboxNotFound as exc:
        _not_found(exc)
        raise AssertionError("unreachable") from exc
    except messaging_inbox_service.MessagingInboxVersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
