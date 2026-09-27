"""After-commit effects of match transitions.

``dispatch`` runs each effect in order after the transition is committed. A
failing effect is rolled back, logged with its error class, and recorded as a
``match_effect_failed`` activity row on the match; later effects still run and
the request still succeeds.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import AuditEventType
from app.db.models import Match, StatusChangeRequest

logger = logging.getLogger(__name__)

Effect = tuple[str, Callable[[], None]]


@dataclass
class TransitionEvent:
    action: str
    match: Match
    actor_user_id: UUID
    effects: list[Effect] = field(default_factory=list)


def dispatch(db: Session, event: TransitionEvent) -> list[str]:
    """Run every effect in isolation; return the names of the effects that failed."""
    failed: list[str] = []
    match_id = event.match.id
    org_id = event.match.organization_id
    for name, run in event.effects:
        try:
            run()
            db.commit()
        except Exception as exc:
            _rollback(db, match_id, name)
            failed.append(name)
            logger.error(
                "match_effect_failed",
                extra={
                    "match_id": str(match_id),
                    "action": event.action,
                    "effect": name,
                    "error_class": type(exc).__name__,
                },
            )
            _record_failure(db, org_id, match_id, event, name, exc)
    return failed


def _rollback(db: Session, match_id: UUID, name: str) -> None:
    """Roll back after a failed effect; a failed rollback is logged, never raised."""
    try:
        db.rollback()
    except Exception as exc:
        logger.error(
            "match_effect_rollback_failed",
            extra={
                "match_id": str(match_id),
                "effect": name,
                "error_class": type(exc).__name__,
            },
        )


def _record_failure(
    db: Session, org_id: UUID, match_id: UUID, event: TransitionEvent, name: str, exc: Exception
) -> None:
    from app.services import audit_service

    try:
        audit_service.log_event(
            db=db,
            org_id=org_id,
            event_type=AuditEventType.MATCH_EFFECT_FAILED,
            actor_user_id=event.actor_user_id,
            target_type="match",
            target_id=match_id,
            details={
                "match_id": str(match_id),
                "action": event.action,
                "effect": name,
                "error_class": type(exc).__name__,
            },
        )
        db.commit()
    except Exception as record_exc:
        _rollback(db, match_id, name)
        logger.error(
            "match_effect_failure_record_failed",
            extra={
                "match_id": str(match_id),
                "effect": name,
                "error_class": type(record_exc).__name__,
            },
        )


# =============================================================================
# Effects
# =============================================================================


def workflow_trigger(db: Session, action: str, match: Match) -> list[Effect]:
    """Workflow triggers fire for both surrogate and donor matches."""
    from app.services import workflow_triggers

    name = f"trigger_match_{action}"

    def run() -> None:
        getattr(workflow_triggers, name)(db, match)

    return [(f"workflow_{name}", run)]


def dashboard_push(db: Session, org_id: UUID) -> list[Effect]:
    def run() -> None:
        from app.services import dashboard_service

        dashboard_service.push_dashboard_stats_or_raise(db, org_id)

    return [("dashboard_push", run)]


def cancel_request_pending_notification(
    db: Session, match: Match, request: StatusChangeRequest, actor_user_id: UUID
) -> list[Effect]:
    def run() -> None:
        from app.services import match_queries, notification_service, user_service

        org_id = match.organization_id
        participant = (
            match_queries.get_donor(db, match.donor_id, org_id)
            if match.donor_id
            else match_queries.get_surrogate_with_stage(db, match.surrogate_id, org_id)
        )
        intended_parent = match_queries.get_intended_parent(db, match.intended_parent_id, org_id)
        requester = user_service.get_user_by_id(db, actor_user_id)
        if participant and intended_parent:
            notification_service.notify_match_cancel_request_pending(
                db=db,
                request=request,
                match=match,
                surrogate=participant,
                intended_parent=intended_parent,
                requester_name=requester.display_name if requester else "Someone",
            )

    return [("cancel_request_pending_notification", run)]


def cancel_request_resolved_notification(
    db: Session,
    match: Match,
    request: StatusChangeRequest,
    resolver_user_id: UUID,
    *,
    approved: bool,
    reason: str | None = None,
) -> list[Effect]:
    def run() -> None:
        from app.db.models import User
        from app.services import notification_service

        resolver = db.query(User).filter(User.id == resolver_user_id).first()
        kwargs = {} if approved else {"reason": reason}
        notification_service.notify_match_cancel_request_resolved(
            db=db,
            request=request,
            match=match,
            approved=approved,
            resolver_name=resolver.display_name if resolver else "Admin",
            **kwargs,
        )

    return [("cancel_request_resolved_notification", run)]
