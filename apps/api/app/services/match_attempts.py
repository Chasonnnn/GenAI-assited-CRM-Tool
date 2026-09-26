"""Treatment attempts on one match: create, update, type rules, and closure on cancel."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import MatchStatus
from app.db.models import Match, MatchAttempt
from app.services import match_participants

OPEN_ATTEMPT_STATUSES = ("planned", "in_progress")


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
    """Create or update an attempt on an accepted match under the match lock."""
    from app.services import match_lifecycle

    match_lifecycle.require_expansion()
    match = match_lifecycle.lock_match(db, match)
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
            raise HTTPException(status_code=404, detail="Attempt not found")
    next_started_at = values.get("started_at", attempt.started_at if attempt else None)
    next_ended_at = values.get("ended_at", attempt.ended_at if attempt else None)
    next_type = values.get("attempt_type", attempt.attempt_type if attempt else None)
    if next_started_at and next_ended_at and next_ended_at < next_started_at:
        raise ValueError("End date must be on or after start date")
    match_participants.primary(match).check_attempt_type(next_type)
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
    match_lifecycle.write_case_change(
        db,
        match,
        actor_user_id,
        "match_attempt_updated" if attempt_id else "match_attempt_created",
        {"attempt_id": str(attempt.id)},
    )
    db.commit()
    db.refresh(attempt)
    return attempt


def close_open_attempts(db: Session, match: Match, now: datetime) -> None:
    """Open attempts end with the cancelled match, keeping recorded dates and outcomes."""
    for attempt in list_attempts(db, match):
        if attempt.status in OPEN_ATTEMPT_STATUSES:
            attempt.status = "cancelled"
            attempt.updated_at = now
