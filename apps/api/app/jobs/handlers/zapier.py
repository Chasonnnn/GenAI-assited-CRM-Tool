"""Zapier outbound job handlers."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.core.url_validation import validate_outbound_webhook_url
from app.db.models import (
    Donor,
    DonorStatusHistory,
    FormSubmission,
    IntakeLead,
    MetaLead,
    Pipeline,
    PipelineStage,
    ZapierOutboundEvent,
)
from app.jobs.utils import safe_url
from app.services import zapier_monitor_service, zapier_settings_service

logger = logging.getLogger(__name__)

DONOR_PAYLOAD_KEYS = frozenset(
    {
        "event_id",
        "event_name",
        "lifecycle_stage_name",
        "stage_in_sales_process",
        "event_time",
        "attribution_source",
        "lead_id",
        "facebook_lead_id",
        "meta_lead_id",
        "first_party_submission_id",
        "meta_form_id",
        "meta_page_id",
        "meta_ad_id",
        "meta_adset_id",
        "meta_campaign_id",
        "ad_id",
        "adset_id",
        "campaign_id",
        "fbclid",
        "fbc",
        "fbp",
        "user_data",
    }
)
DONOR_USER_DATA_KEYS = frozenset({"email_hash", "phone_hash"})


def _skip_donor_delivery(db, job, reason: str) -> None:
    zapier_monitor_service.mark_job_skipped(db=db, job_id=job.id, reason=reason)


async def _process_donor_stage_event(db, job, payload: dict) -> None:
    try:
        event_record_id = UUID(str(payload.get("event_record_id") or ""))
    except ValueError as exc:
        raise RuntimeError("Invalid donor Zapier event reference") from exc
    if job.organization_id is None:
        raise RuntimeError("Donor Zapier event is missing organization scope")

    event = (
        db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.id == event_record_id,
            ZapierOutboundEvent.organization_id == job.organization_id,
            ZapierOutboundEvent.job_id == job.id,
        )
        .first()
    )
    if event is None:
        raise RuntimeError("Donor Zapier event is unavailable")

    settings = zapier_settings_service.get_settings(db, job.organization_id)
    if settings is None or not settings.donor_outbound_enabled:
        _skip_donor_delivery(db, job, "donor_dispatch_disabled")
        return
    if not settings.outbound_webhook_url:
        _skip_donor_delivery(db, job, "donor_dispatch_url_missing")
        return
    if (
        not event.donor_type
        or event.donor_id is None
        or event.donor_status_history_id is None
        or event.pipeline_id is None
        or event.stage_id is None
    ):
        _skip_donor_delivery(db, job, "donor_event_invalid")
        return

    history_id = (
        db.query(DonorStatusHistory.id)
        .join(Donor, Donor.id == DonorStatusHistory.donor_id)
        .filter(
            Donor.id == event.donor_id,
            Donor.organization_id == job.organization_id,
            DonorStatusHistory.id == event.donor_status_history_id,
            DonorStatusHistory.organization_id == job.organization_id,
            DonorStatusHistory.new_stage_id == event.stage_id,
        )
        .scalar()
    )
    if history_id is None:
        _skip_donor_delivery(db, job, "donor_subject_missing")
        return

    if event.attribution_source == "meta":
        meta_lead_id = (
            db.query(MetaLead.id)
            .filter(
                MetaLead.organization_id == job.organization_id,
                MetaLead.converted_donor_id == event.donor_id,
                MetaLead.meta_lead_id == event.lead_id,
            )
            .scalar()
        )
        if meta_lead_id is None:
            _skip_donor_delivery(db, job, "donor_attribution_missing")
            return
    elif event.attribution_source == "website":
        if event.first_party_submission_id is None:
            _skip_donor_delivery(db, job, "donor_attribution_missing")
            return
        submission_donor_id = (
            db.query(FormSubmission.donor_id)
            .filter(
                FormSubmission.id == event.first_party_submission_id,
                FormSubmission.organization_id == job.organization_id,
            )
            .scalar()
        )
        promoted_lead_id = (
            db.query(IntakeLead.id)
            .filter(
                IntakeLead.organization_id == job.organization_id,
                IntakeLead.form_submission_id == event.first_party_submission_id,
                IntakeLead.promoted_donor_id == event.donor_id,
            )
            .scalar()
        )
        if submission_donor_id != event.donor_id and promoted_lead_id is None:
            _skip_donor_delivery(db, job, "donor_attribution_missing")
            return
    else:
        _skip_donor_delivery(db, job, "donor_attribution_missing")
        return

    active_stage = (
        db.query(PipelineStage)
        .join(Pipeline, Pipeline.id == PipelineStage.pipeline_id)
        .filter(
            Pipeline.organization_id == job.organization_id,
            Pipeline.id == event.pipeline_id,
            Pipeline.entity_type == f"{event.donor_type}_donor",
            PipelineStage.id == event.stage_id,
            PipelineStage.is_active.is_(True),
        )
        .first()
    )
    if active_stage is None:
        _skip_donor_delivery(db, job, "donor_stage_inactive")
        return

    mapping_item = zapier_settings_service.resolve_donor_mapping_item(
        settings.donor_outbound_event_mapping,
        donor_type=event.donor_type,
        pipeline_id=event.pipeline_id,
        stage_id=event.stage_id,
    )
    if mapping_item is None:
        _skip_donor_delivery(db, job, "donor_mapping_changed")
        return

    current_fingerprint = zapier_settings_service.donor_config_fingerprint(
        webhook_url=settings.outbound_webhook_url,
        donor_type=event.donor_type,
        pipeline_id=event.pipeline_id,
        stage_id=event.stage_id,
        event_name=str(mapping_item["event_name"]),
    )
    queued_fingerprint = str(payload.get("config_fingerprint") or "")
    if (
        not event.config_fingerprint
        or queued_fingerprint != event.config_fingerprint
        or current_fingerprint != event.config_fingerprint
    ):
        _skip_donor_delivery(db, job, "donor_config_changed")
        return

    webhook_data = payload.get("data")
    if not isinstance(webhook_data, dict):
        raise RuntimeError("Donor Zapier event payload is invalid")
    webhook_data = {key: value for key, value in webhook_data.items() if key in DONOR_PAYLOAD_KEYS}
    user_data = webhook_data.get("user_data")
    if isinstance(user_data, dict):
        webhook_data["user_data"] = {
            key: value for key, value in user_data.items() if key in DONOR_USER_DATA_KEYS
        }
        if not webhook_data["user_data"]:
            webhook_data.pop("user_data")
    else:
        webhook_data.pop("user_data", None)
    if not settings.outbound_send_hashed_pii:
        webhook_data.pop("user_data", None)
    if webhook_data.get("attribution_source") == "website" and not (
        webhook_data.get("fbc") or webhook_data.get("fbp") or webhook_data.get("user_data")
    ):
        _skip_donor_delivery(db, job, "missing_matching_data")
        return

    webhook_url = validate_outbound_webhook_url(settings.outbound_webhook_url)
    headers: dict[str, str] = {}
    secret = zapier_settings_service.decrypt_webhook_secret(
        settings.outbound_webhook_secret_encrypted
    )
    if secret:
        headers["X-Webhook-Token"] = secret

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=webhook_data, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Zapier webhook returned HTTP {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Zapier webhook request failed") from exc
    logger.info("Donor Zapier stage event delivered for job %s", job.id)


async def process_zapier_stage_event(db, job) -> None:
    """Send a Zapier stage event via webhook."""
    logger.info("Processing Zapier stage event job %s", job.id)
    payload = job.payload or {}

    if payload.get("delivery_kind") == "donor_stage":
        await _process_donor_stage_event(db, job, payload)
        return

    webhook_url = payload.get("url")
    webhook_data = payload.get("data")
    webhook_headers = payload.get("headers", {})

    if not webhook_url or not webhook_data:
        logger.warning("Invalid Zapier stage event payload: missing url or data")
        return

    try:
        webhook_url = validate_outbound_webhook_url(str(webhook_url))
    except ValueError as exc:
        logger.warning(
            "Blocked unsafe Zapier outbound webhook URL: %s (%s)",
            safe_url(str(webhook_url)),
            str(exc),
        )
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(webhook_url, json=webhook_data, headers=webhook_headers)
        response.raise_for_status()
        logger.info("Zapier stage event delivered: %s", safe_url(webhook_url))
