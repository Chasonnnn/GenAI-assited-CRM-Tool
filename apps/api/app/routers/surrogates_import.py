"""
CSV Import API endpoints.

Provides REST interface for bulk surrogate imports via CSV upload.
"""

from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.schemas.import_template import (
    ColumnMappingItem,
    ColumnSuggestionResponse,
    EnhancedImportPreviewResponse,
    ImportApprovalItem,
    ImportRejectRequest,
    MatchingTemplate,
)

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
    require_roles,
)
from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import import_service


router = APIRouter(
    prefix="/surrogates/import",
    tags=["surrogates", "import"],
    dependencies=[Depends(require_permission(POLICIES["surrogates"].actions["import"]))],
)


# =============================================================================
# Schemas
# =============================================================================


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


class ImportSubmitResponse(BaseModel):
    import_id: UUID
    status: str
    deduplication_stats: dict | None = None
    message: str | None = None
    total_rows: int | None = None
    new_count: int | None = None
    duplicate_count: int | None = None


class ImportApprovalResponse(BaseModel):
    import_id: UUID
    status: str
    rejection_reason: str | None = None
    message: str | None = None


# =============================================================================
# Endpoints
# =============================================================================


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


# NOTE: /pending MUST come before /{import_id} to avoid routing conflict
@router.get("/pending", response_model=list[ImportApprovalItem])
def list_pending_approvals(
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """List imports awaiting admin approval."""
    imports = import_service.list_pending_approvals(db, session.org_id)

    response_items: list[ImportApprovalItem] = []
    for imp in imports:
        dedup_stats = imp.deduplication_stats
        if dedup_stats:
            duplicates = dedup_stats.get("duplicates") or []
            duplicate_count = dedup_stats.get("duplicate_emails_db", len(duplicates)) or len(
                duplicates
            )
            new_records = dedup_stats.get("new_records")
            if new_records is None:
                new_records = max(imp.total_rows - int(duplicate_count), 0)
            dedup_stats = {
                **dedup_stats,
                "duplicates": duplicates,
                "new_records": new_records,
            }

        response_items.append(
            ImportApprovalItem(
                id=imp.id,
                filename=imp.filename,
                status=imp.status,
                total_rows=imp.total_rows,
                created_at=imp.created_at,
                created_by_name=imp.created_by.display_name if imp.created_by else None,
                deduplication_stats=dedup_stats,
                column_mapping_snapshot=imp.column_mapping_snapshot,
            )
        )

    return response_items


@router.get("/{import_id:uuid}", response_model=ImportDetailResponse)
def get_import_details(
    import_id: UUID,
    request: Request,
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

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate_import_detail",
        target_id=import_record.id,
        request=request,
        details={
            "status": import_record.status,
            "total_rows": import_record.total_rows,
            "imported_count": import_record.imported_count,
            "skipped_count": import_record.skipped_count,
            "error_count": import_record.error_count,
        },
    )
    db.commit()

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


# =============================================================================
# Enhanced Preview (v2)
# =============================================================================


@router.post(
    "/preview/enhanced",
    response_model=EnhancedImportPreviewResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def preview_csv_enhanced(
    request: Request,
    file: UploadFile = File(..., description="CSV file to preview"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Enhanced CSV preview with smart detection and column suggestions.

    Features:
    - Auto-detects encoding (UTF-8, UTF-16, etc.)
    - Auto-detects delimiter (comma, tab, etc.)
    - Provides column mapping suggestions with confidence scores
    - Shows matching templates
    - Indicates AI availability for unmatched columns
    """
    content = await file.read()

    if not file.filename or not (file.filename.endswith(".csv") or file.filename.endswith(".tsv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV or TSV file",
        )

    try:
        preview = import_service.preview_import_enhanced(
            db=db,
            org_id=session.org_id,
            file_content=content,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to analyze CSV: {str(e)}",
        )

    from app.services import audit_service

    import_record = import_service.create_import_job(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        filename=file.filename,
        total_rows=preview.total_rows,
        file_content=content,
        status="pending",
    )
    import_record.detected_encoding = preview.detected_encoding
    import_record.detected_delimiter = preview.detected_delimiter
    import_record.date_ambiguity_warnings = preview.date_ambiguity_warnings
    import_record.deduplication_stats = {
        "total": preview.total_rows,
        "new_records": preview.new_records,
        "duplicates": preview.duplicate_details,
        "duplicate_emails_db": preview.duplicate_emails_db,
        "duplicate_emails_csv": preview.duplicate_emails_csv,
    }
    db.commit()

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate_import_preview_enhanced",
        target_id=None,
        request=request,
        details={
            "total_rows": preview.total_rows,
            "detected_encoding": preview.detected_encoding,
            "matched_columns": preview.matched_count,
            "unmatched_columns": preview.unmatched_count,
        },
    )
    db.commit()

    return EnhancedImportPreviewResponse(
        import_id=import_record.id,
        total_rows=preview.total_rows,
        sample_rows=preview.sample_rows,
        detected_encoding=preview.detected_encoding,
        detected_delimiter=preview.detected_delimiter,
        has_header=preview.has_header,
        column_suggestions=[
            ColumnSuggestionResponse(
                csv_column=s.csv_column,
                suggested_field=s.suggested_field,
                confidence=s.confidence,
                confidence_level=s.confidence_level.value,
                transformation=s.transformation,
                sample_values=s.sample_values,
                reason=s.reason,
                warnings=s.warnings,
                default_action=s.default_action,
                needs_inversion=s.needs_inversion,
            )
            for s in preview.column_suggestions
        ],
        matched_count=preview.matched_count,
        unmatched_count=preview.unmatched_count,
        matching_templates=[
            MatchingTemplate(
                id=t["id"],
                name=t["name"],
                match_score=t["match_score"],
            )
            for t in preview.matching_templates
        ],
        available_fields=preview.available_fields,
        duplicate_emails_db=preview.duplicate_emails_db,
        duplicate_emails_csv=preview.duplicate_emails_csv,
        validation_errors=preview.validation_errors,
        date_ambiguity_warnings=preview.date_ambiguity_warnings,
        ai_available=preview.ai_available,
    )


# =============================================================================
# AI Mapping Assistance
# =============================================================================


class AIMapRequest(BaseModel):
    """Request for AI mapping assistance."""

    unmatched_columns: list[str]
    sample_values: dict[str, list[str]]  # column -> sample values


class AIMapResponse(BaseModel):
    """AI mapping suggestions."""

    suggestions: list[ColumnSuggestionResponse]


@router.post(
    "/ai-map",
    response_model=AIMapResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def get_ai_mapping_suggestions(
    data: AIMapRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get AI-powered column mapping suggestions.

    This is opt-in - called when user clicks "Get AI Help".
    Only analyzes unmatched columns.
    PII is masked before sending to AI.
    """
    from app.services.import_ai_mapper_service import ai_suggest_mappings, is_ai_available
    from app.services.import_detection_service import ColumnSuggestion, ConfidenceLevel

    if not is_ai_available(db, session.org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI is not enabled for this organization",
        )

    # Build ColumnSuggestion objects from request
    unmatched = [
        ColumnSuggestion(
            csv_column=col,
            suggested_field=None,
            confidence=0,
            confidence_level=ConfidenceLevel.NONE,
            transformation=None,
            sample_values=data.sample_values.get(col, [])[:5],
            reason="User requested AI analysis",
        )
        for col in data.unmatched_columns
    ]

    # Get AI suggestions
    suggestions = await ai_suggest_mappings(
        db=db,
        org_id=session.org_id,
        unmatched_columns=unmatched,
    )

    return AIMapResponse(
        suggestions=[
            ColumnSuggestionResponse(
                csv_column=s.csv_column,
                suggested_field=s.suggested_field,
                confidence=s.confidence,
                confidence_level=s.confidence_level.value,
                transformation=s.transformation,
                sample_values=s.sample_values,
                reason=s.reason,
                warnings=s.warnings,
                default_action=s.default_action,
                needs_inversion=s.needs_inversion,
            )
            for s in suggestions
        ]
    )


# =============================================================================
# Approval Workflow
# =============================================================================


class ImportSubmitRequest(BaseModel):
    """Request to submit import for approval."""

    column_mappings: list[ColumnMappingItem] = Field(default_factory=list)
    unknown_column_behavior: Literal["ignore", "metadata", "warn"] = "ignore"
    save_as_template_name: str | None = None


@router.post(
    "/{import_id:uuid}/submit",
    response_model=ImportSubmitResponse,
    dependencies=[Depends(require_csrf_header)],
)
def submit_import_for_approval(
    import_id: UUID,
    data: ImportSubmitRequest | None = None,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Submit an import for admin approval.

    The import must be in 'pending' status.
    Column mappings are saved as a snapshot for the reviewer.
    """
    import_record = import_service.get_import(db, session.org_id, import_id)
    if not import_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    if import_record.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import is not in pending status (current: {import_record.status})",
        )

    data = data or ImportSubmitRequest()

    # Convert mappings for service
    from app.services.import_service import ColumnMapping

    mappings = [
        ColumnMapping(
            csv_column=m.csv_column,
            surrogate_field=m.surrogate_field,
            transformation=m.transformation,
            action=m.action,
            custom_field_key=m.custom_field_key,
        )
        for m in data.column_mappings
    ]

    dedup_stats = import_record.deduplication_stats or {
        "total": import_record.total_rows,
        "new_records": import_record.total_rows,
        "duplicates": [],
        "duplicate_emails_db": 0,
        "duplicate_emails_csv": 0,
    }

    try:
        updated = import_service.submit_for_approval(
            db=db,
            org_id=session.org_id,
            import_id=import_id,
            column_mappings=mappings,
            dedup_stats=dedup_stats,
            unknown_column_behavior=data.unknown_column_behavior,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Optionally save as template
    if data.save_as_template_name:
        from app.services import import_template_service

        import_template_service.create_template(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            name=data.save_as_template_name,
            description=f"Created from import {import_record.filename}",
            is_default=False,
            encoding=import_record.detected_encoding or "auto",
            delimiter=import_record.detected_delimiter or "auto",
            has_header=True,
            column_mappings=[m.model_dump() for m in data.column_mappings],
            transformations=None,
            unknown_column_behavior=data.unknown_column_behavior,
        )

    return ImportSubmitResponse(
        import_id=updated.id,
        status=updated.status,
        deduplication_stats=updated.deduplication_stats or dedup_stats,
    )


@router.post(
    "/{import_id:uuid}/approve",
    response_model=ImportApprovalResponse,
    dependencies=[Depends(require_csrf_header)],
)
def approve_import(
    import_id: UUID,
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """
    Approve an import for execution.

    Requires admin role. After approval, the import will be queued for processing.
    """
    from app.db.enums import JobType
    from app.services import job_service

    import_record = import_service.get_import(db, session.org_id, import_id)
    if not import_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    try:
        updated = import_service.approve_import(
            db=db,
            org_id=session.org_id,
            import_id=import_id,
            approved_by_user_id=session.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Queue background job for processing
    job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.CSV_IMPORT,
        payload={
            "import_id": str(updated.id),
            "dedupe_action": "skip",
            "use_mappings": True,
            "unknown_column_behavior": import_record.unknown_column_behavior,
        },
    )

    return ImportApprovalResponse(
        import_id=updated.id,
        status=updated.status,
        message="Import approved and queued for processing",
    )


@router.post(
    "/{import_id:uuid}/reject",
    response_model=ImportApprovalResponse,
    dependencies=[Depends(require_csrf_header)],
)
def reject_import(
    import_id: UUID,
    data: ImportRejectRequest,
    session: UserSession = Depends(require_roles([Role.ADMIN, Role.DEVELOPER])),
    db: Session = Depends(get_db),
):
    """
    Reject an import with a reason.

    Requires admin role.
    """
    import_record = import_service.get_import(db, session.org_id, import_id)
    if not import_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    try:
        updated = import_service.reject_import(
            db=db,
            org_id=session.org_id,
            import_id=import_id,
            rejected_by_user_id=session.user_id,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ImportApprovalResponse(
        import_id=updated.id,
        status=updated.status,
        rejection_reason=updated.rejection_reason,
        message=f"Import rejected: {data.reason}",
    )
