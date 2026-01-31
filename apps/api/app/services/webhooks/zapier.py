"""Zapier webhook handler for inbound leads."""

from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.db.models import MetaLead, Organization
from app.services import meta_api, meta_lead_service, meta_form_mapping_service
from app.services import zapier_settings_service
from app.utils.datetime_parsing import parse_datetime_with_timezone

logger = logging.getLogger(__name__)


MAX_PAYLOAD_BYTES = 5 * 1024 * 1024

_FIELD_DATA_KEYS = ("field_data", "fieldData")
_FIELDS_KEYS = ("fields", "fieldDataRaw", "field_data_raw")

_META_ID_KEYS = {
    "lead_id": ("lead_id", "leadgen_id", "meta_lead_id"),
    "ad_id": ("ad_id", "meta_ad_id"),
    "adset_id": ("adset_id", "adgroup_id", "ad_set_id"),
    "campaign_id": ("campaign_id", "meta_campaign_id"),
    "form_id": ("form_id", "meta_form_id"),
    "page_id": ("page_id", "meta_page_id"),
    "platform": ("platform", "publisher_platform", "meta_platform"),
}

_META_NAME_KEYS = {
    "ad_name": ("ad_name", "adgroup_name"),
    "adset_name": ("adset_name", "ad_group_name"),
    "campaign_name": ("campaign_name",),
    "form_name": ("form_name",),
    "page_name": ("page_name",),
}


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _coerce_form_value(value: Any) -> Any:
    if hasattr(value, "filename"):
        return value.filename
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _form_to_payload(form_data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if hasattr(form_data, "multi_items"):
        for key, value in form_data.multi_items():
            value = _coerce_form_value(value)
            if key in payload:
                existing = payload[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    payload[key] = [existing, value]
            else:
                payload[key] = value
        return payload
    for key in form_data:
        payload[key] = _coerce_form_value(form_data[key])
    return payload


def _unwrap_payload(value: Any) -> Any:
    if isinstance(value, dict):
        if isinstance(value.get("data"), dict):
            return value["data"]
        if isinstance(value.get("lead"), dict):
            return value["lead"]
    return value


def _normalize_payload(value: Any) -> dict[str, Any]:
    unwrapped = _unwrap_payload(value)
    if isinstance(unwrapped, dict):
        return unwrapped
    return {"payload": unwrapped}


def _get_any(payload: dict[str, Any], raw_fields: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
        if key in raw_fields:
            return raw_fields.get(key)
    return None


def _build_field_data_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _FIELD_DATA_KEYS:
        field_data = payload.get(key)
        if isinstance(field_data, list):
            return field_data

    for key in _FIELDS_KEYS:
        fields = payload.get(key)
        if isinstance(fields, dict):
            return [
                {"name": k, "values": [v] if not isinstance(v, list) else v}
                for k, v in fields.items()
            ]

    # Fallback: treat payload as flat fields (exclude meta keys)
    candidates = {}
    for key, value in payload.items():
        if key in _FIELD_DATA_KEYS or key in _FIELDS_KEYS:
            continue
        if key in _META_ID_KEYS or key in _META_NAME_KEYS:
            continue
        candidates[key] = value
    return [
        {"name": k, "values": [v] if not isinstance(v, list) else v} for k, v in candidates.items()
    ]


def _extract_tracking_fields(payload: dict[str, Any], raw_fields: dict[str, Any]) -> dict[str, Any]:
    tracking: dict[str, Any] = {}

    for key, candidates in _META_ID_KEYS.items():
        value = _get_any(payload, raw_fields, candidates)
        if value:
            tracking[key] = value

    for key, candidates in _META_NAME_KEYS.items():
        value = _get_any(payload, raw_fields, candidates)
        if value:
            tracking[key] = value

    return tracking


def _parse_created_time(payload: dict[str, Any]) -> datetime | None:
    value = (
        payload.get("created_time") or payload.get("submitted_at") or payload.get("submission_time")
    )
    if not value:
        return None
    parsed = meta_api.parse_meta_timestamp(str(value))
    if parsed:
        return parsed
    return None


def _ensure_form_identifier(payload: Any, webhook_id: str) -> Any:
    """
    Ensure Zapier payloads include a stable form_id so mapping can be configured.
    """
    if isinstance(payload, list):
        return [_ensure_form_identifier(item, webhook_id) for item in payload]
    if not isinstance(payload, dict):
        return payload

    if payload.get("form_id") or payload.get("formId") or payload.get("meta_form_id"):
        return payload

    form_id = f"zapier-{webhook_id}"
    payload["form_id"] = form_id
    if not payload.get("form_name"):
        payload["form_name"] = f"Zapier Lead Intake ({webhook_id[:8]})"
    return payload


def _build_status_message(status: str, duplicate: bool, surrogate_id: str | None) -> str:
    if duplicate:
        return "Duplicate lead received; existing record retained."
    if status == "converted" and surrogate_id:
        return "Webhook received. Lead converted into a surrogate."
    if status == "awaiting_mapping":
        return "Webhook received. Lead stored; mapping is required before conversion."
    if status == "stored":
        return "Webhook received. Lead stored successfully."
    if status == "convert_failed":
        return "Webhook received. Lead stored but conversion failed; check mappings."
    return f"Webhook received with status: {status}."


def build_test_payload(form_id: str | None, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a test payload that exercises the Meta lead mapping pipeline."""
    created_time = datetime.now(timezone.utc).isoformat()
    base_fields: dict[str, Any] = {
        "full_name": "Zapier Test Lead",
        "email": "zapier-test@example.com",
        "phone_number": "+15551234567",
        "state": "CA",
        "created_time": created_time,
    }
    if fields:
        base_fields.update({k: v for k, v in fields.items() if v is not None})

    field_data = []
    for key, value in base_fields.items():
        values = value if isinstance(value, list) else [value]
        field_data.append({"name": key, "values": values})

    payload: dict[str, Any] = {
        "lead_id": f"zapier-test-{uuid.uuid4()}",
        "created_time": created_time,
        "form_name": "Zapier Test Lead",
        "field_data": field_data,
    }
    if form_id:
        payload["form_id"] = form_id

    return payload


def process_zapier_payload(
    db: Session,
    org_id: Any,
    payload: dict[str, Any],
    *,
    raw_payload: dict | list | None = None,
    test_mode: bool = False,
) -> dict[str, Any]:
    field_data_list = _build_field_data_list(payload)
    field_keys = [
        str(item.get("name"))
        for item in field_data_list
        if isinstance(item, dict) and item.get("name")
    ]
    if (
        payload.get("created_time") or payload.get("submitted_at") or payload.get("submission_time")
    ) and "created_time" not in field_keys:
        field_keys.append("created_time")
    field_data = meta_api.normalize_field_data(field_data_list)
    field_data_raw = meta_api.extract_field_data_raw(field_data_list)

    tracking = _extract_tracking_fields(payload, field_data_raw)

    lead_id = (
        tracking.get("lead_id")
        or payload.get("lead_id")
        or payload.get("leadgen_id")
        or payload.get("meta_lead_id")
    )
    duplicate = False
    existing = None
    if lead_id:
        existing = (
            db.query(MetaLead)
            .filter(
                MetaLead.organization_id == org_id,
                MetaLead.meta_lead_id == str(lead_id),
            )
            .first()
        )
        if existing:
            duplicate = True

    if lead_id:
        field_data_raw.setdefault("zapier_lead_id", str(lead_id))

    # Add tracking fields (meta_* keys for mapping rules)
    if tracking.get("ad_id"):
        field_data["meta_ad_id"] = tracking["ad_id"]
        field_data_raw["meta_ad_id"] = tracking["ad_id"]
    if tracking.get("ad_name"):
        field_data_raw["meta_ad_name"] = tracking["ad_name"]
    if tracking.get("adset_id"):
        field_data_raw["meta_adset_id"] = tracking["adset_id"]
    if tracking.get("adset_name"):
        field_data_raw["meta_adset_name"] = tracking["adset_name"]
    if tracking.get("campaign_id"):
        field_data_raw["meta_campaign_id"] = tracking["campaign_id"]
    if tracking.get("campaign_name"):
        field_data_raw["meta_campaign_name"] = tracking["campaign_name"]
    if tracking.get("form_name"):
        field_data_raw["meta_form_name"] = tracking["form_name"]
    if tracking.get("platform"):
        field_data_raw["meta_platform"] = tracking["platform"]

    if test_mode:
        field_data_raw["zapier_test"] = True

    meta_created_time = _parse_created_time(payload)
    if not meta_created_time:
        org = db.get(Organization, org_id)
        org_timezone = org.timezone if org else None
        parsed = parse_datetime_with_timezone(
            str(payload.get("created_time") or payload.get("submitted_at") or ""),
            org_timezone,
        )
        meta_created_time = parsed.value

    meta_form_id = (
        str(tracking.get("form_id")) if tracking.get("form_id") else payload.get("form_id")
    )
    meta_page_id = (
        str(tracking.get("page_id")) if tracking.get("page_id") else payload.get("page_id")
    )
    meta_form_name = tracking.get("form_name") or payload.get("form_name")
    if meta_form_id:
        meta_form_mapping_service.upsert_form_from_payload(
            db,
            org_id,
            form_external_id=str(meta_form_id),
            form_name=str(meta_form_name) if meta_form_name else None,
            field_keys=field_keys,
            page_id=str(meta_page_id) if meta_page_id else None,
        )

    meta_lead, error = meta_lead_service.store_meta_lead(
        db=db,
        org_id=org_id,
        meta_lead_id=str(lead_id or f"zapier-{uuid.uuid4()}"),
        field_data=field_data,
        field_data_raw=field_data_raw,
        raw_payload=raw_payload if raw_payload is not None else payload,
        meta_form_id=str(meta_form_id) if meta_form_id else None,
        meta_page_id=str(meta_page_id) if meta_page_id else None,
        meta_created_time=meta_created_time,
    )
    if error:
        raise HTTPException(status_code=500, detail=error)

    status, surrogate = meta_lead_service.process_stored_meta_lead(db, meta_lead)

    surrogate_id = str(surrogate.id) if surrogate else None
    message = _build_status_message(status, duplicate, surrogate_id)

    return {
        "status": status,
        "duplicate": duplicate,
        "meta_lead_id": str(meta_lead.id),
        "surrogate_id": surrogate_id,
        "message": message,
    }


class ZapierWebhookHandler:
    async def handle(self, request: Request, db: Session, **kwargs) -> dict:
        webhook_id = kwargs.get("webhook_id")
        if not webhook_id:
            raise HTTPException(status_code=400, detail="Missing webhook_id")

        settings = zapier_settings_service.get_settings_by_webhook_id(db, webhook_id)
        if not settings or not settings.is_active:
            raise HTTPException(status_code=404, detail="Webhook not found")

        token = request.headers.get("X-Webhook-Token") or request.query_params.get("token")
        if not token:
            raise HTTPException(status_code=401, detail="Missing webhook token")

        secret = zapier_settings_service.decrypt_webhook_secret(settings.webhook_secret_encrypted)
        if not secret or not hmac.compare_digest(token, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook token")

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                payload_size = int(content_length)
            except ValueError:
                payload_size = None
            if payload_size and payload_size > MAX_PAYLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Payload too large (max 5MB).")

        content_type = (request.headers.get("content-type") or "").lower()
        try:
            if (
                "application/json" in content_type
                or content_type.endswith("+json")
                or "text/json" in content_type
            ):
                payload = await request.json()
            elif (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                form_data = await request.form()
                payload = _form_to_payload(form_data)
            else:
                try:
                    payload = await request.json()
                except Exception:
                    form_data = await request.form()
                    payload = _form_to_payload(form_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            payload = payload["data"]
        elif isinstance(payload, dict) and isinstance(payload.get("lead"), list):
            payload = payload["lead"]

        payload = _ensure_form_identifier(payload, webhook_id)

        if isinstance(payload, list):
            if not payload:
                return {"status": "ignored", "processed": 0}
            results = []
            for item in payload:
                normalized = _normalize_payload(item)
                results.append(
                    process_zapier_payload(
                        db,
                        settings.organization_id,
                        normalized,
                        raw_payload=item if isinstance(item, (dict, list)) else payload,
                    )
                )
            if len(results) == 1:
                result = results[0]
            else:
                result = {"status": "ok", "processed": len(results), "results": results}
        else:
            normalized = _normalize_payload(payload)
            result = process_zapier_payload(
                db,
                settings.organization_id,
                normalized,
                raw_payload=payload if isinstance(payload, (dict, list)) else None,
            )

        logger.info("Zapier lead ingested for org=%s", settings.organization_id)

        return result
