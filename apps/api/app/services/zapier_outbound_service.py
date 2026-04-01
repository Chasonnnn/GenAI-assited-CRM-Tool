"""Zapier outbound stage event service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.stage_definitions import LABEL_OVERRIDES
from app.db.enums import JobType, SurrogateSource
from app.db.models import MetaLead, Surrogate
from app.services import (
    job_service,
    meta_capi,
    meta_outbound_service,
    zapier_monitor_service,
    zapier_settings_service,
)
from app.utils.presentation import humanize_identifier

logger = logging.getLogger(__name__)
MAX_META_LEAD_AGE = timedelta(days=90)
FBC_CANDIDATE_KEYS = ("fbc", "meta_fbc", "click_id", "meta_click_id")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_meta_lead_timestamp(meta_lead: MetaLead) -> datetime | None:
    return _coerce_utc(meta_lead.meta_created_time) or _coerce_utc(meta_lead.received_at)


def _is_meta_lead_within_reporting_window(meta_lead: MetaLead, *, event_time: datetime) -> bool:
    lead_timestamp = _resolve_meta_lead_timestamp(meta_lead)
    if lead_timestamp is None:
        return True
    return (event_time - lead_timestamp) <= MAX_META_LEAD_AGE


def resolve_mapping_item(mapping: list[dict], stage_key: str) -> dict | None:
    for item in mapping:
        if item.get("stage_key") == stage_key and item.get("enabled", True):
            return item
    return None


def _normalize_json_key(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _coerce_string_scalar(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, list):
        for item in value:
            coerced = _coerce_string_scalar(item)
            if coerced:
                return coerced
    return None


def _find_json_value_by_key(payload: object, candidate_keys: tuple[str, ...]) -> str | None:
    normalized_keys = {_normalize_json_key(key) for key in candidate_keys}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if _normalize_json_key(str(key)) in normalized_keys:
                coerced = _coerce_string_scalar(value)
                if coerced:
                    return coerced
        for value in payload.values():
            nested = _find_json_value_by_key(value, candidate_keys)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _find_json_value_by_key(item, candidate_keys)
            if nested:
                return nested
    return None


def _normalize_meta_click_id(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized or not normalized.startswith("fb."):
        return None
    return normalized


def _resolve_meta_click_id(meta_lead: MetaLead) -> str | None:
    return _normalize_meta_click_id(
        _find_json_value_by_key(meta_lead.field_data_raw or {}, FBC_CANDIDATE_KEYS)
        or _find_json_value_by_key(meta_lead.field_data or {}, FBC_CANDIDATE_KEYS)
        or _find_json_value_by_key(meta_lead.raw_payload or {}, FBC_CANDIDATE_KEYS)
    )


def _skip_event(
    db: Session,
    *,
    surrogate: Surrogate,
    source: str,
    reason: str,
    stage_key: str,
    stage_slug: str | None,
    stage_label: str | None,
    event_id: str | None = None,
    event_name: str | None = None,
    lead_id: str | None = None,
) -> dict[str, object]:
    zapier_monitor_service.record_skipped_event(
        db=db,
        org_id=surrogate.organization_id,
        source=source,
        reason=reason,
        event_id=event_id,
        event_name=event_name,
        lead_id=lead_id,
        stage_key=stage_key,
        stage_slug=stage_slug,
        stage_label=stage_label,
        surrogate_id=surrogate.id,
    )
    return {
        "queued": False,
        "reason": reason,
        "event_name": event_name,
        "event_id": event_id,
        "lead_id": lead_id,
    }


def build_stage_event_payload(
    *,
    lead_id: str,
    event_name: str,
    event_time: datetime,
    stage_key: str,
    stage_slug: str | None,
    stage_id: str | None,
    stage_label: str | None,
    surrogate_id: str | None,
    include_hashed_pii: bool,
    email: str | None,
    phone: str | None,
    meta_fields: dict | None = None,
    fbc: str | None = None,
    event_id: str | None = None,
    test_mode: bool = False,
) -> dict:
    payload = {
        "event_id": event_id or f"zapier_stage:{lead_id}:{stage_key}",
        "event_name": event_name,
        "lifecycle_stage_name": event_name,
        "stage_in_sales_process": event_name,
        "event_time": event_time.astimezone(timezone.utc).isoformat(),
        "lead_id": lead_id,
        "facebook_lead_id": lead_id,
        "stage_key": stage_key,
        "stage_slug": stage_slug,
        "stage_id": stage_id,
        "stage_label": stage_label,
    }

    if surrogate_id:
        payload["surrogate_id"] = surrogate_id

    if meta_fields:
        payload.update({k: v for k, v in meta_fields.items() if v is not None})

    normalized_fbc = _normalize_meta_click_id(fbc)
    if normalized_fbc:
        payload["fbc"] = normalized_fbc
        payload["facebook_click_id"] = normalized_fbc

    if include_hashed_pii:
        user_data: dict[str, str] = {}
        if email:
            payload["customer_email"] = email
            user_data["email_hash"] = meta_capi.hash_for_capi(email)
        if phone:
            payload["customer_phone_number"] = phone
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
    stage_key: str,
    stage_slug: str | None,
    stage_id: str | None = None,
    stage_label: str | None,
    effective_at: datetime | None = None,
    source: str = "automatic",
) -> dict[str, object]:
    """Enqueue a Zapier stage event if configured and applicable."""
    if surrogate.source != SurrogateSource.META.value:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="not_meta_source",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )
    if not surrogate.meta_lead_id:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_meta_lead_fk",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )

    settings = zapier_settings_service.get_settings(db, surrogate.organization_id)
    if not settings or not settings.outbound_enabled:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="outbound_disabled",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )
    if not settings.outbound_webhook_url:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_webhook_url",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )

    mapping = zapier_settings_service.normalize_event_mapping(
        settings.outbound_event_mapping,
        db=db,
        organization_id=surrogate.organization_id,
    )
    mapping_item = resolve_mapping_item(mapping, stage_key)
    if not mapping_item:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="unmapped_stage",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )
    event_name = str(mapping_item.get("event_name") or "").strip()
    if not event_name:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="unmapped_stage",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )

    meta_lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.id == surrogate.meta_lead_id,
            MetaLead.organization_id == surrogate.organization_id,
        )
        .first()
    )
    if not meta_lead:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_meta_lead",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_name=event_name,
        )
    if not meta_lead.meta_lead_id:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_meta_lead_id",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_name=event_name,
        )

    event_time = effective_at or _now_utc()
    if not _is_meta_lead_within_reporting_window(meta_lead, event_time=event_time):
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="stale_meta_lead",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
        )
    meta_fields = _extract_meta_fields(meta_lead, surrogate)
    event_id = meta_outbound_service.build_stage_event_key(
        "zapier_stage",
        meta_lead.meta_lead_id,
        stage_key,
        mapping,
    )
    payload = build_stage_event_payload(
        lead_id=meta_lead.meta_lead_id,
        event_name=event_name,
        event_time=event_time,
        stage_key=stage_key,
        stage_slug=stage_slug,
        stage_id=stage_id,
        stage_label=stage_label,
        surrogate_id=str(surrogate.id),
        include_hashed_pii=settings.outbound_send_hashed_pii,
        email=surrogate.email,
        phone=surrogate.phone,
        meta_fields=meta_fields,
        fbc=_resolve_meta_click_id(meta_lead),
        event_id=event_id,
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
    idempotency_key = event_id

    existing_job = job_service.get_job_by_idempotency_key(
        db,
        org_id=surrogate.organization_id,
        idempotency_key=idempotency_key,
    )
    if existing_job:
        return _skip_event(
            surrogate=surrogate,
            source=source,
            reason="duplicate",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_id=event_id,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
        ) | {"idempotency_key": idempotency_key}

    try:
        job = job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.ZAPIER_STAGE_EVENT,
            payload=job_payload,
            idempotency_key=idempotency_key,
        )
        zapier_monitor_service.record_queued_event(
            db=db,
            org_id=surrogate.organization_id,
            job_id=job.id,
            source=source,
            event_id=event_id,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            surrogate_id=surrogate.id,
        )
        return {
            "queued": True,
            "reason": None,
            "event_name": event_name,
            "event_id": event_id,
            "lead_id": meta_lead.meta_lead_id,
            "idempotency_key": idempotency_key,
        }
    except IntegrityError:
        db.rollback()
        logger.info("Skipping duplicate Zapier stage event for key=%s", idempotency_key)
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="duplicate",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_id=event_id,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
        ) | {"idempotency_key": idempotency_key}
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to enqueue Zapier stage event: %s", exc)
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="enqueue_failed",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_id=event_id,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
        ) | {"idempotency_key": idempotency_key}


def enqueue_test_event(
    db: Session,
    organization_id: UUID,
    *,
    stage_key: str,
    event_name: str,
    lead_id: str,
    include_hashed_pii: bool,
) -> dict:
    settings = zapier_settings_service.get_settings(db, organization_id)
    if not settings or not settings.outbound_webhook_url:
        raise ValueError("Outbound webhook is not configured")

    event_time = _now_utc()
    event_id = f"zapier_stage_test:{lead_id}:{stage_key}:{event_time.timestamp()}"
    payload = build_stage_event_payload(
        lead_id=lead_id,
        event_name=event_name,
        event_time=event_time,
        stage_key=stage_key,
        stage_slug=stage_key,
        stage_id=None,
        stage_label=LABEL_OVERRIDES.get(stage_key, humanize_identifier(stage_key)),
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
        fbc="fb.1.1772952996.test-click-id",
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

    job = job_service.schedule_job(
        db=db,
        org_id=organization_id,
        job_type=JobType.ZAPIER_STAGE_EVENT,
        payload=job_payload,
        idempotency_key=event_id,
    )
    zapier_monitor_service.record_queued_event(
        org_id=organization_id,
        job_id=job.id,
        source="test",
        event_id=event_id,
        event_name=event_name,
        lead_id=lead_id,
        stage_key=stage_key,
        stage_slug=stage_key,
        stage_label=LABEL_OVERRIDES.get(stage_key, humanize_identifier(stage_key)),
        surrogate_id=None,
    )

    return {"event_id": event_id, "event_name": event_name, "lead_id": lead_id}
