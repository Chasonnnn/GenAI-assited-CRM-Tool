"""Public form endpoints for applicants."""

import json
import os
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.db.enums import FormStatus
from app.schemas.forms import (
    FormDraftPublicRead,
    FormDraftUpsertRequest,
    FormDraftWriteResponse,
    FormIntakeDraftPublicRead,
    FormIntakeDraftWriteResponse,
    FormIntakePublicRead,
    FormPublicRead,
    FormSchema,
    FormSubmissionSharedResponse,
    FormSubmissionPublicResponse,
)
from app.services import (
    form_draft_service,
    form_intake_service,
    form_service,
    form_submission_service,
    media_service,
    org_service,
)

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


@router.get("/{org_id}/signature-logo")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_org_signature_logo(request: Request, org_id: UUID, db: Session = Depends(get_db)):
    org = org_service.get_org_by_id(db, org_id)
    if not org or not org.signature_logo_url:
        raise HTTPException(status_code=404, detail="Logo not found")

    signed_url = media_service.get_signed_media_url(org.signature_logo_url)
    if not signed_url:
        raise HTTPException(status_code=404, detail="Logo not found")

    return RedirectResponse(signed_url, status_code=307)


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
        allowed_mime_types=form.allowed_mime_types
        or form_submission_service.DEFAULT_ALLOWED_FORM_UPLOAD_MIME_TYPES,
    )


def _has_submission(db: Session, token_row) -> bool:
    return (
        form_submission_service.get_submission_by_surrogate(
            db,
            token_row.organization_id,
            token_row.form_id,
            token_row.surrogate_id,
        )
        is not None
    )


