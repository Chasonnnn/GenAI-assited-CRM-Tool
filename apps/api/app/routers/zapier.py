"""Zapier webhook integration settings."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.permissions import PermissionKey as P
from app.schemas.auth import UserSession
from app.services import (
    meta_form_mapping_service,
    zapier_settings_service,
    zapier_outbound_service,
)
from app.services.webhooks import zapier as zapier_webhook_service

router = APIRouter(prefix="/integrations/zapier", tags=["zapier"])


class ZapierInboundWebhookResponse(BaseModel):
    webhook_id: str
    webhook_url: str
    label: str | None
    is_active: bool
    secret_configured: bool
    created_at: datetime


class ZapierSettingsResponse(BaseModel):
    webhook_url: str
    is_active: bool
    secret_configured: bool
    inbound_webhooks: list[ZapierInboundWebhookResponse]
    outbound_webhook_url: str | None
    outbound_enabled: bool
    outbound_secret_configured: bool
    send_hashed_pii: bool
    event_mapping: list["ZapierEventMappingItem"]


class RotateSecretResponse(BaseModel):
    webhook_url: str
    webhook_secret: str
    webhook_id: str | None = None


class ZapierInboundWebhookCreateRequest(BaseModel):
    label: str | None = None


class ZapierInboundWebhookCreateResponse(BaseModel):
    webhook_id: str
    webhook_url: str
    webhook_secret: str
    label: str | None
    is_active: bool


class ZapierInboundWebhookUpdateRequest(BaseModel):
    label: str | None = None
    is_active: bool | None = None


class ZapierEventMappingItem(BaseModel):
    stage_key: str
    event_name: str
    enabled: bool = True
    bucket: Literal["qualified", "converted", "lost", "not_qualified"] | None = None


class ZapierOutboundSettingsUpdate(BaseModel):
    outbound_webhook_url: str | None = None
    outbound_webhook_secret: str | None = None
    outbound_enabled: bool | None = None
    send_hashed_pii: bool | None = None
    event_mapping: list[ZapierEventMappingItem] | None = None


class ZapierTestLeadRequest(BaseModel):
    form_id: str | None = None
    fields: dict | None = None


class ZapierTestLeadResponse(BaseModel):
    status: str
    duplicate: bool
    meta_lead_id: str
    surrogate_id: str | None = None
    message: str | None = None


class ZapierOutboundTestRequest(BaseModel):
    stage_key: str | None = None
    lead_id: str | None = None


class ZapierOutboundTestResponse(BaseModel):
    status: str
    event_name: str
    event_id: str


class ZapierFieldPasteRequest(BaseModel):
    paste: str
    webhook_id: str | None = None
    form_id: str | None = None
    form_name: str | None = None


class ZapierFieldPasteResponse(BaseModel):
    form_id: str
    form_name: str | None
    meta_form_id: str
    field_count: int
    field_keys: list[str]
    mapping_url: str


@router.get("/settings", response_model=ZapierSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    settings = zapier_settings_service.get_or_create_settings(db, session.org_id)
    inbound_webhooks = zapier_settings_service.list_inbound_webhooks(db, session.org_id)
    return _serialize_settings(settings, inbound_webhooks)


@router.post("/settings/rotate-secret", response_model=RotateSecretResponse)
def rotate_secret(
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    settings, secret = zapier_settings_service.rotate_webhook_secret(db, session.org_id)
    inbound = zapier_settings_service.get_primary_inbound_webhook(db, session.org_id)
    webhook_id = inbound.webhook_id if inbound else settings.webhook_id
    webhook_url = (
        zapier_settings_service.get_webhook_url(webhook_id)
        if webhook_id
        else zapier_settings_service.get_webhook_url(settings.webhook_id)
    )
    return RotateSecretResponse(
        webhook_url=webhook_url,
        webhook_secret=secret,
        webhook_id=webhook_id,
    )


@router.post("/webhooks", response_model=ZapierInboundWebhookCreateResponse)
def create_inbound_webhook(
    data: ZapierInboundWebhookCreateRequest,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    zapier_settings_service.get_or_create_settings(db, session.org_id)
    inbound, secret = zapier_settings_service.create_inbound_webhook(
        db, session.org_id, label=data.label
    )
    return ZapierInboundWebhookCreateResponse(
        webhook_id=inbound.webhook_id,
        webhook_url=zapier_settings_service.get_webhook_url(inbound.webhook_id),
        webhook_secret=secret,
        label=inbound.label,
        is_active=inbound.is_active,
    )


@router.post("/webhooks/{webhook_id}/rotate-secret", response_model=RotateSecretResponse)
def rotate_inbound_secret(
    webhook_id: str,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    try:
        inbound, secret = zapier_settings_service.rotate_inbound_webhook_secret(
            db, session.org_id, webhook_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RotateSecretResponse(
        webhook_url=zapier_settings_service.get_webhook_url(inbound.webhook_id),
        webhook_secret=secret,
        webhook_id=inbound.webhook_id,
    )


@router.patch("/webhooks/{webhook_id}", response_model=ZapierInboundWebhookResponse)
def update_inbound_webhook(
    webhook_id: str,
    data: ZapierInboundWebhookUpdateRequest,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    try:
        inbound = zapier_settings_service.update_inbound_webhook(
            db,
            session.org_id,
            webhook_id,
            label=data.label,
            is_active=data.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ZapierInboundWebhookResponse(
        webhook_id=inbound.webhook_id,
        webhook_url=zapier_settings_service.get_webhook_url(inbound.webhook_id),
        label=inbound.label,
        is_active=inbound.is_active,
        secret_configured=bool(inbound.webhook_secret_encrypted),
        created_at=inbound.created_at,
    )


@router.delete("/webhooks/{webhook_id}", status_code=204)
def delete_inbound_webhook(
    webhook_id: str,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    try:
        zapier_settings_service.delete_inbound_webhook(db, session.org_id, webhook_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/settings/outbound", response_model=ZapierSettingsResponse)
def update_outbound_settings(
    data: ZapierOutboundSettingsUpdate,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    try:
        settings = zapier_settings_service.update_outbound_settings(
            db,
            session.org_id,
            outbound_webhook_url=data.outbound_webhook_url,
            outbound_webhook_secret=data.outbound_webhook_secret,
            outbound_enabled=data.outbound_enabled,
            send_hashed_pii=data.send_hashed_pii,
            event_mapping=[m.model_dump() for m in data.event_mapping]
            if data.event_mapping
            else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    inbound_webhooks = zapier_settings_service.list_inbound_webhooks(db, session.org_id)
    return _serialize_settings(settings, inbound_webhooks)


@router.post("/test-lead", response_model=ZapierTestLeadResponse)
def send_test_lead(
    data: ZapierTestLeadRequest,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    form_id = data.form_id
    if not form_id:
        forms = meta_form_mapping_service.list_active_forms(db, session.org_id)
        if not forms:
            raise HTTPException(
                status_code=400, detail="No Meta lead forms found for this organization."
            )
        if len(forms) > 1:
            raise HTTPException(
                status_code=400,
                detail="form_id is required when multiple Meta lead forms exist.",
            )
        form_id = forms[0].form_external_id

    payload = zapier_webhook_service.build_test_payload(form_id, fields=data.fields)
    result = zapier_webhook_service.process_zapier_payload(
        db,
        session.org_id,
        payload,
        test_mode=True,
    )
    return ZapierTestLeadResponse(**result)


@router.post("/field-paste", response_model=ZapierFieldPasteResponse)
def parse_field_paste(
    data: ZapierFieldPasteRequest,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    paste = data.paste.strip()
    if not paste:
        raise HTTPException(status_code=400, detail="Paste field list is required.")

    parsed = zapier_webhook_service.parse_zapier_field_paste(paste)
    field_keys = parsed.get("field_keys") or []
    if not field_keys:
        raise HTTPException(
            status_code=400,
            detail="No field keys detected. Paste the Zapier field list or sample data.",
        )

    inbound = None
    if data.webhook_id:
        inbound = zapier_settings_service.get_inbound_webhook_by_id(db, data.webhook_id)
        if not inbound or inbound.organization_id != session.org_id:
            raise HTTPException(status_code=404, detail="Inbound webhook not found.")

    form_id = data.form_id or parsed.get("form_id")
    if not form_id and inbound:
        form_id = f"zapier-{inbound.webhook_id}"

    if not form_id:
        raise HTTPException(
            status_code=400,
            detail="form_id or webhook_id is required to create the mapping.",
        )

    form_name = data.form_name or parsed.get("form_name")
    if not form_name:
        if inbound and inbound.label:
            form_name = inbound.label
        else:
            form_name = f"Zapier Lead Intake ({form_id})"

    form = meta_form_mapping_service.upsert_form_from_payload(
        db,
        session.org_id,
        form_external_id=str(form_id),
        form_name=form_name,
        field_keys=field_keys,
        page_id="zapier",
    )
    if not form:
        raise HTTPException(status_code=500, detail="Unable to save form mapping.")

    db.commit()
    db.refresh(form)

    return ZapierFieldPasteResponse(
        form_id=form.form_external_id,
        form_name=form.form_name,
        meta_form_id=str(form.id),
        field_count=len(field_keys),
        field_keys=field_keys,
        mapping_url=f"/settings/integrations/meta/forms/{form.id}",
    )


@router.post("/test-outbound", response_model=ZapierOutboundTestResponse)
def send_outbound_test(
    data: ZapierOutboundTestRequest,
    _csrf: None = Depends(require_csrf_header),
    db: Session = Depends(get_db),
    session: UserSession = Depends(require_permission(P.INTEGRATIONS_MANAGE)),
):
    settings = zapier_settings_service.get_or_create_settings(db, session.org_id)
    if not settings or not settings.outbound_webhook_url:
        raise HTTPException(status_code=400, detail="Outbound webhook URL not configured.")
    if not settings.outbound_enabled:
        raise HTTPException(status_code=400, detail="Outbound webhook is disabled.")

    mapping = zapier_settings_service.normalize_event_mapping(settings.outbound_event_mapping)
    stage_key = data.stage_key or (mapping[0]["stage_key"] if mapping else None)
    if not stage_key:
        raise HTTPException(status_code=400, detail="No stage mapping available.")

    event_name = None
    for item in mapping:
        if item.get("stage_key") == stage_key and item.get("enabled", True):
            event_name = item.get("event_name")
            break
    if not event_name:
        raise HTTPException(status_code=400, detail="Stage is not enabled for outbound events.")

    lead_id = data.lead_id or f"zapier-test-{session.org_id}"

    result = zapier_outbound_service.enqueue_test_event(
        db,
        session.org_id,
        stage_key=stage_key,
        event_name=event_name,
        lead_id=lead_id,
        include_hashed_pii=settings.outbound_send_hashed_pii,
    )
    return ZapierOutboundTestResponse(status="queued", **result)


def _serialize_settings(
    settings,
    inbound_webhooks: list,
) -> ZapierSettingsResponse:
    mapping = zapier_settings_service.normalize_event_mapping(settings.outbound_event_mapping)
    inbound_payload = [
        ZapierInboundWebhookResponse(
            webhook_id=inbound.webhook_id,
            webhook_url=zapier_settings_service.get_webhook_url(inbound.webhook_id),
            label=inbound.label,
            is_active=inbound.is_active,
            secret_configured=bool(inbound.webhook_secret_encrypted),
            created_at=inbound.created_at,
        )
        for inbound in inbound_webhooks
    ]
    primary = inbound_webhooks[0] if inbound_webhooks else None
    webhook_id = primary.webhook_id if primary else settings.webhook_id
    return ZapierSettingsResponse(
        webhook_url=zapier_settings_service.get_webhook_url(webhook_id),
        is_active=primary.is_active if primary else settings.is_active,
        secret_configured=bool(primary.webhook_secret_encrypted)
        if primary
        else bool(settings.webhook_secret_encrypted),
        inbound_webhooks=inbound_payload,
        outbound_webhook_url=settings.outbound_webhook_url,
        outbound_enabled=bool(settings.outbound_enabled),
        outbound_secret_configured=bool(settings.outbound_webhook_secret_encrypted),
        send_hashed_pii=bool(settings.outbound_send_hashed_pii),
        event_mapping=mapping,
    )
