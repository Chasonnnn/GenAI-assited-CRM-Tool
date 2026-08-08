"""Admin APIs for organization-level messaging consent, templates, media, and exports."""

import os
from datetime import datetime
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.deps import get_db, require_csrf_header, require_permission, require_roles
from app.core.permissions import PermissionKey as P
from app.db.enums import AuditEventType, JobStatus, JobType, Role
from app.schemas.auth import UserSession
from app.schemas.messaging import (
    MessagingConsentImportRequest,
    MessagingConsentRevocationRequest,
    MessagingConsentTransitionResponse,
    MessagingContentClassification,
    MessagingMediaAccessResponse,
    MessagingMediaAssetResponse,
    MessagingMediaScanStatus,
    MessagingPurpose,
    MessagingTemplateCreateRequest,
    MessagingTemplateNextVersionRequest,
    MessagingTemplateResponse,
    MessagingTemplateStatus,
)
from app.services import (
    admin_export_service,
    audit_service,
    compliance_service,
    job_service,
    message_content_service,
    messaging_consent_service,
)

router = APIRouter(
    prefix="/messaging",
    tags=["messaging"],
    dependencies=[Depends(require_roles([Role.ADMIN, Role.DEVELOPER]))],
)

media_router = APIRouter(prefix="/messaging/media", tags=["messaging-media"])


class MessagingExportJobResponse(BaseModel):
    job_id: str
    status: str
    export_type: str
    filename: str | None
    created_at: datetime
    completed_at: datetime | None
    error: str | None


class MessagingExportDownloadResponse(BaseModel):
    download_url: str
    filename: str


def _messaging_export_job_response(job: object) -> MessagingExportJobResponse:
    payload = job.payload or {}
    return MessagingExportJobResponse(
        job_id=str(job.id),
        status=job.status,
        export_type=payload.get("export_type", ""),
        filename=payload.get("filename"),
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.last_error,
    )


def _get_messaging_export_job(db: Session, job_id: UUID, organization_id: UUID):
    job = job_service.get_job(db, job_id, organization_id)
    if (
        not job
        or job.job_type != JobType.ADMIN_EXPORT.value
        or (job.payload or {}).get("export_type") != "messaging_zip"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    return job


def _response(
    result: messaging_consent_service.ConsentTransitionResult,
) -> MessagingConsentTransitionResponse:
    return MessagingConsentTransitionResponse(
        contact_id=result.contact_id,
        phone_last4=result.phone_last4,
        purpose_states=result.purpose_states,
        global_suppression_active=result.global_suppression_active,
        global_suppression_reason=result.global_suppression_reason,
        evidence_id=result.evidence_id,
        classification=result.classification,
    )


def _raise_http_error(exc: ValueError) -> None:
    if isinstance(exc, messaging_consent_service.MessagingConsentEntityNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, messaging_consent_service.MessagingConsentIdempotencyConflict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _raise_content_http_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (message_content_service.TemplateNotFound, message_content_service.MessagingMediaNotFound),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            message_content_service.TemplateStateConflict,
            message_content_service.MessagingMediaUnavailable,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, message_content_service.MessagingMediaStorageError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/exports",
    response_model=MessagingExportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf_header)],
)
def create_messaging_export(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingExportJobResponse:
    """Queue a sensitive organization messaging archive without provider credentials."""
    filename = admin_export_service.build_export_filename("messaging_zip")
    job = job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.ADMIN_EXPORT,
        payload={
            "export_type": "messaging_zip",
            "filename": filename,
            "requested_by": str(session.user_id),
        },
    )
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_EXPORT_MESSAGING,
        actor_user_id=session.user_id,
        details={"export": "messaging_zip", "stage": "requested"},
    )
    db.commit()
    return _messaging_export_job_response(job)


