"""Explicit correspondence history for light record workspaces."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
    require_roles,
)
from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import record_correspondence_service

router = APIRouter(
    prefix="/records",
    tags=["Correspondence"],
    dependencies=[
        Depends(require_roles([Role.DEVELOPER])),
        Depends(require_permission(POLICIES["tickets"].default)),
    ],
)
RecordKind = Literal["donor", "intended_parent"]
SessionDep = Annotated[UserSession, Depends(get_current_session)]
DbDep = Annotated[Session, Depends(get_db)]


class CorrespondenceItem(BaseModel):
    id: UUID
    kind: Literal["ticket", "email"]
    subject: str
    status: str
    recipient: str | None
    occurred_at: datetime
    ticket_code: str | None


class CorrespondenceList(BaseModel):
    items: list[CorrespondenceItem]
    total: int


@router.get("/{kind}/{record_id}/correspondence", response_model=CorrespondenceList)
def list_correspondence(
    kind: RecordKind,
    record_id: UUID,
    session: SessionDep,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CorrespondenceList:
    return CorrespondenceList.model_validate(
        record_correspondence_service.list_correspondence(
            db, session, kind, record_id, limit=limit, offset=offset
        )
    )


@router.put(
    "/{kind}/{record_id}/correspondence/{ticket_id}",
    status_code=204,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["tickets"].actions["edit"])),
    ],
)
def link_ticket(
    kind: RecordKind, record_id: UUID, ticket_id: UUID, session: SessionDep, db: DbDep
) -> Response:
    record_correspondence_service.link_ticket(db, session, kind, record_id, ticket_id)
    return Response(status_code=204)


@router.delete(
    "/{kind}/{record_id}/correspondence/{ticket_id}",
    status_code=204,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["tickets"].actions["edit"])),
    ],
)
def unlink_ticket(
    kind: RecordKind, record_id: UUID, ticket_id: UUID, session: SessionDep, db: DbDep
) -> Response:
    record_correspondence_service.link_ticket(db, session, kind, record_id, ticket_id, remove=True)
    return Response(status_code=204)
