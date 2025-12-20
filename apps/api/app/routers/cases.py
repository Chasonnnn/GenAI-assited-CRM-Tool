"""Cases router - API endpoints for case management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access, can_modify_case
from app.core.deps import (
    CSRF_HEADER,
    can_archive,
    can_assign,
    can_hard_delete,
    get_current_session,
    get_db,
    is_owner_or_can_manage,
    require_csrf_header,
    require_permission,
)
from app.db.enums import CaseSource, Role, ROLES_CAN_ARCHIVE, OwnerType
from app.db.models import User, Queue
from app.schemas.auth import UserSession
from app.schemas.case import (
    CaseAssign,
    CaseCreate,
    CaseHandoffDeny,
    CaseListItem,
    CaseListResponse,
    CaseRead,
    CaseStats,
    CaseStatusChange,
    CaseStatusHistoryRead,
    CaseUpdate,
    BulkAssign,
    CaseActivityRead,
    CaseActivityResponse,
)
from app.services import case_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter()


def _case_to_read(case, db: Session) -> CaseRead:
    """Convert Case model to CaseRead schema with joined user names."""
    owner_name = None
    if case.owner_type == OwnerType.USER.value:
        user = db.query(User).filter(User.id == case.owner_id).first()
        owner_name = user.display_name if user else None
    elif case.owner_type == OwnerType.QUEUE.value:
        queue = db.query(Queue).filter(Queue.id == case.owner_id).first()
        owner_name = queue.name if queue else None
    
    return CaseRead(
        id=case.id,
        case_number=case.case_number,
        stage_id=case.stage_id,
        status_label=case.status_label,
        source=CaseSource(case.source),
        is_priority=case.is_priority,
        owner_type=case.owner_type,
        owner_id=case.owner_id,
        owner_name=owner_name,
        created_by_user_id=case.created_by_user_id,
        full_name=case.full_name,
        email=case.email,
        phone=case.phone,
        state=case.state,
        date_of_birth=case.date_of_birth,
        race=case.race,
        height_ft=case.height_ft,
        weight_lb=case.weight_lb,
        is_age_eligible=case.is_age_eligible,
        is_citizen_or_pr=case.is_citizen_or_pr,
        has_child=case.has_child,
        is_non_smoker=case.is_non_smoker,
        has_surrogate_experience=case.has_surrogate_experience,
        num_deliveries=case.num_deliveries,
        num_csections=case.num_csections,
        is_archived=case.is_archived,
        archived_at=case.archived_at,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _case_to_list_item(case, db: Session) -> CaseListItem:
    """Convert Case model to CaseListItem schema."""
    from datetime import date
    
    # Use preloaded relationships instead of separate queries (fixes N+1)
    owner_name = None
    if case.owner_type == OwnerType.USER.value and case.owner_user:
        owner_name = case.owner_user.display_name
    elif case.owner_type == OwnerType.QUEUE.value and case.owner_queue:
        owner_name = case.owner_queue.name
    
    # Calculate age from date_of_birth
    age = None
    if case.date_of_birth:
        today = date.today()
        dob = case.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    
    # Calculate BMI from height_ft and weight_lb
    # BMI = (weight in lbs / (height in inches)^2) * 703
    bmi = None
    if case.height_ft and case.weight_lb:
        height_inches = case.height_ft * 12  # Convert feet to inches
        if height_inches > 0:
            bmi = round((case.weight_lb / (height_inches ** 2)) * 703, 1)
    
    return CaseListItem(
        id=case.id,
        case_number=case.case_number,
        stage_id=case.stage_id,
        status_label=case.status_label,
        source=CaseSource(case.source),
        full_name=case.full_name,
        email=case.email,
        phone=case.phone,
        state=case.state,
        owner_type=case.owner_type,
        owner_id=case.owner_id,
        owner_name=owner_name,
        is_priority=case.is_priority,
        is_archived=case.is_archived,
        age=age,
        bmi=bmi,
        created_at=case.created_at,
    )


@router.get("/stats", response_model=CaseStats)
def get_case_stats(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get aggregated case statistics for dashboard."""
    from app.services import task_service
    
    stats = case_service.get_case_stats(db, session.org_id)
    
    # Add pending tasks count (cross-module)
    pending_tasks = task_service.count_pending_tasks(db, session.org_id)
    
    return CaseStats(
        total=stats["total"],
        by_status=stats["by_status"],
        this_week=stats["this_week"],
        this_month=stats["this_month"],
        pending_tasks=pending_tasks,
    )


