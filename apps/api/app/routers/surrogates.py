"""Surrogates router - API endpoints for surrogate management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.surrogate_access import check_surrogate_access, can_modify_surrogate
from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import AuditEventType, SurrogateSource, OwnerType
from app.db.models import User
from app.schemas.auth import UserSession
from app.schemas.surrogate import (
    SurrogateAssign,
    SurrogateCreate,
    SurrogateListItem,
    SurrogateListResponse,
    SurrogateRead,
    SurrogateStats,
    SurrogateStatusChange,
    SurrogateStatusHistoryRead,
    SurrogateUpdate,
    BulkAssign,
    SurrogateActivityRead,
    SurrogateActivityResponse,
    ContactAttemptCreate,
    ContactAttemptResponse,
    ContactAttemptsSummary,
)
from app.services import (
    surrogate_service,
    dashboard_service,
    import_service,
    membership_service,
    queue_service,
    user_service,
    contact_attempt_service,
)
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter(dependencies=[Depends(require_permission(POLICIES["surrogates"].default))])


def _surrogate_to_read(surrogate, db: Session) -> SurrogateRead:
    """Convert Surrogate model to SurrogateRead schema with joined user names."""
    owner_name = None
    if surrogate.owner_type == OwnerType.USER.value:
        user = user_service.get_user_by_id(db, surrogate.owner_id)
        owner_name = user.display_name if user else None
    elif surrogate.owner_type == OwnerType.QUEUE.value:
        queue = queue_service.get_queue(db, surrogate.organization_id, surrogate.owner_id)
        owner_name = queue.name if queue else None

    return SurrogateRead(
        id=surrogate.id,
        surrogate_number=surrogate.surrogate_number,
        stage_id=surrogate.stage_id,
        status_label=surrogate.status_label,
        source=SurrogateSource(surrogate.source),
        is_priority=surrogate.is_priority,
        owner_type=surrogate.owner_type,
        owner_id=surrogate.owner_id,
        owner_name=owner_name,
        created_by_user_id=surrogate.created_by_user_id,
        full_name=surrogate.full_name,
        email=surrogate.email,
        phone=surrogate.phone,
        state=surrogate.state,
        date_of_birth=surrogate.date_of_birth,
        race=surrogate.race,
        height_ft=surrogate.height_ft,
        weight_lb=surrogate.weight_lb,
        is_age_eligible=surrogate.is_age_eligible,
        is_citizen_or_pr=surrogate.is_citizen_or_pr,
        has_child=surrogate.has_child,
        is_non_smoker=surrogate.is_non_smoker,
        has_surrogate_experience=surrogate.has_surrogate_experience,
        num_deliveries=surrogate.num_deliveries,
        num_csections=surrogate.num_csections,
        is_archived=surrogate.is_archived,
        archived_at=surrogate.archived_at,
        created_at=surrogate.created_at,
        updated_at=surrogate.updated_at,
    )


def _surrogate_to_list_item(surrogate, db: Session) -> SurrogateListItem:
    """Convert Surrogate model to SurrogateListItem schema."""
    from datetime import date

    # Use preloaded relationships instead of separate queries (fixes N+1)
    owner_name = None
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_user:
        owner_name = surrogate.owner_user.display_name
    elif surrogate.owner_type == OwnerType.QUEUE.value and surrogate.owner_queue:
        owner_name = surrogate.owner_queue.name

    # Calculate age from date_of_birth
    age = None
    if surrogate.date_of_birth:
        today = date.today()
        dob = surrogate.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # Calculate BMI from height_ft and weight_lb
    # BMI = (weight in lbs / (height in inches)^2) * 703
    bmi = None
    if surrogate.height_ft and surrogate.weight_lb:
        height_inches = surrogate.height_ft * 12  # Convert feet to inches
        if height_inches > 0:
            bmi = round((surrogate.weight_lb / (height_inches**2)) * 703, 1)

    return SurrogateListItem(
        id=surrogate.id,
        surrogate_number=surrogate.surrogate_number,
        stage_id=surrogate.stage_id,
        stage_slug=surrogate.stage.slug if surrogate.stage else None,
        stage_type=surrogate.stage.stage_type if surrogate.stage else None,
        status_label=surrogate.status_label,
        source=SurrogateSource(surrogate.source),
        full_name=surrogate.full_name,
        email=surrogate.email,
        phone=surrogate.phone,
        state=surrogate.state,
        owner_type=surrogate.owner_type,
        owner_id=surrogate.owner_id,
        owner_name=owner_name,
        is_priority=surrogate.is_priority,
        is_archived=surrogate.is_archived,
        age=age,
        bmi=bmi,
        created_at=surrogate.created_at,
    )


@router.get("/stats", response_model=SurrogateStats)
def get_surrogate_stats(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get aggregated surrogate statistics for dashboard with period comparisons."""
    stats = surrogate_service.get_surrogate_stats(db, session.org_id)

    return SurrogateStats(
        total=stats["total"],
        by_status=stats["by_status"],
        this_week=stats["this_week"],
        last_week=stats["last_week"],
        week_change_pct=stats["week_change_pct"],
        this_month=stats["this_month"],
        last_month=stats["last_month"],
        month_change_pct=stats["month_change_pct"],
        pending_tasks=stats["pending_tasks"],
    )


