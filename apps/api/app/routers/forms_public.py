"""Public form endpoints for applicants."""

import json
import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.db.enums import FormStatus
from app.schemas.forms import FormPublicRead, FormSubmissionPublicResponse, FormSchema
from app.services import form_service, form_submission_service

router = APIRouter(prefix="/forms/public", tags=["forms-public"])


def _schema_or_none(schema_json: dict | None) -> FormSchema | None:
    if not schema_json:
        return None
    try:
        return FormSchema.model_validate(schema_json)
    except Exception:
        return None


@router.get("/{org_id}/logos/{logo_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_form_logo(request: Request, org_id: UUID, logo_id: UUID, db: Session = Depends(get_db)):
    logo = form_service.get_form_logo_by_id(db, org_id, logo_id)
    if not logo:
        raise HTTPException(status_code=404, detail="Logo not found")

    signed_url = form_service.get_form_logo_download_url(logo)
    if signed_url:
        return RedirectResponse(signed_url, status_code=307)

    file_path = form_service.get_form_logo_local_path(logo)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Logo not found")

    return FileResponse(
        file_path,
        media_type=logo.content_type,
        filename=logo.filename,
    )


@router.get("/{token}", response_model=FormPublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_public_form(request: Request, token: str, db: Session = Depends(get_db)):
    token_record = form_submission_service.get_valid_token(db, token)
    if not token_record:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, token_record.organization_id, token_record.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    schema = _schema_or_none(form.published_schema_json)
    if not schema:
        raise HTTPException(status_code=404, detail="Form not found")

    schema = form_service.normalize_form_schema_logo_url(schema, token_record.organization_id)

    return FormPublicRead(
        form_id=form.id,
        name=form.name,
        description=form.description,
        form_schema=schema,
        max_file_size_bytes=form.max_file_size_bytes,
        max_file_count=form.max_file_count,
        allowed_mime_types=form.allowed_mime_types,
    )


@router.post("/{token}/submit", response_model=FormSubmissionPublicResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_FORMS}/minute")
async def submit_public_form(
    token: str,
    request: Request,
    answers: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
):
    token_record = form_submission_service.get_valid_token(db, token)
    if not token_record:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, token_record.organization_id, token_record.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        answers_data = json.loads(answers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid answers JSON") from exc

    try:
        submission = form_submission_service.create_submission(
            db=db,
            token=token_record,
            form=form,
            answers=answers_data,
            files=files or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FormSubmissionPublicResponse(
        id=submission.id,
        status=submission.status,
    )