@router.get("/assignees")
def get_assignees(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get list of org members who can be assigned cases.
    
    Returns users with their ID, name, and role.
    """
    from app.db.models import Membership
    
    members = db.query(Membership).filter(
        Membership.organization_id == session.org_id
    ).all()
    
    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        if user:
            result.append({
                "id": str(user.id),
                "name": user.display_name,
                "role": m.role,
            })
    
    return result


@router.get("", response_model=CaseListResponse)
def list_cases(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    stage_id: UUID | None = None,
    source: CaseSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = Query(None, max_length=100),
    include_archived: bool = False,
    queue_id: UUID | None = None,
    owner_type: str | None = Query(None, pattern="^(user|queue)$"),
    created_from: str | None = Query(None, description="Filter by creation date from (ISO format)"),
    created_to: str | None = Query(None, description="Filter by creation date to (ISO format)"),
):
    """
    List cases with filters and pagination.
    
    - Default excludes archived cases
    - Search (q) searches name, email, phone, case_number
    - Intake specialists only see their owned cases
    - queue_id: Filter by cases in a specific queue
    - owner_type: Filter by owner type ('user' or 'queue')
    - owner_id: Filter by owner ID (when owner_type='user')
    - created_from/created_to: ISO date strings for date range filtering
    - Post-approval cases hidden if user lacks view_post_approval_cases permission
    """
    from app.services import permission_service
    
    # Permission-based stage filtering (Developer bypasses via permission_service)
    exclude_stage_types = []
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "view_post_approval_cases"
    ):
        exclude_stage_types.append("post_approval")
    
    cases, total = case_service.list_cases(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
        stage_id=stage_id,
        source=source,
        owner_id=owner_id,
        q=q,
        include_archived=include_archived,
        role_filter=session.role,
        user_id=session.user_id,
        owner_type=owner_type,
        queue_id=queue_id,
        created_from=created_from,
        created_to=created_to,
        exclude_stage_types=exclude_stage_types if exclude_stage_types else None,
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return CaseListResponse(
        items=[_case_to_list_item(c, db) for c in cases],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# =============================================================================
# CSV Import Endpoints
# =============================================================================

from fastapi import File, UploadFile, Request
from pydantic import BaseModel
from app.services import import_service


class ImportPreviewResponse(BaseModel):
    """Preview response for CSV import."""
    total_rows: int
    sample_rows: list[dict]
    detected_columns: list[str]
    unmapped_columns: list[str]
    duplicate_emails_db: int
    duplicate_emails_csv: int
    validation_errors: int


class ImportConfirmRequest(BaseModel):
    """Request to confirm and execute import."""
    import_id: UUID
    dedupe_action: str = "skip"  # "skip" or "update" (future)


class ImportStatusResponse(BaseModel):
    """Status of an import job."""
    id: UUID
    filename: str
    status: str
    total_rows: int
    imported_count: int
    skipped_count: int
    error_count: int
    errors: list[dict] | None
    created_at: str
    completed_at: str | None


@router.post("/import/preview", response_model=ImportPreviewResponse, dependencies=[Depends(require_csrf_header)])
async def preview_import(
    request: Request,
    file: UploadFile = File(...),
    session: UserSession = Depends(require_permission("edit_cases")),
    db: Session = Depends(get_db),
):
    """
    Preview CSV import without executing.
    
    Returns:
    - Column mapping results
    - Sample rows (first 5)
    - Duplicate detection counts (DB + within CSV)
    - Validation error count
    
    Requires: Manager+ role
    """
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    preview = import_service.preview_import(db, session.org_id, content)
    
    # Create import job for later confirmation
    import_job = import_service.create_import_job(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        filename=file.filename,
        total_rows=preview.total_rows,
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


@router.post("/import/confirm", response_model=ImportStatusResponse, dependencies=[Depends(require_csrf_header)])
async def confirm_import(
    request: Request,
    file: UploadFile = File(...),
    session: UserSession = Depends(require_permission("edit_cases")),
    db: Session = Depends(get_db),
):
    """
    Confirm and execute CSV import.
    
    For large files, consider scheduling as async job (future enhancement).
    Currently executes synchronously.
    
    Requires: Manager+ role
    """
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    # Create import job
    import_job = import_service.create_import_job(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        filename=file.filename,
        total_rows=0,  # Will be updated during execution
    )
    
    # Execute import (synchronous for now, async via job queue for large files later)
    import_job.status = "processing"
    db.commit()
    
    # Audit log
    from app.services import audit_service
    audit_service.log_import_started(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        import_id=import_job.id,
        filename=file.filename,
        row_count=0,
        request=request,
    )
    db.commit()
    
    result = import_service.execute_import(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        import_id=import_job.id,
        file_content=content,
    )
    
    # Audit log completion
    audit_service.log_import_completed(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        import_id=import_job.id,
        imported=result.imported,
        skipped=result.skipped,
        errors=len(result.errors),
    )
    db.commit()
    
    # Refresh to get updated counts
    db.refresh(import_job)
    
    return ImportStatusResponse(
        id=import_job.id,
        filename=import_job.filename,
        status=import_job.status,
        total_rows=import_job.total_rows,
        imported_count=import_job.imported_count,
        skipped_count=import_job.skipped_count,
        error_count=import_job.error_count,
        errors=import_job.errors,
        created_at=import_job.created_at.isoformat(),
        completed_at=import_job.completed_at.isoformat() if import_job.completed_at else None,
    )


@router.get("/import/{import_id}", response_model=ImportStatusResponse)
def get_import_status(
    import_id: UUID,
    session: UserSession = Depends(require_permission("edit_cases")),
    db: Session = Depends(get_db),
):
    """Get status of an import job."""
    import_job = import_service.get_import(db, session.org_id, import_id)
    if not import_job:
        raise HTTPException(status_code=404, detail="Import not found")
    
    return ImportStatusResponse(
        id=import_job.id,
        filename=import_job.filename,
        status=import_job.status,
        total_rows=import_job.total_rows,
        imported_count=import_job.imported_count,
        skipped_count=import_job.skipped_count,
        error_count=import_job.error_count,
        errors=import_job.errors,
        created_at=import_job.created_at.isoformat(),
        completed_at=import_job.completed_at.isoformat() if import_job.completed_at else None,
    )


@router.get("/import", response_model=list[ImportStatusResponse])
def list_imports(
    session: UserSession = Depends(require_permission("edit_cases")),
    db: Session = Depends(get_db),
):
    """List recent imports for the organization."""
    imports = import_service.list_imports(db, session.org_id)
    
    return [
        ImportStatusResponse(
            id=i.id,
            filename=i.filename,
            status=i.status,
            total_rows=i.total_rows,
            imported_count=i.imported_count,
            skipped_count=i.skipped_count,
            error_count=i.error_count,
            errors=i.errors,
            created_at=i.created_at.isoformat(),
            completed_at=i.completed_at.isoformat() if i.completed_at else None,
        )
        for i in imports
    ]


# NOTE: /handoff-queue MUST come before /{case_id} routes to avoid routing conflict
@router.get("/handoff-queue", response_model=CaseListResponse)
def list_handoff_queue(
    session: UserSession = Depends(require_permission("view_post_approval_cases")),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """
    List cases awaiting case manager review (status=pending_handoff).
    
    Requires: case_manager+ role
    """
    cases, total = case_service.list_handoff_queue(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return CaseListResponse(
        items=[_case_to_list_item(c, db) for c in cases],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("", response_model=CaseRead, status_code=201, dependencies=[Depends(require_csrf_header)])
def create_case(
    data: CaseCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new case."""
    try:
        case = case_service.create_case(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
        )
    except Exception as e:
        # Handle unique constraint violations
        if "uq_case_email_active" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="A case with this email already exists")
        raise
    
    return _case_to_read(case, db)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get case by ID (respects permission-based access)."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: checks ownership + post-approval permission
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    
    return _case_to_read(case, db)