@router.get("/assignees")
def get_assignees(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get list of org members who can be assigned surrogates.

    Returns users with their ID, name, and role.
    """
    return surrogate_service.list_assignees(db, session.org_id)


@router.get("", response_model=SurrogateListResponse)
def list_surrogates(
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    stage_id: UUID | None = None,
    source: SurrogateSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = Query(None, max_length=100),
    include_archived: bool = False,
    queue_id: UUID | None = None,
    owner_type: str | None = Query(None, pattern="^(user|queue)$"),
    created_from: str | None = Query(None, description="Filter by creation date from (ISO format)"),
    created_to: str | None = Query(None, description="Filter by creation date to (ISO format)"),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
):
    """
    List surrogates with filters and pagination.

    - Default excludes archived surrogates
    - Search (q) searches name, surrogate_number, and exact email/phone matches
    - Intake specialists only see their owned surrogates
    - queue_id: Filter by surrogates in a specific queue
    - owner_type: Filter by owner type ('user' or 'queue')
    - owner_id: Filter by owner ID (when owner_type='user')
    - created_from/created_to: ISO date strings for date range filtering
    - Post-approval surrogates hidden if user lacks view_post_approval_surrogates permission
    """
    from app.services import permission_service

    # Permission-based stage filtering (Developer bypasses via permission_service)
    exclude_stage_types = []
    if not permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        "view_post_approval_surrogates",
    ):
        exclude_stage_types.append("post_approval")

    surrogates, total = surrogate_service.list_surrogates(
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
        sort_by=sort_by,
        sort_order=sort_order,
    )

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    from app.services import audit_service

    q_type = None
    if q:
        if "@" in q:
            q_type = "email"
        else:
            digit_count = sum(1 for ch in q if ch.isdigit())
            q_type = "phone" if digit_count >= 7 else "text"

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate_list",
        target_id=None,
        request=request,
        details={
            "count": len(surrogates),
            "page": page,
            "per_page": per_page,
            "include_archived": include_archived,
            "stage_id": str(stage_id) if stage_id else None,
            "owner_id": str(owner_id) if owner_id else None,
            "owner_type": owner_type,
            "queue_id": str(queue_id) if queue_id else None,
            "source": source.value if source else None,
            "q_type": q_type,
            "created_from": created_from,
            "created_to": created_to,
        },
    )
    db.commit()

    return SurrogateListResponse(
        items=[_surrogate_to_list_item(s, db) for s in surrogates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


# =============================================================================
# CSV Import Endpoints
# =============================================================================


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


@router.post(
    "/import/preview",
    response_model=ImportPreviewResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def preview_import(
    request: Request,
    file: UploadFile = File(...),
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["import"])),
    db: Session = Depends(get_db),
):
    """
    Preview CSV import without executing.

    Returns:
    - Column mapping results
    - Sample rows (first 5)
    - Duplicate detection counts (DB + within CSV)
    - Validation error count

    Requires: import_surrogates permission
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    preview = import_service.preview_import(db, session.org_id, content)

    # Create import job for later confirmation
    import_service.create_import_job(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        filename=file.filename,
        total_rows=preview.total_rows,
    )

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogates_import_preview",
        target_id=None,
        request=request,
        details={
            "filename": file.filename,
            "total_rows": preview.total_rows,
            "duplicate_emails_db": preview.duplicate_emails_db,
            "duplicate_emails_csv": preview.duplicate_emails_csv,
            "validation_errors": preview.validation_errors,
        },
    )
    db.commit()

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
    "/import/confirm",
    response_model=ImportStatusResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def confirm_import(
    request: Request,
    file: UploadFile = File(...),
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["import"])),
    db: Session = Depends(get_db),
):
    """
    Confirm and execute CSV import.

    For large files, consider scheduling as async job (future enhancement).
    Currently executes synchronously.

    Requires: import_surrogates permission
    """
    if not file.filename or not file.filename.endswith(".csv"):
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
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["import"])),
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
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["import"])),
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


