"""Form builder and submission review endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.case_access import check_case_access
from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.models import Case, Form, FormSubmission, Organization
from app.schemas.auth import UserSession
from app.schemas.forms import (
    FormCreate,
    FormFieldMappingsUpdate,
    FormPublishResponse,
    FormRead,
    FormSubmissionRead,
    FormSubmissionStatusUpdate,
    FormSummary,
    FormTokenRead,
    FormTokenRequest,
    FormUpdate,
    FormFieldMappingItem,
    FormSchema,
    FormSubmissionFileRead,
    FormSubmissionFileDownloadResponse,
    FormLogoRead,
    FormSubmissionAnswersUpdate,
    FormSubmissionAnswersUpdateResponse,
)
from app.services import form_service, audit_service

router = APIRouter(prefix="/forms", tags=["forms"])


def _schema_or_none(schema_json: dict | None) -> FormSchema | None:
    if not schema_json:
        return None
    try:
        return FormSchema.model_validate(schema_json)
    except Exception:
        return None


def _form_summary(form: Form) -> FormSummary:
    return FormSummary(
        id=form.id,
        name=form.name,
        status=form.status,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _form_read(form: Form) -> FormRead:
    return FormRead(
        id=form.id,
        name=form.name,
        status=form.status,
        description=form.description,
        form_schema=_schema_or_none(form.schema_json),
        published_schema=_schema_or_none(form.published_schema_json),
        max_file_size_bytes=form.max_file_size_bytes,
        max_file_count=form.max_file_count,
        allowed_mime_types=form.allowed_mime_types,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _submission_read(submission: FormSubmission, files: list) -> FormSubmissionRead:
    return FormSubmissionRead(
        id=submission.id,
        form_id=submission.form_id,
        case_id=submission.case_id,
        status=submission.status,
        submitted_at=submission.submitted_at,
        reviewed_at=submission.reviewed_at,
        reviewed_by_user_id=submission.reviewed_by_user_id,
        review_notes=submission.review_notes,
        answers=submission.answers_json,
        schema_snapshot=submission.schema_snapshot,
        files=[
            FormSubmissionFileRead(
                id=f.id,
                filename=f.filename,
                content_type=f.content_type,
                file_size=f.file_size,
                quarantined=f.quarantined,
                scan_status=f.scan_status,
            )
            for f in files
        ],
    )


# =============================================================================
# Form CRUD (Admin)
# =============================================================================


@router.get(
    "",
    response_model=list[FormSummary],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_forms(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    forms = form_service.list_forms(db, session.org_id)
    return [_form_summary(form) for form in forms]


@router.post(
    "",
    response_model=FormRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def create_form(
    body: FormCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.create_form(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=body.name,
        description=body.description,
        schema=body.form_schema.model_dump() if body.form_schema else None,
        max_file_size_bytes=body.max_file_size_bytes,
        max_file_count=body.max_file_count,
        allowed_mime_types=body.allowed_mime_types,
    )
    return _form_read(form)


@router.get(
    "/{form_id}",
    response_model=FormRead,
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def get_form(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    return _form_read(form)


@router.patch(
    "/{form_id}",
    response_model=FormRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def update_form(
    form_id: UUID,
    body: FormUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    form = form_service.update_form(
        db=db,
        form=form,
        user_id=session.user_id,
        name=body.name,
        description=body.description,
        schema=body.form_schema.model_dump() if body.form_schema else None,
        max_file_size_bytes=body.max_file_size_bytes,
        max_file_count=body.max_file_count,
        allowed_mime_types=body.allowed_mime_types,
    )
    return _form_read(form)


@router.post(
    "/logos",
    response_model=FormLogoRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def upload_form_logo(
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    try:
        logo = form_service.upload_form_logo(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            file=file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FormLogoRead(
        id=logo.id,
        logo_url=form_service.get_form_logo_public_url(logo),
        filename=logo.filename,
        content_type=logo.content_type,
        file_size=logo.file_size,
        created_at=logo.created_at,
    )


@router.post(
    "/{form_id}/publish",
    response_model=FormPublishResponse,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def publish_form(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    try:
        form = form_service.publish_form(db, form, session.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FormPublishResponse(
        id=form.id,
        status=form.status,
        published_at=form.updated_at,
    )


# =============================================================================
# Field Mapping (Admin)
# =============================================================================


@router.get(
    "/{form_id}/mappings",
    response_model=list[FormFieldMappingItem],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_mappings(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    mappings = form_service.list_field_mappings(db, form.id)
    return [
        FormFieldMappingItem(field_key=m.field_key, case_field=m.case_field)
        for m in mappings
    ]


@router.put(
    "/{form_id}/mappings",
    response_model=list[FormFieldMappingItem],
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def set_mappings(
    form_id: UUID,
    body: FormFieldMappingsUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    try:
        created = form_service.set_field_mappings(
            db=db,
            form=form,
            mappings=[m.model_dump() for m in body.mappings],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        FormFieldMappingItem(field_key=m.field_key, case_field=m.case_field)
        for m in created
    ]


# =============================================================================
# Token + Submission Review (Case-level)
# =============================================================================


@router.post(
    "/{form_id}/tokens",
    response_model=FormTokenRead,
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def create_submission_token(
    form_id: UUID,
    body: FormTokenRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    case = db.query(Case).filter(Case.id == body.case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        token = form_service.create_submission_token(
            db=db,
            org_id=session.org_id,
            form=form,
            case=case,
            user_id=session.user_id,
            expires_in_days=body.expires_in_days,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already exists" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return FormTokenRead(token=token.token, expires_at=token.expires_at)


@router.get(
    "/{form_id}/cases/{case_id}/submission",
    response_model=FormSubmissionRead,
    dependencies=[Depends(require_permission(POLICIES["cases"].default))],
)
def get_case_submission(
    form_id: UUID,
    case_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case or case.organization_id != session.org_id:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    submission = form_service.get_submission_by_case(
        db, session.org_id, form.id, case.id
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    files = form_service.list_submission_files(db, session.org_id, submission.id)
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="form_submission",
        target_id=submission.id,
        request=request,
        details={"form_id": str(form_id), "case_id": str(case_id)},
    )
    db.commit()
    return _submission_read(submission, files)


@router.get(
    "/{form_id}/submissions",
    response_model=list[FormSubmissionRead],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_submissions(
    form_id: UUID,
    request: Request,
    status_filter: str | None = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    submissions = form_service.list_form_submissions(
        db, session.org_id, form.id, status_filter
    )
    output = []
    for submission in submissions:
        files = form_service.list_submission_files(db, session.org_id, submission.id)
        output.append(_submission_read(submission, files))
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="form_submission_list",
        target_id=None,
        request=request,
        details={
            "form_id": str(form_id),
            "status": status_filter,
            "count": len(output),
        },
    )
    db.commit()
    return output


@router.post(
    "/submissions/{submission_id}/approve",
    response_model=FormSubmissionRead,
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def approve_submission(
    submission_id: UUID,
    body: FormSubmissionStatusUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        submission = form_service.approve_submission(
            db=db,
            submission=submission,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_service.list_submission_files(db, session.org_id, submission.id)
    return _submission_read(submission, files)


@router.post(
    "/submissions/{submission_id}/reject",
    response_model=FormSubmissionRead,
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def reject_submission(
    submission_id: UUID,
    body: FormSubmissionStatusUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        submission = form_service.reject_submission(
            db=db,
            submission=submission,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_service.list_submission_files(db, session.org_id, submission.id)
    return _submission_read(submission, files)


@router.patch(
    "/submissions/{submission_id}/answers",
    response_model=FormSubmissionAnswersUpdateResponse,
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def update_submission_answers(
    submission_id: UUID,
    body: FormSubmissionAnswersUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update submission answers and sync mapped case fields."""
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        _, case_updates = form_service.update_submission_answers(
            db=db,
            submission=submission,
            updates=[u.model_dump() for u in body.updates],
            user_id=session.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_service.list_submission_files(db, session.org_id, submission.id)
    return FormSubmissionAnswersUpdateResponse(
        submission=_submission_read(submission, files),
        case_updates=case_updates,
    )


@router.get(
    "/submissions/{submission_id}/files/{file_id}/download",
    response_model=FormSubmissionFileDownloadResponse,
    dependencies=[Depends(require_permission(POLICIES["cases"].default))],
)
def download_submission_file(
    submission_id: UUID,
    file_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    file_record = form_service.get_submission_file(
        db, session.org_id, submission_id, file_id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.quarantined:
        raise HTTPException(status_code=403, detail="File is pending virus scan")

    url = form_service.get_submission_file_download_url(
        db=db,
        org_id=session.org_id,
        submission=submission,
        file_record=file_record,
        user_id=session.user_id,
    )
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="form_submission_file",
        target_id=file_record.id,
        request=request,
        details={"submission_id": str(submission_id)},
    )
    db.commit()

    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

    if url.startswith("/"):
        url = f"{request.base_url}".rstrip("/") + url

    return FormSubmissionFileDownloadResponse(
        download_url=url,
        filename=file_record.filename,
    )


@router.post(
    "/submissions/{submission_id}/files",
    response_model=FormSubmissionFileRead,
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
async def upload_submission_file(
    submission_id: UUID,
    file: UploadFile = File(...),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Upload a file to an existing submission (edit mode)."""
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        file_record = form_service.add_submission_file(
            db=db,
            org_id=session.org_id,
            submission=submission,
            file=file,
            user_id=session.user_id,
        )
        db.commit()
        return FormSubmissionFileRead(
            id=file_record.id,
            filename=file_record.filename,
            content_type=file_record.content_type,
            file_size=file_record.file_size,
            quarantined=file_record.quarantined,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/submissions/{submission_id}/files/{file_id}",
    dependencies=[
        Depends(require_permission(POLICIES["cases"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def delete_submission_file(
    submission_id: UUID,
    file_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Soft-delete a file from a submission (edit mode)."""
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    file_record = form_service.get_submission_file(
        db, session.org_id, submission_id, file_id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    success = form_service.soft_delete_submission_file(
        db=db,
        org_id=session.org_id,
        submission=submission,
        file_record=file_record,
        user_id=session.user_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="File already deleted")

    db.commit()
    return {"deleted": True}


@router.get(
    "/submissions/{submission_id}/export",
    dependencies=[Depends(require_permission(POLICIES["cases"].default))],
)
def export_submission_pdf(
    submission_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export a submission as PDF."""
    submission = form_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    case = db.query(Case).filter(Case.id == submission.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    check_case_access(case, session.role, session.user_id, db=db, org_id=session.org_id)

    org = db.query(Organization).filter(Organization.id == session.org_id).first()
    org_name = org.name if org else ""
    case_name = case.full_name or f"Case #{case.case_number or case.id}"

    from app.services import pdf_export_service

    try:
        pdf_bytes = pdf_export_service.export_submission_pdf(
            db=db,
            submission_id=submission.id,
            org_id=session.org_id,
            case_name=case_name,
            org_name=org_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"application_{case.case_number or case.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
