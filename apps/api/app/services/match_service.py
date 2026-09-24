"""Compatibility entry points for matches.

Status changes live in ``match_lifecycle``; access in ``match_access``; reads in
``match_queries``; attempts in ``match_attempts``; calendar events in
``match_event_service``. Application code imports those modules directly.

Temporary: this module exists only because unchanged tests (test_match_cases,
test_match_lifecycle_characterization, test_record_scopes_v2) import these names.
Remove it in plan step 5, when those tests change to import the modules above.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Match
from app.services import match_access, match_lifecycle
from app.services.match_lifecycle import generate_match_number, lock_match
from app.services.match_queries import (
    COMMITTED_STATUSES,
    OPEN_STATUSES,
    get_accepted_match_for_intended_parent,
    get_accepted_match_for_surrogate,
    get_match,
    match_visibility_filter,
)

__all__ = [
    "COMMITTED_STATUSES",
    "OPEN_STATUSES",
    "accept_match",
    "generate_match_number",
    "get_accepted_match_for_intended_parent",
    "get_accepted_match_for_surrogate",
    "get_match",
    "get_match_with_access",
    "lock_match",
    "match_visibility_filter",
]


def get_match_with_access(
    db: Session, session, match_id: UUID, *, write: bool = False, allow_archived: bool = False
) -> Match:
    """Resolve the match and both parties under authenticated membership."""
    return match_access.load(
        db, session, match_id, "edit_attempts" if write else "view", allow_archived=allow_archived
    )


def accept_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    actor_role,
    org_id: UUID,
    notes: str | None = None,
) -> Match:
    """Accept a match through the lifecycle engine."""
    return match_lifecycle.transition(
        db, match, "accept", actor_user_id=actor_user_id, actor_role=actor_role, notes=notes
    )