@router.get("/{token}/draft", response_model=FormDraftPublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def get_public_form_draft(request: Request, token: str, db: Session = Depends(get_db)):
    token_row = form_submission_service.get_token_row(db, token)
    if not token_row:
        raise HTTPException(status_code=404, detail="Form not found")

    # If already submitted, hide drafts (treat as not found).
    if _has_submission(db, token_row):
        raise HTTPException(status_code=404, detail="Draft not found")

    token_record = form_submission_service.get_valid_token(db, token)
    if not token_record:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, token_record.organization_id, token_record.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    draft = form_draft_service.get_draft_by_surrogate_form(
        db=db,
        org_id=token_record.organization_id,
        form_id=token_record.form_id,
        surrogate_id=token_record.surrogate_id,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return FormDraftPublicRead(
        answers=draft.answers_json or {},
        started_at=draft.started_at,
        updated_at=draft.updated_at,
    )


@router.put("/{token}/draft", response_model=FormDraftWriteResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def upsert_public_form_draft(
    token: str,
    body: FormDraftUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    token_row = form_submission_service.get_token_row(db, token)
    if not token_row:
        raise HTTPException(status_code=404, detail="Form not found")
    if _has_submission(db, token_row):
        raise HTTPException(status_code=409, detail="Submission already exists for this surrogate")

    token_record = form_submission_service.get_valid_token(db, token)
    if not token_record:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, token_record.organization_id, token_record.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        draft = form_draft_service.upsert_public_draft(
            db=db,
            token_record=token_record,
            form=form,
            answers=body.answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FormDraftWriteResponse(started_at=draft.started_at, updated_at=draft.updated_at)


@router.delete("/{token}/draft")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def delete_public_form_draft(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    token_row = form_submission_service.get_token_row(db, token)
    if not token_row:
        raise HTTPException(status_code=404, detail="Form not found")
    if _has_submission(db, token_row):
        raise HTTPException(status_code=409, detail="Submission already exists for this surrogate")

    token_record = form_submission_service.get_valid_token(db, token)
    if not token_record:
        raise HTTPException(status_code=404, detail="Form not found")

    form_draft_service.delete_draft(
        db=db,
        org_id=token_record.organization_id,
        form_id=token_record.form_id,
        surrogate_id=token_record.surrogate_id,
    )
    return Response(status_code=204)


@router.post("/{token}/submit", response_model=FormSubmissionPublicResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_FORMS}/minute")
async def submit_public_form(
    token: str,
    request: Request,
    answers: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    file_field_keys: str | None = Form(default=None),
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
        parsed_keys: list[str] | None = None
        if file_field_keys:
            try:
                parsed = json.loads(file_field_keys)
                if not isinstance(parsed, list) or not all(isinstance(k, str) for k in parsed):
                    raise ValueError("Invalid file_field_keys payload")
                parsed_keys = parsed
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid file_field_keys payload") from exc

        submission = form_submission_service.create_submission(
            db=db,
            token=token_record,
            form=form,
            answers=answers_data,
            files=files or [],
            file_field_keys=parsed_keys,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FormSubmissionPublicResponse(
        id=submission.id,
        status=submission.status,
    )


@router.get("/intake/{slug}", response_model=FormIntakePublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_shared_public_form(request: Request, slug: str, db: Session = Depends(get_db)):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = form_intake_service.get_active_intake_link_by_slug(db, slug)
    if not intake_link:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, intake_link.organization_id, intake_link.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    schema = _schema_or_none(form.published_schema_json)
    if not schema:
        raise HTTPException(status_code=404, detail="Form not found")
    schema = form_service.normalize_form_schema_logo_url(schema, intake_link.organization_id)

    return FormIntakePublicRead(
        form_id=form.id,
        intake_link_id=intake_link.id,
        name=form.name,
        description=form.description,
        form_schema=schema,
        max_file_size_bytes=form.max_file_size_bytes,
        max_file_count=form.max_file_count,
        allowed_mime_types=form.allowed_mime_types
        or form_submission_service.DEFAULT_ALLOWED_FORM_UPLOAD_MIME_TYPES,
        campaign_name=intake_link.campaign_name,
        event_name=intake_link.event_name,
    )


@router.get("/intake/{slug}/draft/{draft_session_id}", response_model=FormIntakeDraftPublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def get_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Draft not found")

    intake_link = form_intake_service.get_active_intake_link_by_slug(db, slug)
    if not intake_link:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft = form_intake_service.get_shared_draft(
        db=db,
        link=intake_link,
        draft_session_id=draft_session_id,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return FormIntakeDraftPublicRead(
        answers=draft.answers_json or {},
        started_at=draft.started_at,
        updated_at=draft.updated_at,
    )


@router.put("/intake/{slug}/draft/{draft_session_id}", response_model=FormIntakeDraftWriteResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def upsert_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    body: FormDraftUpsertRequest,
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = form_intake_service.get_active_intake_link_by_slug(db, slug)
    if not intake_link:
        raise HTTPException(status_code=404, detail="Form not found")
    form = form_service.get_form(db, intake_link.organization_id, intake_link.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        draft = form_intake_service.upsert_shared_draft(
            db=db,
            link=intake_link,
            form=form,
            draft_session_id=draft_session_id,
            answers=body.answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FormIntakeDraftWriteResponse(started_at=draft.started_at, updated_at=draft.updated_at)


@router.delete("/intake/{slug}/draft/{draft_session_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def delete_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Draft not found")

    intake_link = form_intake_service.get_active_intake_link_by_slug(db, slug)
    if not intake_link:
        raise HTTPException(status_code=404, detail="Draft not found")
    deleted = form_intake_service.delete_shared_draft(
        db=db,
        link=intake_link,
        draft_session_id=draft_session_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Draft not found")
    return Response(status_code=204)


@router.post("/intake/{slug}/submit", response_model=FormSubmissionSharedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_FORMS}/minute")
async def submit_shared_public_form(
    slug: str,
    request: Request,
    answers: str = Form(...),
    files: list[UploadFile] | None = File(default=None),
    file_field_keys: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = form_intake_service.get_active_intake_link_by_slug(db, slug)
    if not intake_link:
        raise HTTPException(status_code=404, detail="Form not found")

    form = form_service.get_form(db, intake_link.organization_id, intake_link.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        answers_data = json.loads(answers)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid answers JSON") from exc

    parsed_keys: list[str] | None = None
    if file_field_keys:
        try:
            parsed = json.loads(file_field_keys)
            if not isinstance(parsed, list) or not all(isinstance(k, str) for k in parsed):
                raise ValueError("Invalid file_field_keys payload")
            parsed_keys = parsed
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid file_field_keys payload") from exc

    utm_fields = {
        key: request.query_params.get(key)
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
        if request.query_params.get(key)
    }
    source_metadata = {
        "campaign_name": intake_link.campaign_name,
        "event_name": intake_link.event_name,
        "utm": {**(intake_link.utm_defaults or {}), **utm_fields},
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    challenge_token = request.headers.get("x-intake-challenge")

    try:
        submission, outcome = form_intake_service.create_shared_submission(
            db=db,
            link=intake_link,
            form=form,
            answers=answers_data,
            files=files or [],
            file_field_keys=parsed_keys,
            source_metadata=source_metadata,
            challenge_token=challenge_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FormSubmissionSharedResponse(
        id=submission.id,
        status=submission.status,
        outcome=outcome,
        surrogate_id=submission.surrogate_id,
        intake_lead_id=submission.intake_lead_id,
    )
