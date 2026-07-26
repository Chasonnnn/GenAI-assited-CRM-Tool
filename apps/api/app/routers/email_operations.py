"""Authenticated organization-scoped email operations API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.schemas.email_operations import (
    EmailOperationMessageDetail,
    EmailOperationMessageListResponse,
    EmailOperationsReadinessResponse,
    EmailReconciliationCaseListResponse,
    EmailReconciliationCaseSummary,
    EmailReconciliationDeliveryResolutionRequest,
    EmailReconciliationDismissRequest,
    EmailReconciliationLinkRequest,
    EmailReconciliationRetryRequest,
)
from app.schemas.resend_readiness import ResendReadinessEnvelope
from app.services import (
    email_operations_service,
    email_reconciliation_service,
    resend_readiness_orchestration_service,
)


router = APIRouter(prefix="/email-operations", tags=["email-operations"])


@router.post(
    "/reconciliation-cases/{case_id}/resolve-delivery",
    dependencies=[Depends(require_csrf_header)],
)
def resolve_reconciliation_delivery(
    case_id: UUID,
    body: EmailReconciliationDeliveryResolutionRequest,
    request: Request,
    session: Annotated[UserSession, Depends(require_permission(P.OPS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> EmailReconciliationCaseSummary:
    """Resolve one unknown delivery outcome without invoking provider transport."""
    try:
        case = email_reconciliation_service.resolve_unknown_delivery_by_operator(
            db,
            organization_id=session.org_id,
            case_id=case_id,
            expected_version=body.expected_version,
            outcome=body.outcome,
            provider_message_id=body.provider_message_id,
            actor_user_id=session.user_id,
            request=request,
        )
    except email_reconciliation_service.ReconciliationCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Reconciliation case not found") from exc
    except email_reconciliation_service.ReconciliationCaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation case changed or evidence conflicts",
        ) from exc
    return email_operations_service.project_reconciliation_case(case)


@router.post(
    "/reconciliation-cases/{case_id}/dismiss",
    dependencies=[Depends(require_csrf_header)],
)
def dismiss_reconciliation_event(
    case_id: UUID,
    body: EmailReconciliationDismissRequest,
    request: Request,
    session: Annotated[UserSession, Depends(require_permission(P.OPS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> EmailReconciliationCaseSummary:
    """Dismiss a controlled unsupported/test event without projecting it."""
    try:
        case = email_reconciliation_service.dismiss_orphan_event(
            db,
            organization_id=session.org_id,
            case_id=case_id,
            expected_version=body.expected_version,
            resolution_code=body.resolution_code,
            actor_user_id=session.user_id,
            request=request,
        )
    except email_reconciliation_service.ReconciliationCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Reconciliation case not found") from exc
    except email_reconciliation_service.ReconciliationCaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation case changed or cannot be dismissed",
        ) from exc
    return email_operations_service.project_reconciliation_case(case)


@router.post(
    "/reconciliation-cases/{case_id}/link-event",
    dependencies=[Depends(require_csrf_header)],
)
def link_reconciliation_event(
    case_id: UUID,
    body: EmailReconciliationLinkRequest,
    request: Request,
    session: Annotated[UserSession, Depends(require_permission(P.OPS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> EmailReconciliationCaseSummary:
    """Link one signed orphan provider event to an existing organization message."""
    try:
        case = email_reconciliation_service.link_orphan_event(
            db,
            organization_id=session.org_id,
            case_id=case_id,
            expected_version=body.expected_version,
            email_log_id=body.email_log_id,
            actor_user_id=session.user_id,
            request=request,
        )
    except email_reconciliation_service.ReconciliationCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Reconciliation case not found") from exc
    except email_reconciliation_service.ReconciliationCaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation case changed or evidence conflicts",
        ) from exc
    return email_operations_service.project_reconciliation_case(case)


@router.post(
    "/reconciliation-cases/{case_id}/retry-correlation",
    dependencies=[Depends(require_csrf_header)],
)
def retry_reconciliation_correlation(
    case_id: UUID,
    body: EmailReconciliationRetryRequest,
    request: Request,
    session: Annotated[UserSession, Depends(require_permission(P.OPS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> EmailReconciliationCaseSummary:
    """Retry only local correlation for an exhausted orphan provider event."""
    try:
        case = email_reconciliation_service.retry_orphan_correlation(
            db,
            organization_id=session.org_id,
            case_id=case_id,
            expected_version=body.expected_version,
            actor_user_id=session.user_id,
            request=request,
        )
    except email_reconciliation_service.ReconciliationCaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Reconciliation case not found") from exc
    except email_reconciliation_service.ReconciliationCaseConflict as exc:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation case changed; refresh and try again",
        ) from exc
    return email_operations_service.project_reconciliation_case(case)


@router.get("/reconciliation-cases")
def list_reconciliation_cases(
    session: Annotated[UserSession, Depends(require_permission(P.OPS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    status: Annotated[
        str | None,
        Query(pattern="^(monitoring|pending|running|action_required|resolved|dismissed)$"),
    ] = None,
) -> EmailReconciliationCaseListResponse:
    """List sanitized email reconciliation cases for an operations user."""
    try:
        return email_operations_service.list_reconciliation_cases(
            db,
            organization_id=session.org_id,
            limit=limit,
            cursor=cursor,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("/readiness")
def get_readiness(
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> EmailOperationsReadinessResponse:
    """Return persisted send, tracking, and recent-activity readiness."""
    return email_operations_service.get_readiness(
        db,
        organization_id=session.org_id,
    )


@router.get("/readiness/live")
def get_live_readiness(
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> ResendReadinessEnvelope:
    """Return the latest cached live-readiness result without provider I/O."""
    view = resend_readiness_orchestration_service.get_organization_envelope(
        db,
        organization_id=session.org_id,
    )
    return ResendReadinessEnvelope.model_validate(view)


@router.post(
    "/readiness/check",
    status_code=202,
    dependencies=[Depends(require_csrf_header)],
)
def queue_live_readiness_check(
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
) -> ResendReadinessEnvelope:
    """Queue one coalesced, read-only provider readiness check."""
    view = resend_readiness_orchestration_service.queue_organization_check(
        db,
        organization_id=session.org_id,
    )
    return ResendReadinessEnvelope.model_validate(view)


@router.get("/messages")
def list_messages(
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
) -> EmailOperationMessageListResponse:
    """List sanitized outbound messages for the authenticated organization."""
    try:
        return email_operations_service.list_messages(
            db,
            organization_id=session.org_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


@router.get("/messages/{message_id}")
def get_message(
    message_id: UUID,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> EmailOperationMessageDetail:
    """Return sanitized delivery diagnostics for one organization message."""
    message = email_operations_service.get_message(
        db,
        organization_id=session.org_id,
        message_id=message_id,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Email message not found")
    return message
