"""Zapier outbound stage event service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import JobType, SurrogateSource
from app.db.models import MetaLead, Surrogate
from app.services import job_service, meta_capi, zapier_settings_service

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def resolve_event_name(mapping: list[dict], stage_slug: str) -> str | None:
    for item in mapping:
        if item.get("stage_slug") == stage_slug and item.get("enabled", True):
            return item.get("event_name")
    return None


def build_stage_event_payload(
    *,
    lead_id: str,
    event_name: str,
    event_time: datetime,
    stage_slug: str,
    stage_label: str | None,
    surrogate_id: str | None,
    include_hashed_pii: bool,
    email: str | None,
    phone: str | None,
    meta_fields: dict | None = None,
    event_id: str | None = None,
    test_mode: bool = False,
) -> dict:
    payload = {
        "event_id": event_id or f"zapier_stage:{lead_id}:{stage_slug}",
        "event_name": event_name,
        "event_time": event_time.astimezone(timezone.utc).isoformat(),
        "lead_id": lead_id,
        "stage_slug": stage_slug,
        "stage_label": stage_label,
    }

    if surrogate_id:
        payload["surrogate_id"] = surrogate_id

    if meta_fields:
        payload.update({k: v for k, v in meta_fields.items() if v is not None})

    if include_hashed_pii:
        user_data: dict[str, str] = {}
        if email:
            user_data["email_hash"] = meta_capi.hash_for_capi(email)
        if phone:
            user_data["phone_hash"] = meta_capi.hash_for_capi(phone)
        if user_data:
            payload["user_data"] = user_data

    if test_mode:
        payload["test_mode"] = True

    return payload


def _extract_meta_fields(meta_lead: MetaLead, surrogate: Surrogate) -> dict[str, str | None]:
    fields = meta_lead.field_data_raw or meta_lead.field_data or {}
    return {
        "meta_lead_id": meta_lead.meta_lead_id,
        "meta_form_id": surrogate.meta_form_id or meta_lead.meta_form_id,
        "meta_page_id": meta_lead.meta_page_id,
        "meta_ad_id": surrogate.meta_ad_external_id
        or fields.get("meta_ad_id")
        or fields.get("ad_id"),
        "meta_adset_id": surrogate.meta_adset_external_id
        or fields.get("meta_adset_id")
        or fields.get("adset_id")
        or fields.get("ad_set_id"),
        "meta_campaign_id": surrogate.meta_campaign_external_id
        or fields.get("meta_campaign_id")
        or fields.get("campaign_id"),
        "meta_ad_name": fields.get("meta_ad_name") or fields.get("ad_name"),
        "meta_adset_name": fields.get("meta_adset_name")
        or fields.get("adset_name")
        or fields.get("ad_set_name"),
        "meta_campaign_name": fields.get("meta_campaign_name") or fields.get("campaign_name"),
        "meta_form_name": fields.get("meta_form_name") or fields.get("form_name"),
        "meta_page_name": fields.get("meta_page_name") or fields.get("page_name"),
        "meta_platform": fields.get("meta_platform")
        or fields.get("platform")
        or fields.get("publisher_platform"),
    }


def enqueue_stage_event(
    db: Session,
    surrogate: Surrogate,
    *,
    stage_slug: str,
    stage_label: str | None,
    effective_at: datetime | None = None,
) -> None:
    """Enqueue a Zapier stage event if configured and applicable."""
    if surrogate.source != SurrogateSource.META.value:
        return
    if not surrogate.meta_lead_id:
        return

    settings = zapier_settings_service.get_settings(db, surrogate.organization_id)
    if not settings or not settings.outbound_enabled:
        return
    if not settings.outbound_webhook_url:
        return

    mapping = zapier_settings_service.normalize_event_mapping(settings.outbound_event_mapping)
    event_name = resolve_event_name(mapping, stage_slug)
    if not event_name:
        return

    meta_lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.id == surrogate.meta_lead_id,
            MetaLead.organization_id == surrogate.organization_id,
        )
        .first()
    )
    if not meta_lead or not meta_lead.meta_lead_id:
        return

    event_time = effective_at or _now_utc()
    meta_fields = _extract_meta_fields(meta_lead, surrogate)
    payload = build_stage_event_payload(
        lead_id=meta_lead.meta_lead_id,
        event_name=event_name,
        event_time=event_time,
        stage_slug=stage_slug,
        stage_label=stage_label,
        surrogate_id=str(surrogate.id),
        include_hashed_pii=settings.outbound_send_hashed_pii,
        email=surrogate.email,
        phone=surrogate.phone,
        meta_fields=meta_fields,
    )

    headers: dict[str, str] = {}
    secret = zapier_settings_service.decrypt_webhook_secret(
        settings.outbound_webhook_secret_encrypted
    )
    if secret:
        headers["X-Webhook-Token"] = secret

    job_payload = {
        "url": settings.outbound_webhook_url,
        "headers": headers,
        "data": payload,
        "webhook_id": settings.webhook_id,
    }
    idempotency_key = f"zapier_stage:{meta_lead.meta_lead_id}:{stage_slug}"

    try:
        job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.ZAPIER_STAGE_EVENT,
            payload=job_payload,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        logger.warning("Failed to enqueue Zapier stage event: %s", exc)


def enqueue_test_event(
    db: Session,
    organization_id: UUID,
    *,
    stage_slug: str,
    event_name: str,
    lead_id: str,
    include_hashed_pii: bool,
) -> dict:
    settings = zapier_settings_service.get_settings(db, organization_id)
    if not settings or not settings.outbound_webhook_url:
        raise ValueError("Outbound webhook is not configured")

    event_time = _now_utc()
    event_id = f"zapier_stage_test:{lead_id}:{stage_slug}:{event_time.timestamp()}"
    payload = build_stage_event_payload(
        lead_id=lead_id,
        event_name=event_name,
        event_time=event_time,
        stage_slug=stage_slug,
        stage_label=stage_slug.replace("_", " ").title(),
        surrogate_id=None,
        include_hashed_pii=include_hashed_pii,
        email="zapier-test@example.com" if include_hashed_pii else None,
        phone="+15551234567" if include_hashed_pii else None,
        meta_fields={
            "meta_form_id": "test_form",
            "meta_campaign_id": "test_campaign",
            "meta_ad_id": "test_ad",
            "meta_platform": "facebook",
        },
        event_id=event_id,
        test_mode=True,
    )

    headers: dict[str, str] = {}
    secret = zapier_settings_service.decrypt_webhook_secret(
        settings.outbound_webhook_secret_encrypted
    )
    if secret:
        headers["X-Webhook-Token"] = secret

    job_payload = {
        "url": settings.outbound_webhook_url,
        "headers": headers,
        "data": payload,
        "webhook_id": settings.webhook_id,
    }

    job_service.schedule_job(
        db=db,
        org_id=organization_id,
        job_type=JobType.ZAPIER_STAGE_EVENT,
        payload=job_payload,
        idempotency_key=event_id,
    )

    return {"event_id": event_id, "event_name": event_name}
