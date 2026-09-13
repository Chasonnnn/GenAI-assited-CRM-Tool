"""Match service - query helpers for matches and match events."""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, asc, desc, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.stage_definitions import INTENDED_PARENT_PIPELINE_ENTITY
from app.db.enums import AuditEventType, MatchStatus, SurrogateActivityType
from app.db.models import (
    Donor,
    IntendedParent,
    Match,
    MatchAttempt,
    MatchEvent,
    StatusChangeRequest,
    Surrogate,
)
from app.utils.normalization import escape_like_string, normalize_identifier, normalize_search_text
from app.utils.pagination import paginate_query_by_offset


def _log_intended_parent_match_activity(
    db: Session,
    *,
    org_id: UUID,
    intended_parent_id: UUID,
    match_id: UUID,
    surrogate_id: UUID | None,
    activity_type: str,
    actor_user_id: UUID | None,
) -> None:
    """Mirror applicable match lifecycle events into the Intended Parent feed."""
    from app.services import entity_activity_service

    entity_activity_service.record_activity(
        db,
        org_id=org_id,
        entity_type="intended_parent",
        entity_id=intended_parent_id,
        activity_type=activity_type,
        actor_user_id=actor_user_id,
        details={
            "match_id": str(match_id),
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
        },
    )


def generate_match_number(db: Session, org_id: UUID) -> str:
    """
    Generate next sequential match number for org (M10001+).

    Uses atomic INSERT...ON CONFLICT for race-condition-free counter increment.
    """
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


def get_surrogate_with_stage(
    db: Session,
    surrogate_id: UUID,
    org_id: UUID | None = None,
) -> Surrogate | None:
    """Get surrogate with stage loaded, optionally org-scoped."""
    filters = [Surrogate.id == surrogate_id]
    if org_id:
        filters.append(Surrogate.organization_id == org_id)
    return db.query(Surrogate).options(joinedload(Surrogate.stage)).filter(*filters).first()


def get_intended_parent(
    db: Session,
    intended_parent_id: UUID,
    org_id: UUID | None = None,
) -> IntendedParent | None:
    """Get intended parent, optionally org-scoped."""
    filters = [IntendedParent.id == intended_parent_id]
    if org_id:
        filters.append(IntendedParent.organization_id == org_id)
    return (
        db.query(IntendedParent).options(joinedload(IntendedParent.stage)).filter(*filters).first()
    )


def get_match(
    db: Session,
    match_id: UUID,
    org_id: UUID,
) -> Match | None:
    """Get match by ID (org-scoped)."""
    return (
        db.query(Match)
        .filter(
            Match.id == match_id,
            Match.organization_id == org_id,
        )
        .first()
    )


def get_existing_match(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID | None,
    intended_parent_id: UUID,
    donor_id: UUID | None = None,
) -> Match | None:
    """Find an existing match for a surrogate/IP in org."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.donor_id == donor_id,
            Match.intended_parent_id == intended_parent_id,
            Match.status.in_(OPEN_STATUSES),
        )
        .first()
    )


def get_accepted_match_for_surrogate(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
) -> Match | None:
    """Get accepted match for a surrogate (org-scoped)."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    )


