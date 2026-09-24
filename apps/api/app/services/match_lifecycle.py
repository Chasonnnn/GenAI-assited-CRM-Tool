"""Match lifecycle engine: every match status change goes through ``transition``.

One transition takes the row locks in a fixed order, checks the source status
and party rules, applies party stage moves, writes match history (audit and
party activity), commits once, and then dispatches after-commit effects in
isolation through ``match_effects``.

Lock order: status-change request (locked by the approvals service before it
calls the engine), then the match row (plus, on surrogate accept, the
surrogate's other open proposals in id order), then the surrogate or donor row,
then the intended parent row. Each row is locked once.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import AuditEventType, MatchStatus, SurrogateActivityType
from app.db.models import Match, MatchAttempt, StatusChangeRequest
from app.services import match_effects, match_participants, match_queries
from app.services.match_access import MatchAction

PROPOSED = MatchStatus.PROPOSED.value
REVIEWING = MatchStatus.REVIEWING.value
ACCEPTED = MatchStatus.ACCEPTED.value
CANCEL_PENDING = MatchStatus.CANCEL_PENDING.value
REJECTED = MatchStatus.REJECTED.value
CANCELLED = MatchStatus.CANCELLED.value
COMPLETED = MatchStatus.COMPLETED.value

CONCURRENT_ACCEPT_DETAIL = (
    "This surrogate already has an accepted match (concurrent accept detected)"
)


class TransitionError(ValueError):
    """A refused transition; ``status_code`` is the HTTP status the API returns."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class Transition:
    action: str
    sources: tuple[str, ...]
    target: str
    access: MatchAction | None
    # Refusal when the match is outside ``sources``. None resolves the request
    # without changing the match (approvals queue reject and withdraw).
    source_error: str | None
    history: str


TRANSITIONS: dict[str, Transition] = {
    t.action: t
    for t in (
        Transition(
            "accept",
            (PROPOSED, REVIEWING),
            ACCEPTED,
            "accept",
            "Cannot accept match with status: {status}",
            "match_accepted",
        ),
        Transition(
            "reject",
            (PROPOSED, REVIEWING),
            REJECTED,
            "reject",
            "Cannot reject match with status: {status}",
            "match_rejected",
        ),
        Transition(
            "cancel",
            (PROPOSED, REVIEWING),
            CANCELLED,
            "cancel",
            "Cannot cancel match with status: {status}",
            "match_cancelled",
        ),
        Transition(
            "request_cancel",
            (ACCEPTED,),
            CANCEL_PENDING,
            "request_cancel",
            "Only accepted matches can be cancelled",
            "match_cancel_requested",
        ),
        Transition(
            "complete",
            (ACCEPTED,),
            COMPLETED,
            "complete",
            "Only accepted matches can be completed",
            "match_completed",
        ),
        # Approvals queue (ADR 0004): the approvals service checks
        # approve_status_change_requests and owns the request record.
        Transition(
            "approve_cancel",
            (CANCEL_PENDING,),
            CANCELLED,
            None,
            "Match is no longer pending cancellation",
            "match_cancelled",
        ),
        Transition(
            "reject_cancel",
            (CANCEL_PENDING,),
            ACCEPTED,
            None,
            None,
            "match_cancel_request_rejected",
        ),
        Transition(
            "withdraw_cancel",
            (CANCEL_PENDING,),
            ACCEPTED,
            None,
            None,
            "match_cancel_request_withdrawn",
        ),
    )
}


# =============================================================================
# Rollout flag (the only reader of MATCH_CASE_EXPANSION_ENABLED)
# =============================================================================


def expansion_enabled() -> bool:
    return settings.MATCH_CASE_EXPANSION_ENABLED


def require_expansion() -> None:
    """Fence new match data until all application readers support it.

    Gated while disabled: donor proposals, repeat surrogate/IP proposals, donor
    accept, complete, attempt writes, match work writes, and donor or match
    links on appointments. Surrogate propose, accept, reject, cancel,
    cancellation requests and their resolution, notes, and reads stay open.
    """
    if not expansion_enabled():
        raise HTTPException(
            status_code=503, detail="New match features are temporarily unavailable"
        )