# =============================================================================
# Email Sending
# =============================================================================

class SendEmailRequest(BaseModel):
    """Request to send email to case contact."""
    template_id: UUID
    subject: str | None = None
    body: str | None = None
    provider: str = "auto"  # "gmail", "resend", or "auto" (gmail first, then resend)
    
class SendEmailResponse(BaseModel):
    """Response after sending email."""
    success: bool
    email_log_id: UUID | None = None
    message_id: str | None = None
    provider_used: str | None = None
    error: str | None = None


@router.post("/{case_id}/send-email", response_model=SendEmailResponse, dependencies=[Depends(require_csrf_header)])
async def send_case_email(
    case_id: UUID,
    data: SendEmailRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Send email to case contact using template.
    
    Provider options:
    - "auto": Try Gmail first (if connected), fall back to Resend
    - "gmail": Use user's connected Gmail (fails if not connected)
    - "resend": Use Resend API (fails if not configured)
    
    The email is logged and linked to the case activity.
    """
    from app.services import email_service, gmail_service, oauth_service, activity_service
    from datetime import datetime
    import os
    
    # Get case
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    
    if not case.email:
        raise HTTPException(status_code=400, detail="Case has no email address")
    
    # Get template
    template = email_service.get_template(db, data.template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")
    
    # Prepare variables for template rendering
    variables = email_service.build_case_template_variables(db, case)

    # Render template (allow UI overrides)
    subject_template = data.subject if data.subject is not None else template.subject
    body_template = data.body if data.body is not None else template.body
    subject, body = email_service.render_template(subject_template, body_template, variables)
    
    # Determine provider
    provider = data.provider
    gmail_connected = oauth_service.get_user_integration(db, session.user_id, "gmail") is not None
    resend_configured = bool(os.getenv("RESEND_API_KEY"))
    
    use_gmail = False
    use_resend = False
    
    if provider == "gmail":
        if not gmail_connected:
            return SendEmailResponse(
                success=False,
                error="Gmail not connected. Connect Gmail in Settings > Integrations."
            )
        use_gmail = True
    elif provider == "resend":
        if not resend_configured:
            return SendEmailResponse(
                success=False,
                error="Resend not configured. Contact administrator."
            )
        use_resend = True
    else:  # auto
        if gmail_connected:
            use_gmail = True
        elif resend_configured:
            use_resend = True
        else:
            return SendEmailResponse(
                success=False,
                error="No email provider available. Connect Gmail in Settings."
            )
    
    # Send email
    if use_gmail:
        # Create email log for direct Gmail send
        from app.db.models import EmailLog
        from app.db.enums import EmailStatus

        email_log = EmailLog(
            organization_id=session.org_id,
            template_id=data.template_id,
            case_id=case_id,
            recipient_email=case.email,
            subject=subject,
            body=body,
            status=EmailStatus.PENDING.value,
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)

        result = await gmail_service.send_email(
            db=db,
            user_id=str(session.user_id),
            to=case.email,
            subject=subject,
            body=body,
            html=True,  # Templates are typically HTML
        )
        
        if result.get("success"):
            email_log.status = EmailStatus.SENT.value
            email_log.sent_at = datetime.utcnow()
            email_log.external_id = result.get("message_id")
            db.commit()
            
            # Log activity
            activity_service.log_email_sent(
                db=db,
                case_id=case_id,
                organization_id=session.org_id,
                actor_user_id=session.user_id,
                email_log_id=email_log.id,
                subject=subject,
                provider="gmail",
            )
            
            return SendEmailResponse(
                success=True,
                email_log_id=email_log.id,
                message_id=result.get("message_id"),
                provider_used="gmail",
            )
        else:
            email_log.status = EmailStatus.FAILED.value
            email_log.error = result.get("error")
            db.commit()
            
            return SendEmailResponse(
                success=False,
                email_log_id=email_log.id,
                error=result.get("error"),
            )
    
    elif use_resend:
        # Queue via existing email service (uses job queue)
        try:
            result = email_service.send_email(
                db=db,
                org_id=session.org_id,
                template_id=data.template_id,
                recipient_email=case.email,
                subject=subject,
                body=body,
                case_id=case_id,
            )
            
            if result:
                log, job = result
                
                # Log activity
                activity_service.log_email_sent(
                    db=db,
                    case_id=case_id,
                    organization_id=session.org_id,
                    actor_user_id=session.user_id,
                    email_log_id=log.id,
                    subject=subject,
                    provider="resend",
                )
                
                return SendEmailResponse(
                    success=True,
                    email_log_id=log.id,
                    provider_used="resend",
                )
            else:
                return SendEmailResponse(success=False, error="Failed to queue email")
        except Exception as e:
            return SendEmailResponse(success=False, error=str(e))
    
    return SendEmailResponse(success=False, error="No provider selected")


@router.patch("/{case_id}", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def update_case(
    case_id: UUID,
    data: CaseUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Update case fields.
    
    Requires: creator or manager+ (blocked after handoff for intake)
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    
    # Permission check: must be able to modify
    if not can_modify_case(case, str(session.user_id), session.role):
        raise HTTPException(status_code=403, detail="Not authorized to update this case")
    
    try:
        case = case_service.update_case(
            db, case, data,
            user_id=session.user_id,
            org_id=session.org_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    return _case_to_read(case, db)


@router.patch("/{case_id}/status", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def change_status(
    case_id: UUID,
    data: CaseStatusChange,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Change case stage (records history, respects access control)."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control: intake can't access handed-off cases
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    
    if case.is_archived:
        raise HTTPException(status_code=400, detail="Cannot change status of archived case")
    
    try:
        case = case_service.change_status(
            db=db,
            case=case,
            new_stage_id=data.stage_id,
            user_id=session.user_id,
            user_role=session.role,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return _case_to_read(case, db)


@router.patch("/{case_id}/assign", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def assign_case(
    case_id: UUID,
    data: CaseAssign,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Assign case to a user or queue.
    
    Requires: manager+ role
    """
    if not can_assign(session):
        raise HTTPException(status_code=403, detail="Only managers can assign cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if data.owner_type == OwnerType.USER:
        from app.db.models import Membership
        membership = db.query(Membership).filter(
            Membership.user_id == data.owner_id,
            Membership.organization_id == session.org_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        from app.services import queue_service
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")
    
    case = case_service.assign_case(db, case, data.owner_type, data.owner_id, session.user_id)
    return _case_to_read(case, db)


@router.post("/bulk-assign", dependencies=[Depends(require_csrf_header)])
def bulk_assign_cases(
    data: BulkAssign,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Bulk assign multiple cases to a user or queue.
    
    Requires: case_manager, manager, or developer role
    """
    from app.db.enums import Role
    
    # Role check: case_manager+
    allowed_roles = {Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER}
    if session.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Only case managers and above can bulk assign cases")
    
    if data.owner_type == OwnerType.USER:
        from app.db.models import Membership
        membership = db.query(Membership).filter(
            Membership.user_id == data.owner_id,
            Membership.organization_id == session.org_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        from app.services import queue_service
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")
    
    # Process each case
    results = {"assigned": 0, "failed": []}
    for case_id in data.case_ids:
        case = case_service.get_case(db, session.org_id, case_id)
        if not case:
            results["failed"].append({"case_id": str(case_id), "reason": "Case not found"})
            continue
        
        try:
            case_service.assign_case(db, case, data.owner_type, data.owner_id, session.user_id)
            results["assigned"] += 1
        except Exception as e:
            results["failed"].append({"case_id": str(case_id), "reason": str(e)})
    
    return results


@router.post("/{case_id}/archive", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def archive_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Soft-delete (archive) a case.
    
    Requires: manager+ role
    """
    if not can_archive(session):
        raise HTTPException(status_code=403, detail="Only managers can archive cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = case_service.archive_case(db, case, session.user_id)
    return _case_to_read(case, db)


@router.post("/{case_id}/restore", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def restore_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Restore an archived case.
    
    Requires: manager+ role
    Fails if email is now used by another active case.
    """
    if not can_archive(session):
        raise HTTPException(status_code=403, detail="Only managers can restore cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.restore_case(db, case, session.user_id)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)


@router.delete("/{case_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_case(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a case.
    
    Requires: manager+ role AND case must be archived first.
    """
    if not can_hard_delete(session):
        raise HTTPException(status_code=403, detail="Only managers can delete cases")
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if not case.is_archived:
        raise HTTPException(
            status_code=400, 
            detail="Case must be archived before permanent deletion"
        )
    
    case_service.hard_delete_case(db, case)
    return None


@router.get("/{case_id}/history", response_model=list[CaseStatusHistoryRead])
def get_case_history(
    case_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get status change history for a case."""
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    history = case_service.get_status_history(db, case_id, session.org_id)
    
    result = []
    for h in history:
        changed_by_name = None
        if h.changed_by_user_id:
            user = db.query(User).filter(User.id == h.changed_by_user_id).first()
            changed_by_name = user.display_name if user else None
        
        result.append(CaseStatusHistoryRead(
            id=h.id,
            from_stage_id=h.from_stage_id,
            to_stage_id=h.to_stage_id,
            from_label_snapshot=h.from_label_snapshot,
            to_label_snapshot=h.to_label_snapshot,
            changed_by_user_id=h.changed_by_user_id,
            changed_by_name=changed_by_name,
            reason=h.reason,
            changed_at=h.changed_at,
        ))
    
    return result


@router.get("/{case_id}/activity", response_model=CaseActivityResponse)
def get_case_activity(
    case_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive activity log for a case (paginated).
    
    Includes: creates, edits, status changes, assignments, notes, etc.
    """
    from sqlalchemy import func
    from app.db.models import CaseActivityLog
    
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Access control
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    
    # Query activity log with pagination
    base_query = db.query(CaseActivityLog).filter(
        CaseActivityLog.case_id == case_id,
        CaseActivityLog.organization_id == session.org_id,
    )
    
    total = base_query.count()
    pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    activities = base_query.order_by(
        CaseActivityLog.created_at.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    
    # Resolve actor names
    items = []
    for activity in activities:
        actor_name = None
        if activity.actor_user_id:
            actor = db.query(User).filter(User.id == activity.actor_user_id).first()
            actor_name = actor.display_name if actor else None
        
        items.append(CaseActivityRead(
            id=activity.id,
            activity_type=activity.activity_type,
            actor_user_id=activity.actor_user_id,
            actor_name=actor_name,
            details=activity.details,
            created_at=activity.created_at,
        ))
    
    return CaseActivityResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


# =============================================================================
# Handoff Accept/Deny Endpoints (Case Manager+ only)
# =============================================================================


@router.post("/{case_id}/accept", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def accept_handoff(
    case_id: UUID,
    session: UserSession = Depends(require_permission("assign_cases")),
    db: Session = Depends(get_db),
):
    """
    Accept a pending_handoff case and transition to pending_match.
    
    Requires: case_manager+ role
    Returns 409 if case is not in pending_handoff status.
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.accept_handoff(db, case, session.user_id)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)


@router.post("/{case_id}/deny", response_model=CaseRead, dependencies=[Depends(require_csrf_header)])
def deny_handoff(
    case_id: UUID,
    data: CaseHandoffDeny,
    session: UserSession = Depends(require_permission("assign_cases")),
    db: Session = Depends(get_db),
):
    """
    Deny a pending_handoff case and revert to under_review.
    
    Requires: case_manager+ role
    Reason is optional but stored in status history.
    Returns 409 if case is not in pending_handoff status.
    """
    case = case_service.get_case(db, session.org_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case, error = case_service.deny_handoff(db, case, session.user_id, data.reason)
    if error:
        raise HTTPException(status_code=409, detail=error)
    
    return _case_to_read(case, db)
