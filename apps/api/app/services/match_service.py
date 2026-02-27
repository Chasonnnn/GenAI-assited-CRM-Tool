"""Match service - query helpers for matches and match events."""

from datetime import datetime, date, timezone
from uuid import UUID

from sqlalchemy import asc, desc, func, and_, or_, text
from sqlalchemy.orm import Session, joinedload

from app.db.enums import AuditEventType, MatchStatus, IntendedParentStatus, SurrogateActivityType
from app.db.models import (
    Surrogate,
    IntendedParent,
    Match,
    MatchEvent,
    StatusChangeRequest,
    IntendedParentStatusHistory,
)
from app.utils.normalization import escape_like_string, normalize_identifier, normalize_search_text
from sqlalchemy.exc import IntegrityError


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
    return db.query(IntendedParent).filter(*filters).first()


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
    surrogate_id: UUID,
    intended_parent_id: UUID,
) -> Match | None:
    """Find an existing match for a surrogate/IP in org."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.intended_parent_id == intended_parent_id,
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
            Match.status == MatchStatus.ACCEPTED.value,
        )
        .first()
    )


def list_matches(
    db: Session,
    org_id: UUID,
    status_filter: str | None = None,
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[Match], int]:
    """List matches with filters and pagination."""
    query = db.query(Match).filter(Match.organization_id == org_id)

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
            .join(
                IntendedParent,
                Match.intended_parent_id == IntendedParent.id,
                isouter=True,
            )
            .filter(
                or_(
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

    total = query.count()

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

    matches = query.offset((page - 1) * per_page).limit(per_page).all()
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
) -> tuple[int, dict[str, int]]:
    """Return total matches and counts by status."""
    total = db.query(Match).filter(Match.organization_id == org_id).count()
    counts = {status.value: 0 for status in MatchStatus}
    rows = (
        db.query(Match.status, func.count(Match.id))
        .filter(Match.organization_id == org_id)
        .group_by(Match.status)
        .all()
    )

    for status, count in rows:
        counts[status] = count

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
    surrogate_id: UUID,
    intended_parent_id: UUID,
    proposed_by_user_id: UUID,
    compatibility_score: float | None = None,
    notes: str | None = None,
) -> Match:
    """Create a proposed match and log activity."""
    from app.services import activity_service, audit_service, note_service

    clean_notes = note_service.sanitize_html(notes) if notes else None

    match = Match(
        organization_id=org_id,
        match_number=generate_match_number(db, org_id),
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        status=MatchStatus.PROPOSED.value,
        proposed_by_user_id=proposed_by_user_id,
        notes=clean_notes,
    )
    db.add(match)
    db.flush()

    activity_service.log_activity(
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
        from app.services import activity_service

        match.status = MatchStatus.REVIEWING.value
        match.reviewed_by_user_id = actor_user_id
        match.reviewed_at = datetime.now(timezone.utc)
        match.updated_at = datetime.now(timezone.utc)

        activity_service.log_activity(
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
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot accept match with status: {match.status}")

    from app.services import (
        activity_service,
        audit_service,
        dashboard_events,
        note_service,
        pipeline_service,
        surrogate_service,
    )

    surrogate = get_surrogate_with_stage(db, match.surrogate_id, org_id)
    if surrogate:
        current_stage = surrogate.stage
        pipeline_id = current_stage.pipeline_id if current_stage else None
        if not pipeline_id:
            pipeline_id = pipeline_service.get_or_create_default_pipeline(
                db,
                org_id,
                actor_user_id,
            ).id
        matched_stage = pipeline_service.get_stage_by_key(db, pipeline_id, "matched")
        if matched_stage:
            surrogate_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=matched_stage.id,
                user_id=actor_user_id,
                user_role=actor_role,
                reason="Match accepted",
            )

    match.status = MatchStatus.ACCEPTED.value
    match.reviewed_by_user_id = actor_user_id
    match.reviewed_at = datetime.now(timezone.utc)
    if notes:
        clean_notes = note_service.sanitize_html(notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(timezone.utc)

    ip = get_intended_parent(db, match.intended_parent_id, org_id)
    if ip and ip.status != IntendedParentStatus.MATCHED.value:
        old_status = ip.status
        ip.status = IntendedParentStatus.MATCHED.value
        ip.last_activity = datetime.now(timezone.utc)
        ip.updated_at = datetime.now(timezone.utc)
        db.add(
            IntendedParentStatusHistory(
                intended_parent_id=ip.id,
                changed_by_user_id=actor_user_id,
                old_status=old_status,
                new_status=IntendedParentStatus.MATCHED.value,
                reason="Match accepted",
            )
        )

    other_matches = list_pending_matches_for_surrogate(
        db=db,
        surrogate_id=match.surrogate_id,
        exclude_match_id=match.id,
    )
    for other in other_matches:
        other.status = MatchStatus.CANCELLED.value
        other.updated_at = datetime.now(timezone.utc)

    activity_service.log_activity(
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
    dashboard_events.push_dashboard_stats(db, org_id)
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
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot reject match with status: {match.status}")

    from app.services import activity_service, audit_service, note_service

    match.status = MatchStatus.REJECTED.value
    match.reviewed_by_user_id = actor_user_id
    match.reviewed_at = datetime.now(timezone.utc)
    match.rejection_reason = rejection_reason
    if notes:
        clean_notes = note_service.sanitize_html(notes)
        match.notes = (match.notes or "") + "\n\n" + clean_notes
    match.updated_at = datetime.now(timezone.utc)

    activity_service.log_activity(
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

    now = datetime.now(timezone.utc)
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

    db.commit()
    db.refresh(match)
    db.refresh(request)

    from app.services import notification_facade, user_service

    surrogate = get_surrogate_with_stage(db, match.surrogate_id, org_id)
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
    if match.status not in [MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value]:
        raise ValueError(f"Cannot cancel match with status: {match.status}")

    from app.services import activity_service, audit_service

    match.status = MatchStatus.CANCELLED.value
    match.updated_at = datetime.now(timezone.utc)

    activity_service.log_activity(
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
    match.updated_at = datetime.now(timezone.utc)
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

    event.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return event


def delete_match_event(db: Session, event: MatchEvent) -> None:
    """Delete a match event."""
    db.delete(event)
    db.commit()
