"""Meta lead form mapping endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.db.enums import JobType
from app.db.models import MetaPageMapping, User
from app.schemas.auth import UserSession
from app.schemas.meta_forms import (
    MetaFormMappingPreviewResponse,
    MetaFormMappingUpdateRequest,
    MetaFormMappingUpdateResponse,
    MetaFormSummary,
    MetaFormSyncRequest,
)
from app.schemas.import_template import ColumnSuggestionResponse, ColumnMappingItem
from app.services import job_service, meta_form_mapping_service, meta_sync_service


router = APIRouter(
    prefix="/integrations/meta/forms",
    tags=["integrations"],
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)


@router.get("", response_model=list[MetaFormSummary])
def list_meta_forms(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    forms = meta_form_mapping_service.list_forms(db, session.org_id)
    if not forms:
        return []

    # Page name lookup
    pages = (
        db.query(MetaPageMapping).filter(MetaPageMapping.organization_id == session.org_id).all()
    )
    page_names = {p.page_id: p.page_name for p in pages}

    # Lead stats by form_external_id
    lead_stats = meta_form_mapping_service.get_lead_stats(db, session.org_id)

    # User lookup for mapping updated by
    user_ids = {f.mapping_updated_by_user_id for f in forms if f.mapping_updated_by_user_id}
    user_names = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_names = {u.id: u.display_name for u in users}

    summaries: list[MetaFormSummary] = []
    for form in forms:
        stats = lead_stats.get(form.form_external_id, {})
        summaries.append(
            MetaFormSummary(
                id=form.id,
                form_external_id=form.form_external_id,
                form_name=form.form_name,
                page_id=form.page_id,
                page_name=page_names.get(form.page_id),
                mapping_status=form.mapping_status,
                current_version_id=form.current_version_id,
                mapping_version_id=form.mapping_version_id,
                mapping_updated_at=form.mapping_updated_at,
                mapping_updated_by_name=user_names.get(form.mapping_updated_by_user_id),
                is_active=form.is_active,
                synced_at=form.synced_at,
                unconverted_leads=int(stats.get("unconverted", 0)),
                total_leads=int(stats.get("total", 0)),
                last_lead_at=stats.get("last_lead_at"),
            )
        )

    return summaries


@router.post("/sync", response_model=dict)
async def sync_meta_forms(
    data: MetaFormSyncRequest,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    result = await meta_sync_service.sync_forms(db, session.org_id, data.page_id)
    return {
        "success": result.get("error") is None,
        "message": f"Forms sync completed: {result.get('forms_synced', 0)} forms",
        "details": result,
    }


@router.get("/{form_id}/mapping", response_model=MetaFormMappingPreviewResponse)
def preview_meta_form_mapping(
    form_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")

    preview = meta_form_mapping_service.build_mapping_preview(db, form)

    # Build form summary for response
    lead_stats = meta_form_mapping_service.get_lead_stats(db, session.org_id)
    stats = lead_stats.get(form.form_external_id, {})
    page = (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.organization_id == session.org_id,
            MetaPageMapping.page_id == form.page_id,
        )
        .first()
    )

    updated_by_name = None
    if form.mapping_updated_by_user_id:
        user = db.query(User).filter(User.id == form.mapping_updated_by_user_id).first()
        updated_by_name = user.display_name if user else None

    form_summary = MetaFormSummary(
        id=form.id,
        form_external_id=form.form_external_id,
        form_name=form.form_name,
        page_id=form.page_id,
        page_name=page.page_name if page else None,
        mapping_status=form.mapping_status,
        current_version_id=form.current_version_id,
        mapping_version_id=form.mapping_version_id,
        mapping_updated_at=form.mapping_updated_at,
        mapping_updated_by_name=updated_by_name,
        is_active=form.is_active,
        synced_at=form.synced_at,
        unconverted_leads=int(stats.get("unconverted", 0)),
        total_leads=int(stats.get("total", 0)),
        last_lead_at=stats.get("last_lead_at"),
    )

    return MetaFormMappingPreviewResponse(
        form=form_summary,
        columns=preview["columns"],
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
            for s in preview["column_suggestions"]
        ],
        sample_rows=preview["sample_rows"],
        has_live_leads=preview["has_live_leads"],
        available_fields=preview["available_fields"],
        ai_available=preview["ai_available"],
        mapping_rules=[ColumnMappingItem(**m) for m in (form.mapping_rules or [])]
        if form.mapping_rules
        else None,
        unknown_column_behavior=form.unknown_column_behavior or "metadata",
    )


@router.put("/{form_id}/mapping", response_model=MetaFormMappingUpdateResponse)
def update_meta_form_mapping(
    form_id: UUID,
    data: MetaFormMappingUpdateRequest,
    _csrf: None = Depends(require_csrf_header),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")

    try:
        meta_form_mapping_service.save_mapping(
            db,
            form,
            column_mappings=[m.model_dump() for m in data.column_mappings],
            unknown_column_behavior=data.unknown_column_behavior,
            user_id=session.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Reprocess existing leads for this form
    job_service.schedule_job(
        db=db,
        org_id=session.org_id,
        job_type=JobType.META_LEAD_REPROCESS_FORM,
        payload={"form_id": str(form.id)},
    )

    return MetaFormMappingUpdateResponse(
        success=True,
        mapping_status=form.mapping_status,
        mapping_version_id=form.mapping_version_id,
        message="Mapping saved and reprocessing queued.",
    )
