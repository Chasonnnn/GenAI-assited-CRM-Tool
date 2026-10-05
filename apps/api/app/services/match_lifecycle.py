"""Match lifecycle engine: every match status change goes through this module.

User actions go through ``transition``. The surrogate stage service applies the
``SYSTEM_TRANSITIONS`` (completion on entering Delivered and its undo) inside
its own stage-change transaction; see "Surrogate Delivered stage" below.

One transition takes the row locks in a fixed order, checks the source status
and party rules, applies party stage moves, writes match history (audit and
party activity), commits once, and then dispatches after-commit effects in
isolation through ``match_effects``.

Lock order: status-change request (locked by the approvals service before it
calls the engine), then the match row (plus, on surrogate accept, the
surrogate's other open proposals in id order) FOR UPDATE, then the surrogate
or donor row, then the intended parent row FOR NO KEY UPDATE. Each row is
locked once. Party locks do not conflict with the FOR KEY SHARE locks that
activity inserts take, so history written for another match's parties does not
wait on them. Permission v2 takes the existing organization configuration lock
before these domain locks, matching the approval and stage services.
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
from app.core.constants import SYSTEM_USER_ID
from app.db.enums import AuditEventType, MatchStatus, SurrogateActivityType
from app.db.models import Match, StatusChangeRequest, Surrogate, SurrogateStatusHistory
from app.services import match_effects, match_participants, match_queries

UNDER_REVIEW = MatchStatus.UNDER_REVIEW.value
ACCEPTED = MatchStatus.ACCEPTED.value
CANCELLATION_PENDING = MatchStatus.CANCELLATION_PENDING.value
DECLINED = MatchStatus.DECLINED.value
CANCELLED = MatchStatus.CANCELLED.value
COMPLETED = MatchStatus.COMPLETED.value

CONCURRENT_ACCEPT_DETAIL = "Surrogate has an accepted match"


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
    # Refusal when the match is outside ``sources``. None resolves the request
    # without changing the match (approvals queue reject and withdraw).
    source_error: str | None
    history: str


TRANSITIONS: dict[str, Transition] = {
    t.action: t
    for t in (
        Transition(
            "accept",
            (UNDER_REVIEW,),
            ACCEPTED,
            "Cannot accept match with status: {status}",
            "match_accepted",
        ),
        Transition(
            "decline",
            (UNDER_REVIEW,),
            DECLINED,
            "Cannot decline match with status: {status}",
            "match_declined",
        ),
        Transition(
            "request_cancel",
            (ACCEPTED,),
            CANCELLATION_PENDING,
            "Only accepted matches can be cancelled",
            "match_cancel_requested",
        ),
        # Approvals queue (ADR 0004): the approvals service checks
        # approve_status_change_requests and owns the request record.
        Transition(
            "approve_cancel",
            (CANCELLATION_PENDING,),
            CANCELLED,
            "Match is no longer pending cancellation",
            "match_cancelled",
        ),
        Transition(
            "reject_cancel",
            (CANCELLATION_PENDING,),
            ACCEPTED,
            None,
            "match_cancel_request_rejected",
        ),
        Transition(
            "withdraw_cancel",
            (CANCELLATION_PENDING,),
            ACCEPTED,
            None,
            "match_cancel_request_withdrawn",
        ),
    )
}

# No user action offers these. The surrogate stage service applies them in its
# own transaction; a match outside ``sources`` is left unchanged. Rejecting or
# withdrawing a cancellation also completes the restored match of a surrogate
# who is in Delivered.
SYSTEM_TRANSITIONS: dict[str, Transition] = {
    t.action: t
    for t in (
        Transition("complete_on_delivery", (ACCEPTED,), COMPLETED, None, "match_completed"),
        Transition(
            "undo_delivery_completion",
            (COMPLETED,),
            ACCEPTED,
            None,
            "match_completion_undone",
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
    accept, and donor links on appointments.
    Surrogate propose, accept, decline, cancellation requests and their
    resolution, match notes, files and tasks, match links on appointments,
    and reads stay open.
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
    from app.services import permission_policy_service

    # Activation takes organization then record locks, including while still on V1.
    permission_policy_service.lock_configuration(db, match.organization_id)
    locked, competitors = _lock_match_rows(db, match, with_competitors=with_competitors)
    for party in match_participants.parties(locked):
        party.lock(db, locked)
    return locked, competitors


def lock_match(db: Session, match: Match, org_id: UUID | None = None) -> Match:
    """Lock organization, match, then parties; return the fresh match row."""
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
        "surrogate_id": str(match.surrogate_id) if match.surrogate_id else None,
        "donor_id": str(match.donor_id) if match.donor_id else None,
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
    dispatch_effects: bool = True,
) -> Match:
    """Create an under-review match. Parties may be at any stage.

    ``dispatch_effects=False`` commits the match and its history but skips
    after-commit effects such as workflow triggers. Its only caller is
    ``scripts/seed_mock_data.py``, so seeding a dev database does not run org
    workflows.
    """
    from app.services import note_service

    if not match_queries.get_intended_parent(db, intended_parent_id, org_id):
        raise TransitionError("Intended parent not found", 404)
    existing = match_queries.get_existing_match(
        db, org_id, surrogate_id, intended_parent_id, donor_id=donor_id
    )
    if existing:
        raise TransitionError(f"Match already exists with status: {existing.status}", 409)

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
            status=UNDER_REVIEW,
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
    if not dispatch_effects:
        return match
    match_effects.dispatch(
        db,
        match_effects.TransitionEvent(
            "propose",
            match,
            proposed_by_user_id,
            [
                *match_effects.workflow_trigger(db, "proposed", match),
                *match_effects.surrogate_conflict_notifications(db, match),
            ],
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
    before_commit: Callable[[], None] | None = None,
    dispatch_effects: bool = True,
) -> Match:
    """Apply one row of TRANSITIONS atomically, then dispatch its effects.

    ``request`` is the status-change request for approvals-queue actions; the
    caller locks it before calling. ``before_commit`` lets that caller resolve
    the request in the same transaction after the engine checks pass.
    ``dispatch_effects=False`` commits the transition and its history but skips
    after-commit effects. Its only caller is ``scripts/seed_mock_data.py``, so
    seeding a dev database does not run org workflows.
    """
    spec = TRANSITIONS[action]
    locked, _ = _lock(db, match, with_competitors=action == "accept" and bool(match.surrogate_id))
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
    )
    if action == "request_cancel" and locked.status == CANCELLATION_PENDING:
        raise TransitionError("A pending cancellation request already exists for this match", 409)
    if action in {"decline", "request_cancel"}:
        ctx.reason = (reason or "").strip()
        if not ctx.reason:
            label = "Decline" if action == "decline" else "Cancellation"
            raise TransitionError(f"{label} reason is required")
    applies = locked.status in spec.sources
    if not applies and spec.source_error is not None:
        raise TransitionError(spec.source_error.format(status=locked.status))

    try:
        # Keep refused stage moves atomic even when the caller retains its session.
        with db.begin_nested():
            effects = _APPLY[action](ctx) if applies else []
            if not applies:
                write_case_change(
                    db,
                    locked,
                    actor_user_id,
                    spec.history,
                    {
                        "status_request_id": str(request.id),
                        "status": locked.status,
                    },
                )
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
    if dispatch_effects:
        if action == "accept":
            effects += match_effects.surrogate_conflict_notifications(db, locked)
        match_effects.dispatch(
            db, match_effects.TransitionEvent(action, locked, actor_user_id, effects)
        )
    return locked


def check_action(db: Session, match: Match, action: str, *, actor_user_id: UUID) -> None:
    """State-based denials shared by action previews and transition execution."""
    if action == "accept":
        if match.donor_id:
            require_expansion()
        if match_queries.has_surrogate_conflict(db, match):
            raise TransitionError("Surrogate has an accepted match")
        warnings = match_participants.accept_eligibility_warnings(db, match)
        if warnings:
            raise TransitionError("; ".join(warnings))
        match_participants.check_accept_stage_changes(db, match, actor_user_id)
    elif action == "request_cancel":
        if (
            db.query(StatusChangeRequest.id)
            .filter(
                StatusChangeRequest.organization_id == match.organization_id,
                StatusChangeRequest.entity_type == "match",
                StatusChangeRequest.entity_id == match.id,
                StatusChangeRequest.status == "pending",
            )
            .first()
        ):
            raise TransitionError(
                "A pending cancellation request already exists for this match", 409
            )


def _accept(ctx: _Context) -> list:
    db, match = ctx.db, ctx.match
    primary = match_participants.primary(match)
    check_action(db, match, "accept", actor_user_id=ctx.actor_user_id)
    match.status = ACCEPTED
    # Sessions disable autoflush; the donor guard must see this acceptance
    # inside the same savepoint before the participant stage is written.
    db.flush()
    effects = primary.on_accept(
        db, match, actor_user_id=ctx.actor_user_id, actor_role=ctx.actor_role, now=ctx.now
    )
    match.reviewed_by_user_id = ctx.actor_user_id
    match.reviewed_at = ctx.now
    _append_notes(match, ctx.notes)
    match.updated_at = ctx.now
    match_participants.INTENDED_PARENT.on_accept(
        db, match, actor_user_id=ctx.actor_user_id, actor_role=ctx.actor_role, now=ctx.now
    )
    audit, party = _pair_details(match)
    write_history(
        db,
        match,
        ctx.actor_user_id,
        "match_accepted",
        audit_details=audit,
        party_details=party,
    )
    return [
        *effects,
        *match_effects.dashboard_push(db, match.organization_id),
        *match_effects.workflow_trigger(db, "accepted", match),
    ]


def _decline(ctx: _Context) -> list:
    match = ctx.match
    match.status = DECLINED
    match.closed_at = ctx.now
    match.closed_by_user_id = ctx.actor_user_id
    match.closure_reason = ctx.reason
    match.reviewed_by_user_id = ctx.actor_user_id
    match.reviewed_at = ctx.now
    match.decline_reason = ctx.reason
    _append_notes(match, ctx.notes)
    match.updated_at = ctx.now
    audit, party = _pair_details(match)
    write_history(
        ctx.db,
        match,
        ctx.actor_user_id,
        "match_declined",
        audit_details={**audit, "decline_reason_provided": bool(ctx.reason)},
        party_details={**party, "decline_reason": ctx.reason},
    )
    return match_effects.workflow_trigger(ctx.db, "declined", match)


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
    match.status = CANCELLATION_PENDING
    match.updated_at = ctx.now
    write_case_change(db, match, ctx.actor_user_id, "match_cancel_requested")
    return match_effects.cancel_request_pending_notification(db, match, request, ctx.actor_user_id)


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
        *match_effects.workflow_trigger(db, "cancelled", match),
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
    if match.surrogate_id:
        from app.services import pipeline_service

        # _lock refreshed the surrogate row under its lock, so its stage is current.
        surrogate = ctx.db.get(Surrogate, match.surrogate_id)
        stage = pipeline_service.get_stage_by_id(ctx.db, surrogate.stage_id)
        if stage is not None and _is_delivered(stage):
            # Delivery left the match pending; it completes once the request is resolved.
            _complete(ctx.db, match, stage, _system_actor(ctx.actor_user_id), ctx.now)
    return []


_APPLY: dict[str, Callable[[_Context], list]] = {
    "accept": _accept,
    "decline": _decline,
    "request_cancel": _request_cancel,
    "approve_cancel": _approve_cancel,
    "reject_cancel": _restore_accepted,
    "withdraw_cancel": _restore_accepted,
}


# =============================================================================
# Surrogate Delivered stage (system transitions)
# =============================================================================
#
# surrogate_status_service.apply_status_change, and the legacy direct stage
# writes of v1 workflows and AI actions, call these before they write the
# surrogate row; the caller commits the stage move and the match together.
# Lock order therefore matches ``transition``: the organization configuration
# (permission v2), then the surrogate's match rows FOR UPDATE in id order, then
# the surrogate row, which the stage write locks with its UPDATE. The intended
# parent row is not locked; its activity insert takes only FOR KEY SHARE.


def _system_actor(actor_user_id: UUID | None) -> UUID | None:
    """The workflow system user is not recorded as the closing user."""
    return None if actor_user_id == SYSTEM_USER_ID else actor_user_id


def _is_delivered(stage) -> bool:
    from app.core.stage_definitions import SURROGATE_PIPELINE_ENTITY
    from app.services import pipeline_service

    return pipeline_service.stage_matches_system_role(stage, "delivered", SURROGATE_PIPELINE_ENTITY)


def _lock_surrogate_matches(
    db: Session, surrogate, statuses: tuple[str, ...], *, closed_since: datetime | None = None
) -> list[Match]:
    from app.services import permission_policy_service

    permission_policy_service.lock_configuration(db, surrogate.organization_id)
    query = db.query(Match).filter(
        Match.organization_id == surrogate.organization_id,
        Match.surrogate_id == surrogate.id,
        Match.status.in_(statuses),
    )
    if closed_since is not None:
        query = query.filter(Match.closed_at >= closed_since)
    return query.order_by(Match.id).populate_existing().with_for_update().all()


def _complete(db: Session, match: Match, delivered_stage, actor: UUID | None, now: datetime):
    from app.services import match_attempts

    spec = SYSTEM_TRANSITIONS["complete_on_delivery"]
    match.status = spec.target
    match.closed_at = now
    match.closed_by_user_id = actor
    match.closure_reason = None
    match.outcome = delivered_stage.label
    match.updated_at = now
    match_attempts.close_open_attempts(db, match, now)
    write_case_change(db, match, actor, spec.history)


def complete_on_delivery(
    db: Session, surrogate, new_stage, *, actor_user_id: UUID | None, now: datetime
) -> list[Match]:
    """Complete the surrogate's accepted match when she enters the Delivered stage.

    The Delivered stage label becomes the outcome and open attempts close.
    Cancellation-pending matches stay pending; rejecting or withdrawing the
    request later completes them (``_restore_accepted``). Does not commit.
    """
    if not _is_delivered(new_stage):
        return []
    spec = SYSTEM_TRANSITIONS["complete_on_delivery"]
    actor = _system_actor(actor_user_id)
    # Lock pending matches too: a cancellation resolved concurrently must either see
    # this stage move or be seen here once it restores the match to accepted.
    locked = _lock_surrogate_matches(db, surrogate, match_queries.COMMITTED_STATUSES)
    matches = [match for match in locked if match.status in spec.sources]
    for match in matches:
        _complete(db, match, new_stage, actor, now)
    return matches


def _completed_by_delivery(db: Session, surrogate, current_stage, *, lock: bool) -> Match | None:
    """The match completed by the surrogate's latest entry into Delivered, if it can be
    accepted again without colliding with another committed or open match."""
    if not _is_delivered(current_stage):
        return None
    entry = (
        db.query(SurrogateStatusHistory)
        .filter(
            SurrogateStatusHistory.organization_id == surrogate.organization_id,
            SurrogateStatusHistory.surrogate_id == surrogate.id,
        )
        .order_by(SurrogateStatusHistory.recorded_at.desc())
        .first()
    )
    if entry is None or entry.to_stage_id != current_stage.id:
        return None
    # Only a Delivered entry completes a surrogate match, at or after the entry's
    # recorded time, so a match completed since then was completed by this entry.
    sources = SYSTEM_TRANSITIONS["undo_delivery_completion"].sources
    if lock:
        candidates = _lock_surrogate_matches(db, surrogate, sources, closed_since=entry.recorded_at)
    else:
        candidates = (
            db.query(Match)
            .filter(
                Match.organization_id == surrogate.organization_id,
                Match.surrogate_id == surrogate.id,
                Match.status.in_(sources),
                Match.closed_at >= entry.recorded_at,
            )
            .all()
        )
    match = max(candidates, key=lambda row: row.closed_at, default=None)
    if match is None:
        return None
    if match_queries.get_accepted_match_for_surrogate(db, match.organization_id, surrogate.id):
        return None
    if match_queries.get_existing_match(
        db, match.organization_id, surrogate.id, match.intended_parent_id
    ):
        return None
    return match


def can_undo_delivery_completion(db: Session, surrogate, current_stage) -> bool:
    """Read-only: undoing the current Delivered entry would restore an accepted match."""
    return _completed_by_delivery(db, surrogate, current_stage, lock=False) is not None


def undo_delivery_completion(
    db: Session, surrogate, current_stage, *, actor_user_id: UUID | None, now: datetime
) -> Match | None:
    """Restore the match completed by the Delivered entry being undone.

    Clears the closure fields. Attempts closed at completion stay cancelled.
    Does nothing when the match is no longer completed or the surrogate or the
    pair has another committed or open match. Does not commit.
    """
    match = _completed_by_delivery(db, surrogate, current_stage, lock=True)
    if match is None:
        return None
    spec = SYSTEM_TRANSITIONS["undo_delivery_completion"]
    match.status = spec.target
    match.closed_at = None
    match.closed_by_user_id = None
    match.closure_reason = None
    match.outcome = None
    match.updated_at = now
    # Sessions disable autoflush; later reads in this stage change must see the match.
    db.flush()
    write_case_change(db, match, _system_actor(actor_user_id), spec.history)
    return match


def update_notes(db: Session, match: Match, *, notes: str) -> Match:
    """Replace match notes; not a status change."""
    from app.services import note_service

    match.notes = note_service.sanitize_html(notes)
    match.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(match)
    return match
