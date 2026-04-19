"""Helpers for latest surrogate outcome summaries shown on detail pages."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import SurrogateActivityLog, SurrogateContactAttempt
from app.schemas.surrogate import LatestContactOutcomeRead, LatestInterviewOutcomeRead


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or value.strip() == "":
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def get_latest_contact_outcome(surrogate, db: Session) -> LatestContactOutcomeRead | None:
    attempt = (
        db.query(SurrogateContactAttempt)
        .filter(
            SurrogateContactAttempt.surrogate_id == surrogate.id,
            SurrogateContactAttempt.organization_id == surrogate.organization_id,
        )
        .order_by(
            SurrogateContactAttempt.attempted_at.desc(),
            SurrogateContactAttempt.created_at.desc(),
            SurrogateContactAttempt.id.desc(),
        )
        .first()
    )
    if attempt is None:
        return None

    return LatestContactOutcomeRead(
        outcome=attempt.outcome,
        at=attempt.attempted_at,
    )


def get_latest_interview_outcome(surrogate, db: Session) -> LatestInterviewOutcomeRead | None:
    activities = (
        db.query(SurrogateActivityLog)
        .filter(
            SurrogateActivityLog.surrogate_id == surrogate.id,
            SurrogateActivityLog.organization_id == surrogate.organization_id,
            SurrogateActivityLog.activity_type == "interview_outcome_logged",
        )
        .order_by(SurrogateActivityLog.created_at.desc(), SurrogateActivityLog.id.desc())
        .all()
    )

    latest: LatestInterviewOutcomeRead | None = None
    latest_created_at: datetime | None = None
    for activity in activities:
        details = activity.details if isinstance(activity.details, dict) else {}
        outcome = details.get("outcome")
        if not isinstance(outcome, str):
            continue
        effective_at = _parse_iso_datetime(details.get("occurred_at")) or activity.created_at
        if latest is None or effective_at > latest.at or (
            effective_at == latest.at and latest_created_at is not None and activity.created_at > latest_created_at
        ):
            latest = LatestInterviewOutcomeRead(
                outcome=outcome,
                at=effective_at,
            )
            latest_created_at = activity.created_at

    return latest