def get_accepted_match_for_intended_parent(
    db: Session,
    org_id: UUID,
    intended_parent_id: UUID,
) -> Match | None:
    """Get accepted match for an intended parent (org-scoped)."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.intended_parent_id == intended_parent_id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    )


def list_matches(
    db: Session,
    org_id: UUID,
    status_filter: str | None = None,
    donor_id: UUID | None = None,
    match_kind: str | None = None,
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
    session=None,
) -> tuple[list[Match], int]:
    """List matches with filters and pagination."""
    query = db.query(Match).filter(Match.organization_id == org_id)
    if session is not None:
        query = query.filter(match_visibility_filter(db, session))

    if donor_id:
        query = query.filter(Match.donor_id == donor_id)
    if match_kind:
        query = query.filter(Match.match_kind == match_kind)
    if status_filter:
        query = query.filter(Match.status == status_filter)
    if surrogate_id:
        query = query.filter(Match.surrogate_id == surrogate_id)
    if intended_parent_id:
        query = query.filter(Match.intended_parent_id == intended_parent_id)

    if q:
        normalized_text = normalize_search_text(q)
        normalized_identifier = normalize_identifier(q) or q
        escaped_identifier = escape_like_string(normalized_identifier)
        escaped_text = escape_like_string(normalized_text or normalized_identifier)
        query = (
            query.join(Surrogate, Match.surrogate_id == Surrogate.id, isouter=True)
            .join(Donor, Match.donor_id == Donor.id, isouter=True)
            .join(
                IntendedParent,
                Match.intended_parent_id == IntendedParent.id,
                isouter=True,
            )
            .filter(
                or_(
                    Donor.full_name.ilike(f"%{escaped_text}%", escape="\\"),
                    Donor.donor_number.ilike(f"%{escaped_identifier}%", escape="\\"),
                    Match.match_number.ilike(f"%{escaped_identifier}%", escape="\\"),
                    Surrogate.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\"),
                    Surrogate.surrogate_number_normalized.ilike(
                        f"%{escaped_identifier}%", escape="\\"
                    ),
                    IntendedParent.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\"),
                    IntendedParent.intended_parent_number_normalized.ilike(
                        f"%{escaped_identifier}%", escape="\\"
                    ),
                )
            )
        )

    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "match_number": Match.match_number,
        "status": Match.status,
        "proposed_at": Match.proposed_at,
        "created_at": Match.created_at,
    }

    if sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        query = query.order_by(Match.proposed_at.desc())

    offset = (page - 1) * per_page
    matches, total = paginate_query_by_offset(query, offset=offset, limit=per_page)
    return matches, total


def get_surrogates_with_stage_by_ids(
    db: Session,
    org_id: UUID,
    surrogate_ids: set[UUID],
) -> dict[UUID, Surrogate]:
    """Batch load surrogates with stages for match list."""
    if not surrogate_ids:
        return {}
    surrogates = (
        db.query(Surrogate)
        .options(joinedload(Surrogate.stage))
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.id.in_(surrogate_ids),
        )
        .all()
    )
    return {surrogate.id: surrogate for surrogate in surrogates}


def get_intended_parents_by_ids(
    db: Session,
    org_id: UUID,
    intended_parent_ids: set[UUID],
) -> dict[UUID, IntendedParent]:
    """Batch load intended parents for match list."""
    if not intended_parent_ids:
        return {}
    ips = (
        db.query(IntendedParent)
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.id.in_(intended_parent_ids),
        )
        .all()
    )
    return {ip.id: ip for ip in ips}


def get_match_stats(
    db: Session,
    org_id: UUID,
    session=None,
) -> tuple[int, dict[str, int]]:
    """Return total matches and counts by status."""
    counts = {status.value: 0 for status in MatchStatus}
    rows = (
        db.query(Match.status, func.count(Match.id))
        .filter(
            Match.organization_id == org_id,
            match_visibility_filter(db, session) if session else True,
        )
        .group_by(Match.status)
        .all()
    )

    for status, count in rows:
        status_key = status.value if hasattr(status, "value") else status
        counts[status_key] = count

    total = sum(counts.values())
    return total, counts


def list_pending_matches_for_surrogate(
    db: Session,
    surrogate_id: UUID,
    exclude_match_id: UUID | None = None,
) -> list[Match]:
    """List proposed/reviewing matches for a surrogate, excluding one."""
    query = db.query(Match).filter(
        Match.surrogate_id == surrogate_id,
        Match.status.in_([MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]),
    )
    if exclude_match_id:
        query = query.filter(Match.id != exclude_match_id)
    return query.all()


def list_match_events(
    db: Session,
    match_id: UUID,
    person_type: str | None = None,
    event_type: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    from_day: date | None = None,
    to_day: date | None = None,
) -> list[MatchEvent]:
    """List match events with optional filters."""
    query = db.query(MatchEvent).filter(MatchEvent.match_id == match_id)

    if person_type:
        query = query.filter(MatchEvent.person_type == person_type)
    if event_type:
        query = query.filter(MatchEvent.event_type == event_type)

    if from_dt or to_dt or from_day or to_day:
        date_filters = []

        timed_filters = []
        if from_dt:
            timed_filters.append(MatchEvent.starts_at >= from_dt)
        if to_dt:
            timed_filters.append(MatchEvent.starts_at < to_dt)
        if timed_filters:
            date_filters.append(and_(MatchEvent.starts_at.isnot(None), *timed_filters))

        all_day_filters = [
            MatchEvent.all_day.is_(True),
            MatchEvent.start_date.isnot(None),
        ]
        if to_day:
            all_day_filters.append(MatchEvent.start_date <= to_day)
        if from_day:
            all_day_filters.append(
                func.coalesce(MatchEvent.end_date, MatchEvent.start_date) >= from_day
            )
        date_filters.append(and_(*all_day_filters))

        query = query.filter(or_(*date_filters))

    return query.order_by(MatchEvent.starts_at, MatchEvent.start_date).all()


def get_match_event(
    db: Session,
    match_id: UUID,
    event_id: UUID,
    org_id: UUID,
) -> MatchEvent | None:
    """Get a match event by ID (org-scoped)."""
    return (
        db.query(MatchEvent)
        .filter(
            MatchEvent.id == event_id,
            MatchEvent.match_id == match_id,
            MatchEvent.organization_id == org_id,
        )
        .first()
    )


def create_match(
    db: Session,
    *,
    org_id: UUID,
    surrogate_id: UUID | None,
    intended_parent_id: UUID,
    proposed_by_user_id: UUID,
    donor_id: UUID | None = None,
    compatibility_score: float | None = None,
    notes: str | None = None,
) -> Match:
    """Create a proposed match and log activity."""
    from app.services import audit_service, note_service

    if (surrogate_id is None) == (donor_id is None):
        raise ValueError("Exactly one surrogate or donor is required")
    participant = (
        get_donor(db, donor_id, org_id)
        if donor_id
        else get_surrogate_with_stage(db, surrogate_id, org_id)
    )
    if not participant or not get_intended_parent(db, intended_parent_id, org_id):
        raise ValueError("Match participants not found")
    from app.core.match_rollout import require_match_expansion

    if donor_id or (
        db.query(Match.id)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.intended_parent_id == intended_parent_id,
        )
        .first()
    ):
        require_match_expansion()
    clean_notes = note_service.sanitize_html(notes) if notes else None

    match = Match(
        organization_id=org_id,
        match_number=generate_match_number(db, org_id),
        surrogate_id=surrogate_id,
        donor_id=donor_id,
        match_kind="donor" if donor_id else "surrogate",
        intended_parent_id=intended_parent_id,
        status=MatchStatus.PROPOSED.value,
        proposed_by_user_id=proposed_by_user_id,
        notes=clean_notes,
    )
    db.add(match)
    db.flush()

    _log_party_activity(
        db=db,
        surrogate_id=surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.MATCH_PROPOSED,
        actor_user_id=proposed_by_user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(intended_parent_id),
        },
    )
    _log_intended_parent_match_activity(
        db,
        org_id=org_id,
        intended_parent_id=intended_parent_id,
        match_id=match.id,
        surrogate_id=surrogate_id,
        activity_type="match_proposed",
        actor_user_id=proposed_by_user_id,
    )

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.MATCH_PROPOSED,
        actor_user_id=proposed_by_user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(surrogate_id),
            "intended_parent_id": str(intended_parent_id),
        },
    )

    db.commit()
    db.refresh(match)
    return match


def mark_match_reviewing_if_needed(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    org_id: UUID,
) -> Match:
    """Auto-transition match to reviewing if viewed by non-proposer."""
    if match.status == MatchStatus.PROPOSED.value and match.proposed_by_user_id != actor_user_id:
        participant = (
            get_donor(db, match.donor_id, org_id)
            if match.donor_id
            else get_surrogate_with_stage(db, match.surrogate_id, org_id)
        )
        ip = get_intended_parent(db, match.intended_parent_id, org_id)
        if (participant and participant.is_archived) or (ip and ip.is_archived):
            return match
        match = lock_match(db, match, org_id)
        if match.status != MatchStatus.PROPOSED.value:
            return match
        match.status = MatchStatus.REVIEWING.value
        match.reviewed_by_user_id = actor_user_id
        match.reviewed_at = datetime.now(UTC)
        match.updated_at = datetime.now(UTC)

        _log_party_activity(
            db=db,
            surrogate_id=match.surrogate_id,
            organization_id=org_id,
            activity_type=SurrogateActivityType.MATCH_REVIEWING,
            actor_user_id=actor_user_id,
            details={
                "match_id": str(match.id),
                "intended_parent_id": str(match.intended_parent_id),
            },
        )
        _log_intended_parent_match_activity(
            db,
            org_id=org_id,
            intended_parent_id=match.intended_parent_id,
            match_id=match.id,
            surrogate_id=match.surrogate_id,
            activity_type="match_reviewing",
            actor_user_id=actor_user_id,
        )

        db.commit()
        db.refresh(match)

    return match


def accept_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    actor_role: str,
    org_id: UUID,
    notes: str | None = None,
) -> Match:
    """Accept a match and apply related side effects."""
    match = lock_match(db, match, org_id)
    from app.core.match_rollout import require_match_expansion

    if match.donor_id or (
        db.query(Match.id)
        .filter(
            Match.organization_id == org_id,
            Match.intended_parent_id == match.intended_parent_id,
            Match.id != match.id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    ):
        require_match_expansion()
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot accept match with status: {match.status}")

    from app.services import (
        audit_service,
        dashboard_service,
        note_service,
        pipeline_service,
        surrogate_status_service,
    )

    stage_event = None
    surrogate = (
        get_surrogate_with_stage(db, match.surrogate_id, org_id) if match.surrogate_id else None
    )
    if surrogate:
        db.query(Surrogate).filter(
            Surrogate.id == surrogate.id, Surrogate.organization_id == org_id
        ).with_for_update().one()
        committed = get_accepted_match_for_surrogate(db, org_id, surrogate.id)
        if committed and committed.id != match.id:
            raise ValueError("Surrogate already has an accepted match")
        current_stage = surrogate.stage
        pipeline_id = current_stage.pipeline_id if current_stage else None
        if not pipeline_id:
            pipeline_id = pipeline_service.get_or_create_default_pipeline(
                db,
                org_id,
                actor_user_id,
            ).id
        matched_stage = pipeline_service.get_stage_by_system_role(
            db,
            pipeline_id,
            "matched",
        )
        if matched_stage and surrogate.stage_id != matched_stage.id:
            result = surrogate_status_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=matched_stage.id,
                user_id=actor_user_id,
                user_role=actor_role,
                reason="Match accepted",
                commit=False,
            )
            stage_event = result.get("after_commit")
            if result["status"] != "applied":
                db.rollback()
                raise ValueError("Surrogate stage requires approval before accepting this match")

    match.status = MatchStatus.ACCEPTED.value
    match.reviewed_by_user_id = actor_user_id
    match.reviewed_at = datetime.now(UTC)
    if notes:
        clean_notes = note_service.sanitize_html(notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(UTC)

    ip = get_intended_parent(db, match.intended_parent_id, org_id)
    if ip:
        from app.services import intended_parent_status_service

        current_ip_stage = intended_parent_status_service.get_current_stage(db, ip)
        if not pipeline_service.stage_matches_system_role(
            current_ip_stage,
            "matched",
            INTENDED_PARENT_PIPELINE_ENTITY,
        ):
            ip_pipeline_id = current_ip_stage.pipeline_id
            matched_ip_stage = pipeline_service.get_stage_by_system_role(
                db,
                ip_pipeline_id,
                "matched",
                INTENDED_PARENT_PIPELINE_ENTITY,
            )
            if matched_ip_stage and current_ip_stage.order < matched_ip_stage.order:
                intended_parent_status_service.apply_status_change(
                    db=db,
                    ip=ip,
                    old_stage=current_ip_stage,
                    new_stage=matched_ip_stage,
                    user_id=actor_user_id,
                    reason="Match accepted",
                    effective_at=datetime.now(UTC),
                    recorded_at=datetime.now(UTC),
                    commit=False,
                )

    other_matches = (
        list_pending_matches_for_surrogate(
            db=db,
            surrogate_id=match.surrogate_id,
            exclude_match_id=match.id,
        )
        if match.surrogate_id
        else []
    )
    for other in other_matches:
        other.status = MatchStatus.CANCELLED.value
        other.closed_at = datetime.now(UTC)
        other.closed_by_user_id = actor_user_id
        other.closure_reason = "Another match accepted"
        other.updated_at = datetime.now(UTC)
        _log_case_change(db, other, actor_user_id, "match_cancelled")

    _log_party_activity(
        db=db,
        surrogate_id=match.surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.MATCH_ACCEPTED,
        actor_user_id=actor_user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
            "cancelled_matches": len(other_matches),
        },
    )
    _log_intended_parent_match_activity(
        db,
        org_id=org_id,
        intended_parent_id=match.intended_parent_id,
        match_id=match.id,
        surrogate_id=match.surrogate_id,
        activity_type="match_accepted",
        actor_user_id=actor_user_id,
    )

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.MATCH_ACCEPTED,
        actor_user_id=actor_user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id),
            "cancelled_matches": len(other_matches),
        },
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(match)
    if stage_event:
        stage_event()
    dashboard_service.push_dashboard_stats(db, org_id)
    return match


def reject_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    org_id: UUID,
    rejection_reason: str,
    notes: str | None = None,
) -> Match:
    """Reject a match with reason and log activity."""
    match = lock_match(db, match, org_id)
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot reject match with status: {match.status}")

    from app.services import audit_service, note_service

    match.status = MatchStatus.REJECTED.value
    match.closed_at = datetime.now(UTC)
    match.closed_by_user_id = actor_user_id
    match.closure_reason = rejection_reason
    match.reviewed_by_user_id = actor_user_id
    match.reviewed_at = datetime.now(UTC)
    match.rejection_reason = rejection_reason
    if notes:
        clean_notes = note_service.sanitize_html(notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(UTC)

    _log_party_activity(
        db=db,
        surrogate_id=match.surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.MATCH_REJECTED,
        actor_user_id=actor_user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
            "rejection_reason": rejection_reason,
        },
    )
    _log_intended_parent_match_activity(
        db,
        org_id=org_id,
        intended_parent_id=match.intended_parent_id,
        match_id=match.id,
        surrogate_id=match.surrogate_id,
        activity_type="match_rejected",
        actor_user_id=actor_user_id,
    )

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.MATCH_REJECTED,
        actor_user_id=actor_user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id),
            "rejection_reason_provided": bool(rejection_reason),
        },
    )

    db.commit()
    db.refresh(match)
    return match


def request_cancel_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    org_id: UUID,
    reason: str | None = None,
) -> Match:
    """Create a pending cancellation request for an accepted match."""
    match = lock_match(db, match, org_id)
    if match.status != MatchStatus.ACCEPTED.value:
        raise ValueError("Only accepted matches can be cancelled")

    existing_request = (
        db.query(StatusChangeRequest)
        .filter(
            StatusChangeRequest.organization_id == org_id,
            StatusChangeRequest.entity_type == "match",
            StatusChangeRequest.entity_id == match.id,
            StatusChangeRequest.status == "pending",
        )
        .first()
    )
    if existing_request:
        raise ValueError("A pending cancellation request already exists for this match")

    now = datetime.now(UTC)
    request = StatusChangeRequest(
        organization_id=org_id,
        entity_type="match",
        entity_id=match.id,
        target_status=MatchStatus.CANCELLED.value,
        effective_at=now,
        reason=(reason or "").strip(),
        requested_by_user_id=actor_user_id,
        requested_at=now,
        status="pending",
    )
    db.add(request)

    match.status = MatchStatus.CANCEL_PENDING.value
    match.updated_at = now
    _log_case_change(db, match, actor_user_id, "match_cancel_requested")

    db.commit()
    db.refresh(match)
    db.refresh(request)

    from app.services import notification_facade, user_service

    surrogate = (
        get_donor(db, match.donor_id, org_id)
        if match.donor_id
        else get_surrogate_with_stage(db, match.surrogate_id, org_id)
    )
    intended_parent = get_intended_parent(db, match.intended_parent_id, org_id)
    requester = user_service.get_user_by_id(db, actor_user_id)
    requester_name = requester.display_name if requester else "Someone"

    if surrogate and intended_parent:
        notification_facade.notify_match_cancel_request_pending(
            db=db,
            request=request,
            match=match,
            surrogate=surrogate,
            intended_parent=intended_parent,
            requester_name=requester_name,
        )

    return match


def cancel_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    org_id: UUID,
) -> None:
    """Cancel a proposed/reviewing match."""
    match = lock_match(db, match, org_id)
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot cancel match with status: {match.status}")

    from app.services import audit_service

    match.status = MatchStatus.CANCELLED.value
    match.closed_at = datetime.now(UTC)
    match.closed_by_user_id = actor_user_id
    match.updated_at = datetime.now(UTC)

    _log_party_activity(
        db=db,
        surrogate_id=match.surrogate_id,
        organization_id=org_id,
        activity_type=SurrogateActivityType.MATCH_CANCELLED,
        actor_user_id=actor_user_id,
        details={
            "match_id": str(match.id),
            "intended_parent_id": str(match.intended_parent_id),
        },
    )
    _log_intended_parent_match_activity(
        db,
        org_id=org_id,
        intended_parent_id=match.intended_parent_id,
        match_id=match.id,
        surrogate_id=match.surrogate_id,
        activity_type="match_cancelled",
        actor_user_id=actor_user_id,
    )

    audit_service.log_event(
        db=db,
        org_id=org_id,
        event_type=AuditEventType.MATCH_CANCELLED,
        actor_user_id=actor_user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id),
        },
    )

    db.commit()


def update_match_notes(
    db: Session,
    match: Match,
    *,
    notes: str,
) -> Match:
    """Update match notes."""
    from app.services import note_service

    match.notes = note_service.sanitize_html(notes)
    match.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(match)
    return match


def create_match_event(
    db: Session,
    *,
    org_id: UUID,
    match_id: UUID,
    created_by_user_id: UUID,
    person_type: str,
    event_type: str,
    title: str,
    description: str | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    timezone: str,
    all_day: bool,
    start_date: date | None,
    end_date: date | None,
) -> MatchEvent:
    """Create a match event."""
    event = MatchEvent(
        organization_id=org_id,
        match_id=match_id,
        person_type=person_type,
        event_type=event_type,
        title=title,
        description=description,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=timezone,
        all_day=all_day,
        start_date=start_date,
        end_date=end_date,
        created_by_user_id=created_by_user_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_match_event(
    db: Session,
    event: MatchEvent,
    *,
    person_type: str | None = None,
    event_type: str | None = None,
    title: str | None = None,
    description: str | None = None,
    tz_name: str | None = None,
    all_day: bool,
    start_date: date | None,
    end_date: date | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> MatchEvent:
    """Update a match event."""
    if person_type is not None:
        event.person_type = person_type
    if event_type is not None:
        event.event_type = event_type
    if title is not None:
        event.title = title
    if description is not None:
        event.description = description
    if tz_name is not None:
        event.timezone = tz_name

    event.all_day = all_day
    if all_day:
        event.start_date = start_date
        event.end_date = end_date
        event.starts_at = None
        event.ends_at = None
    else:
        event.start_date = None
        event.end_date = None
        event.starts_at = starts_at
        event.ends_at = ends_at

    event.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    return event


def delete_match_event(db: Session, event: MatchEvent) -> None:
    """Delete a match event."""
    db.delete(event)
    db.commit()


OPEN_STATUSES = ("proposed", "reviewing", "accepted", "cancel_pending")
COMMITTED_STATUSES = ("accepted", "cancel_pending")


def get_donor(db: Session, donor_id: UUID | None, org_id: UUID) -> Donor | None:
    return (
        db.query(Donor)
        .options(joinedload(Donor.stage))
        .filter(Donor.id == donor_id, Donor.organization_id == org_id)
        .first()
    )


def get_match_with_access(
    db: Session, session, match_id: UUID, *, write: bool = False, allow_archived: bool = False
) -> Match:
    """Resolve exact case and both records under authenticated membership."""
    from fastapi import HTTPException

    from app.core.policies import POLICIES
    from app.services import permission_service, record_access_service

    match = get_match(db, match_id, session.org_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    policy = POLICIES["matches"]
    required = [policy.default]
    if write:
        required.append(policy.actions["propose"])
    for permission in required:
        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, permission.value
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission.value}")
    record_access_service.get_record_with_access(
        db, session, "intended_parent", match.intended_parent_id
    )
    record_access_service.get_record_with_access(
        db,
        session,
        "donor" if match.donor_id else "surrogate",
        match.donor_id or match.surrogate_id,
        allow_archived=allow_archived and not write,
    )
    return match


def lock_match(db: Session, match: Match, org_id: UUID) -> Match:
    # Shared surrogate first, then IP, then case. Cancelling competing proposals
    # also writes IP activity FKs, so taking other IP locks first could deadlock.
    if match.surrogate_id:
        db.query(Surrogate.id).filter(
            Surrogate.id == match.surrogate_id, Surrogate.organization_id == org_id
        ).with_for_update().one()
    db.query(IntendedParent).filter(
        IntendedParent.id == match.intended_parent_id, IntendedParent.organization_id == org_id
    ).with_for_update().one()
    return (
        db.query(Match)
        .filter(Match.id == match.id, Match.organization_id == org_id)
        .populate_existing()
        .with_for_update()
        .one()
    )


def _log_party_activity(
    *, db: Session, surrogate_id, organization_id, activity_type, actor_user_id, details
):
    from app.services import activity_service, entity_activity_service

    if surrogate_id:
        return activity_service.log_activity(
            db=db,
            surrogate_id=surrogate_id,
            organization_id=organization_id,
            activity_type=SurrogateActivityType(activity_type),
            actor_user_id=actor_user_id,
            details=details,
        )
    match = get_match(db, UUID(details["match_id"]), organization_id)
    if match and match.donor_id:
        return entity_activity_service.record_activity(
            db,
            org_id=organization_id,
            entity_type="donor",
            entity_id=match.donor_id,
            activity_type=activity_type.value if hasattr(activity_type, "value") else activity_type,
            actor_user_id=actor_user_id,
            details={
                k: v
                for k, v in details.items()
                if k in {"match_id", "attempt_id", "intended_parent_id"}
            },
        )


def _log_case_change(
    db: Session, match: Match, actor_user_id: UUID, event: str, details: dict | None = None
) -> None:
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
    _log_party_activity(
        db=db,
        surrogate_id=match.surrogate_id,
        organization_id=match.organization_id,
        activity_type=event,
        actor_user_id=actor_user_id,
        details=data,
    )
    _log_intended_parent_match_activity(
        db,
        org_id=match.organization_id,
        intended_parent_id=match.intended_parent_id,
        match_id=match.id,
        surrogate_id=match.surrogate_id,
        activity_type=event,
        actor_user_id=actor_user_id,
    )


def complete_match(
    db: Session,
    match: Match,
    *,
    actor_user_id: UUID,
    org_id: UUID,
    outcome: str,
    reason: str | None = None,
) -> Match:
    from app.core.match_rollout import require_match_expansion

    require_match_expansion()
    match = lock_match(db, match, org_id)
    if match.status != MatchStatus.ACCEPTED.value:
        raise ValueError("Only accepted matches can be completed")
    if not outcome.strip():
        raise ValueError("Completion outcome is required")
    if (
        db.query(MatchAttempt.id)
        .filter(
            MatchAttempt.organization_id == org_id,
            MatchAttempt.match_id == match.id,
            MatchAttempt.status.in_(("planned", "in_progress")),
        )
        .first()
    ):
        raise ValueError("Finish or cancel open attempts before completing the match")
    match.status = MatchStatus.COMPLETED.value
    match.closed_at = datetime.now(UTC)
    match.closed_by_user_id = actor_user_id
    match.closure_reason = reason.strip() if reason else None
    match.outcome = outcome.strip()
    match.updated_at = datetime.now(UTC)
    _log_case_change(db, match, actor_user_id, "match_completed")
    db.commit()
    db.refresh(match)
    return match


def list_attempts(db: Session, match: Match) -> list[MatchAttempt]:
    return (
        db.query(MatchAttempt)
        .filter(
            MatchAttempt.organization_id == match.organization_id, MatchAttempt.match_id == match.id
        )
        .order_by(MatchAttempt.sequence)
        .all()
    )


def save_attempt(
    db: Session, match: Match, *, actor_user_id: UUID, values: dict, attempt_id: UUID | None = None
) -> MatchAttempt:
    from app.core.match_rollout import require_match_expansion

    require_match_expansion()
    match = lock_match(db, match, match.organization_id)
    if match.status != MatchStatus.ACCEPTED.value:
        raise ValueError("Only accepted matches can change attempts")
    attempt = None
    if attempt_id:
        attempt = (
            db.query(MatchAttempt)
            .filter(
                MatchAttempt.id == attempt_id,
                MatchAttempt.match_id == match.id,
                MatchAttempt.organization_id == match.organization_id,
            )
            .first()
        )
        if not attempt:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Attempt not found")
    next_started_at = values.get("started_at", attempt.started_at if attempt else None)
    next_ended_at = values.get("ended_at", attempt.ended_at if attempt else None)
    next_type = values.get("attempt_type", attempt.attempt_type if attempt else None)
    if next_started_at and next_ended_at and next_ended_at < next_started_at:
        raise ValueError("End date must be on or after start date")
    if next_type == "embryo_transfer" and match.match_kind != "surrogate":
        raise ValueError("Embryo transfers belong to surrogate cases")
    if next_type in ("retrieval", "collection") and match.match_kind != "donor":
        raise ValueError("Retrieval and collection attempts belong to donor cases")
    if attempt is None:
        sequence = (
            db.query(func.max(MatchAttempt.sequence))
            .filter(
                MatchAttempt.match_id == match.id,
                MatchAttempt.organization_id == match.organization_id,
            )
            .scalar()
            or 0
        ) + 1
        attempt = MatchAttempt(
            organization_id=match.organization_id,
            match_id=match.id,
            sequence=sequence,
            created_by_user_id=actor_user_id,
            status="planned",
        )
        db.add(attempt)
    for key, value in values.items():
        setattr(attempt, key, value)
    attempt.updated_at = datetime.now(UTC)
    db.flush()
    _log_case_change(
        db,
        match,
        actor_user_id,
        "match_attempt_updated" if attempt_id else "match_attempt_created",
        {"attempt_id": str(attempt.id)},
    )
    db.commit()
    db.refresh(attempt)
    return attempt


def apply_approved_cancellation(
    db: Session, match: Match, *, request: StatusChangeRequest, actor_user_id: UUID
):
    """Apply cancellation in the approval owner's transaction."""
    from app.services import (
        intended_parent_status_service,
        pipeline_service,
        surrogate_status_service,
    )

    match = lock_match(db, match, match.organization_id)
    if match.status != MatchStatus.CANCEL_PENDING.value:
        raise ValueError("Match is no longer pending cancellation")
    ip = get_intended_parent(db, match.intended_parent_id, match.organization_id)
    if not ip:
        raise ValueError("Match participants not found")
    now = datetime.now(UTC)
    event = None
    if match.surrogate_id:
        surrogate = get_surrogate_with_stage(db, match.surrogate_id, match.organization_id)
        if not surrogate or not surrogate.stage:
            raise ValueError("Match participants not found")
        old_stage = surrogate.stage
        ready = pipeline_service.get_stage_by_system_role(db, old_stage.pipeline_id, "handoff")
        if not ready:
            raise ValueError("Ready to match stage not found")
        result = surrogate_status_service.apply_status_change(
            db=db,
            surrogate=surrogate,
            new_stage=ready,
            current_stage=old_stage,
            old_stage_id=surrogate.stage_id,
            old_label=surrogate.status_label,
            old_slug=old_stage.slug,
            user_id=request.requested_by_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            request_id=request.id,
            approved_by_user_id=actor_user_id,
            approved_at=now,
            requested_at=request.requested_at,
            commit=False,
        )
        event = result.get("after_commit")
    elif not get_donor(db, match.donor_id, match.organization_id):
        raise ValueError("Match participants not found")
    remaining = (
        db.query(Match.id)
        .filter(
            Match.organization_id == match.organization_id,
            Match.intended_parent_id == match.intended_parent_id,
            Match.id != match.id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    )
    old_ip_stage = intended_parent_status_service.get_current_stage(db, ip)
    if not remaining and pipeline_service.stage_matches_system_role(
        old_ip_stage, "matched", INTENDED_PARENT_PIPELINE_ENTITY
    ):
        ready = pipeline_service.get_stage_by_system_role(
            db, old_ip_stage.pipeline_id, "handoff", INTENDED_PARENT_PIPELINE_ENTITY
        )
        if not ready:
            raise ValueError("Ready to match stage not found")
        intended_parent_status_service.apply_status_change(
            db=db,
            ip=ip,
            old_stage=old_ip_stage,
            new_stage=ready,
            user_id=request.requested_by_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            request_id=request.id,
            approved_by_user_id=actor_user_id,
            approved_at=now,
            requested_at=request.requested_at,
            commit=False,
        )
    match.status = MatchStatus.CANCELLED.value
    match.closed_at = now
    match.closed_by_user_id = actor_user_id
    match.closure_reason = request.reason
    match.updated_at = now
    # Open attempts end with the cancelled relationship, retaining recorded dates/outcomes.
    for attempt in list_attempts(db, match):
        if attempt.status in ("planned", "in_progress"):
            attempt.status = "cancelled"
            attempt.updated_at = now
    _log_case_change(db, match, actor_user_id, "match_cancelled")
    return event


def match_visibility_filter(db: Session, session):
    """Filter authorized participants before case pagination and summary counts."""
    from app.services import permission_policy_service, record_scope_service

    if permission_policy_service.is_enabled(db, session.org_id):
        return record_scope_service.build_linked_visibility_filter(db, session, Match)
    from sqlalchemy import false

    from app.core.policies import POLICIES
    from app.core.surrogate_access import build_surrogate_visibility_filter
    from app.services import permission_service

    def allowed(resource):
        return permission_service.check_permission(
            db,
            session.org_id,
            session.user_id,
            session.role.value,
            POLICIES[resource].default.value,
        )

    if not allowed("intended_parents"):
        return false()
    clauses = []
    if allowed("donors"):
        clauses.append(
            and_(
                Match.donor_id.isnot(None),
                Match.donor_id.in_(
                    db.query(Donor.id).filter(Donor.organization_id == session.org_id)
                ),
            )
        )
    if allowed("surrogates"):
        visible = db.query(Surrogate.id).filter(
            Surrogate.organization_id == session.org_id,
            build_surrogate_visibility_filter(db, session.org_id, session.role, session.user_id),
        )
        clauses.append(Match.surrogate_id.in_(visible))
    return and_(
        Match.intended_parent_id.in_(
            db.query(IntendedParent.id).filter(IntendedParent.organization_id == session.org_id)
        ),
        or_(*clauses) if clauses else false(),
    )


def get_donors_by_ids(db: Session, org_id: UUID, donor_ids: set[UUID]) -> dict[UUID, Donor]:
    if not donor_ids:
        return {}
    return {
        donor.id: donor
        for donor in db.query(Donor)
        .options(joinedload(Donor.stage))
        .filter(Donor.organization_id == org_id, Donor.id.in_(donor_ids))
        .all()
    }
