"""Compliance router - retention policies and legal holds."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.compliance import (
    LegalHoldCreate,
    LegalHoldRead,
    PurgePreviewItem,
    PurgePreviewResponse,
    PurgeExecuteResponse,
    RetentionPolicyRead,
    RetentionPolicyUpsert,
)
from app.services import audit_service, compliance_service, job_service
from app.db.enums import JobType


router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("/policies", response_model=list[RetentionPolicyRead])
def list_policies(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
) -> list[RetentionPolicyRead]:
    """List retention policies for the organization."""
    return compliance_service.list_retention_policies(db, session.org_id)


@router.post("/policies", response_model=RetentionPolicyRead)
def upsert_policy(
    payload: RetentionPolicyUpsert,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
) -> RetentionPolicyRead:
    """Create or update a retention policy."""
    try:
        return compliance_service.upsert_retention_policy(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            entity_type=payload.entity_type,
            retention_days=payload.retention_days,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/legal-holds", response_model=list[LegalHoldRead])
def list_legal_holds(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
) -> list[LegalHoldRead]:
    """List legal holds for the organization."""
    return compliance_service.list_legal_holds(db, session.org_id)


@router.post("/legal-holds", response_model=LegalHoldRead)
def create_legal_hold(
    payload: LegalHoldCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
) -> LegalHoldRead:
    """Create a legal hold (org-wide or entity-specific)."""
    return compliance_service.create_legal_hold(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        reason=payload.reason,
    )


@router.post("/legal-holds/{hold_id}/release", response_model=LegalHoldRead)
def release_legal_hold(
    hold_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
) -> LegalHoldRead:
    """Release a legal hold."""
    hold = compliance_service.release_legal_hold(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        hold_id=hold_id,
    )
    if not hold:
        raise HTTPException(status_code=404, detail="Legal hold not found or already released")
    return hold


@router.get("/purge-preview", response_model=PurgePreviewResponse)
def purge_preview(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
) -> PurgePreviewResponse:
    """Preview data purge counts by entity type."""
    results = compliance_service.preview_purge(db, session.org_id)
    audit_service.log_compliance_purge_previewed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        results=[{"entity_type": item.entity_type, "count": item.count} for item in results],
    )
    return PurgePreviewResponse(
        items=[PurgePreviewItem(entity_type=item.entity_type, count=item.count) for item in results]
    )


@router.post("/purge-execute", response_model=PurgeExecuteResponse)
def purge_execute(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_roles([Role.DEVELOPER])),
) -> PurgeExecuteResponse:
    """Execute data purge based on retention policies."""
    job = job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.DATA_PURGE,
        payload={"org_id": str(session.org_id), "user_id": str(session.user_id)},
    )
    return PurgeExecuteResponse(job_id=job.id)