# =============================================================================
# Locks
# =============================================================================


def _lock_match_rows(
    db: Session, match: Match, *, with_competitors: bool
) -> tuple[Match, list[Match]]:
    criteria = Match.id == match.id
    if with_competitors:
        criteria = or_(
            criteria,
            and_(
                Match.surrogate_id == match.surrogate_id,
                Match.status.in_(match_queries.PENDING_STATUSES),
                Match.id != match.id,
            ),
        )
    rows = (
        db.query(Match)
        .filter(Match.organization_id == match.organization_id, criteria)
        .order_by(Match.id)
        .populate_existing()
        .with_for_update()
        .all()
    )
    locked = next(row for row in rows if row.id == match.id)
    competitors = [
        row for row in rows if row.id != match.id and row.status in match_queries.PENDING_STATUSES
    ]
    return locked, competitors


def _lock(db: Session, match: Match, *, with_competitors: bool = False) -> tuple[Match, list]:
    locked, competitors = _lock_match_rows(db, match, with_competitors=with_competitors)
    for party in match_participants.parties(locked):
        party.lock(db, locked)
    return locked, competitors


def lock_match(db: Session, match: Match, org_id: UUID | None = None) -> Match:
    """Lock the match, then its parties, in the engine order; return the fresh match row."""
    return _lock(db, match)[0]


# =============================================================================
# History
# =============================================================================


def _party_activity(db: Session, match: Match, event: str, actor_user_id, details: dict) -> None:
    from app.services import activity_service, entity_activity_service

    if match.surrogate_id:
        activity_service.log_activity(
            db=db,
            surrogate_id=match.surrogate_id,
            organization_id=match.organization_id,
            activity_type=SurrogateActivityType(event),
            actor_user_id=actor_user_id,
            details=details,
        )
    elif match.donor_id:
        entity_activity_service.record_activity(
            db,
            org_id=match.organization_id,
            entity_type="donor",
            entity_id=match.donor_id,
            activity_type=event,
            actor_user_id=actor_user_id,
            details={
                k: v
                for k, v in details.items()
                if k in {"match_id", "attempt_id", "intended_parent_id"}
            },
        )


def _intended_parent_activity(db: Session, match: Match, event: str, actor_user_id) -> None:
    from app.services import entity_activity_service

    entity_activity_service.record_activity(
        db,
        org_id=match.organization_id,
        entity_type="intended_parent",
        entity_id=match.intended_parent_id,
        activity_type=event,
        actor_user_id=actor_user_id,
        details={
            "match_id": str(match.id),
            "surrogate_id": str(match.surrogate_id) if match.surrogate_id else None,
        },
    )


def write_history(
    db: Session,
    match: Match,
    actor_user_id: UUID | None,
    event: str,
    *,
    audit_details: dict,
    party_details: dict,
) -> None:
    """Audit row on the match plus activity on both parties, in the caller's transaction."""
    from app.services import audit_service

    _party_activity(db, match, event, actor_user_id, party_details)
    _intended_parent_activity(db, match, event, actor_user_id)
    audit_service.log_event(
        db=db,
        org_id=match.organization_id,
        event_type=AuditEventType(event),
        actor_user_id=actor_user_id,
        target_type="match",
        target_id=match.id,
        details=audit_details,
    )


def write_case_change(
    db: Session, match: Match, actor_user_id: UUID | None, event: str, details: dict | None = None
) -> None:
    """History with the same details on the audit row and the party activity."""
    from app.services import audit_service

    data = {"match_id": str(match.id), **(details or {})}
    audit_service.log_event(
        db=db,
        org_id=match.organization_id,
        event_type=AuditEventType(event),
        actor_user_id=actor_user_id,
        target_type="match",
        target_id=match.id,
        details=data,
    )
    _party_activity(db, match, event, actor_user_id, data)
    _intended_parent_activity(db, match, event, actor_user_id)


