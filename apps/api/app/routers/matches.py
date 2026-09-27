"""Matches router - API endpoints for matching surrogates with intended parents."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.matches import (
    AttemptCreate,
    AttemptRead,
    AttemptUpdate,
    MatchAcceptRequest,
    MatchCancelRequest,
    MatchCompleteRequest,
    MatchCreate,
    MatchDeclineRequest,
    MatchEventCreate,
    MatchEventRead,
    MatchEventUpdate,
    MatchListResponse,
    MatchRead,
    MatchStatsResponse,
    MatchUpdateNotesRequest,
)
from app.services import (
    match_access,
    match_attempts,
    match_event_service,
    match_lifecycle,
    match_queries,
)

router = APIRouter(
    prefix="/matches",
    tags=["Matches"],
    dependencies=[Depends(require_permission(POLICIES["matches"].default))],
)

_propose_permission = require_permission(POLICIES["matches"].actions["propose"])


def _refused(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))


def _transition(
    db: Session, session: UserSession, match_id: UUID, action: match_access.MatchAction, **kwargs
) -> MatchRead:
    match = match_access.load(db, session, match_id, action)
    try:
        match = match_lifecycle.transition(
            db,
            match,
            action,
            actor_user_id=session.user_id,
            actor_role=session.role,
            **kwargs,
        )
    except ValueError as exc:
        raise _refused(exc)
    return match_queries.to_read(db, match, session.org_id)


@router.post(
    "/",
    response_model=MatchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_match(
    data: MatchCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchRead:
    """
    Propose a new match between a surrogate and intended parent.

    Requires: Manager+ role
    """
    match_access.authorize_proposal(
        db,
        session,
        surrogate_id=data.surrogate_id,
        donor_id=data.donor_id,
        intended_parent_id=data.intended_parent_id,
    )
    try:
        match = match_lifecycle.propose(
            db=db,
            org_id=session.org_id,
            surrogate_id=data.surrogate_id,
            donor_id=data.donor_id,
            intended_parent_id=data.intended_parent_id,
            proposed_by_user_id=session.user_id,
            notes=data.notes,
        )
    except match_lifecycle.TransitionError as exc:
        raise _refused(exc)
    return match_queries.to_read(db, match, session.org_id)


@router.get("/", response_model=MatchListResponse)
def list_matches(
    request: Request,
    status_filter: Annotated[str | None, "fastapi_param"] = Query(
        None, alias="status", description="Filter by status"
    ),
    surrogate_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by surrogate ID"
    ),
    intended_parent_id: Annotated[UUID | None, "fastapi_param"] = Query(
        None, description="Filter by intended parent ID"
    ),
    donor_id: Annotated[UUID | None, "fastapi_param"] = Query(None),
    match_kind: Annotated[Literal["surrogate", "donor"] | None, "fastapi_param"] = Query(None),
    q: Annotated[str | None, "fastapi_param"] = Query(
        None, max_length=100, description="Search surrogate/IP names"
    ),
    page: Annotated[int, "fastapi_param"] = Query(1, ge=1),
    per_page: Annotated[int, "fastapi_param"] = Query(20, ge=1, le=100),
    sort_by: Annotated[str | None, "fastapi_param"] = Query(None, description="Column to sort by"),
    sort_order: Annotated[str, "fastapi_param"] = Query(
        "desc", pattern="^(asc|desc)$", description="Sort direction"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchListResponse:
    """
    List matches with optional filters.

    Requires: Manager+ role
    """
    return match_queries.list_for_session(
        db,
        session,
        request,
        status_filter=status_filter,
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        donor_id=donor_id,
        match_kind=match_kind,
        q=q,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/stats", response_model=MatchStatsResponse)
def get_match_stats(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchStatsResponse:
    """Get match counts by status for the org."""
    total, counts = match_queries.get_match_stats(db, session.org_id, session=session)
    return MatchStatsResponse(total=total, by_status=counts)


@router.get("/{match_id}", response_model=MatchRead)
def get_match(
    match_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchRead:
    """Get match details."""
    return match_queries.get_detail(db, session, match_id)


@router.put(
    "/{match_id}/accept",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def accept_match(
    match_id: UUID,
    data: MatchAcceptRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchRead:
    """
    Accept a match.

    This will:
    - Set match status to accepted
    - Decline all other pending matches for this surrogate
    - Log activity

    Requires: Manager+ role
    """
    return _transition(db, session, match_id, "accept", notes=data.notes)


@router.put(
    "/{match_id}/decline",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def decline_match(
    match_id: UUID,
    data: MatchDeclineRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchRead:
    """
    Decline a match with reason.

    Requires: Manager+ role
    """
    return _transition(db, session, match_id, "decline", reason=data.reason, notes=data.notes)


@router.post(
    "/{match_id}/cancel-request",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def request_cancel_match(
    match_id: UUID,
    data: MatchCancelRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchRead:
    """
    Request cancellation of an accepted match (requires admin approval).

    This will:
    - Create a pending status change request tied to the match
    - Mark the match as cancellation_pending
    """
    return _transition(db, session, match_id, "request_cancel", reason=data.reason)


@router.patch(
    "/{match_id}/notes",
    response_model=MatchRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_match_notes(
    match_id: UUID,
    data: MatchUpdateNotesRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchRead:
    """Update match notes. Requires: Manager+ role."""
    match = match_access.load(db, session, match_id, "edit_notes")
    match = match_lifecycle.update_notes(db, match, notes=data.notes)
    return match_queries.to_read(db, match, session.org_id)


# =============================================================================
# Match Events (Calendar) Endpoints
# =============================================================================


@router.get("/{match_id}/events", response_model=list[MatchEventRead])
def list_match_events(
    match_id: UUID,
    from_date: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter events from this date (YYYY-MM-DD)"
    ),
    to_date: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter events until this date (YYYY-MM-DD)"
    ),
    person_type: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter by person type (surrogate/ip)"
    ),
    event_type: Annotated[str | None, "fastapi_param"] = Query(
        None, description="Filter by event type"
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> list[MatchEventRead]:
    """
    List events for a match.

    Requires: Case Manager+ role
    """
    return match_event_service.list_events(
        db,
        session,
        match_id,
        from_date=from_date,
        to_date=to_date,
        person_type=person_type,
        event_type=event_type,
    )


@router.post(
    "/{match_id}/events",
    response_model=MatchEventRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_match_event(
    match_id: UUID,
    data: MatchEventCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchEventRead:
    """
    Create an event for a match.

    Requires: Case Manager+ role
    """
    return match_event_service.create_event(db, session, match_id, data)


@router.get("/{match_id}/events/{event_id}", response_model=MatchEventRead)
def get_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
) -> MatchEventRead:
    """
    Get a specific match event.

    Requires: Case Manager+ role
    """
    return match_event_service.get_event(db, session, match_id, event_id)


@router.put(
    "/{match_id}/events/{event_id}",
    response_model=MatchEventRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_match_event(
    match_id: UUID,
    event_id: UUID,
    data: MatchEventUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchEventRead:
    """
    Update a match event.

    Requires: Case Manager+ role
    """
    return match_event_service.update_event(db, session, match_id, event_id, data)


@router.delete(
    "/{match_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_match_event(
    match_id: UUID,
    event_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> Response:
    """
    Delete a match event.

    Requires: Case Manager+ role
    """
    match_event_service.delete_event(db, session, match_id, event_id)


@router.put(
    "/{match_id}/complete", response_model=MatchRead, dependencies=[Depends(require_csrf_header)]
)
def complete_match(
    match_id: UUID,
    data: MatchCompleteRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
) -> MatchRead:
    return _transition(db, session, match_id, "complete", outcome=data.outcome, reason=data.reason)


@router.get("/{match_id}/attempts", response_model=list[AttemptRead])
def list_attempts(
    match_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
):
    match = match_access.load(db, session, match_id, "view", allow_archived=True)
    return match_attempts.list_attempts(db, match)


@router.post(
    "/{match_id}/attempts",
    response_model=AttemptRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_attempt(
    match_id: UUID,
    data: AttemptCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
):
    match = match_access.load(db, session, match_id, "edit_attempts")
    try:
        return match_attempts.save_attempt(
            db, match, actor_user_id=session.user_id, values=data.model_dump()
        )
    except ValueError as exc:
        raise _refused(exc)


@router.patch(
    "/{match_id}/attempts/{attempt_id}",
    response_model=AttemptRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_attempt(
    match_id: UUID,
    attempt_id: UUID,
    data: AttemptUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(_propose_permission),
):
    match = match_access.load(db, session, match_id, "edit_attempts")
    try:
        return match_attempts.save_attempt(
            db,
            match,
            actor_user_id=session.user_id,
            values=data.model_dump(exclude_unset=True),
            attempt_id=attempt_id,
        )
    except ValueError as exc:
        raise _refused(exc)
