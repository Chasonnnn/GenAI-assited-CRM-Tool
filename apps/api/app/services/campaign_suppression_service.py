"""Organization campaign email suppression."""

from uuid import UUID

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import (
    EmailSuppression,
)
from app.utils.pagination import paginate_query_by_offset


def load_suppressed_emails(db: Session, org_id: UUID, *, ignore_opt_out: bool = False) -> set[str]:
    query = db.query(EmailSuppression.email, EmailSuppression.reason).filter(
        EmailSuppression.organization_id == org_id
    )
    if ignore_opt_out:
        query = query.filter(EmailSuppression.reason != "opt_out")

    rows = query.all()
    return {email.lower() for email, _reason in rows if email}


def is_email_suppressed(
    db: Session, org_id: UUID, email: str, *, ignore_opt_out: bool = False
) -> bool:
    """Check if an email is in the suppression list.

    By default, *any* suppression reason suppresses sending.
    When `ignore_opt_out=True`, only opt-outs are ignored (bounces/complaints still suppress).
    """
    suppression = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == org_id,
            EmailSuppression.email == email.lower(),
        )
        .first()
    )
    if not suppression:
        return False

    if ignore_opt_out and suppression.reason == "opt_out":
        return False

    return True


def add_to_suppression(
    db: Session,
    org_id: UUID,
    email: str,
    reason: str,
    source_type: str | None = None,
    source_id: UUID | None = None,
) -> EmailSuppression:
    """Atomically add or strengthen one tenant-scoped suppression."""
    statement = insert(EmailSuppression).values(
        organization_id=org_id,
        email=email.lower(),
        reason=reason,
        source_type=str(source_type) if source_type is not None else None,
        source_id=source_id,
    )
    incoming_reason = statement.excluded.reason
    incoming_precedence = case(
        (incoming_reason == "archived", 10),
        (incoming_reason == "opt_out", 20),
        (incoming_reason == "bounced", 30),
        (incoming_reason == "complaint", 40),
        else_=0,
    )
    stored_precedence = case(
        (EmailSuppression.reason == "archived", 10),
        (EmailSuppression.reason == "opt_out", 20),
        (EmailSuppression.reason == "bounced", 30),
        (EmailSuppression.reason == "complaint", 40),
        else_=0,
    )
    should_strengthen = incoming_precedence > stored_precedence
    statement = statement.on_conflict_do_update(
        constraint="uq_email_suppression",
        set_={
            "reason": case(
                (should_strengthen, statement.excluded.reason),
                else_=EmailSuppression.reason,
            ),
            "source_type": case(
                (should_strengthen, statement.excluded.source_type),
                else_=EmailSuppression.source_type,
            ),
            "source_id": case(
                (should_strengthen, statement.excluded.source_id),
                else_=EmailSuppression.source_id,
            ),
        },
    )
    return db.execute(statement.returning(EmailSuppression)).scalar_one()


def list_suppressions(
    db: Session, org_id: UUID, limit: int = 100, offset: int = 0
) -> tuple[list[EmailSuppression], int]:
    """List suppressed emails for an organization."""
    query = db.query(EmailSuppression).filter(EmailSuppression.organization_id == org_id)

    items, total = paginate_query_by_offset(
        query.order_by(EmailSuppression.created_at.desc()),
        offset=offset,
        limit=limit,
        count_query=query,
    )

    return items, total


def remove_from_suppression(db: Session, org_id: UUID, email: str) -> bool:
    """Remove an email from the suppression list."""
    result = (
        db.query(EmailSuppression)
        .filter(
            EmailSuppression.organization_id == org_id,
            EmailSuppression.email == email.lower(),
        )
        .delete()
    )

    return result > 0
