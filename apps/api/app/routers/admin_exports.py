"""Developer-only exports for cases, configuration, and analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.core.rate_limit import limiter
from app.db.enums import AuditEventType, JobStatus, JobType
from app.schemas.auth import UserSession
from app.services import (
    admin_export_service,
    audit_service,
    compliance_service,
    job_service,
)


router = APIRouter(prefix="/admin/exports", tags=["Admin - Exports"])

EXPORT_EVENT_MAP = {
    "surrogates_csv": AuditEventType.DATA_EXPORT_SURROGATES,
    "org_config_zip": AuditEventType.DATA_EXPORT_CONFIG,
    "analytics_zip": AuditEventType.DATA_EXPORT_ANALYTICS,
}


class AdminExportJobResponse(BaseModel):
    job_id: str
    status: str
    export_type: str
    filename: str | None
    created_at: datetime
    completed_at: datetime | None
    error: str | None


class AdminExportDownloadResponse(BaseModel):
    download_url: str
    filename: str


def _build_job_response(job) -> AdminExportJobResponse:
    payload = job.payload or {}
    return AdminExportJobResponse(
        job_id=str(job.id),
        status=job.status,
        export_type=payload.get("export_type", ""),
        filename=payload.get("filename"),
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.last_error,
    )


def _schedule_export_job(
    db: Session,
    session: UserSession,
    export_type: str,
    filename: str,
    details: dict | None = None,
    payload: dict | None = None,
):
    job_payload = {
        "export_type": export_type,
        "filename": filename,
        "requested_by": str(session.user_id),
    }
    if payload:
        job_payload.update(payload)

    job = job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.ADMIN_EXPORT,
        payload=job_payload,
    )

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=EXPORT_EVENT_MAP[export_type],
        actor_user_id=session.user_id,
        details={"export": export_type, "stage": "requested", **(details or {})},
    )
    db.commit()

    return _build_job_response(job)


@router.post(
    "/surrogates",
    response_model=AdminExportJobResponse,
    status_code=202,
    dependencies=[Depends(require_csrf_header)],
)
@limiter.limit("5/minute")
def export_surrogates(
    request: Request,
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
) -> AdminExportJobResponse:
    """Queue a surrogates export (CSV)."""
    filename = admin_export_service.build_export_filename("surrogates_csv")
    return _schedule_export_job(db, session, "surrogates_csv", filename)


@router.post(
    "/config",
    response_model=AdminExportJobResponse,
    status_code=202,
    dependencies=[Depends(require_csrf_header)],
)
@limiter.limit("5/minute")
def export_config(
    request: Request,
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
) -> AdminExportJobResponse:
    """Queue an organization configuration export (ZIP)."""
    filename = admin_export_service.build_export_filename("org_config_zip")
    return _schedule_export_job(db, session, "org_config_zip", filename)


@router.post(
    "/analytics",
    response_model=AdminExportJobResponse,
    status_code=202,
    dependencies=[Depends(require_csrf_header)],
)
@limiter.limit("5/minute")
def export_analytics(
    request: Request,
    from_date: Optional[str] = Query(None, description="ISO date string"),
    to_date: Optional[str] = Query(None, description="ISO date string"),
    ad_id: Optional[str] = Query(None, description="Optional campaign filter"),
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
) -> AdminExportJobResponse:
    """Queue analytics export datasets (ZIP)."""
    filename = admin_export_service.build_export_filename("analytics_zip")
    return _schedule_export_job(
        db,
        session,
        "analytics_zip",
        filename,
        details={"from_date": from_date, "to_date": to_date, "ad_id": ad_id},
        payload={"from_date": from_date, "to_date": to_date, "ad_id": ad_id},
    )


@router.get("/jobs/{job_id}", response_model=AdminExportJobResponse)
def get_export_job(
    job_id: UUID,
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
) -> AdminExportJobResponse:
    """Get admin export job status."""
    job = job_service.get_job(db, job_id, session.org_id)
    if not job or job.job_type != JobType.ADMIN_EXPORT.value:
        raise HTTPException(status_code=404, detail="Export job not found")
    return _build_job_response(job)


@router.get("/jobs/{job_id}/download", response_model=AdminExportDownloadResponse)
def download_export(
    job_id: UUID,
    request: Request,
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
) -> AdminExportDownloadResponse:
    """Get a download URL for a completed admin export."""
    job = job_service.get_job(db, job_id, session.org_id)
    if not job or job.job_type != JobType.ADMIN_EXPORT.value:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Export not ready")

    payload = job.payload or {}
    file_path = payload.get("file_path")
    filename = payload.get("filename")
    export_type = payload.get("export_type")
    if not file_path or not filename or not export_type:
        raise HTTPException(status_code=404, detail="Export file missing")

    if settings.EXPORT_STORAGE_BACKEND == "s3":
        download_url = compliance_service.generate_s3_download_url(file_path)
    else:
        download_url = f"/admin/exports/jobs/{job_id}/file"

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=EXPORT_EVENT_MAP.get(export_type, AuditEventType.DATA_EXPORT_SURROGATES),
        actor_user_id=session.user_id,
        details={"export": export_type, "stage": "downloaded"},
    )
    db.commit()

    if download_url.startswith("/"):
        download_url = f"{request.base_url}".rstrip("/") + download_url

    return AdminExportDownloadResponse(download_url=download_url, filename=filename)


@router.get("/jobs/{job_id}/file")
def download_export_file(
    job_id: UUID,
    session: UserSession = Depends(require_permission(P.ADMIN_EXPORTS_MANAGE)),
    db: Session = Depends(get_db),
):
    """Serve a local admin export file when using local storage."""
    if settings.EXPORT_STORAGE_BACKEND == "s3":
        raise HTTPException(status_code=400, detail="S3 exports use signed URLs")

    job = job_service.get_job(db, job_id, session.org_id)
    if not job or job.job_type != JobType.ADMIN_EXPORT.value:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="Export not ready")

    payload = job.payload or {}
    file_path = payload.get("file_path")
    filename = payload.get("filename")
    export_type = payload.get("export_type")
    if not file_path or not filename or not export_type:
        raise HTTPException(status_code=404, detail="Export file missing")

    resolved_path = admin_export_service.resolve_admin_export_path(file_path)
    media_type = "text/csv" if export_type == "surrogates_csv" else "application/zip"

    return FileResponse(
        resolved_path,
        media_type=media_type,
        filename=filename,
        status_code=status.HTTP_200_OK,
    )
