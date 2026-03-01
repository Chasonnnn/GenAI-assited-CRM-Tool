"""Form builder and submission review endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.surrogate_access import check_surrogate_access
from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.forms import (
    FormCreate,
    FormDeliverySettings,
    FormDeliverySettingsUpdate,
    FormDraftStatusRead,
    FormFieldMappingsUpdate,
    FormIntakeLinkCreate,
    FormIntakeLinkRead,
    FormIntakeLinkSendRequest,
    FormIntakeLinkSendResponse,
    FormIntakeLinkUpdate,
    FormSubmissionMatchRetryRequest,
    FormSubmissionMatchResolveRequest,
    FormSubmissionMatchResolveResponse,
    FormPublishResponse,
    FormRead,
    FormMappingOption,
    FormTokenSendRequest,
    FormTokenSendResponse,
    FormSubmissionRead,
    FormSubmissionStatusUpdate,
    FormSummary,
    FormTokenRead,
    FormTokenRequest,
    IntakeLeadPromoteRequest,
    IntakeLeadPromoteResponse,
    IntakeLeadRead,
    MatchCandidateRead,
    FormUpdate,
    FormFieldMappingItem,
    FormSchema,
    FormSubmissionFileRead,
    FormSubmissionFileDownloadResponse,
    FormLogoRead,
    FormSubmissionAnswersUpdate,
    FormSubmissionAnswersUpdateResponse,
)
from app.schemas.platform_templates import (
    FormTemplateLibraryItem,
    FormTemplateLibraryDetail,
)
from app.services import (
    audit_service,
    email_service,
    form_draft_service,
    form_intake_service,
    form_service,
    form_submission_service,
    org_service,
    surrogate_service,
)

router = APIRouter(prefix="/forms", tags=["forms"])
DEDICATED_LINK_RETIRED_DETAIL = (
    "Dedicated application links have been retired. Please use shared intake links."
)


def _schema_or_none(schema_json: dict | None) -> FormSchema | None:
    if not schema_json:
        return None
    try:
        return FormSchema.model_validate(schema_json)
    except Exception:
        return None


def _form_summary(form, *, default_form_id: UUID | None = None) -> FormSummary:
    return FormSummary(
        id=form.id,
        name=form.name,
        status=form.status,
        purpose=form.purpose,
        is_default_surrogate_application=bool(default_form_id and form.id == default_form_id),
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _form_read(form, *, default_form_id: UUID | None = None) -> FormRead:
    schema = _schema_or_none(form.schema_json)
    published_schema = _schema_or_none(form.published_schema_json)
    if schema:
        schema = form_service.normalize_form_schema_logo_url(schema, form.organization_id)
    if published_schema:
        published_schema = form_service.normalize_form_schema_logo_url(
            published_schema, form.organization_id
        )

    return FormRead(
        id=form.id,
        name=form.name,
        status=form.status,
        purpose=form.purpose,
        is_default_surrogate_application=bool(default_form_id and form.id == default_form_id),
        description=form.description,
        form_schema=schema,
        published_schema=published_schema,
        max_file_size_bytes=form.max_file_size_bytes,
        max_file_count=form.max_file_count,
        allowed_mime_types=form.allowed_mime_types,
        default_application_email_template_id=form.default_application_email_template_id,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _submission_read(submission, files: list) -> FormSubmissionRead:
    return FormSubmissionRead(
        id=submission.id,
        form_id=submission.form_id,
        surrogate_id=submission.surrogate_id,
        status=submission.status,
        submitted_at=submission.submitted_at,
        reviewed_at=submission.reviewed_at,
        reviewed_by_user_id=submission.reviewed_by_user_id,
        review_notes=submission.review_notes,
        answers=submission.answers_json,
        schema_snapshot=submission.schema_snapshot,
        source_mode=submission.source_mode,
        intake_link_id=submission.intake_link_id,
        intake_lead_id=submission.intake_lead_id,
        match_status=submission.match_status,
        match_reason=submission.match_reason,
        matched_at=submission.matched_at,
        files=[
            FormSubmissionFileRead(
                id=f.id,
                filename=f.filename,
                content_type=f.content_type,
                file_size=f.file_size,
                quarantined=f.quarantined,
                scan_status=f.scan_status,
                field_key=f.field_key,
            )
            for f in files
        ],
    )


def _intake_link_read(link, intake_url: str | None = None) -> FormIntakeLinkRead:
    return FormIntakeLinkRead(
        id=link.id,
        form_id=link.form_id,
        slug=link.slug,
        campaign_name=link.campaign_name,
        event_name=link.event_name,
        utm_defaults=link.utm_defaults,
        is_active=link.is_active,
        expires_at=link.expires_at,
        max_submissions=link.max_submissions,
        submissions_count=link.submissions_count,
        intake_url=intake_url,
        created_at=link.created_at,
        updated_at=link.updated_at,
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
    default_form_id = form_service.ensure_default_surrogate_application_form(
        db,
        session.org_id,
        commit=False,
    )
    return [_form_summary(form, default_form_id=default_form_id) for form in forms]


# =============================================================================
# Platform Form Template Library
# =============================================================================


class FormTemplateUseRequest(BaseModel):
    name: str
    description: str | None = None


@router.get(
    "/templates",
    response_model=list[FormTemplateLibraryItem],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_form_templates(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """List published platform form templates visible to this org."""
    from app.services import platform_template_service

    templates = platform_template_service.list_published_form_templates_for_org(db, session.org_id)
    return [
        FormTemplateLibraryItem(
            id=t.id,
            name=t.published_name or t.name,
            description=t.published_description,
            published_at=t.published_at,
            # Org library reflects the published snapshot; draft edits shouldn't appear as "updated" until re-published.
            updated_at=t.published_at or t.updated_at,
        )
        for t in templates
    ]


@router.get(
    "/templates/{template_id}",
    response_model=FormTemplateLibraryDetail,
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def get_form_template(
    template_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    from app.services import platform_template_service

    template = platform_template_service.get_published_form_template_for_org(
        db, template_id, session.org_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return FormTemplateLibraryDetail(
        id=template.id,
        name=template.published_name or template.name,
        description=template.published_description,
        schema_json=template.published_schema_json,
        settings_json=template.published_settings_json,
        published_at=template.published_at,
        # Org library reflects the published snapshot; draft edits shouldn't appear as "updated" until re-published.
        updated_at=template.published_at or template.updated_at,
    )


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def remove_form_template_from_library(
    template_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Hide a published platform form template from this org's library."""
    from app.services import platform_template_service

    template = platform_template_service.get_published_form_template_for_org(
        db, template_id, session.org_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    platform_template_service.hide_published_form_template_for_org(
        db,
        template_id=template.id,
        org_id=session.org_id,
        hidden_by_user_id=session.user_id,
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/templates/{template_id}/use",
    response_model=FormRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def use_form_template(
    template_id: UUID,
    body: FormTemplateUseRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a draft form from a platform template."""
    from app.services import platform_template_service

    template = platform_template_service.get_published_form_template_for_org(
        db, template_id, session.org_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    schema = template.published_schema_json
    settings = template.published_settings_json or {}
    if schema is None:
        raise HTTPException(status_code=400, detail="Template schema is missing")

    form = form_service.create_form(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=body.name,
        description=body.description or template.published_description,
        schema=schema,
        max_file_size_bytes=settings.get("max_file_size_bytes"),
        max_file_count=settings.get("max_file_count"),
        allowed_mime_types=settings.get("allowed_mime_types"),
    )

    mappings = settings.get("mappings")
    if isinstance(mappings, list) and mappings:
        try:
            form_service.set_field_mappings(db=db, form=form, mappings=mappings)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    default_form_id = form_service.ensure_default_surrogate_application_form(db, session.org_id)
    return _form_read(form, default_form_id=default_form_id)


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
        purpose=body.purpose,
        schema=body.form_schema.model_dump() if body.form_schema else None,
        max_file_size_bytes=body.max_file_size_bytes,
        max_file_count=body.max_file_count,
        allowed_mime_types=body.allowed_mime_types,
        default_application_email_template_id=body.default_application_email_template_id,
    )
    default_form_id = form_service.ensure_default_surrogate_application_form(db, session.org_id)
    return _form_read(form, default_form_id=default_form_id)


@router.get(
    "/mapping-options",
    response_model=list[FormMappingOption],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_mapping_options():
    return [
        FormMappingOption(
            value=option["value"],
            label=option["label"],
            is_critical=bool(option.get("is_critical", False)),
        )
        for option in form_submission_service.list_surrogate_mapping_options()
    ]


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
    default_form_id = form_service.ensure_default_surrogate_application_form(
        db,
        session.org_id,
        commit=False,
    )
    return _form_read(form, default_form_id=default_form_id)


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
    update_kwargs = {
        "db": db,
        "form": form,
        "user_id": session.user_id,
        "name": body.name,
        "description": body.description,
        "purpose": body.purpose,
        "schema": body.form_schema.model_dump() if body.form_schema else None,
        "max_file_size_bytes": body.max_file_size_bytes,
        "max_file_count": body.max_file_count,
        "allowed_mime_types": body.allowed_mime_types,
    }
    if "default_application_email_template_id" in body.model_fields_set:
        update_kwargs["default_application_email_template_id"] = (
            body.default_application_email_template_id
        )
    form = form_service.update_form(**update_kwargs)
    default_form_id = form_service.ensure_default_surrogate_application_form(db, session.org_id)
    return _form_read(form, default_form_id=default_form_id)


@router.delete(
    "/{form_id}",
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def delete_form(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    form_service.delete_form(db=db, form=form)
    return {"message": "Form deleted"}


@router.post(
    "/{form_id}/set-default-surrogate-application",
    response_model=FormRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def set_default_surrogate_application_form(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    try:
        form = form_service.set_default_surrogate_application_form(
            db=db,
            org_id=session.org_id,
            form_id=form_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return _form_read(form, default_form_id=form.id)


@router.patch(
    "/{form_id}/delivery-settings",
    response_model=FormDeliverySettings,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def update_form_delivery_settings(
    form_id: UUID,
    body: FormDeliverySettingsUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    if (
        body.default_application_email_template_id is not None
        and not email_service.get_template(
            db,
            body.default_application_email_template_id,
            session.org_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Email template not found")

    form = form_service.update_form(
        db=db,
        form=form,
        user_id=session.user_id,
        name=None,
        description=None,
        purpose=None,
        schema=None,
        max_file_size_bytes=None,
        max_file_count=None,
        allowed_mime_types=None,
        default_application_email_template_id=body.default_application_email_template_id,
    )
    return FormDeliverySettings(
        default_application_email_template_id=form.default_application_email_template_id
    )


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
        if settings.FORMS_SHARED_INTAKE:
            form_intake_service.ensure_default_intake_link(
                db,
                org_id=session.org_id,
                form=form,
                user_id=session.user_id,
            )
            form_intake_service.ensure_default_intake_routing_workflow(
                db,
                org_id=session.org_id,
                form=form,
                user_id=session.user_id,
            )
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
    mappings = form_submission_service.list_field_mappings(db, form.id)
    return [
        FormFieldMappingItem(field_key=m.field_key, surrogate_field=m.surrogate_field)
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
        FormFieldMappingItem(field_key=m.field_key, surrogate_field=m.surrogate_field)
        for m in created
    ]


# =============================================================================
# Token + Submission Review (Surrogate-level)
# =============================================================================


@router.post(
    "/{form_id}/tokens",
    response_model=FormTokenRead,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def create_submission_token(
    form_id: UUID,
    body: FormTokenRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.get(
    "/{form_id}/intake-links",
    response_model=list[FormIntakeLinkRead],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_form_intake_links(
    form_id: UUID,
    include_inactive: bool = Query(False),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    links = form_intake_service.list_intake_links(
        db,
        org_id=session.org_id,
        form_id=form.id,
        include_inactive=include_inactive,
    )
    if settings.FORMS_SHARED_INTAKE and form.status == "published" and len(links) == 0:
        form_intake_service.ensure_default_intake_link(
            db,
            org_id=session.org_id,
            form=form,
            user_id=session.user_id,
        )
        links = form_intake_service.list_intake_links(
            db,
            org_id=session.org_id,
            form_id=form.id,
            include_inactive=include_inactive,
        )
    return [
        _intake_link_read(
            link,
            intake_url=form_intake_service.build_shared_application_link(base_url, link.slug),
        )
        for link in links
    ]


@router.post(
    "/{form_id}/intake-links",
    response_model=FormIntakeLinkRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def create_form_intake_link(
    form_id: UUID,
    body: FormIntakeLinkCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Shared intake is disabled")

    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    try:
        link = form_intake_service.create_intake_link(
            db=db,
            org_id=session.org_id,
            form=form,
            user_id=session.user_id,
            campaign_name=body.campaign_name,
            event_name=body.event_name,
            expires_at=body.expires_at,
            max_submissions=body.max_submissions,
            utm_defaults=body.utm_defaults,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    return _intake_link_read(
        link,
        intake_url=form_intake_service.build_shared_application_link(base_url, link.slug),
    )


@router.patch(
    "/intake-links/{link_id}",
    response_model=FormIntakeLinkRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def update_form_intake_link(
    link_id: UUID,
    body: FormIntakeLinkUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Shared intake is disabled")

    link = form_intake_service.get_intake_link(db, org_id=session.org_id, intake_link_id=link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Intake link not found")

    link = form_intake_service.update_intake_link(
        db=db,
        link=link,
        campaign_name=body.campaign_name,
        event_name=body.event_name,
        expires_at=body.expires_at,
        max_submissions=body.max_submissions,
        utm_defaults=body.utm_defaults,
        is_active=body.is_active,
        fields_set=body.model_fields_set,
    )
    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    return _intake_link_read(
        link,
        intake_url=form_intake_service.build_shared_application_link(base_url, link.slug),
    )


@router.post(
    "/intake-links/{link_id}/rotate",
    response_model=FormIntakeLinkRead,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def rotate_form_intake_link(
    link_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Shared intake is disabled")

    link = form_intake_service.get_intake_link(db, org_id=session.org_id, intake_link_id=link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Intake link not found")

    link = form_intake_service.rotate_intake_link(db=db, link=link)
    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    return _intake_link_read(
        link,
        intake_url=form_intake_service.build_shared_application_link(base_url, link.slug),
    )


@router.post(
    "/{form_id}/intake-links/{link_id}/send",
    response_model=FormIntakeLinkSendResponse,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def send_form_intake_link(
    form_id: UUID,
    link_id: UUID,
    body: FormIntakeLinkSendRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Shared intake is disabled")

    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    link = form_intake_service.get_intake_link(db, org_id=session.org_id, intake_link_id=link_id)
    if not link or link.form_id != form.id:
        raise HTTPException(status_code=404, detail="Intake link not found")

    surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    if not surrogate.email:
        raise HTTPException(status_code=400, detail="Surrogate has no email address")

    template_id = body.template_id or form.default_application_email_template_id
    if not template_id:
        raise HTTPException(
            status_code=400,
            detail="No delivery template selected. Set a form default or pass template_id.",
        )
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Email template not found")

    org = org_service.get_org_by_id(db, session.org_id)
    intake_url = form_intake_service.build_shared_application_link(
        org_service.get_org_portal_base_url(org),
        link.slug,
    )
    result = email_service.send_from_template(
        db=db,
        org_id=session.org_id,
        template_id=template.id,
        recipient_email=surrogate.email,
        variables={"form_link": intake_url},
        surrogate_id=surrogate.id,
        sender_user_id=session.user_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Email template not found")

    email_log, _job = result
    return FormIntakeLinkSendResponse(
        intake_link_id=link.id,
        template_id=template.id,
        email_log_id=email_log.id,
        sent_at=datetime.now(timezone.utc),
        intake_url=intake_url,
    )


@router.post(
    "/{form_id}/tokens/{token_id}/send",
    response_model=FormTokenSendResponse,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def send_submission_token(
    form_id: UUID,
    token_id: UUID,
    body: FormTokenSendRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    raise HTTPException(status_code=410, detail=DEDICATED_LINK_RETIRED_DETAIL)


@router.get(
    "/{form_id}/submissions",
    response_model=list[FormSubmissionRead],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_form_submissions(
    form_id: UUID,
    status: str | None = Query(default=None),
    match_status: str | None = Query(default=None),
    source_mode: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    submissions = form_submission_service.list_form_submissions(
        db,
        session.org_id,
        form.id,
        status=status,
        match_status=match_status,
        source_mode=source_mode,
        limit=limit,
    )
    results: list[FormSubmissionRead] = []
    for submission in submissions:
        files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
        results.append(_submission_read(submission, files))
    return results


@router.get(
    "/{form_id}/surrogates/{surrogate_id}/submission",
    response_model=FormSubmissionRead,
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)
def get_surrogate_submission(
    form_id: UUID,
    surrogate_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    submission = form_submission_service.get_submission_by_surrogate(
        db, session.org_id, form.id, surrogate.id
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="form_submission",
        target_id=submission.id,
        request=request,
        details={"form_id": str(form_id), "surrogate_id": str(surrogate_id)},
    )
    db.commit()
    return _submission_read(submission, files)


@router.get(
    "/{form_id}/surrogates/{surrogate_id}/draft",
    response_model=FormDraftStatusRead,
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)
def get_surrogate_draft_status(
    form_id: UUID,
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = form_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    draft = form_draft_service.get_draft_by_surrogate_form(
        db=db,
        org_id=session.org_id,
        form_id=form.id,
        surrogate_id=surrogate.id,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return FormDraftStatusRead(started_at=draft.started_at, updated_at=draft.updated_at)


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
    submissions = form_submission_service.list_form_submissions(
        db, session.org_id, form.id, status_filter
    )
    output = []
    for submission in submissions:
        files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
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


@router.get(
    "/submissions/{submission_id}/match-candidates",
    response_model=list[MatchCandidateRead],
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def list_submission_match_candidates(
    submission_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    candidates = form_intake_service.list_match_candidates(
        db,
        org_id=session.org_id,
        submission_id=submission.id,
    )
    return [
        MatchCandidateRead(
            id=candidate.id,
            submission_id=candidate.submission_id,
            surrogate_id=candidate.surrogate_id,
            reason=candidate.reason,
            created_at=candidate.created_at,
        )
        for candidate in candidates
    ]


@router.post(
    "/submissions/{submission_id}/match/resolve",
    response_model=FormSubmissionMatchResolveResponse,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def resolve_submission_match(
    submission_id: UUID,
    body: FormSubmissionMatchResolveRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if body.surrogate_id:
        surrogate = surrogate_service.get_surrogate(db, session.org_id, body.surrogate_id)
        if not surrogate:
            raise HTTPException(status_code=404, detail="Surrogate not found")
        check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        submission, outcome = form_intake_service.resolve_submission_match(
            db=db,
            submission=submission,
            surrogate_id=body.surrogate_id,
            create_intake_lead=body.create_intake_lead,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    candidate_count = len(
        form_intake_service.list_match_candidates(
            db, org_id=session.org_id, submission_id=submission.id
        )
    )
    return FormSubmissionMatchResolveResponse(
        submission=_submission_read(submission, files),
        outcome=outcome,
        candidate_count=candidate_count,
    )


@router.post(
    "/submissions/{submission_id}/match/retry",
    response_model=FormSubmissionMatchResolveResponse,
    dependencies=[
        Depends(require_permission(POLICIES["forms"].default)),
        Depends(require_csrf_header),
    ],
)
def retry_submission_match(
    submission_id: UUID,
    body: FormSubmissionMatchRetryRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    try:
        submission, outcome = form_intake_service.retry_submission_match(
            db=db,
            submission=submission,
            unlink_surrogate=body.unlink_surrogate,
            unlink_intake_lead=body.unlink_intake_lead,
            rerun_auto_match=body.rerun_auto_match,
            create_intake_lead_if_unmatched=body.create_intake_lead_if_unmatched,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    candidate_count = len(
        form_intake_service.list_match_candidates(
            db, org_id=session.org_id, submission_id=submission.id
        )
    )
    return FormSubmissionMatchResolveResponse(
        submission=_submission_read(submission, files),
        outcome=outcome,
        candidate_count=candidate_count,
    )


@router.get(
    "/intake-leads/{lead_id}",
    response_model=IntakeLeadRead,
    dependencies=[Depends(require_permission(POLICIES["forms"].default))],
)
def get_intake_lead(
    lead_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    lead = form_intake_service.get_intake_lead(db, org_id=session.org_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Intake lead not found")
    return IntakeLeadRead(
        id=lead.id,
        form_id=lead.form_id,
        intake_link_id=lead.intake_link_id,
        full_name=lead.full_name,
        email=lead.email,
        phone=lead.phone,
        date_of_birth=lead.date_of_birth.isoformat() if lead.date_of_birth else None,
        status=lead.status,
        promoted_surrogate_id=lead.promoted_surrogate_id,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        promoted_at=lead.promoted_at,
    )


@router.post(
    "/intake-leads/{lead_id}/promote",
    response_model=IntakeLeadPromoteResponse,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def promote_intake_lead(
    lead_id: UUID,
    body: IntakeLeadPromoteRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    lead = form_intake_service.get_intake_lead(db, org_id=session.org_id, lead_id=lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Intake lead not found")

    try:
        surrogate, linked_submission_count = form_intake_service.promote_intake_lead(
            db=db,
            lead=lead,
            user_id=session.user_id,
            source=body.source,
            is_priority=body.is_priority,
            assign_to_user=body.assign_to_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return IntakeLeadPromoteResponse(
        intake_lead_id=lead.id,
        surrogate_id=surrogate.id,
        linked_submission_count=linked_submission_count,
    )


@router.post(
    "/submissions/{submission_id}/approve",
    response_model=FormSubmissionRead,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def approve_submission(
    submission_id: UUID,
    body: FormSubmissionStatusUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        submission = form_submission_service.approve_submission(
            db=db,
            submission=submission,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    return _submission_read(submission, files)


@router.post(
    "/submissions/{submission_id}/reject",
    response_model=FormSubmissionRead,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def reject_submission(
    submission_id: UUID,
    body: FormSubmissionStatusUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        submission = form_submission_service.reject_submission(
            db=db,
            submission=submission,
            reviewer_id=session.user_id,
            review_notes=body.review_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    return _submission_read(submission, files)


@router.patch(
    "/submissions/{submission_id}/answers",
    response_model=FormSubmissionAnswersUpdateResponse,
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
def update_submission_answers(
    submission_id: UUID,
    body: FormSubmissionAnswersUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update submission answers and sync mapped surrogate fields."""
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    try:
        _, surrogate_updates = form_submission_service.update_submission_answers(
            db=db,
            submission=submission,
            updates=[u.model_dump() for u in body.updates],
            user_id=session.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = form_submission_service.list_submission_files(db, session.org_id, submission.id)
    return FormSubmissionAnswersUpdateResponse(
        submission=_submission_read(submission, files),
        surrogate_updates=surrogate_updates,
    )


@router.get(
    "/submissions/{submission_id}/files/{file_id}/download",
    response_model=FormSubmissionFileDownloadResponse,
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)
def download_submission_file(
    submission_id: UUID,
    file_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    file_record = form_submission_service.get_submission_file(
        db, session.org_id, submission_id, file_id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.scan_status in ("infected", "error"):
        detail = (
            "File is infected"
            if file_record.scan_status == "infected"
            else "File failed virus scan"
        )
        raise HTTPException(status_code=403, detail=detail)
    if settings.ATTACHMENT_SCAN_ENABLED and file_record.scan_status != "clean":
        raise HTTPException(status_code=409, detail="File is still being scanned")

    url = form_submission_service.get_submission_file_download_url(
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
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
        Depends(require_csrf_header),
    ],
)
async def upload_submission_file(
    submission_id: UUID,
    file: UploadFile = File(...),
    field_key: str | None = Form(default=None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Upload a file to an existing submission (edit mode)."""
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    try:
        file_record = form_submission_service.add_submission_file(
            db=db,
            org_id=session.org_id,
            submission=submission,
            file=file,
            field_key=field_key,
            user_id=session.user_id,
        )
        db.commit()
        return FormSubmissionFileRead(
            id=file_record.id,
            filename=file_record.filename,
            content_type=file_record.content_type,
            file_size=file_record.file_size,
            quarantined=file_record.quarantined,
            scan_status=file_record.scan_status,
            field_key=file_record.field_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/submissions/{submission_id}/files/{file_id}",
    dependencies=[
        Depends(require_permission(POLICIES["surrogates"].actions["edit"])),
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
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    file_record = form_submission_service.get_submission_file(
        db, session.org_id, submission_id, file_id
    )
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    success = form_submission_service.soft_delete_submission_file(
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
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)
def export_submission_pdf(
    submission_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Export a submission as PDF."""
    submission = form_submission_service.get_submission(db, session.org_id, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not submission.surrogate_id:
        raise HTTPException(
            status_code=409,
            detail="Submission is not linked to a surrogate. Resolve matching first.",
        )
    surrogate = surrogate_service.get_surrogate(db, session.org_id, submission.surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    org = org_service.get_org_by_id(db, session.org_id)
    org_name = org.name if org else ""
    surrogate_name = (
        surrogate.full_name or f"Surrogate #{surrogate.surrogate_number or surrogate.id}"
    )

    from app.services import pdf_export_service

    try:
        pdf_bytes = pdf_export_service.export_submission_pdf(
            db=db,
            submission_id=submission.id,
            org_id=session.org_id,
            surrogate_name=surrogate_name,
            org_name=org_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"application_{surrogate.surrogate_number or surrogate.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
