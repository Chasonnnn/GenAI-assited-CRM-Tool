"""Attachment endpoints for file uploads and downloads."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access, can_modify_case
from app.core.deps import get_current_session, get_db, require_csrf_header
from app.db.enums import Role
from app.db.models import Case
from app.schemas.auth import UserSession
from app.services import attachment_service, case_service, ip_service


router = APIRouter(prefix="/attachments", tags=["attachments"])


# =============================================================================
# Schemas
# =============================================================================

class AttachmentRead(BaseModel):
    model_config = {"from_attributes": True}
    
    id: str
    filename: str
    content_type: str
    file_size: int
    scan_status: str
    quarantined: bool
    uploaded_by_user_id: str | None
    created_at: str


class AttachmentDownloadResponse(BaseModel):
    download_url: str
    filename: str


# =============================================================================
# Helpers
# =============================================================================

def _get_case_with_access(
    db: Session,
    case_id: UUID,
    session: UserSession,
    require_write: bool = False,
) -> Case:
    """Get case and verify user has access."""
    case = case_service.get_case(db, session.org_id, case_id)
    
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    if require_write and not can_modify_case(case, session.user_id, session.role):
        raise HTTPException(status_code=403, detail="Not authorized to modify this case")
    
    return case


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/cases/{case_id}/attachments", response_model=AttachmentRead)
async def upload_attachment(
    case_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """
    Upload a file attachment to a case.
    
    File is quarantined until virus scan completes.
    """
    case = _get_case_with_access(db, case_id, session, require_write=True)
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    # Create file-like object for service
    from io import BytesIO
    file_obj = BytesIO(content)
    
    try:
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=case.organization_id,
            user_id=session.user_id,
            filename=file.filename or "untitled",
            content_type=file.content_type or "application/octet-stream",
            file=file_obj,
            file_size=file_size,
            case_id=case.id,
        )
        db.commit()
        
        return AttachmentRead(
            id=str(attachment.id),
            filename=attachment.filename,
            content_type=attachment.content_type,
            file_size=attachment.file_size,
            scan_status=attachment.scan_status,
            quarantined=attachment.quarantined,
            uploaded_by_user_id=str(attachment.uploaded_by_user_id) if attachment.uploaded_by_user_id else None,
            created_at=attachment.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cases/{case_id}/attachments", response_model=list[AttachmentRead])
async def list_attachments(
    case_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """List attachments for a case (excludes quarantined and deleted)."""
    case = _get_case_with_access(db, case_id, session)
    
    attachments = attachment_service.list_attachments(
        db=db,
        org_id=case.organization_id,
        case_id=case.id,
        include_quarantined=False,
    )
    
    return [
        AttachmentRead(
            id=str(a.id),
            filename=a.filename,
            content_type=a.content_type,
            file_size=a.file_size,
            scan_status=a.scan_status,
            quarantined=a.quarantined,
            uploaded_by_user_id=str(a.uploaded_by_user_id) if a.uploaded_by_user_id else None,
            created_at=a.created_at.isoformat(),
        )
        for a in attachments
    ]


# =============================================================================
# Intended Parent Attachment Endpoints
# =============================================================================

def _get_ip_with_access(db: Session, ip_id: UUID, session: UserSession):
    """Get intended parent and verify org access."""
    ip = ip_service.get_intended_parent(db, ip_id, session.org_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Intended parent not found")
    return ip


@router.get("/intended-parents/{ip_id}/attachments", response_model=list[AttachmentRead])
async def list_ip_attachments(
    ip_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """List attachments for an intended parent."""
    ip = _get_ip_with_access(db, ip_id, session)
    
    attachments = attachment_service.list_attachments(
        db=db,
        org_id=ip.organization_id,
        intended_parent_id=ip.id,
        include_quarantined=False,
    )
    
    return [
        AttachmentRead(
            id=str(a.id),
            filename=a.filename,
            content_type=a.content_type,
            file_size=a.file_size,
            scan_status=a.scan_status,
            quarantined=a.quarantined,
            uploaded_by_user_id=str(a.uploaded_by_user_id) if a.uploaded_by_user_id else None,
            created_at=a.created_at.isoformat(),
        )
        for a in attachments
    ]


@router.post("/intended-parents/{ip_id}/attachments", response_model=AttachmentRead)
async def upload_ip_attachment(
    ip_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """Upload a file attachment to an intended parent."""
    ip = _get_ip_with_access(db, ip_id, session)
    
    content = await file.read()
    file_size = len(content)
    
    from io import BytesIO
    file_obj = BytesIO(content)
    
    try:
        attachment = attachment_service.upload_attachment(
            db=db,
            org_id=ip.organization_id,
            intended_parent_id=ip.id,
            user_id=session.user_id,
            filename=file.filename or "untitled",
            content_type=file.content_type or "application/octet-stream",
            file=file_obj,
            file_size=file_size,
        )
        db.commit()
        
        return AttachmentRead(
            id=str(attachment.id),
            filename=attachment.filename,
            content_type=attachment.content_type,
            file_size=attachment.file_size,
            scan_status=attachment.scan_status,
            quarantined=attachment.quarantined,
            uploaded_by_user_id=str(attachment.uploaded_by_user_id) if attachment.uploaded_by_user_id else None,
            created_at=attachment.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{attachment_id}/download", response_model=AttachmentDownloadResponse)
async def download_attachment(
    attachment_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Get signed download URL for an attachment."""
    attachment = attachment_service.get_attachment(
        db=db,
        org_id=session.org_id,
        attachment_id=attachment_id,
    )
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    if attachment.quarantined:
        raise HTTPException(status_code=403, detail="File is pending virus scan")
    
    # Verify access: case attachment requires case access, IP attachment uses org-wide access
    if attachment.case_id:
        _get_case_with_access(db, attachment.case_id, session)
    elif attachment.intended_parent_id:
        # IP attachments use org-wide access (already verified by get_attachment org_id filter)
        _get_ip_with_access(db, attachment.intended_parent_id, session)
    
    url = attachment_service.get_download_url(
        db=db,
        org_id=session.org_id,
        attachment_id=attachment_id,
        user_id=session.user_id,
    )
    db.commit()
    
    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

    if url.startswith("/"):
        url = f"{request.base_url}".rstrip("/") + url
    
    return AttachmentDownloadResponse(
        download_url=url,
        filename=attachment.filename,
    )


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
    _: str = Depends(require_csrf_header),
):
    """Soft-delete an attachment (uploader or Manager+ only)."""
    attachment = attachment_service.get_attachment(
        db=db,
        org_id=session.org_id,
        attachment_id=attachment_id,
    )
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Access control: uploader or Manager+
    is_manager = session.role in (Role.ADMIN, Role.DEVELOPER)
    is_uploader = attachment.uploaded_by_user_id == session.user_id
    
    if not is_manager and not is_uploader:
        raise HTTPException(status_code=403, detail="Only uploader or manager can delete")

    if attachment.case_id:
        _get_case_with_access(db, attachment.case_id, session, require_write=True)
    
    success = attachment_service.soft_delete_attachment(
        db=db,
        org_id=session.org_id,
        attachment_id=attachment_id,
        user_id=session.user_id,
    )
    db.commit()
    
    if not success:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    return {"deleted": True}


@router.get("/local/{storage_key:path}")
async def download_local_attachment(
    storage_key: str,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Serve local attachments (dev only)."""
    from fastapi.responses import FileResponse
    from app.services.attachment_service import _get_local_storage_path

    attachment = attachment_service.get_attachment_by_storage_key(
        db=db,
        org_id=session.org_id,
        storage_key=storage_key,
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if attachment.quarantined:
        raise HTTPException(status_code=403, detail="File is pending virus scan")

    # Verify access: case attachment requires case access, IP attachment uses org-wide access
    if attachment.case_id:
        _get_case_with_access(db, attachment.case_id, session)
    elif attachment.intended_parent_id:
        _get_ip_with_access(db, attachment.intended_parent_id, session)

    file_path = f"{_get_local_storage_path()}/{storage_key}"
    return FileResponse(
        file_path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )
