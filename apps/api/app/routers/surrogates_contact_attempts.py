"""Surrogate contact attempt routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.surrogate import (
    ContactAttemptCreate,
    ContactAttemptResponse,
    ContactAttemptsSummary,
)
from app.services import contact_attempt_service, surrogate_service

router = APIRouter()


@router.post(
    "/{surrogate_id:uuid}/contact-attempts",
    response_model=ContactAttemptResponse,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_contact_attempt(
    surrogate_id: UUID,
    data: ContactAttemptCreate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
):
    """Log a contact attempt for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        attempt = contact_attempt_service.create_contact_attempt(
            session=db,
            surrogate_id=surrogate_id,
            data=data,
            user=session,
        )
        db.commit()
        return attempt
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{surrogate_id:uuid}/contact-attempts",
    response_model=ContactAttemptsSummary,
)
def get_contact_attempts(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get contact attempts summary for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        summary = contact_attempt_service.get_surrogate_contact_attempts_summary(
            session=db,
            surrogate_id=surrogate_id,
            user=session,
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
