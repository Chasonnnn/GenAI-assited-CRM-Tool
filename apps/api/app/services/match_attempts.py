"""Treatment attempts on one match.

New attempts are no longer recorded. Existing open attempts close with a cancelled match.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Match, MatchAttempt

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


def close_open_attempts(db: Session, match: Match, now: datetime) -> None:
    """Open attempts end with the cancelled match, keeping recorded dates and outcomes."""
    for attempt in list_attempts(db, match):
        if attempt.status in OPEN_ATTEMPT_STATUSES:
            attempt.status = "cancelled"
            attempt.updated_at = now