@router.get("/exports/{job_id}", response_model=MessagingExportJobResponse)
def get_messaging_export(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingExportJobResponse:
    """Get one organization-scoped messaging export job."""
    return _messaging_export_job_response(_get_messaging_export_job(db, job_id, session.org_id))


@router.get(
    "/exports/{job_id}/download",
    response_model=MessagingExportDownloadResponse,
)
def download_messaging_export(
    job_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingExportDownloadResponse:
    """Return a local or signed download URL for a completed messaging archive."""
    job = _get_messaging_export_job(db, job_id, session.org_id)
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export not ready")
    payload = job.payload or {}
    file_path = payload.get("file_path")
    filename = payload.get("filename")
    if not file_path or not filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file missing")

    if app_settings.EXPORT_STORAGE_BACKEND == "s3":
        download_url = compliance_service.generate_s3_download_url(file_path)
    else:
        download_url = f"/messaging/exports/{job_id}/file"
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_EXPORT_MESSAGING,
        actor_user_id=session.user_id,
        details={"export": "messaging_zip", "stage": "downloaded"},
    )
    db.commit()
    if download_url.startswith("/"):
        download_url = f"{request.base_url}".rstrip("/") + download_url
    return MessagingExportDownloadResponse(download_url=download_url, filename=filename)


@router.get("/exports/{job_id}/file")
def download_messaging_export_file(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> object:
    """Serve a completed local messaging archive."""
    if app_settings.EXPORT_STORAGE_BACKEND == "s3":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3 exports use signed URLs",
        )
    job = _get_messaging_export_job(db, job_id, session.org_id)
    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export not ready")
    payload = job.payload or {}
    file_path = payload.get("file_path")
    filename = payload.get("filename")
    if not file_path or not filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file missing")
    try:
        resolved_path = admin_export_service.resolve_admin_export_path(file_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file missing",
        ) from exc
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file missing")
    return FileResponse(
        resolved_path,
        media_type="application/zip",
        filename=filename,
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/consents/import",
    response_model=MessagingConsentTransitionResponse,
    dependencies=[Depends(require_csrf_header)],
)
def import_messaging_consent(
    request: MessagingConsentImportRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingConsentTransitionResponse:
    """Import one explicit consent record or preserve an unchecked input as unknown."""
    try:
        result = messaging_consent_service.record_opt_in(
            db,
            organization_id=session.org_id,
            recorded_by_user_id=session.user_id,
            **request.model_dump(),
        )
    except ValueError as exc:
        _raise_http_error(exc)
        raise AssertionError("unreachable") from exc
    return _response(result)


@router.post(
    "/consents/revocations",
    response_model=MessagingConsentTransitionResponse,
    dependencies=[Depends(require_csrf_header)],
)
def record_messaging_revocation(
    request: MessagingConsentRevocationRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingConsentTransitionResponse:
    """Classify and record a global, purpose-specific, ambiguous, or restore instruction."""
    try:
        result = messaging_consent_service.apply_revocation_instruction(
            db,
            organization_id=session.org_id,
            recorded_by_user_id=session.user_id,
            **request.model_dump(),
        )
    except ValueError as exc:
        _raise_http_error(exc)
        raise AssertionError("unreachable") from exc
    return _response(result)


@router.post(
    "/templates",
    response_model=MessagingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_messaging_template(
    request: MessagingTemplateCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingTemplateResponse:
    """Create version one of an immutable organization template family."""
    try:
        template = message_content_service.create_template_draft(
            db,
            organization_id=session.org_id,
            created_by_user_id=session.user_id,
            **request.model_dump(),
        )
    except (ValueError, RuntimeError) as exc:
        _raise_content_http_error(exc)
        raise AssertionError("unreachable") from exc
    return MessagingTemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_key}/versions",
    response_model=MessagingTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_messaging_template_version(
    template_key: UUID,
    request: MessagingTemplateNextVersionRequest,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingTemplateResponse:
    """Fork the latest immutable template row into its next draft version."""
    try:
        template = message_content_service.create_next_template_version(
            db,
            organization_id=session.org_id,
            template_key=template_key,
            created_by_user_id=session.user_id,
            **request.model_dump(),
        )
    except (ValueError, RuntimeError) as exc:
        _raise_content_http_error(exc)
        raise AssertionError("unreachable") from exc
    return MessagingTemplateResponse.model_validate(template)


@router.get("/templates", response_model=list[MessagingTemplateResponse])
def list_messaging_templates(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
    purpose: Annotated[MessagingPurpose | None, Query()] = None,
    template_status: Annotated[
        MessagingTemplateStatus | None,
        Query(alias="status"),
    ] = None,
) -> list[MessagingTemplateResponse]:
    """List organization-scoped immutable template versions."""
    templates = message_content_service.list_templates(
        db,
        session.org_id,
        purpose=purpose,
        status=template_status,
    )
    return [MessagingTemplateResponse.model_validate(template) for template in templates]


@router.get("/templates/{template_id}", response_model=MessagingTemplateResponse)
def get_messaging_template(
    template_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingTemplateResponse:
    """Get one exact organization-scoped template version."""
    template = message_content_service.get_template(db, session.org_id, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return MessagingTemplateResponse.model_validate(template)


@router.post(
    "/templates/{template_id}/publish",
    response_model=MessagingTemplateResponse,
    dependencies=[Depends(require_csrf_header)],
)
def publish_messaging_template(
    template_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingTemplateResponse:
    """Publish one exact draft and retire its previously published family version."""
    try:
        template = message_content_service.publish_template(
            db,
            organization_id=session.org_id,
            template_id=template_id,
        )
    except (ValueError, RuntimeError) as exc:
        _raise_content_http_error(exc)
        raise AssertionError("unreachable") from exc
    return MessagingTemplateResponse.model_validate(template)


@router.post(
    "/media",
    response_model=list[MessagingMediaAssetResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def upload_messaging_media(
    files: Annotated[list[UploadFile], File()],
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(P.INTEGRATIONS_MANAGE)),
    ],
    content_classification: Annotated[MessagingContentClassification, Form()] = "no_phi",
) -> list[MessagingMediaAssetResponse]:
    """Store up to ten Twilio-safe images as pending, immutable scan-gated assets."""
    uploads = [
        message_content_service.MediaUpload(
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            file=file.file,
        )
        for file in files
    ]
    try:
        assets = message_content_service.upload_media_assets(
            db,
            organization_id=session.org_id,
            uploads=uploads,
            content_classification=content_classification,
        )
    except (ValueError, RuntimeError) as exc:
        _raise_content_http_error(exc)
        raise AssertionError("unreachable") from exc
    return [MessagingMediaAssetResponse.model_validate(asset) for asset in assets]


@router.get("/media", response_model=list[MessagingMediaAssetResponse])
def list_messaging_media(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
    scan_status: Annotated[MessagingMediaScanStatus | None, Query()] = None,
) -> list[MessagingMediaAssetResponse]:
    """List immutable outbound media metadata within one organization."""
    assets = message_content_service.list_media_assets(
        db,
        session.org_id,
        scan_status=scan_status,
    )
    return [MessagingMediaAssetResponse.model_validate(asset) for asset in assets]


@router.get("/media/{asset_id}", response_model=MessagingMediaAssetResponse)
def get_messaging_media(
    asset_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingMediaAssetResponse:
    """Get one organization-scoped outbound media record."""
    asset = message_content_service.get_media_asset(db, session.org_id, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    return MessagingMediaAssetResponse.model_validate(asset)


@router.post(
    "/media/{asset_id}/access",
    response_model=MessagingMediaAccessResponse,
    dependencies=[Depends(require_csrf_header)],
)
def issue_messaging_media_access(
    asset_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(require_permission(P.INTEGRATIONS_MANAGE))],
) -> MessagingMediaAccessResponse:
    """Issue a short-lived method-neutral capability for Twilio GET and HEAD fetches."""
    try:
        grant = message_content_service.issue_media_access(
            db,
            organization_id=session.org_id,
            asset_id=asset_id,
        )
    except (ValueError, RuntimeError) as exc:
        _raise_content_http_error(exc)
        raise AssertionError("unreachable") from exc
    asset = message_content_service.get_media_asset(db, session.org_id, asset_id)
    assert asset is not None
    query = urlencode(
        {
            "expires": int(grant.expires_at.timestamp()),
            "signature": grant.signature,
        }
    )
    base_url = app_settings.API_BASE_URL.rstrip("/")
    return MessagingMediaAccessResponse(
        url=f"{base_url}/messaging/media/{asset.id}/content?{query}",
        expires_at=grant.expires_at,
        content_type=asset.content_type,
        byte_size=asset.byte_size,
    )


def _signed_media_response(
    *,
    asset_id: UUID,
    expires: int,
    signature: str,
    db: Session,
    include_body: bool,
) -> Response:
    try:
        media = message_content_service.load_signed_media(
            db,
            asset_id=asset_id,
            expires_at=expires,
            signature=signature,
        )
    except message_content_service.InvalidMediaAccessSignature as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid media access",
        ) from exc
    except message_content_service.MessagingMediaNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media not found"
        ) from exc
    except message_content_service.MessagingMediaStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media storage unavailable",
        ) from exc
    headers = {
        "Cache-Control": "private, max-age=300",
        "Content-Length": str(media.asset.byte_size),
        "X-Content-Type-Options": "nosniff",
    }
    return Response(
        content=media.content if include_body else b"",
        media_type=media.asset.content_type,
        headers=headers,
    )


@media_router.get("/{asset_id}/content", response_class=Response)
def get_signed_messaging_media(
    asset_id: UUID,
    expires: Annotated[int, Query(gt=0)],
    signature: Annotated[str, Query(min_length=64, max_length=64)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Fetch clean media with a short-lived capability; filenames never enter the URL."""
    return _signed_media_response(
        asset_id=asset_id,
        expires=expires,
        signature=signature,
        db=db,
        include_body=True,
    )


@media_router.head("/{asset_id}/content", response_class=Response)
def head_signed_messaging_media(
    asset_id: UUID,
    expires: Annotated[int, Query(gt=0)],
    signature: Annotated[str, Query(min_length=64, max_length=64)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Validate and inspect the same signed clean-media contract without a response body."""
    return _signed_media_response(
        asset_id=asset_id,
        expires=expires,
        signature=signature,
        db=db,
        include_body=False,
    )
