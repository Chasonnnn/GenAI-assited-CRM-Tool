"""Match service - query helpers for matches and match events."""

from datetime import datetime, date
from uuid import UUID

from sqlalchemy import asc, desc, func, and_, or_, text
from sqlalchemy.orm import Session, joinedload

from app.db.enums import MatchStatus
from app.db.models import Surrogate, IntendedParent, Match, MatchEvent


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
        search_term = f"%{q}%"
        query = (
            query.join(Surrogate, Match.surrogate_id == Surrogate.id, isouter=True)
            .join(
                IntendedParent,
                Match.intended_parent_id == IntendedParent.id,
                isouter=True,
            )
            .filter(
                or_(
                    Match.match_number.ilike(search_term),
                    Surrogate.full_name.ilike(search_term),
                    Surrogate.surrogate_number.ilike(search_term),
                    IntendedParent.full_name.ilike(search_term),
                    IntendedParent.intended_parent_number.ilike(search_term),
                )
            )
        )

    total = query.count()

    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "status": Match.status,
        "compatibility_score": Match.compatibility_score,
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
