"""Helpers for latest surrogate outcome summaries shown on detail pages."""

from sqlalchemy.orm import Session

from app.db.models import SurrogateContactAttempt
from app.schemas.surrogate import LatestContactOutcomeRead


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
