"""Admin APIs for organization-level Twilio messaging configuration."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission, require_roles
from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.twilio import (
    TwilioReadinessCheckResponse,
    TwilioReadinessResponse,
    TwilioSettingsResponse,
    TwilioSettingsTestRequest,
    TwilioSettingsTestResponse,
    TwilioSettingsUpdate,
    TwilioWebhookRotateRequest,
)
from app.services import (
    twilio_provider_service,
    twilio_readiness_orchestration_service,
    twilio_readiness_service,
    twilio_settings_service,
)

router = APIRouter(
    prefix="/twilio",
    tags=["twilio"],
    dependencies=[Depends(require_roles([Role.ADMIN, Role.DEVELOPER]))],
)


@router.get("/settings", response_model=TwilioSettingsResponse)
def get_twilio_settings(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioSettingsResponse:
    """Return only masked provider settings for the authenticated organization."""
    settings = twilio_settings_service.get_or_create_settings(db, session.org_id)
    return twilio_settings_service.project_settings(settings)


@router.patch(
    "/settings",
    response_model=TwilioSettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_twilio_settings(
    update: TwilioSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioSettingsResponse:
    """Persist masked/write-only Twilio configuration with optimistic locking."""
    try:
        settings = twilio_settings_service.update_settings(db, session.org_id, update)
    except twilio_settings_service.TwilioSettingsVersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except twilio_settings_service.TwilioSettingsValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return twilio_settings_service.project_settings(settings)


@router.post(
    "/settings/test",
    response_model=TwilioSettingsTestResponse,
    dependencies=[Depends(require_csrf_header)],
)
def test_twilio_settings(
    request: TwilioSettingsTestRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioSettingsTestResponse:
    """Perform a read-only provider credential and route check."""
    settings = twilio_settings_service.get_or_create_settings(db, session.org_id)
    return twilio_provider_service.test_configuration(settings, request)


@router.post(
    "/settings/rotate-webhook",
    response_model=TwilioSettingsResponse,
    dependencies=[Depends(require_csrf_header)],
)
def rotate_twilio_webhook(
    request: TwilioWebhookRotateRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioSettingsResponse:
    """Rotate one purpose's opaque inbound/status callback token."""
    try:
        settings = twilio_settings_service.rotate_webhook(
            db,
            session.org_id,
            request.purpose,
            request.expected_version,
        )
    except twilio_settings_service.TwilioSettingsVersionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return twilio_settings_service.project_settings(settings)


@router.get("/readiness", response_model=TwilioReadinessResponse)
def get_twilio_readiness(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioReadinessResponse:
    """Return persisted provider evidence and local operational health only."""
    return twilio_readiness_service.get_readiness(db, session.org_id)


@router.post(
    "/readiness",
    response_model=TwilioReadinessCheckResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf_header)],
)
def queue_twilio_readiness(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> TwilioReadinessCheckResponse:
    """Durably queue a coalesced provider check; it never creates a message."""
    check = twilio_readiness_orchestration_service.queue_check(
        db,
        organization_id=session.org_id,
    )
    return TwilioReadinessCheckResponse(
        check_status=check.check_status,
        queued_at=check.queued_at.isoformat(),
        readiness=twilio_readiness_orchestration_service.cached_readiness(
            db,
            organization_id=session.org_id,
        ),
    )
