"""Match action permissions and response capabilities, scoped to the session's parties."""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Match, StatusChangeRequest
from app.schemas.auth import UserSession
from app.services import match_queries, permission_service, record_access_service

MatchAction = Literal[
    "view",
    "propose",
    "accept",
    "decline",
    "request_cancel",
    "complete",
    "withdraw_cancel",
    "approve_cancel",
    "reject_cancel",
    "edit_notes",
    "edit_attempts",
    "edit_events",
]

_ACTION_PERMISSIONS = {
    "accept": "decide_matches",
    "decline": "decide_matches",
    "request_cancel": "close_matches",
    "complete": "close_matches",
    "withdraw_cancel": "close_matches",
    "approve_cancel": "approve_status_change_requests",
    "reject_cancel": "approve_status_change_requests",
    "edit_notes": "propose_matches",
    "edit_attempts": "propose_matches",
    "edit_events": "propose_matches",
}
PUBLIC_ACTIONS = ("accept", "decline", "request_cancel", "withdraw_cancel", "complete")


def required_permissions(action: MatchAction) -> list[str]:
    return [
        "view_matches",
        *([_ACTION_PERMISSIONS[action]] if action in _ACTION_PERMISSIONS else []),
    ]


def pending_cancellation(db: Session, match: Match) -> StatusChangeRequest | None:
    return (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.organization_id == match.organization_id,
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == match.id,
            StatusChangeRequest.status == "pending",
        )
        .first()
    )


def authorize(
    db: Session,
    action: MatchAction,
    match: Match,
    session: UserSession,
    *,
    allow_archived: bool = False,
    request: StatusChangeRequest | None = None,
) -> Match:
    """Raise 403 without the action permission and 403/404 without scope on either party."""
    if match.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Match not found")
    permissions = required_permissions(action)
    if action == "decline" and match.proposed_by_user_id == session.user_id:
        permissions = required_permissions("view")
    for permission in permissions:
        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, permission
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
    try:
        record_access_service.get_record_with_access(
            db, session, "intended_parent", match.intended_parent_id
        )
        record_access_service.get_record_with_access(
            db,
            session,
            "donor" if match.donor_id else "surrogate",
            match.donor_id or match.surrogate_id,
            allow_archived=allow_archived and action == "view",
        )
    except HTTPException as exc:
        if isinstance(exc.detail, str):
            exc.detail = exc.detail.replace("this intended_parent", "this intended parent")
        raise
    if action == "withdraw_cancel":
        request = request or pending_cancellation(db, match)
        if request is None:
            raise HTTPException(
                status_code=400, detail="No pending cancellation request exists for this match"
            )
        if request.requested_by_user_id != session.user_id:
            raise HTTPException(
                status_code=403, detail="Only the requester can withdraw the cancellation request"
            )
    return match


def load(
    db: Session,
    session: UserSession,
    match_id: UUID,
    action: MatchAction = "view",
    *,
    allow_archived: bool = False,
) -> Match:
    """Resolve the match under authenticated membership, then authorize the action."""
    match = match_queries.get_match(db, match_id, session.org_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return authorize(db, action, match, session, allow_archived=allow_archived)


def authorize_proposal(
    db: Session,
    session: UserSession,
    *,
    surrogate_id: UUID | None,
    donor_id: UUID | None,
    intended_parent_id: UUID,
) -> None:
    """Authorize proposal viewing and record scope on both proposed parties."""
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "view_matches"
    ):
        raise HTTPException(status_code=403, detail="Missing permission: view_matches")
    record_access_service.get_record_with_access(
        db, session, "donor" if donor_id else "surrogate", donor_id or surrogate_id
    )
    record_access_service.get_record_with_access(db, session, "intended_parent", intended_parent_id)


def action_availability(
    db: Session, match: Match, session: UserSession
) -> tuple[list[str], dict[str, str]]:
    """Offer only status-applicable actions; explain the first blocking rule for each."""
    from app.services import match_lifecycle

    allowed, blocked = [], {}
    for action in PUBLIC_ACTIONS:
        if match.status not in match_lifecycle.TRANSITIONS[action].sources:
            continue
        try:
            authorize(db, action, match, session)
            match_lifecycle.check_action(db, match, action, actor_user_id=session.user_id)
        except HTTPException as exc:
            blocked[action] = str(exc.detail)
        except ValueError as exc:
            blocked[action] = str(exc)
        else:
            allowed.append(action)
    return allowed, blocked
