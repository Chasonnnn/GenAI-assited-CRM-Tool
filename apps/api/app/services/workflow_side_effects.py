"""Run workflow triggers after a domain change committed, without risking that change."""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_post_commit_trigger[Entity](
    db: Session,
    *,
    org_id: UUID,
    load: Callable[[Session], Entity | None],
    trigger: Callable[[Session, Entity], object],
    integration_key: str,
    title: str,
    details: dict[str, str],
) -> None:
    """Fire one workflow trigger in its own session after the caller committed.

    The workflow engine commits as it executes, so it must not share the caller's
    session: a failure would roll back or poison the committed change. Failures are
    logged without PII and recorded as a workflow alert. Same contract as
    donor_service._dispatch_side_effect_isolated, which predates this helper.
    """
    from app.db.enums import AlertSeverity, AlertType
    from app.db.session import SessionLocal
    from app.services import alert_service

    bind = db.get_bind()
    side_effect_db = (
        Session(bind=bind, autoflush=False, join_transaction_mode="create_savepoint")
        if isinstance(bind, Connection)
        else SessionLocal()
    )
    try:
        entity = load(side_effect_db)
        if entity is None:
            raise LookupError("Workflow trigger entity unavailable")
        trigger(side_effect_db, entity)
    except Exception as exc:
        logger.error(title, extra={**details, "error_class": type(exc).__name__})
        try:
            side_effect_db.rollback()
        except Exception:
            logger.error("Workflow side-effect rollback failed", extra=details)
        try:
            alert_service.record_alert_isolated(
                org_id=org_id,
                alert_type=AlertType.WORKFLOW_EXECUTION_FAILED,
                severity=AlertSeverity.ERROR,
                title=title,
                message="A workflow trigger failed after the record change was saved.",
                integration_key=integration_key,
                error_class=type(exc).__name__,
                details=details,
            )
        except Exception:
            logger.error("Workflow side-effect alert could not be persisted", extra=details)
    finally:
        side_effect_db.close()
