"""Public signed messaging consent preference API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.schemas.messaging import MessagingPreferenceResponse, MessagingPreferenceUpdateRequest
from app.services import messaging_preference_service

router = APIRouter(prefix="/public/messaging-consent", tags=["messaging-consent-public"])


def _parse(token: str):
    try:
        return messaging_preference_service.parse_preference_token(token)
    except messaging_preference_service.MessagingPreferenceInvalid as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _raise_preference_error(exc: ValueError) -> None:
    if isinstance(exc, messaging_preference_service.MessagingPreferenceDisclosureStale):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{token}", response_model=MessagingPreferenceResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_messaging_preference(
    request: Request,
    token: str,
    db: Annotated[Session, Depends(get_db)],
) -> MessagingPreferenceResponse:
    del request
    try:
        return messaging_preference_service.project_preference(db, token=_parse(token))
    except ValueError as exc:
        _raise_preference_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/{token}", response_model=MessagingPreferenceResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_FORMS}/minute")
def update_messaging_preference(
    request: Request,
    token: str,
    payload: MessagingPreferenceUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> MessagingPreferenceResponse:
    del request
    try:
        return messaging_preference_service.update_preference(
            db,
            token=_parse(token),
            **payload.model_dump(),
        )
    except ValueError as exc:
        _raise_preference_error(exc)
        raise AssertionError("unreachable") from exc
