"""Centralized access checks for one match.

Every match action needs its action permission plus record scope on both
parties. Viewing needs ``view_matches``; every change also needs
``propose_matches`` until the v2 match actions exist.
"""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.policies import POLICIES
from app.db.models import Match
from app.schemas.auth import UserSession
from app.services import match_queries, permission_service, record_access_service

MatchAction = Literal[
    "view",
    "propose",
    "accept",
    "reject",
    "cancel",
    "request_cancel",
    "complete",
    "edit_notes",
    "edit_attempts",
    "edit_events",
]

_VIEW_ACTIONS = frozenset({"view"})


def required_permissions(action: MatchAction) -> list[str]:
    policy = POLICIES["matches"]
    required = [policy.default.value]
    if action not in _VIEW_ACTIONS:
        required.append(policy.actions["propose"].value)
    return required


def authorize(
    db: Session,
    action: MatchAction,
    match: Match,
    session: UserSession,
    *,
    allow_archived: bool = False,
) -> Match:
    """Raise 403 without the action permission and 403/404 without scope on either party."""
    for permission in required_permissions(action):
        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, permission
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
    record_access_service.get_record_with_access(
        db, session, "intended_parent", match.intended_parent_id
    )
    record_access_service.get_record_with_access(
        db,
        session,
        "donor" if match.donor_id else "surrogate",
        match.donor_id or match.surrogate_id,
        allow_archived=allow_archived and action in _VIEW_ACTIONS,
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
    """Record scope on both proposed parties; the route dependency holds the action permission."""
    record_access_service.get_record_with_access(
        db, session, "donor" if donor_id else "surrogate", donor_id or surrogate_id
    )
    record_access_service.get_record_with_access(db, session, "intended_parent", intended_parent_id)
