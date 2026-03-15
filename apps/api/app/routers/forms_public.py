"""Public form endpoints for applicants."""

from typing import Annotated

import json
import os
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.db.enums import FormStatus
from app.schemas.forms import (
    FormDraftPublicRead,
    FormDraftUpsertRequest,
    FormDraftWriteResponse,
    FormIntakeDraftLookupRequest,
    FormIntakeDraftLookupResponse,
    FormIntakeDraftPublicRead,
    FormIntakeDraftRestoreRequest,
    FormIntakeDraftRestoreResponse,
    FormIntakeDraftWriteResponse,
    FormIntakePublicRead,
    FormPublicRead,
    FormSchema,
    FormSubmissionSharedResponse,
    FormSubmissionPublicResponse,
)
from app.services import (
    form_intake_service,
    form_service,
    form_submission_service,
    media_service,
    org_service,
)

router = APIRouter(prefix="/forms/public", tags=["forms-public"])
DEDICATED_LINK_RETIRED_DETAIL = (
    "Dedicated application links have been retired. Please use a shared intake link."
)


def _schema_or_none(schema_json: dict | None) -> FormSchema | None:
    if not schema_json:
        return None
    try:
        return FormSchema.model_validate(schema_json)
    except Exception:
        return None


def _get_public_org_from_request(request: Request, db: Session):
    host = (request.headers.get("host") or "").split(":")[0].lower()
    org = org_service.get_org_by_host(db, host)
    if org:
        return org

    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin:
        return None

    try:
        origin_host = (urlparse(origin).hostname or "").lower()
    except Exception:
        return None

    if not origin_host:
        return None

    return org_service.get_org_by_host(db, origin_host)


def _get_active_intake_link_or_404(
    *,
    db: Session,
    request: Request,
    slug: str,
    detail: str,
) -> object:
    org = _get_public_org_from_request(request, db)
    intake_link = form_intake_service.get_active_intake_link_by_slug(
        db,
        slug,
        org_id=org.id if org else None,
    )
    if not intake_link:
        raise HTTPException(status_code=404, detail=detail)
    return intake_link


@router.get("/{org_id}/logos/{logo_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_form_logo(
    request: Request,
    org_id: UUID,
    logo_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
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
def get_org_signature_logo(
    request: Request, org_id: UUID, db: Annotated[Session, "fastapi_param"] = Depends(get_db)
) -> object:
    org = org_service.get_org_by_id(db, org_id)
    if not org or not org.signature_logo_url:
        raise HTTPException(status_code=404, detail="Logo not found")

    signed_url = media_service.get_signed_media_url(org.signature_logo_url)
    if not signed_url:
        raise HTTPException(status_code=404, detail="Logo not found")

    return RedirectResponse(signed_url, status_code=307)


@router.get("/{token}", response_model=FormPublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_public_form(
    request: Request, token: str, db: Annotated[Session, "fastapi_param"] = Depends(get_db)
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.get("/{token}/draft", response_model=FormDraftPublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def get_public_form_draft(
    request: Request, token: str, db: Annotated[Session, "fastapi_param"] = Depends(get_db)
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.put("/{token}/draft", response_model=FormDraftWriteResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def upsert_public_form_draft(
    token: str,
    body: FormDraftUpsertRequest,
    request: Request,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.delete("/{token}/draft")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def delete_public_form_draft(
    token: str,
    request: Request,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.post("/{token}/submit", response_model=FormSubmissionPublicResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_FORMS}/minute")
def submit_public_form(
    token: str,
    request: Request,
    answers: Annotated[str, "fastapi_param"] = Form(),
    files: Annotated[list[UploadFile] | None, "fastapi_param"] = File(default=None),
    file_field_keys: Annotated[str | None, "fastapi_param"] = Form(default=None),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.get("/intake/{slug}", response_model=FormIntakePublicRead)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_READ}/minute")
def get_shared_public_form(
    request: Request, slug: str, db: Annotated[Session, "fastapi_param"] = Depends(get_db)
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Form not found",
    )

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
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Draft not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Draft not found",
    )
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


@router.post("/intake/{slug}/draft/lookup", response_model=FormIntakeDraftLookupResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def lookup_shared_public_form_draft(
    request: Request,
    slug: str,
    body: FormIntakeDraftLookupRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Form not found",
    )
    form = form_service.get_form(db, intake_link.organization_id, intake_link.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    result = form_intake_service.lookup_shared_resume_draft(
        db=db,
        link=intake_link,
        form=form,
        answers=body.answers,
        current_draft_session_id=body.current_draft_session_id,
    )
    return FormIntakeDraftLookupResponse(
        status=result["status"],
        source_draft_id=result.get("source_draft_id"),
        updated_at=result.get("updated_at"),
        match_reason=result.get("match_reason"),
    )


@router.put("/intake/{slug}/draft/{draft_session_id}", response_model=FormIntakeDraftWriteResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def upsert_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    body: FormDraftUpsertRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Form not found",
    )
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


@router.post(
    "/intake/{slug}/draft/{draft_session_id}/restore",
    response_model=FormIntakeDraftRestoreResponse,
)
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def restore_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    body: FormIntakeDraftRestoreRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Form not found",
    )
    form = form_service.get_form(db, intake_link.organization_id, intake_link.form_id)
    if not form or form.status != FormStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        draft = form_intake_service.restore_shared_draft(
            db=db,
            link=intake_link,
            form=form,
            draft_session_id=draft_session_id,
            source_draft_id=body.source_draft_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return FormIntakeDraftRestoreResponse(
        answers=draft.answers_json or {},
        started_at=draft.started_at,
        updated_at=draft.updated_at,
    )


@router.delete("/intake/{slug}/draft/{draft_session_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PUBLIC_DRAFTS}/minute")
def delete_shared_public_form_draft(
    request: Request,
    slug: str,
    draft_session_id: str,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> object:
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Draft not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Draft not found",
    )
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
def submit_shared_public_form(
    slug: str,
    request: Request,
    answers: Annotated[str, "fastapi_param"] = Form(),
    files: Annotated[list[UploadFile] | None, "fastapi_param"] = File(default=None),
    file_field_keys: Annotated[str | None, "fastapi_param"] = Form(default=None),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Form not found")

    intake_link = _get_active_intake_link_or_404(
        db=db,
        request=request,
        slug=slug,
        detail="Form not found",
    )

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
        "client_ip": get_client_ip(request),
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
