"""Meta lead form mapping endpoints."""

from __future__ import annotations
from typing import Annotated

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.db.enums import JobType
from app.schemas.auth import UserSession
from app.schemas.meta_forms import (
    MetaFormMappingPreviewResponse,
    MetaFormReconvertResponse,
    MetaFormMappingUpdateRequest,
    MetaFormMappingUpdateResponse,
    MetaFormSummary,
    MetaFormUnconvertedLeadItem,
    MetaFormUnconvertedLeadListResponse,
    MetaFormSyncRequest,
)
from app.schemas.import_template import ColumnSuggestionResponse, ColumnMappingItem
from app.services import (
    job_service,
    meta_form_mapping_service,
    meta_page_service,
    meta_sync_service,
    user_service,
)

csrf_header_dependency = require_csrf_header


router = APIRouter(
    prefix="/integrations/meta/forms",
    tags=["integrations"],
    dependencies=[Depends(require_permission(POLICIES["meta_leads"].default))],
)


@router.get("", response_model=list[MetaFormSummary])
def list_meta_forms(
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    forms = meta_form_mapping_service.list_forms(db, session.org_id)
    if not forms:
        return []

    # Page name lookup
    pages = meta_page_service.list_meta_pages(db, session.org_id)
    page_names = {p.page_id: p.page_name for p in pages}

    # Lead stats by form_external_id
    lead_stats = meta_form_mapping_service.get_lead_stats(db, session.org_id)

    # User lookup for mapping updated by
    user_ids = {f.mapping_updated_by_user_id for f in forms if f.mapping_updated_by_user_id}
    user_names = user_service.get_display_names_by_ids(db, user_ids)

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


@router.post("/sync", response_model=dict[str, object])
async def sync_meta_forms(
    data: MetaFormSyncRequest,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
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
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")

    preview = meta_form_mapping_service.build_mapping_preview(db, form)

    # Build form summary for response
    lead_stats = meta_form_mapping_service.get_lead_stats(db, session.org_id)
    stats = lead_stats.get(form.form_external_id, {})
    page = meta_page_service.get_mapping_by_page_id(db, session.org_id, form.page_id)

    updated_by_name = None
    if form.mapping_updated_by_user_id:
        updated_by_name = user_service.get_display_names_by_ids(
            db, [form.mapping_updated_by_user_id]
        ).get(form.mapping_updated_by_user_id)

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
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")

    # Get original suggestions for learning
    try:
        preview = meta_form_mapping_service.build_mapping_preview(db, form)
        original_suggestions = [
            {
                "csv_column": s.csv_column,
                "suggested_field": s.suggested_field,
            }
            for s in preview["column_suggestions"]
        ]
    except Exception:
        original_suggestions = None

    try:
        meta_form_mapping_service.save_mapping(
            db,
            form,
            column_mappings=[m.model_dump() for m in data.column_mappings],
            unknown_column_behavior=data.unknown_column_behavior,
            user_id=session.user_id,
            original_suggestions=original_suggestions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Reprocess existing leads for this form
    _, eligible_ids, _, _ = meta_form_mapping_service.get_reprocess_plan_for_form(
        db,
        session.org_id,
        form.form_external_id,
    )
    if eligible_ids:
        job_service.schedule_job(
            db=db,
            org_id=session.org_id,
            job_type=JobType.META_LEAD_REPROCESS_FORM,
            payload={"form_id": str(form.id), "lead_ids": [str(lead_id) for lead_id in eligible_ids]},
        )

    return MetaFormMappingUpdateResponse(
        success=True,
        mapping_status=form.mapping_status,
        mapping_version_id=form.mapping_version_id,
        message=(
            "Mapping saved and eligible leads queued for reprocessing."
            if eligible_ids
            else "Mapping saved. No eligible leads were queued for reprocessing."
        ),
    )


@router.get(
    "/{form_id}/unconverted-leads",
    response_model=MetaFormUnconvertedLeadListResponse,
)
def list_unconverted_leads(
    form_id: UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")

    items, total = meta_form_mapping_service.list_unconverted_leads_for_form(
        db,
        session.org_id,
        form.form_external_id,
        limit=limit,
        offset=offset,
    )
    all_unconverted, eligible_ids, reasons_by_lead, _ = meta_form_mapping_service.get_reprocess_plan_for_form(
        db,
        session.org_id,
        form.form_external_id,
    )
    eligible_set = set(eligible_ids)
    return MetaFormUnconvertedLeadListResponse(
        items=[
            _serialize_unconverted_lead(
                item,
                reprocess_eligible=item.id in eligible_set,
                reprocess_block_reason=reasons_by_lead.get(item.id),
            )
            for item in items
        ],
        total=total,
        eligible_count=len(eligible_ids),
        blocked_count=max(len(all_unconverted) - len(eligible_ids), 0),
    )


@router.post(
    "/{form_id}/reconvert",
    response_model=MetaFormReconvertResponse,
)
def reconvert_meta_form_leads(
    form_id: UUID,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    form = meta_form_mapping_service.get_form(db, session.org_id, form_id)
    if not form:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    if form.mapping_status != "mapped" or form.mapping_version_id != form.current_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Form mapping is not ready for reconversion",
        )

    _, eligible_ids, _, reason_counts = meta_form_mapping_service.get_reprocess_plan_for_form(
        db,
        session.org_id,
        form.form_external_id,
    )

    if eligible_ids:
        job_service.schedule_job(
            db=db,
            org_id=session.org_id,
            job_type=JobType.META_LEAD_REPROCESS_FORM,
            payload={"form_id": str(form.id), "lead_ids": [str(lead_id) for lead_id in eligible_ids]},
        )

    blocked_count = sum(reason_counts.values())
    return MetaFormReconvertResponse(
        success=True,
        queued_count=len(eligible_ids),
        blocked_count=blocked_count,
        blocked_reasons=reason_counts,
        message=(
            f"Queued {len(eligible_ids)} eligible lead(s) for reconversion."
            if eligible_ids
            else "No eligible leads were queued for reconversion."
        ),
    )


@router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meta_form(
    form_id: UUID,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    session: Annotated[UserSession, "fastapi_param"] = Depends(get_current_session),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> Response:
    deleted = meta_form_mapping_service.delete_form(db, session.org_id, form_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")


def _serialize_unconverted_lead(
    lead,
    *,
    reprocess_eligible: bool,
    reprocess_block_reason: str | None,
) -> MetaFormUnconvertedLeadItem:
    raw = lead.field_data_raw or lead.field_data or {}
    return MetaFormUnconvertedLeadItem(
        id=lead.id,
        meta_lead_id=lead.meta_lead_id,
        status=lead.status,
        is_converted=bool(lead.is_converted),
        full_name=raw.get("full_name") or raw.get("name"),
        email=raw.get("email"),
        phone=raw.get("phone") or raw.get("phone_number"),
        conversion_error=lead.conversion_error,
        fetch_error=lead.fetch_error,
        reprocess_eligible=reprocess_eligible,
        reprocess_block_reason=reprocess_block_reason,
        received_at=lead.received_at,
        meta_created_time=lead.meta_created_time,
    )
