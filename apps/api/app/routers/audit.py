"""Audit router - API endpoints for viewing audit logs."""

import os

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_session, get_db, require_permission, require_csrf_header
from app.core.policies import POLICIES
from app.db.enums import AuditEventType, Role
from app.schemas.compliance import ExportJobCreate, ExportJobListResponse, ExportJobRead
from app.services import audit_service, compliance_service
from app.schemas.auth import UserSession

router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
    dependencies=[Depends(require_permission(POLICIES["audit"].default))],
)


# ============================================================================
# Schemas
# ============================================================================


class AuditLogRead(BaseModel):
    """Audit log entry for API response."""

    id: UUID
    event_type: str
    actor_user_id: UUID | None
    actor_name: str | None
    target_type: str | None
    target_id: UUID | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit log response."""

    items: list[AuditLogRead]
    total: int
    page: int
    per_page: int


class AuditAIActivityResponse(BaseModel):
    """Summary of recent AI audit activity."""

    counts_24h: dict[str, int]
    recent: list[AuditLogRead]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    event_type: str | None = Query(None, description="Filter by event type"),
    actor_user_id: UUID | None = Query(None, description="Filter by actor"),
    start_date: datetime | None = Query(None, description="Filter events after this date"),
    end_date: datetime | None = Query(None, description="Filter events before this date"),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> AuditLogListResponse:
    """
    List audit log entries for the organization.

    Requires: Manager or Developer role
    Filters: event_type, actor_user_id, date range
    """
    logs, total, actor_names = audit_service.list_audit_logs(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
        event_type=event_type,
        actor_user_id=actor_user_id,
        start_date=start_date,
        end_date=end_date,
    )

    items = [
        AuditLogRead(
            id=log.id,
            event_type=log.event_type,
            actor_user_id=log.actor_user_id,
            actor_name=actor_names.get(log.actor_user_id) if log.actor_user_id else None,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/event-types")
def list_event_types(
    session: UserSession = Depends(get_current_session),
) -> list[str]:
    """List available audit event types for filtering."""
    return [e.value for e in AuditEventType]


@router.get("/ai-activity", response_model=AuditAIActivityResponse)
def get_ai_activity(
    hours: int = Query(24, ge=1, le=720, description="Hours to look back for counts (default 24)"),
    limit: int = Query(6, ge=1, le=50),
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
) -> AuditAIActivityResponse:
    """Get recent AI audit activity and counts for the specified time window."""
    counts, recent_logs, actor_names = audit_service.get_ai_activity(
        db=db,
        org_id=session.org_id,
        hours=hours,
        limit=limit,
    )

    recent_items = [
        AuditLogRead(
            id=log.id,
            event_type=log.event_type,
            actor_user_id=log.actor_user_id,
            actor_name=actor_names.get(log.actor_user_id) if log.actor_user_id else None,
            target_type=log.target_type,
            target_id=log.target_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in recent_logs
    ]

    return AuditAIActivityResponse(
        counts_24h=counts,
        recent=recent_items,
    )


@router.get("/exports", response_model=ExportJobListResponse)
def list_audit_exports(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["audit"].actions["export"])),
) -> ExportJobListResponse:
    """List recent audit exports for the organization."""
    jobs = compliance_service.list_export_jobs(db, session.org_id, limit=limit)
    items = []
    for job in jobs:
        download_url = (
            f"/audit/exports/{job.id}/download"
            if job.status == compliance_service.EXPORT_STATUS_COMPLETED
            else None
        )
        items.append(
            ExportJobRead(
                id=job.id,
                status=job.status,
                export_type=job.export_type,
                format=job.format,
                redact_mode=job.redact_mode,
                date_range_start=job.date_range_start,
                date_range_end=job.date_range_end,
                record_count=job.record_count,
                error_message=job.error_message,
                created_at=job.created_at,
                completed_at=job.completed_at,
                download_url=download_url,
            )
        )
    return ExportJobListResponse(items=items)


@router.post("/exports", response_model=ExportJobRead, dependencies=[Depends(require_csrf_header)])
def create_audit_export(
    payload: ExportJobCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["audit"].actions["export"])),
) -> ExportJobRead:
    """Request an async audit export job."""
    if payload.redact_mode == "full":
        if session.role != Role.DEVELOPER:
            raise HTTPException(status_code=403, detail="Full exports require Developer role")
        if not payload.acknowledgment or not payload.acknowledgment.strip():
            raise HTTPException(status_code=400, detail="Acknowledgment required for full exports")
    try:
        job = compliance_service.create_export_job(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            export_type="audit",
            start_date=payload.start_date,
            end_date=payload.end_date,
            file_format=payload.format,
            redact_mode=payload.redact_mode,
            acknowledgment=payload.acknowledgment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ExportJobRead(
        id=job.id,
        status=job.status,
        export_type=job.export_type,
        format=job.format,
        redact_mode=job.redact_mode,
        date_range_start=job.date_range_start,
        date_range_end=job.date_range_end,
        record_count=job.record_count,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        download_url=None,
    )


@router.get("/exports/{export_id}", response_model=ExportJobRead)
def get_audit_export(
    export_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["audit"].actions["export"])),
) -> ExportJobRead:
    """Get audit export job status."""
    job = compliance_service.get_export_job(db, session.org_id, export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.redact_mode == "full" and session.role != Role.DEVELOPER:
        raise HTTPException(status_code=403, detail="Full exports require Developer role")
    download_url = (
        f"/audit/exports/{job.id}/download"
        if job.status == compliance_service.EXPORT_STATUS_COMPLETED
        else None
    )
    return ExportJobRead(
        id=job.id,
        status=job.status,
        export_type=job.export_type,
        format=job.format,
        redact_mode=job.redact_mode,
        date_range_start=job.date_range_start,
        date_range_end=job.date_range_end,
        record_count=job.record_count,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        download_url=download_url,
    )


@router.get("/exports/{export_id}/download")
def download_audit_export(
    export_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(POLICIES["audit"].actions["export"])),
):
    """Download an export file via signed URL or local file."""
    job = compliance_service.get_export_job(db, session.org_id, export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status != compliance_service.EXPORT_STATUS_COMPLETED or not job.file_path:
        raise HTTPException(status_code=409, detail="Export not ready")
    if job.redact_mode == "full" and session.role != Role.DEVELOPER:
        raise HTTPException(status_code=403, detail="Full exports require Developer role")

    audit_service.log_compliance_export_downloaded(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        export_job_id=job.id,
    )
    db.commit()

    if settings.EXPORT_STORAGE_BACKEND == "s3":
        url = compliance_service.generate_s3_download_url(job.file_path)
        return RedirectResponse(url=url)

    file_path = compliance_service.resolve_local_export_path(job.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    filename = f"audit_export_{job.id}.{job.format}"
    return FileResponse(
        path=file_path,
        media_type="text/csv" if job.format == "csv" else "application/json",
        filename=filename,
    )