# NOTE: /claim-queue MUST come before /{surrogate_id} routes to avoid routing conflict
@router.get("/claim-queue", response_model=SurrogateListResponse)
def list_claim_queue(
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["view_post_approval"])
    ),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """
    List approved surrogates in Surrogate Pool (ready for claim).

    Requires: view_post_approval_surrogates permission
    """
    surrogates, total = surrogate_service.list_claim_queue(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
    )

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return SurrogateListResponse(
        items=[_surrogate_to_list_item(s, db) for s in surrogates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post(
    "",
    response_model=SurrogateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_surrogate(
    data: SurrogateCreate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
):
    """Create a new surrogate."""
    try:
        surrogate = surrogate_service.create_surrogate(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
        )
    except Exception as e:
        # Handle unique constraint violations
        if "uq_surrogate_email_hash_active" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409, detail="A surrogate with this email already exists"
            )
        raise

    dashboard_service.push_dashboard_stats(db, session.org_id)
    return _surrogate_to_read(surrogate, db)


@router.get("/{surrogate_id}", response_model=SurrogateRead)
def get_surrogate(
    surrogate_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get surrogate by ID (respects permission-based access)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control: checks ownership + post-approval permission
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_VIEW_SURROGATE,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
    )
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
        details={"view": "surrogate_detail"},
    )
    db.commit()

    return _surrogate_to_read(surrogate, db)


# =============================================================================
# Email Sending
# =============================================================================


class SendEmailRequest(BaseModel):
    """Request to send email to surrogate contact."""

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


@router.post(
    "/{surrogate_id}/send-email",
    response_model=SendEmailResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def send_surrogate_email(
    surrogate_id: UUID,
    data: SendEmailRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Send email to surrogate contact using template.

    Provider options:
    - "auto": Try Gmail first (if connected), fall back to Resend
    - "gmail": Use user's connected Gmail (fails if not connected)
    - "resend": Use Resend API (fails if not configured)

    The email is logged and linked to the surrogate activity.
    """
    from app.services import (
        email_service,
        gmail_service,
        oauth_service,
        activity_service,
    )
    from datetime import datetime, timezone
    import os

    # Get surrogate
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if not surrogate.email:
        raise HTTPException(status_code=400, detail="Surrogate has no email address")

    # Get template
    template = email_service.get_template(db, data.template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")

    # Prepare variables for template rendering
    variables = email_service.build_surrogate_template_variables(db, surrogate)

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
                error="Gmail not connected. Connect Gmail in Settings > Integrations.",
            )
        use_gmail = True
    elif provider == "resend":
        if not resend_configured:
            return SendEmailResponse(
                success=False, error="Resend not configured. Contact administrator."
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
                error="No email provider available. Connect Gmail in Settings.",
            )

    # Send email
    if use_gmail:
        # Create email log for direct Gmail send
        from app.db.models import EmailLog
        from app.db.enums import EmailStatus

        email_log = EmailLog(
            organization_id=session.org_id,
            template_id=data.template_id,
            surrogate_id=surrogate_id,
            recipient_email=surrogate.email,
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
            to=surrogate.email,
            subject=subject,
            body=body,
            html=True,  # Templates are typically HTML
        )

        if result.get("success"):
            email_log.status = EmailStatus.SENT.value
            email_log.sent_at = datetime.now(timezone.utc)
            email_log.external_id = result.get("message_id")
            db.commit()

            # Log activity
            activity_service.log_email_sent(
                db=db,
                surrogate_id=surrogate_id,
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
                recipient_email=surrogate.email,
                subject=subject,
                body=body,
                surrogate_id=surrogate_id,
            )

            if result:
                log, job = result

                # Log activity
                activity_service.log_email_sent(
                    db=db,
                    surrogate_id=surrogate_id,
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


@router.patch(
    "/{surrogate_id}", response_model=SurrogateRead, dependencies=[Depends(require_csrf_header)]
)
def update_surrogate(
    surrogate_id: UUID,
    data: SurrogateUpdate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
):
    """
    Update surrogate fields.

    Requires: creator or admin+ (blocked after claim for intake)
    """
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control: intake can't access handed-off surrogates
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    # Permission check: must be able to modify
    if not can_modify_surrogate(surrogate, str(session.user_id), session.role):
        raise HTTPException(status_code=403, detail="Not authorized to update this surrogate")

    try:
        surrogate = surrogate_service.update_surrogate(
            db,
            surrogate,
            data,
            user_id=session.user_id,
            org_id=session.org_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _surrogate_to_read(surrogate, db)


@router.patch(
    "/{surrogate_id}/status",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def change_status(
    surrogate_id: UUID,
    data: SurrogateStatusChange,
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Session = Depends(get_db),
):
    """Change surrogate stage (records history, respects access control)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control: intake can't access handed-off surrogates
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if surrogate.is_archived:
        raise HTTPException(status_code=400, detail="Cannot change status of archived surrogate")

    try:
        surrogate = surrogate_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=data.stage_id,
            user_id=session.user_id,
            user_role=session.role,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    dashboard_service.push_dashboard_stats(db, session.org_id)
    return _surrogate_to_read(surrogate, db)


@router.patch(
    "/{surrogate_id}/assign",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def assign_surrogate(
    surrogate_id: UUID,
    data: SurrogateAssign,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["assign"])),
    db: Session = Depends(get_db),
):
    """
    Assign surrogate to a user or queue.

    Requires: assign_surrogates permission
    """

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    if data.owner_type == OwnerType.USER:
        membership = membership_service.get_membership_for_org(db, session.org_id, data.owner_id)
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")

    surrogate = surrogate_service.assign_surrogate(
        db, surrogate, data.owner_type, data.owner_id, session.user_id
    )
    return _surrogate_to_read(surrogate, db)


@router.post("/bulk-assign", dependencies=[Depends(require_csrf_header)])
def bulk_assign_surrogates(
    data: BulkAssign,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["assign"])),
    db: Session = Depends(get_db),
):
    """
    Bulk assign multiple surrogates to a user or queue.

    Requires: assign_surrogates permission
    """

    if data.owner_type == OwnerType.USER:
        membership = membership_service.get_membership_for_org(db, session.org_id, data.owner_id)
        if not membership:
            raise HTTPException(status_code=400, detail="User not found in organization")
    elif data.owner_type == OwnerType.QUEUE:
        queue = queue_service.get_queue(db, session.org_id, data.owner_id)
        if not queue or not queue.is_active:
            raise HTTPException(status_code=400, detail="Queue not found or inactive")
    else:
        raise HTTPException(status_code=400, detail="Invalid owner_type")

    # Process each surrogate
    results = {"assigned": 0, "failed": []}
    for surrogate_id in data.surrogate_ids:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
        if not surrogate:
            results["failed"].append(
                {"surrogate_id": str(surrogate_id), "reason": "Surrogate not found"}
            )
            continue

        try:
            surrogate_service.assign_surrogate(
                db, surrogate, data.owner_type, data.owner_id, session.user_id
            )
            results["assigned"] += 1
        except Exception as e:
            results["failed"].append({"surrogate_id": str(surrogate_id), "reason": str(e)})

    return results