def _pair_details(match: Match) -> tuple[dict, dict]:
    audit = {
        "surrogate_id": str(match.surrogate_id),
        "intended_parent_id": str(match.intended_parent_id),
    }
    party = {"match_id": str(match.id), "intended_parent_id": str(match.intended_parent_id)}
    return audit, party


def _append_notes(match: Match, notes: str | None) -> None:
    if notes:
        from app.services import note_service

        match.notes = (match.notes or "") + "\n\n" + note_service.sanitize_html(notes)


# =============================================================================
# Propose
# =============================================================================


def generate_match_number(db: Session, org_id: UUID) -> str:
    """Next sequential match number for the org (M10001+), race-free."""
    result = db.execute(
        text("""
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'match_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
        """),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError("Failed to generate match number")
    return f"M{result:05d}"


def propose(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID | None,
    intended_parent_id: UUID,
    proposed_by_user_id: UUID,
    donor_id: UUID | None = None,
    notes: str | None = None,
) -> Match:
    """Create a proposed match. Parties may be at any stage."""
    from app.services import note_service

    if not match_queries.get_intended_parent(db, intended_parent_id, org_id):
        raise TransitionError("Intended parent not found", 404)
    existing = match_queries.get_existing_match(
        db, org_id, surrogate_id, intended_parent_id, donor_id=donor_id
    )
    if existing:
        raise TransitionError(f"Match already exists with status: {existing.status}", 409)
    if surrogate_id and match_queries.get_accepted_match_for_surrogate(db, org_id, surrogate_id):
        raise TransitionError("Surrogate already has an accepted match")

    if (surrogate_id is None) == (donor_id is None):
        raise ValueError("Exactly one surrogate or donor is required")
    participant = (
        match_queries.get_donor(db, donor_id, org_id)
        if donor_id
        else match_queries.get_surrogate_with_stage(db, surrogate_id, org_id)
    )
    if not participant or not match_queries.get_intended_parent(db, intended_parent_id, org_id):
        raise ValueError("Match participants not found")
    if donor_id or match_queries.has_any_match_for_pair(
        db, org_id, surrogate_id, intended_parent_id
    ):
        require_expansion()

    try:
        match = Match(
            organization_id=org_id,
            match_number=generate_match_number(db, org_id),
            surrogate_id=surrogate_id,
            donor_id=donor_id,
            match_kind="donor" if donor_id else "surrogate",
            intended_parent_id=intended_parent_id,
            status=PROPOSED,
            proposed_by_user_id=proposed_by_user_id,
            notes=note_service.sanitize_html(notes) if notes else None,
        )
        db.add(match)
        db.flush()
        audit, party = _pair_details(match)
        write_history(
            db,
            match,
            proposed_by_user_id,
            "match_proposed",
            audit_details=audit,
            party_details=party,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise TransitionError("An open match already exists for these participants", 409)
    db.refresh(match)
    match_effects.dispatch(
        db,
        match_effects.TransitionEvent(
            "propose",
            match,
            proposed_by_user_id,
            match_effects.workflow_trigger(db, "proposed", match),
        ),
    )
    return match


# =============================================================================
# Transition
# =============================================================================


@dataclass
class _Context:
    action: str
    db: Session
    match: Match
    actor_user_id: UUID
    actor_role: object
    now: datetime
    request: StatusChangeRequest | None
    reason: str | None
    notes: str | None
    outcome: str | None
    competitors: list[Match]


def transition(
    db: Session,
    match: Match,
    action: str,
    *,
    actor_user_id: UUID,
    actor_role=None,
    request: StatusChangeRequest | None = None,
    reason: str | None = None,
    notes: str | None = None,
    outcome: str | None = None,
    before_commit: Callable[[], None] | None = None,
) -> Match:
    """Apply one row of TRANSITIONS atomically, then dispatch its effects.

    ``request`` is the status-change request for approvals-queue actions; the
    caller locks it before calling. ``before_commit`` lets that caller resolve
    the request in the same transaction after the engine checks pass.
    """
    spec = TRANSITIONS[action]
    if action == "complete":
        require_expansion()
    locked, competitors = _lock(
        db, match, with_competitors=action == "accept" and bool(match.surrogate_id)
    )
    if action == "accept" and locked.donor_id:
        require_expansion()

    ctx = _Context(
        action=action,
        db=db,
        match=locked,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        now=datetime.now(UTC),
        request=request,
        reason=reason,
        notes=notes,
        outcome=outcome,
        competitors=competitors,
    )
    applies = locked.status in spec.sources
    if not applies and spec.source_error is not None:
        raise TransitionError(spec.source_error.format(status=locked.status))

    try:
        effects = _APPLY[action](ctx) if applies else []
        if action == "reject_cancel":
            effects += match_effects.cancel_request_resolved_notification(
                db, locked, request, actor_user_id, approved=False, reason=reason
            )
        if before_commit is not None:
            before_commit()
        db.commit()
    except IntegrityError:
        db.rollback()
        if action == "accept":
            raise TransitionError(CONCURRENT_ACCEPT_DETAIL, 409)
        raise
    db.refresh(locked)
    match_effects.dispatch(
        db, match_effects.TransitionEvent(action, locked, actor_user_id, effects)
    )
    return locked


def _accept(ctx: _Context) -> list:
    db, match = ctx.db, ctx.match
    primary = match_participants.primary(match)
    primary.check_accept(db, match)
    effects = primary.on_accept(
        db, match, actor_user_id=ctx.actor_user_id, actor_role=ctx.actor_role, now=ctx.now
    )
    match.status = ACCEPTED
    match.reviewed_by_user_id = ctx.actor_user_id
    match.reviewed_at = ctx.now
    _append_notes(match, ctx.notes)
    match.updated_at = ctx.now
    match_participants.INTENDED_PARENT.on_accept(
        db, match, actor_user_id=ctx.actor_user_id, actor_role=ctx.actor_role, now=ctx.now
    )
    for other in ctx.competitors:
        other.status = CANCELLED
        other.closed_at = ctx.now
        other.closed_by_user_id = ctx.actor_user_id
        other.closure_reason = "Another match accepted"
        other.updated_at = ctx.now
        write_case_change(db, other, ctx.actor_user_id, "match_cancelled")
    audit, party = _pair_details(match)
    count = {"cancelled_matches": len(ctx.competitors)}
    write_history(
        db,
        match,
        ctx.actor_user_id,
        "match_accepted",
        audit_details={**audit, **count},
        party_details={**party, **count},
    )
    return [
        *effects,
        *match_effects.dashboard_push(db, match.organization_id),
        *match_effects.workflow_trigger(db, "accepted", match),
    ]


def _reject(ctx: _Context) -> list:
    match = ctx.match
    match.status = REJECTED
    match.closed_at = ctx.now
    match.closed_by_user_id = ctx.actor_user_id
    match.closure_reason = ctx.reason
    match.reviewed_by_user_id = ctx.actor_user_id
    match.reviewed_at = ctx.now
    match.rejection_reason = ctx.reason
    _append_notes(match, ctx.notes)
    match.updated_at = ctx.now
    audit, party = _pair_details(match)
    write_history(
        ctx.db,
        match,
        ctx.actor_user_id,
        "match_rejected",
        audit_details={**audit, "rejection_reason_provided": bool(ctx.reason)},
        party_details={**party, "rejection_reason": ctx.reason},
    )
    return match_effects.workflow_trigger(ctx.db, "rejected", match)


def _cancel(ctx: _Context) -> list:
    match = ctx.match
    match.status = CANCELLED
    match.closed_at = ctx.now
    match.closed_by_user_id = ctx.actor_user_id
    match.updated_at = ctx.now
    audit, party = _pair_details(match)
    write_history(
        ctx.db,
        match,
        ctx.actor_user_id,
        "match_cancelled",
        audit_details=audit,
        party_details=party,
    )
    return []


def _request_cancel(ctx: _Context) -> list:
    db, match = ctx.db, ctx.match
    existing = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.organization_id == match.organization_id,
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == match.id,
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    if existing:
        raise TransitionError("A pending cancellation request already exists for this match", 409)
    request = StatusChangeRequest(
        organization_id=match.organization_id,
        entity_type="match",
        entity_id=match.id,
        target_status=CANCELLED,
        effective_at=ctx.now,
        reason=(ctx.reason or "").strip(),
        requested_by_user_id=ctx.actor_user_id,
        requested_at=ctx.now,
        status="pending",
    )
    db.add(request)
    match.status = CANCEL_PENDING
    match.updated_at = ctx.now
    write_case_change(db, match, ctx.actor_user_id, "match_cancel_requested")
    return match_effects.cancel_request_pending_notification(db, match, request, ctx.actor_user_id)


def _complete(ctx: _Context) -> list:
    db, match = ctx.db, ctx.match
    outcome = ctx.outcome or ""
    if not outcome.strip():
        raise TransitionError("Completion outcome is required")
    if (
        db.query(MatchAttempt.id)
        .filter(
            MatchAttempt.organization_id == match.organization_id,
            MatchAttempt.match_id == match.id,
            MatchAttempt.status.in_(("planned", "in_progress")),
        )
        .first()
    ):
        raise TransitionError("Finish or cancel open attempts before completing the match")
    match.status = COMPLETED
    match.closed_at = ctx.now
    match.closed_by_user_id = ctx.actor_user_id
    match.closure_reason = ctx.reason.strip() if ctx.reason else None
    match.outcome = outcome.strip()
    match.updated_at = ctx.now
    write_case_change(db, match, ctx.actor_user_id, "match_completed")
    return []


def _approve_cancel(ctx: _Context) -> list:
    from app.services import match_attempts

    db, match, request = ctx.db, ctx.match, ctx.request
    if not match_queries.get_intended_parent(db, match.intended_parent_id, match.organization_id):
        raise TransitionError("Match participants not found")
    effects = []
    for party in match_participants.parties(match):
        effects += party.on_cancel_approved(
            db, match, request=request, actor_user_id=ctx.actor_user_id, now=ctx.now
        )
    match.status = CANCELLED
    match.closed_at = ctx.now
    match.closed_by_user_id = ctx.actor_user_id
    match.closure_reason = request.reason
    match.updated_at = ctx.now
    match_attempts.close_open_attempts(db, match, ctx.now)
    write_case_change(db, match, ctx.actor_user_id, "match_cancelled")
    return [
        *effects,
        *match_effects.cancel_request_resolved_notification(
            db, match, request, ctx.actor_user_id, approved=True
        ),
    ]


def _restore_accepted(ctx: _Context) -> list:
    match = ctx.match
    match.status = ACCEPTED
    match.updated_at = ctx.now
    write_case_change(
        ctx.db,
        match,
        ctx.actor_user_id,
        TRANSITIONS[ctx.action].history,
        {"status_request_id": str(ctx.request.id)},
    )
    return []


_APPLY: dict[str, Callable[[_Context], list]] = {
    "accept": _accept,
    "reject": _reject,
    "cancel": _cancel,
    "request_cancel": _request_cancel,
    "complete": _complete,
    "approve_cancel": _approve_cancel,
    "reject_cancel": _restore_accepted,
    "withdraw_cancel": _restore_accepted,
}


def update_notes(db: Session, match: Match, *, notes: str) -> Match:
    """Replace match notes; not a status change."""
    from app.services import note_service

    match.notes = note_service.sanitize_html(notes)
    match.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(match)
    return match
