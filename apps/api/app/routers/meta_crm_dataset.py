"""Direct Meta CRM dataset integration settings and monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import (
    meta_crm_dataset_monitor_service,
    meta_crm_dataset_service,
    meta_crm_dataset_settings_service,
)

csrf_header_dependency = require_csrf_header

router = APIRouter(prefix="/integrations/meta/crm-dataset", tags=["meta-crm-dataset"])


class MetaCrmDatasetEventMappingItem(BaseModel):
    stage_key: str
    event_name: str
    enabled: bool = True
    bucket: Literal["qualified", "converted", "lost", "not_qualified"] | None = None


class MetaCrmDatasetSettingsResponse(BaseModel):
    dataset_id: str | None
    access_token_configured: bool
    enabled: bool
    crm_name: str
    send_hashed_pii: bool
    event_mapping: list[MetaCrmDatasetEventMappingItem]
    test_event_code: str | None = None


class MetaCrmDatasetSettingsUpdate(BaseModel):
    dataset_id: str | None = None
    access_token: str | None = None
    enabled: bool | None = None
    crm_name: str | None = None
    send_hashed_pii: bool | None = None
    event_mapping: list[MetaCrmDatasetEventMappingItem] | None = None
    test_event_code: str | None = None


class MetaCrmDatasetTestRequest(BaseModel):
    stage_key: str | None = None
    lead_id: str | None = None
    fbc: str | None = None
    test_event_code: str | None = None


class MetaCrmDatasetTestResponse(BaseModel):
    status: str
    event_name: str
    event_id: str
    lead_id: str


class MetaCrmDatasetEventResponse(BaseModel):
    id: UUID
    source: str
    status: str
    reason: str | None = None
    event_id: str | None = None
    event_name: str | None = None
    lead_id: str | None = None
    stage_key: str | None = None
    stage_slug: str | None = None
    stage_label: str | None = None
    surrogate_id: UUID | None = None
    attempts: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None = None
    last_attempt_at: datetime | None = None
    can_retry: bool


class MetaCrmDatasetEventsResponse(BaseModel):
    items: list[MetaCrmDatasetEventResponse]
    total: int


class MetaCrmDatasetEventsSummaryResponse(BaseModel):
    window_hours: int
    total_count: int
    queued_count: int
    delivered_count: int
    failed_count: int
    skipped_count: int
    actionable_skipped_count: int
    failure_rate: float
    skipped_rate: float
    failure_rate_alert: bool
    skipped_rate_alert: bool
    warning_messages: list[str]


class MetaCrmDatasetRetryRequest(BaseModel):
    reason: str | None = None


@router.get("/settings", response_model=MetaCrmDatasetSettingsResponse)
def get_settings(
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, session.org_id)
    return _serialize_settings(settings)


@router.patch("/settings", response_model=MetaCrmDatasetSettingsResponse)
def update_settings(
    data: MetaCrmDatasetSettingsUpdate,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    settings = meta_crm_dataset_settings_service.update_settings(
        db,
        session.org_id,
        dataset_id=data.dataset_id,
        access_token=data.access_token,
        enabled=data.enabled,
        crm_name=data.crm_name,
        send_hashed_pii=data.send_hashed_pii,
        event_mapping=(
            [item.model_dump() for item in data.event_mapping]
            if data.event_mapping is not None
            else None
        ),
        test_event_code=data.test_event_code,
    )
    return _serialize_settings(settings)


@router.post("/test-outbound", response_model=MetaCrmDatasetTestResponse)
def send_test_outbound(
    data: MetaCrmDatasetTestRequest,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    settings = meta_crm_dataset_settings_service.get_or_create_settings(db, session.org_id)
    mapping = meta_crm_dataset_settings_service.normalize_event_mapping(settings.event_mapping)
    stage_key = data.stage_key or (mapping[0]["stage_key"] if mapping else None)
    if not stage_key:
        raise HTTPException(status_code=400, detail="stage_key is required")

    event_name = None
    for item in mapping:
        if item.get("stage_key") == stage_key and item.get("enabled", True):
            event_name = item.get("event_name")
            break
    if not event_name:
        raise HTTPException(status_code=400, detail="stage_key is not enabled in event mapping")

    lead_id = (data.lead_id or "").strip() or f"meta-crm-dataset-test-{session.org_id}"
    try:
        result = meta_crm_dataset_service.enqueue_test_event(
            db,
            session.org_id,
            stage_key=stage_key,
            event_name=str(event_name),
            lead_id=lead_id,
            include_hashed_pii=bool(settings.send_hashed_pii),
            fbc=data.fbc,
            test_event_code=data.test_event_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MetaCrmDatasetTestResponse(status="queued", **result)


@router.get("/events", response_model=MetaCrmDatasetEventsResponse)
def list_events(
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    items, total = meta_crm_dataset_monitor_service.list_events(
        db,
        org_id=session.org_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return MetaCrmDatasetEventsResponse(
        items=[_serialize_event(item) for item in items],
        total=total,
    )


@router.get("/events/summary", response_model=MetaCrmDatasetEventsSummaryResponse)
def get_events_summary(
    window_hours: Annotated[int, Query(ge=1, le=24 * 30)] = 24,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    return MetaCrmDatasetEventsSummaryResponse(
        **meta_crm_dataset_monitor_service.get_summary(
            db,
            org_id=session.org_id,
            window_hours=window_hours,
        )
    )


@router.post("/events/{event_id}/retry", response_model=MetaCrmDatasetEventResponse)
def retry_event(
    event_id: UUID,
    data: MetaCrmDatasetRetryRequest,
    _csrf: Annotated[None, "fastapi_param"] = Depends(csrf_header_dependency),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(P.INTEGRATIONS_MANAGE)
    ),
):
    try:
        event = meta_crm_dataset_monitor_service.retry_failed_event(
            db,
            org_id=session.org_id,
            event_id=event_id,
            reason=data.reason,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Event not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return _serialize_event(event)


def _serialize_settings(settings) -> MetaCrmDatasetSettingsResponse:
    return MetaCrmDatasetSettingsResponse(
        dataset_id=settings.dataset_id,
        access_token_configured=bool(settings.access_token_encrypted),
        enabled=bool(settings.enabled),
        crm_name=settings.crm_name or meta_crm_dataset_settings_service.default_crm_name(),
        send_hashed_pii=bool(settings.send_hashed_pii),
        event_mapping=meta_crm_dataset_settings_service.normalize_event_mapping(
            settings.event_mapping
        ),
        test_event_code=settings.test_event_code,
    )


def _serialize_event(event) -> MetaCrmDatasetEventResponse:
    return MetaCrmDatasetEventResponse(
        id=event.id,
        source=event.source,
        status=event.status,
        reason=event.reason,
        event_id=event.event_id,
        event_name=event.event_name,
        lead_id=event.lead_id,
        stage_key=event.stage_key,
        stage_slug=event.stage_slug,
        stage_label=event.stage_label,
        surrogate_id=event.surrogate_id,
        attempts=event.attempts,
        last_error=event.last_error,
        created_at=event.created_at,
        updated_at=event.updated_at,
        delivered_at=event.delivered_at,
        last_attempt_at=event.last_attempt_at,
        can_retry=event.status == "failed" and event.job_id is not None,
    )