@router.post(
    "/{surrogate_id}/archive",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def archive_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["archive"])),
    db: Session = Depends(get_db),
):
    """
    Soft-delete (archive) a surrogate.

    Requires: archive_surrogates permission
    """

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    surrogate = surrogate_service.archive_surrogate(db, surrogate, session.user_id)
    dashboard_service.push_dashboard_stats(db, session.org_id)
    return _surrogate_to_read(surrogate, db)


@router.post(
    "/{surrogate_id}/restore",
    response_model=SurrogateRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["archive"])),
    db: Session = Depends(get_db),
):
    """
    Restore an archived surrogate.

    Requires: archive_surrogates permission
    Fails if email is now used by another active surrogate.
    """

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    surrogate, error = surrogate_service.restore_surrogate(db, surrogate, session.user_id)
    if error:
        raise HTTPException(status_code=409, detail=error)

    dashboard_service.push_dashboard_stats(db, session.org_id)
    return _surrogate_to_read(surrogate, db)


@router.delete("/{surrogate_id}", status_code=204, dependencies=[Depends(require_csrf_header)])
def delete_surrogate(
    surrogate_id: UUID,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["delete"])),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a surrogate.

    Requires: delete_surrogates permission AND surrogate must be archived first.
    """

    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    if not surrogate.is_archived:
        raise HTTPException(
            status_code=400, detail="Surrogate must be archived before permanent deletion"
        )

    deleted = surrogate_service.hard_delete_surrogate(db, surrogate)
    if deleted:
        dashboard_service.push_dashboard_stats(db, session.org_id)
    return None


@router.get("/{surrogate_id}/history", response_model=list[SurrogateStatusHistoryRead])
def get_surrogate_history(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get status change history for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    history = surrogate_service.get_status_history(db, surrogate_id, session.org_id)

    user_ids = {h.changed_by_user_id for h in history if h.changed_by_user_id}
    users_by_id: dict[UUID, str | None] = {}
    if user_ids:
        users_by_id = {
            user.id: user.display_name
            for user in db.query(User).filter(User.id.in_(user_ids)).all()
        }

    result = []
    for h in history:
        changed_by_name = users_by_id.get(h.changed_by_user_id)

        result.append(
            SurrogateStatusHistoryRead(
                id=h.id,
                from_stage_id=h.from_stage_id,
                to_stage_id=h.to_stage_id,
                from_label_snapshot=h.from_label_snapshot,
                to_label_snapshot=h.to_label_snapshot,
                changed_by_user_id=h.changed_by_user_id,
                changed_by_name=changed_by_name,
                reason=h.reason,
                changed_at=h.changed_at,
            )
        )

    return result


@router.get("/{surrogate_id}/activity", response_model=SurrogateActivityResponse)
def get_surrogate_activity(
    surrogate_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive activity log for a surrogate (paginated).

    Includes: creates, edits, status changes, assignments, notes, etc.
    """
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    # Access control
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    items_data, total = surrogate_service.list_surrogate_activity(
        db=db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        page=page,
        per_page=per_page,
    )
    pages = (total + per_page - 1) // per_page if total > 0 else 1

    items = [
        SurrogateActivityRead(
            id=item["id"],
            activity_type=item["activity_type"],
            actor_user_id=item["actor_user_id"],
            actor_name=item["actor_name"],
            details=item["details"],
            created_at=item["created_at"],
        )
        for item in items_data
    ]

    return SurrogateActivityResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )


#
# Contact Attempts Tracking
#


@router.post(
    "/{surrogate_id}/contact-attempts",
    response_model=ContactAttemptResponse,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_contact_attempt(
    surrogate_id: UUID,
    data: ContactAttemptCreate,
    session: UserSession = Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
    db: Session = Depends(get_db),
):
    """
    Log a contact attempt for a surrogate.

    Supports:
    - Multiple contact methods per attempt
    - Back-dating (cannot be future or before assignment)
    - Automatic contact_status update if outcome='reached'
    """
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        attempt = contact_attempt_service.create_contact_attempt(
            session=db,
            surrogate_id=surrogate_id,
            data=data,
            user=session,
        )
        db.commit()
        return attempt
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{surrogate_id}/contact-attempts",
    response_model=ContactAttemptsSummary,
)
def get_contact_attempts(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Get contact attempts summary for a surrogate.

    Returns:
    - All attempts
    - Attempt counts (total, current assignment, distinct days)
    - Success/failure counts
    - Days since last attempt
    """
    # Access control
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        summary = contact_attempt_service.get_surrogate_contact_attempts_summary(
            session=db,
            surrogate_id=surrogate_id,
            user=session,
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
