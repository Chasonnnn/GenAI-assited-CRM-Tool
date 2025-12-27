"""
CSV Import API endpoints.

Provides REST interface for bulk case imports via CSV upload.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.db.models import CaseImport
from app.schemas.auth import UserSession
from app.services import import_service


router = APIRouter(
    prefix="/cases/import",
    tags=["cases", "import"],
    dependencies=[Depends(require_permission(POLICIES["cases"].actions["import"]))],
)


# =============================================================================
# Schemas
# =============================================================================

class ImportPreviewResponse(BaseModel):
    total_rows: int
    sample_rows: list[dict]
    detected_columns: list[str]
    unmapped_columns: list[str]
    duplicate_emails_db: int
    duplicate_emails_csv: int
    validation_errors: int


class ImportExecuteRequest(BaseModel):
    filename: str
    file_content: str  # Base64 or raw CSV string
    dedupe_action: str = "skip"  # "skip" duplicates


class ImportExecuteResponse(BaseModel):
    import_id: UUID
    message: str


class ImportHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    status: str
    total_rows: int
    imported_count: int | None
    skipped_count: int | None
    error_count: int | None
    created_at: str
    completed_at: str | None


class ImportDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    status: str
    total_rows: int
    imported_count: int | None
    skipped_count: int | None
    error_count: int | None
    errors: list[dict] | None
    created_at: str
    completed_at: str | None


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def preview_csv_import(
    file: UploadFile = File(..., description="CSV file to preview"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Upload and preview CSV file before importing.
    
    Returns column mapping, sample data, and duplicate counts.
    """
    # Read file
    content = await file.read()
    
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # Generate preview
    try:
        preview = import_service.preview_import(
            db=db,
            org_id=session.org_id,
            file_content=content,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}"
        )
    
    return ImportPreviewResponse(
        total_rows=preview.total_rows,
        sample_rows=preview.sample_rows,
        detected_columns=preview.detected_columns,
        unmapped_columns=preview.unmapped_columns,
        duplicate_emails_db=preview.duplicate_emails_db,
        duplicate_emails_csv=preview.duplicate_emails_csv,
        validation_errors=preview.validation_errors,
    )


@router.post(
    "/execute",
    response_model=ImportExecuteResponse,
    status_code=status.HTTP_202_ACCEPTED,  # Async - queued for background processing
    dependencies=[Depends(require_csrf_header)],
)
async def execute_csv_import(
    file: UploadFile = File(..., description="CSV file to import"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Execute CSV import asynchronously.
    
    Queues import for background processing and returns immediately.
    Use GET /cases/import/{id} to check status.
    """
    import base64
    from app.db.enums import JobType
    from app.services import job_service
    
    # Read file
    content = await file.read()
    
    # Validate
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # Quick parse to get row count
    try:
        _, rows = import_service.parse_csv_file(content)
        total_rows = len(rows)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV: {str(e)}"
        )
    
    # Create import record with pending status
    import_record = import_service.create_import_job(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        filename=file.filename,
        total_rows=total_rows,
    )
    
    # Queue background job for processing
    job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.CSV_IMPORT,
        payload={
            "import_id": str(import_record.id),
            "file_content_base64": base64.b64encode(content).decode("utf-8"),
            "dedupe_action": "skip",
        },
    )
    
    return ImportExecuteResponse(
        import_id=import_record.id,
        message=f"Import queued for processing. {total_rows} rows will be processed in background."
    )


@router.get("", response_model=list[ImportHistoryItem])
def list_imports(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List recent imports for the organization."""
    imports = import_service.list_imports(
        db=db,
        org_id=session.org_id,
        limit=50,
    )
    
    return [
        ImportHistoryItem(
            id=imp.id,
            filename=imp.filename,
            status=imp.status,
            total_rows=imp.total_rows,
            imported_count=imp.imported_count,
            skipped_count=imp.skipped_count,
            error_count=imp.error_count,
            created_at=imp.created_at.isoformat(),
            completed_at=imp.completed_at.isoformat() if imp.completed_at else None,
        )
        for imp in imports
    ]


@router.get("/{import_id}", response_model=ImportDetailResponse)
def get_import_details(
    import_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get detailed import information including errors."""
    import_record = import_service.get_import(
        db=db,
        org_id=session.org_id,
        import_id=import_id,
    )
    
    if not import_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")
    
    return ImportDetailResponse(
        id=import_record.id,
        filename=import_record.filename,
        status=import_record.status,
        total_rows=import_record.total_rows,
        imported_count=import_record.imported_count,
        skipped_count=import_record.skipped_count,
        error_count=import_record.error_count,
        errors=import_record.errors,
        created_at=import_record.created_at.isoformat(),
        completed_at=import_record.completed_at.isoformat() if import_record.completed_at else None,
    )
