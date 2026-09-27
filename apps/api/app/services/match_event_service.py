"""Calendar events on one match."""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.db.models import Match, MatchEvent
from app.schemas.auth import UserSession
from app.schemas.matches import MatchEventCreate, MatchEventRead, MatchEventUpdate
from app.services import match_access


def to_read(event: MatchEvent) -> MatchEventRead:
    return MatchEventRead(
        id=str(event.id),
        match_id=str(event.match_id),
        person_type=event.person_type,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        starts_at=event.starts_at.isoformat() if event.starts_at else None,
        ends_at=event.ends_at.isoformat() if event.ends_at else None,
        timezone=event.timezone,
        all_day=event.all_day,
        start_date=event.start_date.isoformat() if event.start_date else None,
        end_date=event.end_date.isoformat() if event.end_date else None,
        created_by_user_id=str(event.created_by_user_id) if event.created_by_user_id else None,
        created_at=event.created_at.isoformat(),
        updated_at=event.updated_at.isoformat(),
    )


def query_events(
    db: Session,
    match_id: UUID,
    person_type: str | None = None,
    event_type: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    from_day: date_type | None = None,
    to_day: date_type | None = None,
) -> list[MatchEvent]:
    """Timed events in the window plus all-day events that overlap it."""
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

        all_day_filters = [MatchEvent.all_day.is_(True), MatchEvent.start_date.isnot(None)]
        if to_day:
            all_day_filters.append(MatchEvent.start_date <= to_day)
        if from_day:
            all_day_filters.append(
                func.coalesce(MatchEvent.end_date, MatchEvent.start_date) >= from_day
            )
        date_filters.append(and_(*all_day_filters))
        query = query.filter(or_(*date_filters))

    return query.order_by(MatchEvent.starts_at, MatchEvent.start_date).all()


def _get_event(db: Session, match_id: UUID, event_id: UUID, org_id: UUID) -> MatchEvent:
    event = (
        db.query(MatchEvent)
        .filter(
            MatchEvent.id == event_id,
            MatchEvent.match_id == match_id,
            MatchEvent.organization_id == org_id,
        )
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _check_person(match: Match, person_type: str | None) -> None:
    if person_type is not None and person_type not in (match.match_kind, "ip"):
        raise HTTPException(status_code=400, detail="Event participant is not in this case")


def list_events(
    db: Session,
    session: UserSession,
    match_id: UUID,
    *,
    from_date: str | None,
    to_date: str | None,
    person_type: str | None,
    event_type: str | None,
) -> list[MatchEventRead]:
    match_access.load(db, session, match_id, "view", allow_archived=True)
    from_dt = to_dt = from_day = to_day = None
    if from_date or to_date:
        try:
            from_dt = datetime.fromisoformat(from_date).replace(tzinfo=UTC) if from_date else None
            to_dt = (
                datetime.fromisoformat(to_date).replace(tzinfo=UTC) + timedelta(days=1)
                if to_date
                else None
            )
            from_day = date_type.fromisoformat(from_date) if from_date else None
            to_day = date_type.fromisoformat(to_date) if to_date else None
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    events = query_events(
        db,
        match_id,
        person_type=person_type,
        event_type=event_type,
        from_dt=from_dt,
        to_dt=to_dt,
        from_day=from_day,
        to_day=to_day,
    )
    return [to_read(event) for event in events]


def get_event(db: Session, session: UserSession, match_id: UUID, event_id: UUID) -> MatchEventRead:
    match_access.load(db, session, match_id, "view", allow_archived=True)
    return to_read(_get_event(db, match_id, event_id, session.org_id))


def create_event(
    db: Session, session: UserSession, match_id: UUID, data: MatchEventCreate
) -> MatchEventRead:
    match = match_access.load(db, session, match_id, "edit_events")
    _check_person(match, data.person_type)
    if data.all_day:
        if not data.start_date:
            raise HTTPException(status_code=400, detail="start_date is required for all-day events")
        start_date = date_type.fromisoformat(data.start_date)
        end_date = date_type.fromisoformat(data.end_date) if data.end_date else None
        if end_date and end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
        starts_at = ends_at = None
    else:
        if not data.starts_at:
            raise HTTPException(status_code=400, detail="starts_at is required for timed events")
        if data.ends_at and data.ends_at < data.starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be on or after starts_at")
        start_date = end_date = None
        starts_at, ends_at = data.starts_at, data.ends_at

    event = MatchEvent(
        organization_id=session.org_id,
        match_id=match_id,
        person_type=data.person_type,
        event_type=data.event_type,
        title=data.title,
        description=data.description,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=data.timezone,
        all_day=data.all_day,
        start_date=start_date,
        end_date=end_date,
        created_by_user_id=session.user_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return to_read(event)


def update_event(
    db: Session, session: UserSession, match_id: UUID, event_id: UUID, data: MatchEventUpdate
) -> MatchEventRead:
    match = match_access.load(db, session, match_id, "edit_events")
    event = _get_event(db, match_id, event_id, session.org_id)
    _check_person(match, data.person_type)

    all_day = data.all_day if data.all_day is not None else event.all_day
    start_date = end_date = starts_at = ends_at = None
    if all_day:
        start_date = (
            date_type.fromisoformat(data.start_date)
            if data.start_date is not None
            else event.start_date
        )
        end_date = (
            date_type.fromisoformat(data.end_date) if data.end_date is not None else event.end_date
        )
        if not start_date:
            raise HTTPException(status_code=400, detail="start_date is required for all-day events")
        if end_date and end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    else:
        starts_at = data.starts_at if data.starts_at is not None else event.starts_at
        ends_at = data.ends_at if data.ends_at is not None else event.ends_at
        if not starts_at:
            raise HTTPException(status_code=400, detail="starts_at is required for timed events")
        if ends_at and ends_at < starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be on or after starts_at")

    if data.person_type is not None:
        event.person_type = data.person_type
    if data.event_type is not None:
        event.event_type = data.event_type
    if data.title is not None:
        event.title = data.title
    if data.description is not None:
        event.description = data.description
    if data.timezone is not None:
        event.timezone = data.timezone
    event.all_day = all_day
    event.start_date = start_date
    event.end_date = end_date
    event.starts_at = starts_at
    event.ends_at = ends_at
    event.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    return to_read(event)


def delete_event(db: Session, session: UserSession, match_id: UUID, event_id: UUID) -> None:
    match_access.load(db, session, match_id, "edit_events")
    db.delete(_get_event(db, match_id, event_id, session.org_id))
    db.commit()
