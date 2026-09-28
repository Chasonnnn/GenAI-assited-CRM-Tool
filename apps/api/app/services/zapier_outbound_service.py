"""Zapier outbound stage event service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.stage_definitions import LABEL_OVERRIDES
from app.db.enums import JobStatus, JobType, SurrogateSource
from app.db.models import (
    Donor,
    DonorStatusHistory,
    FormSubmission,
    IntakeLead,
    Job,
    LeadAttribution,
    MetaLead,
    PipelineStage,
    Surrogate,
    ZapierOutboundEvent,
)
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
# Meta leads without an email get this generated address; it must never reach Meta.
PLACEHOLDER_EMAIL_SUFFIX = "@placeholder.invalid"
# Surrogate and donor events share one webhook URL; record_type lets one Zap branch.
SURROGATE_RECORD_TYPE = "surrogate"
SYNTHETIC_META_LEAD_ID_PREFIX = "zapier-"
# A donor event in these states was sent or will be; later occurrences are duplicates.
DONOR_REPORTED_EVENT_STATUSES = ("queued", "delivered", "failed")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _resolve_meta_lead_timestamp(meta_lead: MetaLead) -> datetime | None:
    return _coerce_utc(meta_lead.meta_created_time) or _coerce_utc(meta_lead.received_at)


def _is_meta_lead_within_reporting_window(meta_lead: MetaLead, *, event_time: datetime) -> bool:
    lead_timestamp = _resolve_meta_lead_timestamp(meta_lead)
    if lead_timestamp is None:
        return True
    return (event_time - lead_timestamp) <= MAX_META_LEAD_AGE


def _is_synthetic_meta_lead_id(value: str | None) -> bool:
    """True for the 'zapier-<uuid>' id stored when an inbound Zapier lead had no Meta lead id.

    Same rule as meta_lead_service.is_synthetic_meta_lead_id, kept private here so outbound
    does not depend on the inbound change landing first. Remove when the two are unified.
    """
    if not value or not value.startswith(SYNTHETIC_META_LEAD_ID_PREFIX):
        return False
    try:
        UUID(value.removeprefix(SYNTHETIC_META_LEAD_ID_PREFIX))
    except ValueError:
        return False
    return True


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


def _matchable_email(email: str | None) -> str | None:
    normalized = (email or "").strip()
    if "@" not in normalized or normalized.lower().endswith(PLACEHOLDER_EMAIL_SUFFIX):
        return None
    return normalized


def _customer_match_fields(email: str | None, phone: str | None) -> dict[str, object]:
    """Raw contact fields plus Meta-normalized hashes, shared by surrogate and donor payloads."""
    fields: dict[str, object] = {}
    user_data: dict[str, str] = {}
    matchable_email = _matchable_email(email)
    if matchable_email:
        fields["customer_email"] = matchable_email
        user_data["email_hash"] = meta_capi.hash_for_capi(matchable_email)
    if phone:
        fields["customer_phone_number"] = phone
        normalized_phone = meta_capi.normalize_phone_for_capi(phone)
        if normalized_phone:
            user_data["phone_hash"] = meta_capi.hash_for_capi(normalized_phone)
    if user_data:
        fields["user_data"] = user_data
    return fields


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
        "event_time": event_time.astimezone(UTC).isoformat(),
        "record_type": SURROGATE_RECORD_TYPE,
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
        payload.update(_customer_match_fields(email, phone))

    if test_mode:
        payload["test_mode"] = True

    return payload


def _extract_meta_fields(
    meta_lead: MetaLead,
    surrogate: Surrogate | None = None,
) -> dict[str, str | None]:
    """Meta lead tracking fields; surrogates prefer their tracked columns, donors have none."""
    fields = meta_lead.field_data_raw or meta_lead.field_data or {}
    return {
        "meta_lead_id": meta_lead.meta_lead_id,
        "meta_form_id": (surrogate.meta_form_id if surrogate else None) or meta_lead.meta_form_id,
        "meta_page_id": meta_lead.meta_page_id,
        "meta_ad_id": (surrogate.meta_ad_external_id if surrogate else None)
        or fields.get("meta_ad_id")
        or fields.get("ad_id"),
        "meta_adset_id": (surrogate.meta_adset_external_id if surrogate else None)
        or fields.get("meta_adset_id")
        or fields.get("adset_id")
        or fields.get("ad_set_id"),
        "meta_campaign_id": (surrogate.meta_campaign_external_id if surrogate else None)
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
    if _is_synthetic_meta_lead_id(meta_lead.meta_lead_id):
        return _skip_event(
            db,
            surrogate=surrogate,
            source=source,
            reason="synthetic_meta_lead_id",
            stage_key=stage_key,
            stage_slug=stage_slug,
            stage_label=stage_label,
            event_name=event_name,
            lead_id=meta_lead.meta_lead_id,
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


def _resolve_donor_attribution(db: Session, donor: Donor) -> dict[str, object] | None:
    meta_lead = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == donor.organization_id,
            MetaLead.converted_donor_id == donor.id,
        )
        .order_by(MetaLead.converted_at.desc().nullslast(), MetaLead.received_at.desc())
        .first()
    )
    if meta_lead is not None:
        fields = _extract_meta_fields(meta_lead)
        # lead_id is written from the attribution itself, not from lead tracking fields.
        fields.pop("meta_lead_id", None)
        fbc = _resolve_meta_click_id(meta_lead)
        if fbc:
            fields["fbc"] = fbc
            fields["facebook_click_id"] = fbc
        return {
            "source": "meta",
            "lead_id": meta_lead.meta_lead_id or None,
            "lead_timestamp": _resolve_meta_lead_timestamp(meta_lead),
            "first_party_submission_id": None,
            "fields": fields,
        }

    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == donor.organization_id,
            FormSubmission.donor_id == donor.id,
        )
        .order_by(FormSubmission.submitted_at.desc(), FormSubmission.id.desc())
        .first()
    )
    if submission is None:
        submission = (
            db.query(FormSubmission)
            .join(IntakeLead, IntakeLead.form_submission_id == FormSubmission.id)
            .filter(
                FormSubmission.organization_id == donor.organization_id,
                IntakeLead.organization_id == donor.organization_id,
                IntakeLead.promoted_donor_id == donor.id,
            )
            .order_by(FormSubmission.submitted_at.desc(), FormSubmission.id.desc())
            .first()
        )
    if submission is None:
        return None

    attribution = (
        db.query(LeadAttribution)
        .filter(
            LeadAttribution.organization_id == donor.organization_id,
            LeadAttribution.form_submission_id == submission.id,
        )
        .order_by(LeadAttribution.created_at.desc())
        .first()
    )
    fields: dict[str, str | None] = {}
    if attribution is not None:
        fields = {
            "ad_id": attribution.ad_id,
            "adset_id": attribution.adset_id,
            "campaign_id": attribution.campaign_id,
            "fbclid": attribution.fbclid,
            "fbc": _normalize_meta_click_id(attribution.fbc),
            "fbp": _normalize_meta_click_id(attribution.fbp),
        }
    return {
        "source": "website",
        "lead_id": None,
        "first_party_submission_id": submission.id,
        "fields": fields,
    }


def build_donor_stage_event_payload(
    *,
    event_id: str,
    event_name: str,
    event_time: datetime,
    attribution: dict[str, object],
    donor_type: str,
    include_hashed_pii: bool,
    email: str | None,
    phone: str | None,
    test_mode: bool = False,
) -> dict[str, object]:
    """Build the minimal external donor payload without internal stage/profile data."""
    payload: dict[str, object] = {
        "event_id": event_id,
        "event_name": event_name,
        "lifecycle_stage_name": event_name,
        "stage_in_sales_process": event_name,
        "event_time": event_time.astimezone(UTC).isoformat(),
        "record_type": f"{donor_type}_donor",
        "attribution_source": attribution["source"],
    }
    lead_id = attribution.get("lead_id")
    if isinstance(lead_id, str) and lead_id:
        payload["lead_id"] = lead_id
        payload["facebook_lead_id"] = lead_id
        payload["meta_lead_id"] = lead_id
    submission_id = attribution.get("first_party_submission_id")
    if isinstance(submission_id, UUID):
        payload["first_party_submission_id"] = str(submission_id)

    fields = attribution.get("fields")
    if isinstance(fields, dict):
        payload.update({str(key): value for key, value in fields.items() if value})

    if include_hashed_pii:
        payload.update(_customer_match_fields(email, phone))
    if test_mode:
        payload["test_mode"] = True
    return payload


def _donor_event_id(donor_id: UUID, event_name: str) -> str:
    """Stable id per donor and event name, like the surrogate per-lead bucket key."""
    return f"zapier_donor:{donor_id}:{event_name.strip().lower().replace(' ', '_')}"


def _withdraw_undone_donor_event(
    db: Session,
    *,
    donor: Donor,
    undo_history: DonorStatusHistory,
) -> None:
    """Skip the forward event an undo reverses while its job is still unclaimed.

    Surrogate undo does not withdraw events. Donors do, because each donor event is sent
    at most once and an accidental stage change would otherwise spend that send.
    """
    undone_history = (
        db.query(DonorStatusHistory)
        .filter(
            DonorStatusHistory.organization_id == donor.organization_id,
            DonorStatusHistory.donor_id == donor.id,
            DonorStatusHistory.id != undo_history.id,
            DonorStatusHistory.old_stage_id == undo_history.new_stage_id,
            DonorStatusHistory.new_stage_id == undo_history.old_stage_id,
            DonorStatusHistory.is_undo.is_(False),
        )
        .order_by(DonorStatusHistory.recorded_at.desc())
        .first()
    )
    if undone_history is None:
        return
    event = (
        db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.organization_id == donor.organization_id,
            ZapierOutboundEvent.donor_status_history_id == undone_history.id,
            ZapierOutboundEvent.status == "queued",
        )
        .first()
    )
    if event is None or event.job_id is None:
        return
    # Lock the unclaimed job so a worker cannot claim it until this transaction ends;
    # a job already claimed is past withdrawal and delivers normally.
    pending_job = (
        db.query(Job.id)
        .filter(
            Job.id == event.job_id,
            Job.organization_id == donor.organization_id,
            Job.status == JobStatus.PENDING.value,
        )
        .with_for_update()
        .first()
    )
    if pending_job is None:
        return
    event.status = "skipped"
    event.reason = "donor_stage_undone"
    event.updated_at = _now_utc()
    db.flush()


def enqueue_donor_stage_event(
    db: Session,
    *,
    donor: Donor,
    history: DonorStatusHistory,
    new_stage: PipelineStage,
    source: str = "automatic",
) -> dict[str, object]:
    """Atomically attach a donor stage occurrence to its delivery job."""
    existing = (
        db.query(ZapierOutboundEvent)
        .filter(
            ZapierOutboundEvent.organization_id == donor.organization_id,
            ZapierOutboundEvent.donor_status_history_id == history.id,
        )
        .first()
    )
    if existing is not None:
        return {
            "queued": existing.status == "queued",
            "reason": "duplicate",
            "event_id": existing.event_id,
        }

    # The job key stays per stage occurrence, so a skipped or withdrawn occurrence never
    # blocks the first real send; the stable event_id below carries the dedupe.
    occurrence_key = f"zapier_donor_stage:{history.id}"
    event_id = occurrence_key
    pipeline_id = new_stage.pipeline_id

    def skip(reason: str, *, event_name: str | None = None, attribution=None):
        attribution = attribution or {}
        event = zapier_monitor_service.create_donor_event(
            db,
            org_id=donor.organization_id,
            source=source,
            status="skipped",
            reason=reason,
            event_id=event_id,
            event_name=event_name,
            lead_id=attribution.get("lead_id"),
            stage_key=new_stage.stage_key,
            stage_slug=new_stage.slug,
            stage_label=new_stage.label,
            donor_id=donor.id,
            donor_status_history_id=history.id,
            donor_type=donor.donor_type,
            pipeline_id=pipeline_id,
            stage_id=new_stage.id,
            attribution_source=attribution.get("source"),
            first_party_submission_id=attribution.get("first_party_submission_id"),
        )
        return {"queued": False, "reason": reason, "event_id": event.event_id}

    if history.is_undo:
        _withdraw_undone_donor_event(db, donor=donor, undo_history=history)
        return skip("donor_stage_undo")

    settings = zapier_settings_service.get_settings(db, donor.organization_id)
    if settings is None or not settings.donor_outbound_enabled:
        return skip("donor_outbound_disabled")
    if not settings.outbound_webhook_url:
        return skip("missing_webhook_url")

    mapping_item = zapier_settings_service.resolve_donor_mapping_item(
        settings.donor_outbound_event_mapping,
        donor_type=donor.donor_type,
        pipeline_id=pipeline_id,
        stage_id=new_stage.id,
    )
    if mapping_item is None:
        return skip("unmapped_donor_stage")
    event_name = str(mapping_item["event_name"])
    event_id = _donor_event_id(donor.id, event_name)

    attribution = _resolve_donor_attribution(db, donor)
    if attribution is None:
        return skip("missing_donor_attribution", event_name=event_name)
    if attribution["source"] == "meta":
        lead_id = attribution.get("lead_id")
        if not lead_id:
            return skip("missing_meta_lead_id", event_name=event_name, attribution=attribution)
        if _is_synthetic_meta_lead_id(str(lead_id)):
            return skip("synthetic_meta_lead_id", event_name=event_name, attribution=attribution)
        lead_timestamp = attribution.get("lead_timestamp")
        event_time = _coerce_utc(history.effective_at) or _now_utc()
        if isinstance(lead_timestamp, datetime) and event_time - lead_timestamp > MAX_META_LEAD_AGE:
            return skip("stale_meta_lead", event_name=event_name, attribution=attribution)
    attribution_fields = attribution.get("fields")
    has_browser_matching = isinstance(attribution_fields, dict) and bool(
        attribution_fields.get("fbc") or attribution_fields.get("fbp")
    )
    has_contact_matching = settings.outbound_send_hashed_pii and bool(
        _customer_match_fields(donor.email, donor.phone).get("user_data")
    )
    if attribution["source"] == "website" and not (has_browser_matching or has_contact_matching):
        return skip("missing_matching_data", event_name=event_name, attribution=attribution)

    # Stage changes lock the donor row before this point, so concurrent changes for one
    # donor serialize here and the later one sees the earlier event.
    already_reported = (
        db.query(ZapierOutboundEvent.id)
        .filter(
            ZapierOutboundEvent.organization_id == donor.organization_id,
            ZapierOutboundEvent.donor_id == donor.id,
            ZapierOutboundEvent.event_id == event_id,
            ZapierOutboundEvent.status.in_(DONOR_REPORTED_EVENT_STATUSES),
        )
        .first()
    )
    if already_reported is not None:
        return skip("duplicate", event_name=event_name, attribution=attribution)

    fingerprint = zapier_settings_service.donor_config_fingerprint(
        webhook_url=settings.outbound_webhook_url,
        donor_type=donor.donor_type,
        pipeline_id=pipeline_id,
        stage_id=new_stage.id,
        event_name=event_name,
    )
    payload = build_donor_stage_event_payload(
        event_id=event_id,
        event_name=event_name,
        event_time=history.effective_at,
        attribution=attribution,
        donor_type=donor.donor_type,
        include_hashed_pii=settings.outbound_send_hashed_pii,
        email=donor.email,
        phone=donor.phone,
    )
    event = zapier_monitor_service.create_donor_event(
        db,
        org_id=donor.organization_id,
        source=source,
        status="queued",
        reason=None,
        event_id=event_id,
        event_name=event_name,
        lead_id=attribution.get("lead_id"),
        stage_key=new_stage.stage_key,
        stage_slug=new_stage.slug,
        stage_label=new_stage.label,
        donor_id=donor.id,
        donor_status_history_id=history.id,
        donor_type=donor.donor_type,
        pipeline_id=pipeline_id,
        stage_id=new_stage.id,
        attribution_source=str(attribution["source"]),
        first_party_submission_id=attribution.get("first_party_submission_id"),
        config_fingerprint=fingerprint,
    )
    job = job_service.enqueue_job(
        db,
        org_id=donor.organization_id,
        job_type=JobType.ZAPIER_STAGE_EVENT,
        payload={
            "delivery_kind": "donor_stage",
            "event_record_id": str(event.id),
            "config_fingerprint": fingerprint,
            "data": payload,
        },
        idempotency_key=occurrence_key,
        commit=False,
    )
    event.job_id = job.id
    db.flush()
    return {
        "queued": True,
        "reason": None,
        "event_id": event_id,
        "event_name": event_name,
        "job_id": str(job.id),
    }


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
