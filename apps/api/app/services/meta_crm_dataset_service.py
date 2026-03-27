"""Direct Meta CRM dataset outbound delivery service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.stage_definitions import LABEL_OVERRIDES
from app.db.enums import JobType, SurrogateSource
from app.db.models import MetaLead, Surrogate
from app.services import (
    job_service,
    meta_capi,
    meta_crm_dataset_monitor_service,
    meta_crm_dataset_settings_service,
    zapier_settings_service,
)
from app.utils.presentation import humanize_identifier

logger = logging.getLogger(__name__)

META_GRAPH_BASE_URL = "https://graph.facebook.com"
HTTPX_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
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


def _resolve_dedupe_key(stage_key: str, mapping: list[dict]) -> str:
    bucket = zapier_settings_service.resolve_meta_stage_bucket(stage_key, mapping)
    return bucket or stage_key


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
    meta_crm_dataset_monitor_service.record_skipped_event(
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
    crm_name: str,
    include_hashed_pii: bool,
    email: str | None,
    phone: str | None,
    fbc: str | None = None,
    event_id: str | None = None,
    test_event_code: str | None = None,
) -> dict:
    user_data: dict[str, object] = {"lead_id": lead_id}
    normalized_fbc = _normalize_meta_click_id(fbc)
    if normalized_fbc:
        user_data["fbc"] = normalized_fbc
    if include_hashed_pii:
        if email and "@" in email and "placeholder" not in email:
            user_data["em"] = [meta_capi.hash_for_capi(email)]
        if phone:
            phone_digits = "".join(ch for ch in phone if ch.isdigit())
            if len(phone_digits) >= 10:
                user_data["ph"] = [meta_capi.hash_for_capi(phone_digits)]

    event_payload = {
        "event_name": event_name,
        "event_time": int(event_time.astimezone(timezone.utc).timestamp()),
        "action_source": "system_generated",
        "custom_data": {
            "event_source": "crm",
            "lead_event_source": crm_name,
        },
        "user_data": user_data,
    }
    if event_id:
        event_payload["event_id"] = event_id

    payload = {"data": [event_payload]}
    if test_event_code:
        payload["test_event_code"] = test_event_code
    return payload


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
    del stage_id  # Direct Meta dataset payload uses event name + lead id, not stage ids.

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

    settings_row = meta_crm_dataset_settings_service.get_settings(db, surrogate.organization_id)
    if not settings_row or not settings_row.enabled:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="disabled",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )
    if not settings_row.dataset_id:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_dataset_id",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )
    if not settings_row.access_token_encrypted:
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="missing_access_token",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
        )

    mapping = zapier_settings_service.normalize_event_mapping(
        settings_row.event_mapping,
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

    dedupe_key = _resolve_dedupe_key(stage_key, mapping)
    event_id = f"meta_crm_dataset:{meta_lead.meta_lead_id}:{dedupe_key}"
    body = build_stage_event_payload(
        lead_id=meta_lead.meta_lead_id,
        event_name=event_name,
        event_time=event_time,
        crm_name=settings_row.crm_name or meta_crm_dataset_settings_service.DEFAULT_CRM_NAME,
        include_hashed_pii=settings_row.send_hashed_pii,
        email=surrogate.email,
        phone=surrogate.phone,
        fbc=_resolve_meta_click_id(meta_lead),
        event_id=event_id,
    )
    job_payload = {
        "settings_id": str(settings_row.id),
        "dataset_id": settings_row.dataset_id,
        "body": body,
    }
    idempotency_key = event_id

    existing_job = job_service.get_job_by_idempotency_key(
        db, org_id=surrogate.organization_id, idempotency_key=idempotency_key
    )
    if existing_job:
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

    try:
        job = job_service.schedule_job(
            db=db,
            org_id=surrogate.organization_id,
            job_type=JobType.META_CRM_DATASET_EVENT,
            payload=job_payload,
            idempotency_key=idempotency_key,
        )
        meta_crm_dataset_monitor_service.record_queued_event(
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
        logger.info("Skipping duplicate Meta CRM dataset event for key=%s", idempotency_key)
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
        logger.warning("Failed to enqueue Meta CRM dataset event: %s", exc)
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
    test_event_code: str | None,
    include_hashed_pii: bool,
    fbc: str | None = None,
) -> dict[str, str]:
    settings_row = meta_crm_dataset_settings_service.get_settings(db, organization_id)
    if not settings_row or not settings_row.dataset_id:
        raise ValueError("Meta CRM dataset is not configured")
    if not settings_row.access_token_encrypted:
        raise ValueError("Meta CRM dataset access token is not configured")

    event_time = _now_utc()
    event_id = f"meta_crm_dataset_test:{lead_id}:{stage_key}:{event_time.timestamp()}"
    body = build_stage_event_payload(
        lead_id=lead_id,
        event_name=event_name,
        event_time=event_time,
        crm_name=settings_row.crm_name or meta_crm_dataset_settings_service.DEFAULT_CRM_NAME,
        include_hashed_pii=include_hashed_pii,
        email="meta-crm-test@example.com" if include_hashed_pii else None,
        phone="+15551234567" if include_hashed_pii else None,
        fbc=fbc,
        event_id=event_id,
        test_event_code=test_event_code or settings_row.test_event_code,
    )
    job = job_service.schedule_job(
        db=db,
        org_id=organization_id,
        job_type=JobType.META_CRM_DATASET_EVENT,
        payload={
            "settings_id": str(settings_row.id),
            "dataset_id": settings_row.dataset_id,
            "body": body,
        },
        idempotency_key=event_id,
    )
    meta_crm_dataset_monitor_service.record_queued_event(
        db=db,
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


async def process_job(db: Session, job) -> None:
    payload = job.payload or {}
    dataset_id = str(payload.get("dataset_id") or "").strip()
    body = payload.get("body")
    settings_id = payload.get("settings_id")
    if not dataset_id or not isinstance(body, dict):
        raise Exception("Missing dataset_id or body in job payload")

    settings_row = None
    if settings_id:
        settings_row = meta_crm_dataset_settings_service.get_settings_by_id(db, settings_id)
    if settings_row is None and job.organization_id:
        settings_row = meta_crm_dataset_settings_service.get_settings(db, job.organization_id)
    if settings_row is None:
        raise Exception("Meta CRM dataset settings not found")

    access_token = meta_crm_dataset_settings_service.decrypt_access_token(
        settings_row.access_token_encrypted
    )
    if not access_token:
        raise Exception("Meta CRM dataset access token is not configured")

    url = (
        f"{META_GRAPH_BASE_URL}/{settings.META_API_VERSION}/{dataset_id}/events"
        f"?access_token={quote(access_token, safe='')}"
    )
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        response = await client.post(url, json=body)
    if response.status_code != 200:
        raise Exception(f"Meta CRM dataset error {response.status_code}: {response.text[:500]}")
