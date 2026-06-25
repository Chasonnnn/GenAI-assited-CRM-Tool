"""Service functions for shared/public form intake links."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import hash_date_of_birth, hash_email, hash_phone
from app.db.enums import (
    FormPurpose,
    FormLinkMode,
    FormStatus,
    FormSubmissionMatchStatus,
    FormSubmissionStatus,
    IntakeLeadStatus,
    TrackingMode,
)
from app.db.enums.workflows import WorkflowTriggerType
from app.db.models import (
    AutomationWorkflow,
    ConsentRecord,
    EmbedSession,
    Form,
    FormIntakeDraft,
    FormIntakeLink,
    FormSubmission,
    FormSubmissionMatchCandidate,
    IntakeLead,
    LeadAttribution,
    PublishedIntakeVersion,
    Surrogate,
    TrackingEventLog,
)
from app.services import (
    embed_policy_service,
    form_service,
    form_submission_service,
    meta_capi,
    meta_crm_dataset_service,
    surrogate_input_normalization_service,
)
from app.utils.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_search_text,
)

IDENTITY_SURROGATE_FIELDS = ("full_name", "date_of_birth", "phone", "email")
INTAKE_SLUG_MAX_LENGTH = 100
EMBED_ALLOWED_ATTRIBUTION_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ad_id",
    "adset_id",
    "campaign_id",
    "fbclid",
    "fbc",
    "fbp",
    "referrer",
    "landing_url",
}
EMBED_URL_ATTRIBUTION_KEYS = {"referrer", "landing_url"}
DEFAULT_EMBED_TRACKING_MODE = TrackingMode.ENHANCED_MATCH_LEAD.value
DEFAULT_SHARED_INTAKE_TRACKING_MODE = TrackingMode.INTERNAL_ONLY.value
META_TRACKING_MODES = {
    TrackingMode.PRIVACY_SAFE_LEAD.value,
    TrackingMode.ENHANCED_MATCH_LEAD.value,
}
PRIVACY_SAFE_FIELD_POLICY_MODES = {
    TrackingMode.PRIVACY_SAFE_LEAD.value,
    TrackingMode.ENHANCED_MATCH_LEAD.value,
}
logger = logging.getLogger(__name__)
DUPLICATE_APPLICANT_MESSAGE = "An intake submission is already pending review."


class DuplicateApplicantSubmissionError(ValueError):
    """Raised when a public applicant already has an unresolved submission."""


def _default_tracking_mode_for_form(db: Session, form: Form) -> str:
    if form.purpose == FormPurpose.LEAD_CAPTURE.value:
        try:
            form_service.validate_privacy_safe_lead_schema(db, form)
        except ValueError:
            return DEFAULT_SHARED_INTAKE_TRACKING_MODE
        return DEFAULT_EMBED_TRACKING_MODE
    return DEFAULT_SHARED_INTAKE_TRACKING_MODE


def build_shared_application_link(base_url: str | None, slug: str) -> str:
    cleaned_base = (base_url or "").strip().rstrip("/")
    if not cleaned_base:
        return f"/intake/{slug}"
    return f"{cleaned_base}/intake/{slug}"


def _normalize_slug(value: str) -> str:
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:INTAKE_SLUG_MAX_LENGTH]


def build_intake_slug_base(
    *,
    event_name: str | None,
    campaign_name: str | None,
    form_name: str | None,
) -> str:
    for raw_value in (event_name, campaign_name, form_name):
        if not raw_value:
            continue
        slug = _normalize_slug(raw_value).strip("-")
        if slug:
            return slug[:INTAKE_SLUG_MAX_LENGTH]
    return "intake"


def _format_intake_slug_candidate(base: str, sequence: int) -> str:
    if sequence <= 1:
        return base[:INTAKE_SLUG_MAX_LENGTH]

    suffix = f"-{sequence}"
    trimmed_base = base[: max(1, INTAKE_SLUG_MAX_LENGTH - len(suffix))]
    return f"{trimmed_base}{suffix}"


def generate_unique_intake_slug(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_name: str | None,
    campaign_name: str | None,
    event_name: str | None,
) -> str:
    base = build_intake_slug_base(
        event_name=event_name,
        campaign_name=campaign_name,
        form_name=form_name,
    )
    sequence = 1

    while True:
        candidate = _format_intake_slug_candidate(base, sequence)
        exists = (
            db.query(FormIntakeLink.id)
            .filter(
                FormIntakeLink.organization_id == org_id,
                FormIntakeLink.slug == candidate,
            )
            .first()
        )
        if not exists:
            return candidate
        sequence += 1


def create_intake_link(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    user_id: uuid.UUID | None,
    campaign_name: str | None,
    event_name: str | None,
    expires_at: datetime | None,
    max_submissions: int | None,
    utm_defaults: dict[str, str] | None,
    embed_enabled: bool | None = None,
    allowed_embed_origins: list[str] | None = None,
    tracking_mode: str | None = None,
    consent_text: str | None = None,
    privacy_policy_url: str | None = None,
    thank_you_config: dict[str, Any] | None = None,
    embed_theme_json: dict[str, Any] | None = None,
) -> FormIntakeLink:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form must be published before creating shared links")
    normalized_campaign_name = (campaign_name or "").strip() or None
    normalized_event_name = (event_name or "").strip() or None
    slug = generate_unique_intake_slug(
        db,
        org_id=org_id,
        form_name=form.name,
        campaign_name=normalized_campaign_name,
        event_name=normalized_event_name,
    )
    record = FormIntakeLink(
        organization_id=org_id,
        form_id=form.id,
        slug=slug,
        campaign_name=normalized_campaign_name,
        event_name=normalized_event_name,
        expires_at=expires_at,
        max_submissions=max_submissions,
        utm_defaults=utm_defaults or None,
        embed_enabled=bool(embed_enabled),
        allowed_embed_origins=embed_policy_service.normalize_allowed_origins(allowed_embed_origins),
        tracking_mode=tracking_mode or _default_tracking_mode_for_form(db, form),
        consent_text=(consent_text or "").strip() or None,
        privacy_policy_url=(privacy_policy_url or "").strip() or None,
        thank_you_config=thank_you_config or {},
        embed_theme_json=embed_theme_json or {},
        created_by_user_id=user_id,
    )
    _validate_link_embed_policy(db=db, form=form, link=record)
    db.add(record)
    db.flush()
    version = create_published_intake_version(db=db, form=form, link=record, user_id=user_id)
    record.published_version_id = version.id
    db.commit()
    db.refresh(record)
    return record


def ensure_default_intake_link(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    user_id: uuid.UUID | None,
) -> FormIntakeLink:
    """Ensure one active shared intake link exists for a published form."""
    existing = (
        db.query(FormIntakeLink)
        .filter(
            FormIntakeLink.organization_id == org_id,
            FormIntakeLink.form_id == form.id,
            FormIntakeLink.is_active.is_(True),
        )
        .order_by(FormIntakeLink.created_at.asc())
        .first()
    )
    if existing:
        if not existing.published_version_id:
            ensure_link_published_version(db=db, form=form, link=existing, user_id=user_id)
        return existing

    default_campaign_name = (form.name or "").strip() or "Shared Intake"
    return create_intake_link(
        db,
        org_id=org_id,
        form=form,
        user_id=user_id,
        campaign_name=default_campaign_name,
        event_name=None,
        expires_at=None,
        max_submissions=None,
        utm_defaults=None,
        tracking_mode=_default_tracking_mode_for_form(db, form),
    )


def _validate_link_embed_policy(*, db: Session, form: Form, link: FormIntakeLink) -> None:
    if link.embed_enabled and not link.allowed_embed_origins:
        raise ValueError("Allowed embed origins are required when embed is enabled")
    if link.tracking_mode in PRIVACY_SAFE_FIELD_POLICY_MODES:
        if form.purpose != FormPurpose.LEAD_CAPTURE.value:
            raise ValueError("Lead tracking requires a lead_capture form")
        form_service.validate_privacy_safe_lead_schema(db, form)
    if form.purpose == FormPurpose.LEAD_CAPTURE.value:
        form_service.validate_lead_capture_schema(db, form)


def _snapshot_field_policy(form: Form) -> dict[str, Any]:
    schema_json = form.published_schema_json or form.schema_json or {}
    schema = form_submission_service.parse_schema(schema_json)
    fields = form_submission_service.flatten_fields(schema)
    return {
        key: {
            "type": field.type,
            "required": field.required,
            "sensitivity": field.sensitivity,
        }
        for key, field in fields.items()
    }


def create_published_intake_version(
    db: Session,
    *,
    form: Form,
    link: FormIntakeLink,
    user_id: uuid.UUID | None,
) -> PublishedIntakeVersion:
    schema_snapshot = json.loads(json.dumps(form.published_schema_json or form.schema_json or {}))
    mapping_snapshot = form_submission_service._snapshot_mappings(db, form.id)  # type: ignore[attr-defined]
    version_number = (
        db.query(PublishedIntakeVersion)
        .filter(PublishedIntakeVersion.intake_link_id == link.id)
        .count()
        + 1
    )
    tracking_policy_snapshot = {
        "tracking_mode": link.tracking_mode,
        "allowed_embed_origins": link.allowed_embed_origins or [],
        "embed_enabled": link.embed_enabled,
    }
    version = PublishedIntakeVersion(
        organization_id=link.organization_id,
        intake_link_id=link.id,
        form_id=form.id,
        version=version_number,
        form_version_hash=embed_policy_service.stable_json_hash(schema_snapshot),
        form_schema_snapshot_json=schema_snapshot,
        field_policy_snapshot_json=_snapshot_field_policy(form),
        mapping_snapshot_json=mapping_snapshot,
        consent_text_snapshot=link.consent_text,
        consent_text_hash=embed_policy_service.stable_hash(link.consent_text),
        thank_you_config_snapshot_json=link.thank_you_config or {},
        tracking_mode_snapshot=link.tracking_mode,
        tracking_policy_hash=embed_policy_service.stable_json_hash(tracking_policy_snapshot),
        embed_theme_snapshot_json=link.embed_theme_json or {},
        published_by_user_id=user_id,
    )
    db.add(version)
    db.flush()
    return version


def ensure_link_published_version(
    db: Session,
    *,
    form: Form,
    link: FormIntakeLink,
    user_id: uuid.UUID | None = None,
) -> PublishedIntakeVersion:
    if link.published_version_id:
        existing = (
            db.query(PublishedIntakeVersion)
            .filter(
                PublishedIntakeVersion.organization_id == link.organization_id,
                PublishedIntakeVersion.id == link.published_version_id,
            )
            .first()
        )
        if existing:
            return existing
    version = create_published_intake_version(db=db, form=form, link=link, user_id=user_id)
    link.published_version_id = version.id
    db.commit()
    db.refresh(link)
    return version


def get_embed_setup_health(
    db: Session,
    *,
    link: FormIntakeLink,
) -> dict[str, Any]:
    """Return a PHI-safe readiness report for publishing an embedded intake link."""
    checks: list[dict[str, str]] = []

    def add_check(key: str, label: str, status: str, message: str) -> None:
        checks.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "message": message,
            }
        )

    form = form_service.get_form(db, link.organization_id, link.form_id)
    if not link.is_active:
        add_check("link_active", "Intake link active", "block", "This intake link is inactive.")
    else:
        add_check("link_active", "Intake link active", "pass", "This intake link is active.")

    if not form:
        add_check("form", "Published form", "block", "The linked form no longer exists.")
    elif form.status != FormStatus.PUBLISHED.value:
        add_check("form", "Published form", "block", "The form must be published before embedding.")
    else:
        add_check("form", "Published form", "pass", "The form is published.")

    if form and form.purpose != FormPurpose.LEAD_CAPTURE.value:
        add_check(
            "purpose",
            "Lead capture purpose",
            "block",
            "Embedded v1 intake requires a lead_capture form.",
        )
    else:
        add_check("purpose", "Lead capture purpose", "pass", "The form uses lead_capture purpose.")

    if link.embed_enabled:
        add_check("embed_enabled", "Embed enabled", "pass", "Iframe embedding is enabled.")
    else:
        add_check("embed_enabled", "Embed enabled", "block", "Enable iframe embed for this link.")

    allowed_origins = link.allowed_embed_origins or []
    if allowed_origins:
        origin_count = len(allowed_origins)
        suffix = "s" if origin_count != 1 else ""
        add_check(
            "allowed_origins",
            "Allowed origins",
            "pass",
            f"{origin_count} allowed origin{suffix} configured.",
        )
    else:
        add_check(
            "allowed_origins",
            "Allowed origins",
            "block",
            "Add at least one exact website origin.",
        )

    if link.consent_text and link.consent_text.strip():
        add_check("consent", "Consent text", "pass", "Consent text is configured.")
    else:
        add_check(
            "consent",
            "Consent text",
            "warning",
            "Add contact consent text before a customer pilot.",
        )

    if form and form.status == FormStatus.PUBLISHED.value:
        try:
            if link.tracking_mode in PRIVACY_SAFE_FIELD_POLICY_MODES:
                form_service.validate_privacy_safe_lead_schema(db, form)
            else:
                form_service.validate_lead_capture_schema(db, form)
        except ValueError as exc:
            add_check("tracking_policy", "Tracking policy", "block", str(exc))
        else:
            add_check(
                "tracking_policy",
                "Tracking policy",
                "pass",
                "Field classification is compatible with the selected tracking mode.",
            )
    else:
        add_check(
            "tracking_policy",
            "Tracking policy",
            "block",
            "Publish the form before validating tracking policy.",
        )

    if link.published_version_id:
        add_check(
            "published_version",
            "Published version",
            "pass",
            "A frozen published intake version exists.",
        )
    else:
        add_check(
            "published_version",
            "Published version",
            "block",
            "A frozen published intake version is required before submissions.",
        )

    add_check("snippet", "Embed snippet", "pass", f"Snippet slug {link.slug} is current")

    if any(check["status"] == "block" for check in checks):
        status = "blocked"
    elif any(check["status"] == "warning" for check in checks):
        status = "needs_attention"
    else:
        status = "ready"

    return {
        "status": status,
        "checks": checks,
        "updated_at": datetime.now(timezone.utc),
    }


def _trigger_config_form_id(trigger_config: dict[str, Any] | None) -> str | None:
    if not isinstance(trigger_config, dict):
        return None
    value = trigger_config.get("form_id")
    if value is None:
        return None
    return str(value)


def _has_enabled_form_scoped_submission_workflow(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
) -> bool:
    workflows = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.scope == "org",
            AutomationWorkflow.trigger_type == WorkflowTriggerType.FORM_SUBMITTED.value,
            AutomationWorkflow.is_enabled.is_(True),
        )
        .all()
    )
    target_form_id = str(form_id)
    return any(
        _trigger_config_form_id(workflow.trigger_config) == target_form_id for workflow in workflows
    )


def _default_intake_routing_actions() -> list[dict[str, Any]]:
    return [
        {
            "action_type": "auto_match_submission",
            "requires_approval": True,
        },
        {
            "action_type": "create_intake_lead",
            "requires_approval": True,
        },
    ]


def ensure_default_intake_routing_workflow(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    user_id: uuid.UUID | None,
) -> AutomationWorkflow | None:
    """Ensure an enabled, form-scoped shared-intake routing workflow exists."""
    if form.status != FormStatus.PUBLISHED.value:
        return None

    # Respect existing enabled custom workflows for this form.
    if _has_enabled_form_scoped_submission_workflow(db, org_id=org_id, form_id=form.id):
        return None

    system_key = f"shared_intake_routing:{form.id}"
    workflow = (
        db.query(AutomationWorkflow)
        .filter(
            AutomationWorkflow.organization_id == org_id,
            AutomationWorkflow.system_key == system_key,
            AutomationWorkflow.scope == "org",
            AutomationWorkflow.trigger_type == WorkflowTriggerType.FORM_SUBMITTED.value,
        )
        .first()
    )

    trigger_config = {"form_id": str(form.id)}
    actions = _default_intake_routing_actions()
    now = datetime.now(timezone.utc)

    if workflow:
        workflow.trigger_config = trigger_config
        workflow.actions = actions
        workflow.conditions = []
        workflow.condition_logic = "AND"
        workflow.is_enabled = True
        workflow.requires_review = False
        workflow.is_system_workflow = True
        workflow.updated_by_user_id = user_id
        workflow.updated_at = now
        db.commit()
        db.refresh(workflow)
        return workflow

    workflow = AutomationWorkflow(
        organization_id=org_id,
        name=f"Intake Routing ({str(form.id)[:8]})",
        description=(
            "Automatically routes shared form submissions by running auto-match first, "
            "then creating an intake lead if no deterministic match exists."
        ),
        icon="workflow",
        scope="org",
        owner_user_id=None,
        trigger_type=WorkflowTriggerType.FORM_SUBMITTED.value,
        trigger_config=trigger_config,
        conditions=[],
        condition_logic="AND",
        actions=actions,
        is_enabled=True,
        is_system_workflow=True,
        system_key=system_key,
        requires_review=False,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def list_intake_links(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    include_inactive: bool = False,
) -> list[FormIntakeLink]:
    query = db.query(FormIntakeLink).filter(
        FormIntakeLink.organization_id == org_id,
        FormIntakeLink.form_id == form_id,
    )
    if not include_inactive:
        query = query.filter(FormIntakeLink.is_active.is_(True))
    return query.order_by(FormIntakeLink.created_at.desc()).all()


def get_intake_link(
    db: Session,
    *,
    org_id: uuid.UUID,
    intake_link_id: uuid.UUID,
) -> FormIntakeLink | None:
    return (
        db.query(FormIntakeLink)
        .filter(
            FormIntakeLink.organization_id == org_id,
            FormIntakeLink.id == intake_link_id,
        )
        .first()
    )


def get_intake_link_by_slug(
    db: Session,
    slug: str,
    *,
    org_id: uuid.UUID | None = None,
) -> FormIntakeLink | None:
    query = db.query(FormIntakeLink).filter(FormIntakeLink.slug == slug)

    if org_id is not None:
        return query.filter(FormIntakeLink.organization_id == org_id).first()

    matches = (
        query.order_by(FormIntakeLink.created_at.asc(), FormIntakeLink.id.asc()).limit(2).all()
    )
    if len(matches) == 1:
        return matches[0]
    return None


def _is_link_publicly_available(link: FormIntakeLink) -> bool:
    if not link.is_active:
        return False
    now = datetime.now(timezone.utc)
    if link.expires_at:
        expires_at = link.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            return False
    if link.max_submissions is not None and link.submissions_count >= link.max_submissions:
        return False
    return True


def get_active_intake_link_by_slug(
    db: Session,
    slug: str,
    *,
    org_id: uuid.UUID | None = None,
) -> FormIntakeLink | None:
    link = get_intake_link_by_slug(db, slug, org_id=org_id)
    if not link:
        return None
    if not _is_link_publicly_available(link):
        return None
    return link


def get_active_intake_link_for_form(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
) -> FormIntakeLink | None:
    links = list_intake_links(db, org_id=org_id, form_id=form_id, include_inactive=False)
    for link in links:
        if _is_link_publicly_available(link):
            return link
    return None


def update_intake_link(
    db: Session,
    *,
    link: FormIntakeLink,
    campaign_name: str | None = None,
    event_name: str | None = None,
    expires_at: datetime | None = None,
    max_submissions: int | None = None,
    utm_defaults: dict[str, str] | None = None,
    is_active: bool | None = None,
    embed_enabled: bool | None = None,
    allowed_embed_origins: list[str] | None = None,
    tracking_mode: str | None = None,
    consent_text: str | None = None,
    privacy_policy_url: str | None = None,
    thank_you_config: dict[str, Any] | None = None,
    embed_theme_json: dict[str, Any] | None = None,
    fields_set: set[str] | None = None,
    user_id: uuid.UUID | None = None,
) -> FormIntakeLink:
    fields_set = fields_set or set()
    if "campaign_name" in fields_set:
        link.campaign_name = (campaign_name or "").strip() or None
    if "event_name" in fields_set:
        link.event_name = (event_name or "").strip() or None
    if "expires_at" in fields_set:
        link.expires_at = expires_at
    if "max_submissions" in fields_set:
        link.max_submissions = max_submissions
    if "utm_defaults" in fields_set:
        link.utm_defaults = utm_defaults or None
    if "is_active" in fields_set:
        link.is_active = bool(is_active)
    if "embed_enabled" in fields_set:
        link.embed_enabled = bool(embed_enabled)
    if "allowed_embed_origins" in fields_set:
        link.allowed_embed_origins = embed_policy_service.normalize_allowed_origins(
            allowed_embed_origins
        )
    if "tracking_mode" in fields_set:
        form = form_service.get_form(db, link.organization_id, link.form_id)
        link.tracking_mode = tracking_mode or (
            _default_tracking_mode_for_form(form) if form else DEFAULT_EMBED_TRACKING_MODE
        )
    if "consent_text" in fields_set:
        link.consent_text = (consent_text or "").strip() or None
    if "privacy_policy_url" in fields_set:
        link.privacy_policy_url = (privacy_policy_url or "").strip() or None
    if "thank_you_config" in fields_set:
        link.thank_you_config = thank_you_config or {}
    if "embed_theme_json" in fields_set:
        link.embed_theme_json = embed_theme_json or {}
    if fields_set & {
        "embed_enabled",
        "allowed_embed_origins",
        "tracking_mode",
        "consent_text",
        "privacy_policy_url",
        "thank_you_config",
        "embed_theme_json",
    }:
        form = form_service.get_form(db, link.organization_id, link.form_id)
        if form:
            _validate_link_embed_policy(db=db, form=form, link=link)
            version = create_published_intake_version(
                db=db,
                form=form,
                link=link,
                user_id=user_id,
            )
            link.published_version_id = version.id
    db.commit()
    db.refresh(link)
    return link


def rotate_intake_link(
    db: Session,
    *,
    link: FormIntakeLink,
) -> FormIntakeLink:
    link.slug = generate_unique_intake_slug(
        db,
        org_id=link.organization_id,
        form_name=link.form.name if link.form else None,
        campaign_name=link.campaign_name,
        event_name=link.event_name,
    )
    link.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return link


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("date_of_birth must be YYYY-MM-DD")


def _parse_date_safe(value: Any) -> date | None:
    try:
        return _parse_date(value)
    except Exception:
        return None


def _build_form_mapping_lookup(db: Session, form_id: uuid.UUID) -> dict[str, str]:
    return {
        m.surrogate_field: m.field_key
        for m in form_submission_service.list_field_mappings(db, form_id)
        if m.surrogate_field in IDENTITY_SURROGATE_FIELDS
    }


def _extract_identity(
    *,
    answers: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> dict[str, Any]:
    def _from_answer(surrogate_field: str) -> Any:
        mapped_key = mapping_lookup.get(surrogate_field)
        if mapped_key and mapped_key in answers:
            return answers.get(mapped_key)
        return answers.get(surrogate_field)

    partial = _extract_identity_partial(answers=answers, mapping_lookup=mapping_lookup)

    full_name = partial["full_name"]
    dob = partial["date_of_birth"]
    phone = partial["phone"]
    email = partial["email"]

    if not full_name:
        raise ValueError("Missing required field: full_name")
    if dob is None:
        raise ValueError("Missing required field: date_of_birth")
    if not phone:
        raise ValueError("Missing required field: phone")
    if not email:
        raise ValueError("Missing required field: email")

    return {
        "full_name": full_name,
        "full_name_normalized": normalize_search_text(full_name),
        "date_of_birth": dob,
        "phone": phone,
        "phone_hash": hash_phone(phone),
        "email": email,
        "email_hash": hash_email(email),
    }


def _extract_identity_partial(
    *,
    answers: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> dict[str, Any]:
    def _from_answer(surrogate_field: str) -> Any:
        mapped_key = mapping_lookup.get(surrogate_field)
        if mapped_key and mapped_key in answers:
            return answers.get(mapped_key)
        return answers.get(surrogate_field)

    full_name_raw = _from_answer("full_name")
    dob_raw = _from_answer("date_of_birth")
    phone_raw = _from_answer("phone")
    email_raw = _from_answer("email")

    full_name = normalize_name(str(full_name_raw)) if full_name_raw not in (None, "") else None
    full_name_normalized = normalize_search_text(full_name) if full_name else None
    dob = _parse_date_safe(dob_raw)

    phone: str | None = None
    if phone_raw not in (None, ""):
        try:
            phone = normalize_phone(str(phone_raw))
        except Exception:
            phone = None

    email = normalize_email(str(email_raw)) if email_raw not in (None, "") else None
    email_hash = hash_email(email) if email else None
    phone_hash = hash_phone(phone) if phone else None
    dob_hash = hash_date_of_birth(dob) if dob else None

    return {
        "full_name": full_name,
        "full_name_normalized": full_name_normalized,
        "date_of_birth": dob,
        "date_of_birth_hash": dob_hash,
        "phone": phone,
        "phone_hash": phone_hash,
        "email": email,
        "email_hash": email_hash,
    }


def _match_rule_phone(
    db: Session,
    *,
    org_id: uuid.UUID,
    identity: dict[str, Any],
) -> list[Surrogate]:
    query = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.phone_hash == identity["phone_hash"],
            Surrogate.full_name_normalized == identity["full_name_normalized"],
        )
        .order_by(Surrogate.created_at.asc())
    )
    candidates = query.all()
    target_dob = identity.get("date_of_birth")
    return [candidate for candidate in candidates if candidate.date_of_birth == target_dob]


def _match_rule_email(
    db: Session,
    *,
    org_id: uuid.UUID,
    identity: dict[str, Any],
) -> list[Surrogate]:
    query = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
            Surrogate.email_hash == identity["email_hash"],
            Surrogate.full_name_normalized == identity["full_name_normalized"],
        )
        .order_by(Surrogate.created_at.asc())
    )
    candidates = query.all()
    target_dob = identity.get("date_of_birth")
    return [candidate for candidate in candidates if candidate.date_of_birth == target_dob]


def _has_existing_submission_for_surrogate_form(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    surrogate_id: uuid.UUID,
    exclude_submission_id: uuid.UUID,
) -> bool:
    return (
        db.query(FormSubmission.id)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.form_id == form_id,
            FormSubmission.surrogate_id == surrogate_id,
            FormSubmission.id != exclude_submission_id,
        )
        .first()
        is not None
    )


def _detect_duplicate_recent_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    identity: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> bool:
    window_seconds = max(0, int(settings.FORMS_SHARED_DUPLICATE_WINDOW_SECONDS or 0))
    if window_seconds <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    recent = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.intake_link_id == link.id,
            FormSubmission.submitted_at >= cutoff,
        )
        .order_by(FormSubmission.submitted_at.desc())
        .limit(50)
        .all()
    )
    for submission in recent:
        answers = submission.answers_json if isinstance(submission.answers_json, dict) else {}
        if not isinstance(answers, dict):
            continue
        try:
            existing_identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)
        except Exception:
            continue
        if (
            existing_identity.get("full_name_normalized") == identity.get("full_name_normalized")
            and existing_identity.get("date_of_birth") == identity.get("date_of_birth")
            and existing_identity.get("phone_hash") == identity.get("phone_hash")
            and existing_identity.get("email_hash") == identity.get("email_hash")
        ):
            return True
    return False


def _has_unresolved_duplicate_applicant_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    identity: dict[str, Any],
    exclude_submission_id: uuid.UUID | None = None,
) -> bool:
    full_name_normalized = identity.get("full_name_normalized")
    email_hash = identity.get("email_hash")
    phone_hash = identity.get("phone_hash")
    date_of_birth_hash = identity.get("date_of_birth_hash")

    if not full_name_normalized or (not email_hash and not phone_hash):
        return False

    contact_filters = []
    if email_hash:
        contact_filters.append(FormSubmission.email_hash == email_hash)
    if phone_hash:
        contact_filters.append(FormSubmission.phone_hash == phone_hash)

    query = (
        db.query(FormSubmission.id)
        .outerjoin(
            IntakeLead,
            FormSubmission.intake_lead_id == IntakeLead.id,
        )
        .filter(
            FormSubmission.organization_id == link.organization_id,
            FormSubmission.form_id == link.form_id,
            FormSubmission.full_name_normalized == full_name_normalized,
            or_(*contact_filters),
            or_(
                FormSubmission.status == FormSubmissionStatus.PENDING_REVIEW.value,
                IntakeLead.status == IntakeLeadStatus.PENDING_REVIEW.value,
            ),
        )
    )
    if exclude_submission_id:
        query = query.filter(FormSubmission.id != exclude_submission_id)
    if date_of_birth_hash:
        query = query.filter(
            or_(
                FormSubmission.date_of_birth_hash == date_of_birth_hash,
                FormSubmission.date_of_birth_hash.is_(None),
            )
        )
    else:
        query = query.filter(FormSubmission.date_of_birth_hash.is_(None))

    if query.first() is not None:
        return True

    lead_contact_filters = []
    if email_hash:
        lead_contact_filters.append(IntakeLead.email_hash == email_hash)
    if phone_hash:
        lead_contact_filters.append(IntakeLead.phone_hash == phone_hash)
    lead_candidates = (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == link.organization_id,
            IntakeLead.form_id == link.form_id,
            IntakeLead.status == IntakeLeadStatus.PENDING_REVIEW.value,
            IntakeLead.full_name_normalized == full_name_normalized,
            or_(*lead_contact_filters),
        )
        .limit(25)
        .all()
    )
    target_dob = identity.get("date_of_birth")
    return any(candidate.date_of_birth == target_dob for candidate in lead_candidates)


def _raise_if_duplicate_applicant_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    identity: dict[str, Any],
) -> None:
    if _has_unresolved_duplicate_applicant_submission(db, link=link, identity=identity):
        raise DuplicateApplicantSubmissionError(DUPLICATE_APPLICANT_MESSAGE)


def _create_intake_lead(
    db: Session,
    *,
    org_id: uuid.UUID,
    form: Form,
    link: FormIntakeLink | None,
    identity: dict[str, Any],
    source_metadata: dict[str, Any] | None,
    user_id: uuid.UUID | None = None,
    form_submission_id: uuid.UUID | None = None,
    source: str = "shared_intake",
    lead_type: str = "surrogate",
) -> IntakeLead:
    lead = IntakeLead(
        organization_id=org_id,
        form_id=form.id,
        intake_link_id=link.id if link else None,
        form_submission_id=form_submission_id,
        source=source,
        lead_type=lead_type,
        full_name=identity["full_name"],
        full_name_normalized=identity["full_name_normalized"],
        email=identity["email"],
        email_hash=identity["email_hash"],
        phone=identity["phone"],
        phone_hash=identity["phone_hash"],
        date_of_birth=identity["date_of_birth"],
        status=IntakeLeadStatus.PENDING_REVIEW.value,
        source_metadata=source_metadata or None,
        created_by_user_id=user_id,
    )
    db.add(lead)
    db.flush()
    return lead


def _trigger_intake_lead_created_workflow(
    db: Session,
    *,
    lead: IntakeLead,
    form_id: uuid.UUID | None,
    submission_id: uuid.UUID | None,
) -> None:
    try:
        from app.services import workflow_triggers

        workflow_triggers.trigger_intake_lead_created(
            db,
            lead,
            form_id=form_id,
            submission_id=submission_id,
        )
    except Exception:
        logger.debug(
            "trigger_intake_lead_created_failed",
            exc_info=True,
        )


def _resolve_surrogate_owner_user_id(
    db: Session,
    *,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID | None,
) -> uuid.UUID | None:
    if not surrogate_id:
        return None
    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.id == surrogate_id,
        )
        .first()
    )
    if not surrogate:
        return None
    if surrogate.owner_type == "user" and surrogate.owner_id:
        return surrogate.owner_id
    return None


def _trigger_form_submitted_workflow(
    db: Session,
    *,
    submission: FormSubmission,
) -> None:
    try:
        from app.services import workflow_triggers

        workflow_triggers.trigger_form_submitted(
            db=db,
            org_id=submission.organization_id,
            form_id=submission.form_id,
            submission_id=submission.id,
            submitted_at=submission.submitted_at,
            surrogate_id=submission.surrogate_id,
            source_mode=submission.source_mode,
            entity_owner_id=_resolve_surrogate_owner_user_id(
                db,
                org_id=submission.organization_id,
                surrogate_id=submission.surrogate_id,
            ),
        )
    except Exception:
        logger.debug(
            "trigger_form_submitted_failed",
            exc_info=True,
        )


def _normalize_shared_outcome(match_status: str | None) -> str:
    if match_status in {
        FormSubmissionMatchStatus.LINKED.value,
        FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value,
        FormSubmissionMatchStatus.LEAD_CREATED.value,
        FormSubmissionMatchStatus.WORKFLOW_PENDING.value,
    }:
        return match_status
    return FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value


def _create_shared_submission(
    db: Session,
    *,
    form: Form,
    link: FormIntakeLink,
    answers: dict[str, Any],
    files: list[UploadFile],
    file_field_keys: list[str] | None,
    surrogate_id: uuid.UUID | None,
    intake_lead_id: uuid.UUID | None,
    match_status: str,
    match_reason: str | None,
    matched_at: datetime | None,
    published_version_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    form_schema_hash: str | None = None,
    consent_text_hash: str | None = None,
    tracking_policy_hash: str | None = None,
    identity: dict[str, Any] | None = None,
) -> FormSubmission:
    schema = form_submission_service.parse_schema(form.published_schema_json or {})
    form_submission_service._validate_answers(schema, answers)  # type: ignore[attr-defined]
    file_fields = form_submission_service._get_file_fields(schema, answers)  # type: ignore[attr-defined]
    resolved_file_field_keys = form_submission_service._resolve_file_field_keys(  # type: ignore[attr-defined]
        file_fields=file_fields,
        files=files or [],
        file_field_keys=file_field_keys,
    )
    form_submission_service._validate_required_file_fields(  # type: ignore[attr-defined]
        file_fields, resolved_file_field_keys
    )
    form_submission_service._validate_file_field_limits(  # type: ignore[attr-defined]
        file_fields, resolved_file_field_keys
    )
    validated_content_types = form_submission_service._validate_files(form, files or [])  # type: ignore[attr-defined]
    mapping_snapshot = form_submission_service._snapshot_mappings(db, form.id)  # type: ignore[attr-defined]
    if identity is None:
        mapping_lookup = _build_form_mapping_lookup(db, form.id)
        identity = _extract_identity_partial(answers=answers, mapping_lookup=mapping_lookup)
    now = datetime.now(timezone.utc)

    submission = FormSubmission(
        organization_id=form.organization_id,
        form_id=form.id,
        surrogate_id=surrogate_id,
        intake_link_id=link.id,
        intake_lead_id=intake_lead_id,
        published_version_id=published_version_id,
        idempotency_key=idempotency_key,
        form_schema_hash=form_schema_hash,
        consent_text_hash=consent_text_hash,
        tracking_policy_hash=tracking_policy_hash,
        full_name_normalized=(identity or {}).get("full_name_normalized"),
        date_of_birth=(identity or {}).get("date_of_birth"),
        date_of_birth_hash=(identity or {}).get("date_of_birth_hash"),
        email_hash=(identity or {}).get("email_hash"),
        phone_hash=(identity or {}).get("phone_hash"),
        source_mode=FormLinkMode.SHARED.value,
        status=FormSubmissionStatus.PENDING_REVIEW.value,
        match_status=match_status,
        match_reason=match_reason,
        matched_at=matched_at,
        answers_json=answers,
        schema_snapshot=form.published_schema_json,
        mapping_snapshot=mapping_snapshot,
        submitted_at=now,
    )
    db.add(submission)
    db.flush()

    for idx, file in enumerate(files or []):
        field_key = resolved_file_field_keys[idx] if resolved_file_field_keys else None
        form_submission_service._store_submission_file(  # type: ignore[attr-defined]
            db=db,
            submission=submission,
            file=file,
            form=form,
            field_key=field_key,
            content_type=validated_content_types[idx],
        )

    link.submissions_count = (link.submissions_count or 0) + 1
    return submission


def create_shared_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    answers: dict[str, Any],
    files: list[UploadFile] | None = None,
    file_field_keys: list[str] | None = None,
    source_metadata: dict[str, Any] | None = None,
    challenge_token: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[FormSubmission, str]:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    expected_challenge = (settings.FORMS_SHARED_CHALLENGE_SECRET.get_secret_value() or "").strip()
    if expected_challenge and challenge_token != expected_challenge:
        raise ValueError("Challenge verification failed")

    normalized_idempotency_key = (idempotency_key or "").strip()[:128] or None
    if normalized_idempotency_key:
        existing = _get_idempotent_embed_submission(
            db,
            link=link,
            idempotency_key=normalized_idempotency_key,
        )
        if existing:
            return existing, _normalize_shared_outcome(existing.match_status)

    schema = form_submission_service.parse_schema(form.published_schema_json)
    form_submission_service._validate_answers(schema, answers)  # type: ignore[attr-defined]

    mapping_lookup = _build_form_mapping_lookup(db, form.id)
    identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)
    _raise_if_duplicate_applicant_submission(db, link=link, identity=identity)
    submission = _create_shared_submission(
        db,
        form=form,
        link=link,
        answers=answers,
        identity=identity,
        files=files or [],
        file_field_keys=file_field_keys,
        surrogate_id=None,
        intake_lead_id=None,
        match_status=FormSubmissionMatchStatus.WORKFLOW_PENDING.value,
        match_reason="workflow_pending",
        matched_at=None,
        idempotency_key=normalized_idempotency_key,
    )
    clear_shared_drafts_for_identity(
        db,
        org_id=link.organization_id,
        form_id=form.id,
        identity=identity,
    )
    db.commit()
    db.refresh(submission)
    _trigger_form_submitted_workflow(db, submission=submission)
    db.refresh(submission)
    return submission, _normalize_shared_outcome(submission.match_status)


def sanitize_embed_attribution(payload: dict[str, Any] | None) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in (payload or {}).items():
        if key not in EMBED_ALLOWED_ATTRIBUTION_KEYS:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if key in EMBED_URL_ATTRIBUTION_KEYS:
            parsed = urlparse(text)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            text = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        sanitized[key] = text[:1000]
    return sanitized


def _lead_capture_identity(
    *,
    answers: dict[str, Any],
    mapping_lookup: dict[str, str],
) -> dict[str, Any]:
    identity = _extract_identity_partial(answers=answers, mapping_lookup=mapping_lookup)
    if not identity.get("full_name"):
        raise ValueError("Missing required field: full_name")
    if not identity.get("email") and not identity.get("phone"):
        raise ValueError("Missing required field: email or phone")
    return identity


def _get_idempotent_embed_submission(
    db: Session,
    *,
    link: FormIntakeLink,
    idempotency_key: str,
) -> FormSubmission | None:
    return (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == link.organization_id,
            FormSubmission.intake_link_id == link.id,
            FormSubmission.idempotency_key == idempotency_key,
        )
        .first()
    )


def _create_lead_attribution(
    db: Session,
    *,
    link: FormIntakeLink,
    submission: FormSubmission,
    session: EmbedSession,
    attribution: dict[str, str],
) -> LeadAttribution:
    source = attribution.get("utm_source")
    medium = attribution.get("utm_medium")
    campaign = attribution.get("utm_campaign")
    record = LeadAttribution(
        organization_id=link.organization_id,
        form_submission_id=submission.id,
        intake_link_id=link.id,
        source_surface="form_embed",
        source=source,
        medium=medium,
        campaign=campaign,
        ad_id=attribution.get("ad_id"),
        adset_id=attribution.get("adset_id"),
        campaign_id=attribution.get("campaign_id"),
        fbclid=attribution.get("fbclid"),
        fbc=attribution.get("fbc"),
        fbp=attribution.get("fbp"),
        referrer=attribution.get("referrer"),
        parent_origin=session.parent_origin,
        landing_url=attribution.get("landing_url"),
        first_touch_json=attribution or None,
        last_touch_json=attribution or None,
    )
    db.add(record)
    db.flush()
    return record


def _create_consent_record(
    db: Session,
    *,
    link: FormIntakeLink,
    submission: FormSubmission,
    accepted: bool,
    session: EmbedSession,
) -> ConsentRecord:
    consent = ConsentRecord(
        organization_id=link.organization_id,
        intake_link_id=link.id,
        form_submission_id=submission.id,
        consent_type="contact",
        consent_text_snapshot=link.consent_text,
        consent_text_hash=embed_policy_service.stable_hash(link.consent_text),
        accepted=accepted,
        ip_hash=session.ip_hash,
        user_agent_hash=session.user_agent_hash,
        parent_origin=session.parent_origin,
        privacy_policy_url_snapshot=link.privacy_policy_url,
    )
    db.add(consent)
    db.flush()
    return consent


def _enqueue_privacy_safe_tracking_event(
    db: Session,
    *,
    link: FormIntakeLink,
    submission: FormSubmission,
    identity: dict[str, Any],
    attribution: dict[str, str],
) -> TrackingEventLog:
    event_payload = {
        "event_name": "Lead",
        "event_time": int(datetime.now(timezone.utc).timestamp()),
        "event_id": f"sf_evt_{submission.id}",
        "action_source": "website",
        "event_source_url": f"/embed/forms/{link.slug}",
        "custom_data": {
            "content_name": "lead_capture",
            "content_category": "intake",
        },
    }
    if attribution.get("utm_source"):
        event_payload["custom_data"]["source"] = attribution["utm_source"]
    if attribution.get("utm_campaign"):
        event_payload["custom_data"]["campaign"] = attribution["utm_campaign"]
    if link.tracking_mode == TrackingMode.ENHANCED_MATCH_LEAD.value:
        user_data = _build_enhanced_match_user_data(identity=identity, attribution=attribution)
        if user_data:
            event_payload["user_data"] = user_data
    record = TrackingEventLog(
        organization_id=link.organization_id,
        intake_link_id=link.id,
        form_submission_id=submission.id,
        event_name="Lead",
        destination="meta",
        status="queued",
        payload_json=event_payload,
        payload_hash=embed_policy_service.stable_json_hash(event_payload),
    )
    db.add(record)
    db.flush()
    return record


def _build_enhanced_match_user_data(
    *,
    identity: dict[str, Any],
    attribution: dict[str, str],
) -> dict[str, object]:
    user_data: dict[str, object] = {}
    email = identity.get("email")
    phone = identity.get("phone")
    full_name = identity.get("full_name")
    if isinstance(email, str) and "@" in email:
        user_data["em"] = [meta_capi.hash_for_capi(email)]
    if isinstance(phone, str):
        phone_digits = re.sub(r"\D", "", phone)
        if len(phone_digits) >= 10:
            user_data["ph"] = [meta_capi.hash_for_capi(phone_digits)]
    if isinstance(full_name, str) and full_name.strip():
        name_parts = full_name.strip().split()
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[-1] if len(name_parts) > 1 else None
        if first_name:
            user_data["fn"] = [meta_capi.hash_for_capi(first_name)]
        if last_name:
            user_data["ln"] = [meta_capi.hash_for_capi(last_name)]
    fbc = attribution.get("fbc")
    fbp = attribution.get("fbp")
    if fbc:
        user_data["fbc"] = fbc
    if fbp:
        user_data["fbp"] = fbp
    return user_data


def create_embed_session(
    db: Session,
    *,
    link: FormIntakeLink,
    parent_origin: str,
    attribution: dict[str, Any] | None,
    client_ip: str | None,
    user_agent: str | None,
):
    if not link.embed_enabled:
        raise PermissionError("Embed is not enabled")
    sanitized_attribution = sanitize_embed_attribution(attribution)
    return embed_policy_service.create_embed_session(
        db,
        link=link,
        parent_origin=parent_origin,
        attribution_snapshot=sanitized_attribution,
        client_ip=client_ip,
        user_agent=user_agent,
    )


def submit_lead_capture_embed(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    embed_session_token: str,
    idempotency_key: str,
    published_version_id: uuid.UUID,
    answers: dict[str, Any],
    consent_accepted: bool,
    attribution: dict[str, Any] | None,
) -> tuple[FormSubmission, str]:
    if not link.embed_enabled:
        raise PermissionError("Embed is not enabled")
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if form.purpose != FormPurpose.LEAD_CAPTURE.value:
        raise ValueError("Embed lead capture requires a lead_capture form")

    existing = _get_idempotent_embed_submission(
        db,
        link=link,
        idempotency_key=idempotency_key,
    )
    if existing:
        return existing, _normalize_shared_outcome(existing.match_status)

    session = embed_policy_service.validate_embed_session(
        db,
        link=link,
        token=embed_session_token,
    )
    if not link.published_version_id:
        ensure_link_published_version(db=db, form=form, link=link)
    if str(link.published_version_id) != str(published_version_id):
        raise LookupError("Published version is no longer current")
    version = (
        db.query(PublishedIntakeVersion)
        .filter(
            PublishedIntakeVersion.organization_id == link.organization_id,
            PublishedIntakeVersion.id == link.published_version_id,
        )
        .first()
    )
    if not version:
        raise LookupError("Published version not found")
    if link.tracking_mode in PRIVACY_SAFE_FIELD_POLICY_MODES:
        form_service.validate_privacy_safe_lead_schema(db, form)
    else:
        form_service.validate_lead_capture_schema(db, form)

    mapping_lookup = _build_form_mapping_lookup(db, form.id)
    identity = _lead_capture_identity(answers=answers, mapping_lookup=mapping_lookup)
    _raise_if_duplicate_applicant_submission(db, link=link, identity=identity)
    sanitized_attribution = sanitize_embed_attribution(
        {**(session.attribution_snapshot_json or {}), **(attribution or {})}
    )

    submission = _create_shared_submission(
        db,
        form=form,
        link=link,
        answers=answers,
        identity=identity,
        files=[],
        file_field_keys=None,
        surrogate_id=None,
        intake_lead_id=None,
        match_status=FormSubmissionMatchStatus.WORKFLOW_PENDING.value,
        match_reason="workflow_pending",
        matched_at=None,
        published_version_id=version.id,
        idempotency_key=idempotency_key,
        form_schema_hash=version.form_version_hash,
        consent_text_hash=version.consent_text_hash,
        tracking_policy_hash=version.tracking_policy_hash,
    )
    _create_lead_attribution(
        db,
        link=link,
        submission=submission,
        session=session,
        attribution=sanitized_attribution,
    )
    _create_consent_record(
        db,
        link=link,
        submission=submission,
        accepted=consent_accepted,
        session=session,
    )
    session.consumed_at = datetime.now(timezone.utc)
    if link.tracking_mode in META_TRACKING_MODES:
        _enqueue_privacy_safe_tracking_event(
            db,
            link=link,
            submission=submission,
            identity=identity,
            attribution=sanitized_attribution,
        )
    db.commit()
    db.refresh(submission)
    if link.tracking_mode == TrackingMode.INTERNAL_ONLY.value:
        meta_crm_dataset_service.enqueue_website_lead_event(
            db,
            organization_id=link.organization_id,
            submission_id=submission.id,
            event_source_url=sanitized_attribution.get("landing_url") or session.parent_origin,
            attribution=sanitized_attribution,
            email=identity.get("email"),
            phone=identity.get("phone"),
        )
        db.refresh(submission)
    _trigger_form_submitted_workflow(db, submission=submission)
    db.refresh(submission)
    return submission, _normalize_shared_outcome(submission.match_status)


def auto_match_submission(
    db: Session,
    *,
    submission: FormSubmission,
) -> tuple[FormSubmission, str]:
    """Apply deterministic matching rules for a shared submission."""
    if submission.source_mode != FormLinkMode.SHARED.value:
        outcome = submission.match_status or FormSubmissionMatchStatus.LINKED.value
        return submission, _normalize_shared_outcome(outcome)

    if submission.surrogate_id:
        if submission.match_status != FormSubmissionMatchStatus.LINKED.value:
            submission.match_status = FormSubmissionMatchStatus.LINKED.value
            submission.match_reason = submission.match_reason or "already_linked"
            submission.matched_at = submission.matched_at or datetime.now(timezone.utc)
            db.commit()
            db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    # Keep workflow-driven leads stable; do not rematch after a lead is attached.
    if submission.intake_lead_id:
        return submission, FormSubmissionMatchStatus.LEAD_CREATED.value

    form = (
        db.query(Form)
        .filter(
            Form.organization_id == submission.organization_id,
            Form.id == submission.form_id,
        )
        .first()
    )
    if not form:
        raise ValueError("Form not found")

    answers = submission.answers_json if isinstance(submission.answers_json, dict) else {}
    mapping_lookup = _build_form_mapping_lookup(db, submission.form_id)
    if form.purpose == FormPurpose.LEAD_CAPTURE.value:
        identity = _lead_capture_identity(answers=answers, mapping_lookup=mapping_lookup)
    else:
        identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)

    phone_matches = _match_rule_phone(db, org_id=submission.organization_id, identity=identity)
    email_matches: list[Surrogate] = []
    if not phone_matches:
        email_matches = _match_rule_email(db, org_id=submission.organization_id, identity=identity)

    db.query(FormSubmissionMatchCandidate).filter(
        FormSubmissionMatchCandidate.submission_id == submission.id
    ).delete(synchronize_session=False)

    if len(phone_matches) == 1:
        matched = phone_matches[0]
        if _has_existing_submission_for_surrogate_form(
            db,
            org_id=submission.organization_id,
            form_id=submission.form_id,
            surrogate_id=matched.id,
            exclude_submission_id=submission.id,
        ):
            submission.surrogate_id = None
            submission.match_status = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
            submission.match_reason = "existing_submission_for_surrogate"
            submission.matched_at = None
            db.commit()
            db.refresh(submission)
            return submission, FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
        submission.surrogate_id = matched.id
        submission.match_status = FormSubmissionMatchStatus.LINKED.value
        submission.match_reason = "phone_dob_name_exact"
        submission.matched_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    if len(phone_matches) > 1 or len(email_matches) > 1:
        reason = (
            "phone_dob_name_ambiguous" if len(phone_matches) > 1 else "email_dob_name_ambiguous"
        )
        submission.surrogate_id = None
        submission.match_status = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
        submission.match_reason = reason
        submission.matched_at = None
        for surrogate in phone_matches or email_matches:
            db.add(
                FormSubmissionMatchCandidate(
                    organization_id=submission.organization_id,
                    submission_id=submission.id,
                    surrogate_id=surrogate.id,
                    reason=reason,
                )
            )
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value

    if len(email_matches) == 1:
        matched = email_matches[0]
        if _has_existing_submission_for_surrogate_form(
            db,
            org_id=submission.organization_id,
            form_id=submission.form_id,
            surrogate_id=matched.id,
            exclude_submission_id=submission.id,
        ):
            submission.surrogate_id = None
            submission.match_status = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
            submission.match_reason = "existing_submission_for_surrogate"
            submission.matched_at = None
            db.commit()
            db.refresh(submission)
            return submission, FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
        submission.surrogate_id = matched.id
        submission.match_status = FormSubmissionMatchStatus.LINKED.value
        submission.match_reason = "email_dob_name_exact"
        submission.matched_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    submission.surrogate_id = None
    submission.match_status = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
    submission.match_reason = "no_deterministic_match"
    submission.matched_at = None
    db.commit()
    db.refresh(submission)
    return submission, FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value


def create_intake_lead_for_submission(
    db: Session,
    *,
    submission: FormSubmission,
    user_id: uuid.UUID | None,
    source: str | None = None,
    allow_ambiguous: bool = False,
) -> tuple[FormSubmission, IntakeLead | None]:
    """Create or attach an intake lead for a shared submission."""
    if submission.source_mode != FormLinkMode.SHARED.value:
        return submission, None
    if submission.surrogate_id:
        return submission, None

    if not allow_ambiguous:
        has_candidates = (
            db.query(FormSubmissionMatchCandidate.id)
            .filter(FormSubmissionMatchCandidate.submission_id == submission.id)
            .first()
            is not None
        )
        if has_candidates:
            return submission, None

    if submission.intake_lead_id:
        lead = (
            db.query(IntakeLead)
            .filter(
                IntakeLead.organization_id == submission.organization_id,
                IntakeLead.id == submission.intake_lead_id,
            )
            .first()
        )
        if submission.match_status != FormSubmissionMatchStatus.LEAD_CREATED.value:
            submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
            submission.match_reason = "existing_lead_retained"
            submission.matched_at = None
            db.commit()
            db.refresh(submission)
        return submission, lead

    form = (
        db.query(Form)
        .filter(
            Form.organization_id == submission.organization_id,
            Form.id == submission.form_id,
        )
        .first()
    )
    if not form:
        raise ValueError("Form not found")

    link = None
    if submission.intake_link_id:
        link = (
            db.query(FormIntakeLink)
            .filter(
                FormIntakeLink.organization_id == submission.organization_id,
                FormIntakeLink.id == submission.intake_link_id,
            )
            .first()
        )

    answers = submission.answers_json if isinstance(submission.answers_json, dict) else {}
    mapping_lookup = _build_form_mapping_lookup(db, submission.form_id)
    if form.purpose == FormPurpose.LEAD_CAPTURE.value:
        identity = _lead_capture_identity(answers=answers, mapping_lookup=mapping_lookup)
    else:
        identity = _extract_identity(answers=answers, mapping_lookup=mapping_lookup)
    metadata: dict[str, Any] = {"submission_id": str(submission.id)}
    if source:
        metadata["source"] = source
    if link and link.campaign_name:
        metadata["campaign_name"] = link.campaign_name
    if link and link.event_name:
        metadata["event_name"] = link.event_name
    normalized_action_source = source.strip().lower() if isinstance(source, str) else None
    auto_promote_website_lead = (
        normalized_action_source in {None, "form_embed", "website"}
        and link is not None
        and form.purpose == FormPurpose.LEAD_CAPTURE.value
        and link.embed_enabled
    )
    lead_source = "website" if auto_promote_website_lead else (source or "shared_intake")
    metadata.setdefault("source", lead_source)

    lead = _create_intake_lead(
        db,
        org_id=submission.organization_id,
        form=form,
        link=link,
        identity=identity,
        source_metadata=metadata,
        user_id=user_id,
        form_submission_id=submission.id,
        source=lead_source,
    )
    submission.intake_lead_id = lead.id
    submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
    submission.match_reason = (
        "workflow_website_lead_creation"
        if auto_promote_website_lead
        else "workflow_lead_creation"
    )
    submission.matched_at = None
    db.query(FormSubmissionMatchCandidate).filter(
        FormSubmissionMatchCandidate.submission_id == submission.id
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(submission)
    db.refresh(lead)

    if auto_promote_website_lead:
        surrogate, _linked_submission_count = promote_intake_lead(
            db=db,
            lead=lead,
            user_id=user_id,
            source="website",
            is_priority=False,
            assign_to_user=False,
        )
        submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
        submission.match_reason = "workflow_website_lead_creation"
        submission.matched_at = None
        db.commit()
        db.refresh(submission)
        db.refresh(lead)
        db.refresh(surrogate)

    meta_crm_dataset_service.link_website_lead_event_to_intake_lead(
        db,
        organization_id=submission.organization_id,
        submission_id=submission.id,
        intake_lead_id=lead.id,
    )

    _trigger_intake_lead_created_workflow(
        db,
        lead=lead,
        form_id=form.id,
        submission_id=submission.id,
    )
    db.refresh(submission)
    return submission, lead


def get_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    draft_session_id: str,
) -> FormIntakeDraft | None:
    return (
        db.query(FormIntakeDraft)
        .filter(
            FormIntakeDraft.intake_link_id == link.id,
            FormIntakeDraft.draft_session_id == draft_session_id,
        )
        .first()
    )


def get_shared_draft_by_id(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> FormIntakeDraft | None:
    return (
        db.query(FormIntakeDraft)
        .filter(
            FormIntakeDraft.organization_id == org_id,
            FormIntakeDraft.form_id == form_id,
            FormIntakeDraft.id == draft_id,
        )
        .first()
    )


def _apply_draft_identity(
    *,
    draft: FormIntakeDraft,
    identity: dict[str, Any],
) -> None:
    draft.full_name_normalized = identity.get("full_name_normalized")
    draft.date_of_birth = identity.get("date_of_birth")
    draft.email_hash = identity.get("email_hash")
    draft.phone_hash = identity.get("phone_hash")


def lookup_shared_resume_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    answers: dict[str, Any],
    current_draft_session_id: str | None = None,
) -> dict[str, Any]:
    mapping_lookup = _build_form_mapping_lookup(db, form.id)
    identity = _extract_identity_partial(answers=answers, mapping_lookup=mapping_lookup)
    full_name_normalized = identity.get("full_name_normalized")
    date_of_birth = identity.get("date_of_birth")
    email_hash = identity.get("email_hash")
    phone_hash = identity.get("phone_hash")

    if not full_name_normalized or not date_of_birth or (not email_hash and not phone_hash):
        return {"status": "insufficient_identity"}

    window_days = max(1, int(settings.FORMS_SHARED_DRAFT_RESUME_WINDOW_DAYS or 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    query = db.query(FormIntakeDraft).filter(
        FormIntakeDraft.organization_id == link.organization_id,
        FormIntakeDraft.form_id == form.id,
        FormIntakeDraft.full_name_normalized == full_name_normalized,
        FormIntakeDraft.date_of_birth == date_of_birth,
        FormIntakeDraft.updated_at >= cutoff,
    )
    if current_draft_session_id:
        query = query.filter(FormIntakeDraft.draft_session_id != current_draft_session_id)

    contact_filters: list[Any] = []
    if email_hash:
        contact_filters.append(FormIntakeDraft.email_hash == email_hash)
    if phone_hash:
        contact_filters.append(FormIntakeDraft.phone_hash == phone_hash)
    if not contact_filters:
        return {"status": "insufficient_identity"}

    query = query.filter(or_(*contact_filters))
    matched = query.order_by(
        FormIntakeDraft.updated_at.desc(), FormIntakeDraft.created_at.desc()
    ).first()
    if not matched:
        return {"status": "no_match"}

    reason = "name_dob_phone"
    if email_hash and matched.email_hash == email_hash:
        reason = "name_dob_email"
    elif phone_hash and matched.phone_hash == phone_hash:
        reason = "name_dob_phone"

    return {
        "status": "match_found",
        "source_draft_id": matched.id,
        "updated_at": matched.updated_at,
        "match_reason": reason,
    }


def restore_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    draft_session_id: str,
    source_draft_id: uuid.UUID,
) -> FormIntakeDraft:
    source_draft = get_shared_draft_by_id(
        db,
        org_id=link.organization_id,
        form_id=form.id,
        draft_id=source_draft_id,
    )
    if not source_draft:
        raise ValueError("Source draft not found")

    target = get_shared_draft(db, link=link, draft_session_id=draft_session_id)
    now = datetime.now(timezone.utc)
    if not target:
        target = FormIntakeDraft(
            organization_id=link.organization_id,
            intake_link_id=link.id,
            form_id=form.id,
            draft_session_id=draft_session_id,
            answers_json={},
        )
        db.add(target)
        db.flush()

    target.answers_json = dict(source_draft.answers_json or {})
    target.started_at = source_draft.started_at or target.started_at
    target.updated_at = now
    target.full_name_normalized = source_draft.full_name_normalized
    target.date_of_birth = source_draft.date_of_birth
    target.email_hash = source_draft.email_hash
    target.phone_hash = source_draft.phone_hash

    if target.started_at is None and any(
        v not in (None, "", [], {}) for v in target.answers_json.values()
    ):
        target.started_at = now

    db.commit()
    db.refresh(target)
    return target


def clear_shared_drafts_for_identity(
    db: Session,
    *,
    org_id: uuid.UUID,
    form_id: uuid.UUID,
    identity: dict[str, Any],
) -> int:
    full_name_normalized = identity.get("full_name_normalized")
    date_of_birth = identity.get("date_of_birth")
    email_hash = identity.get("email_hash")
    phone_hash = identity.get("phone_hash")

    if not full_name_normalized or not date_of_birth:
        return 0
    contact_filters: list[Any] = []
    if email_hash:
        contact_filters.append(FormIntakeDraft.email_hash == email_hash)
    if phone_hash:
        contact_filters.append(FormIntakeDraft.phone_hash == phone_hash)
    if not contact_filters:
        return 0

    deleted = (
        db.query(FormIntakeDraft)
        .filter(
            FormIntakeDraft.organization_id == org_id,
            FormIntakeDraft.form_id == form_id,
            FormIntakeDraft.full_name_normalized == full_name_normalized,
            FormIntakeDraft.date_of_birth == date_of_birth,
        )
        .filter(or_(*contact_filters))
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def upsert_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    form: Form,
    draft_session_id: str,
    answers: dict[str, Any],
) -> FormIntakeDraft:
    if form.status != FormStatus.PUBLISHED.value:
        raise ValueError("Form is not published")
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object")
    if not form.published_schema_json:
        raise ValueError("Published form schema missing")

    schema = form_submission_service.parse_schema(form.published_schema_json)
    fields = form_submission_service.flatten_fields(schema)
    for key in answers:
        if key not in fields:
            raise ValueError(f"Unknown field key: {key}")

    for key, value in answers.items():
        if value in (None, ""):
            continue
        form_submission_service._validate_field_value(fields[key], value)  # type: ignore[attr-defined]

    draft = get_shared_draft(db, link=link, draft_session_id=draft_session_id)
    now = datetime.now(timezone.utc)
    if not draft:
        draft = FormIntakeDraft(
            organization_id=link.organization_id,
            intake_link_id=link.id,
            form_id=form.id,
            draft_session_id=draft_session_id,
            answers_json={},
        )
        db.add(draft)
        db.flush()

    merged = dict(draft.answers_json or {})
    merged.update(answers)
    draft.answers_json = merged
    mapping_lookup = _build_form_mapping_lookup(db, form.id)
    partial_identity = _extract_identity_partial(answers=merged, mapping_lookup=mapping_lookup)
    _apply_draft_identity(draft=draft, identity=partial_identity)
    draft.updated_at = now
    if draft.started_at is None and any(v not in (None, "", [], {}) for v in merged.values()):
        draft.started_at = now

    db.commit()
    db.refresh(draft)
    return draft


def delete_shared_draft(
    db: Session,
    *,
    link: FormIntakeLink,
    draft_session_id: str,
) -> bool:
    draft = get_shared_draft(db, link=link, draft_session_id=draft_session_id)
    if not draft:
        return False
    db.delete(draft)
    db.commit()
    return True


def list_match_candidates(
    db: Session,
    *,
    org_id: uuid.UUID,
    submission_id: uuid.UUID,
) -> list[FormSubmissionMatchCandidate]:
    return (
        db.query(FormSubmissionMatchCandidate)
        .filter(
            FormSubmissionMatchCandidate.organization_id == org_id,
            FormSubmissionMatchCandidate.submission_id == submission_id,
        )
        .order_by(FormSubmissionMatchCandidate.created_at.asc())
        .all()
    )


def resolve_submission_match(
    db: Session,
    *,
    submission: FormSubmission,
    surrogate_id: uuid.UUID | None,
    create_intake_lead: bool,
    reviewer_id: uuid.UUID | None,
    review_notes: str | None = None,
) -> tuple[FormSubmission, str]:
    if submission.source_mode != FormLinkMode.SHARED.value:
        raise ValueError("Only shared submissions can be match-resolved")

    if surrogate_id:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == submission.organization_id,
                Surrogate.id == surrogate_id,
            )
            .first()
        )
        if not surrogate:
            raise ValueError("Surrogate not found")
        submission.surrogate_id = surrogate.id
        submission.match_status = FormSubmissionMatchStatus.LINKED.value
        submission.match_reason = "manually_linked"
        submission.matched_at = datetime.now(timezone.utc)
        if review_notes is not None:
            submission.review_notes = review_notes.strip() or None
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id == submission.id
        ).delete(synchronize_session=False)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LINKED.value

    if not create_intake_lead:
        raise ValueError("Provide surrogate_id or set create_intake_lead=true")

    if submission.intake_lead_id:
        submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
        submission.match_reason = "existing_lead_retained"
        submission.matched_at = None
        if review_notes is not None:
            submission.review_notes = review_notes.strip() or None
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id == submission.id
        ).delete(synchronize_session=False)
        db.commit()
        db.refresh(submission)
        return submission, FormSubmissionMatchStatus.LEAD_CREATED.value

    submission, _ = create_intake_lead_for_submission(
        db=db,
        submission=submission,
        user_id=reviewer_id,
        source="manual_review_resolution",
        allow_ambiguous=True,
    )
    submission.match_reason = "manual_lead_creation"
    if review_notes is not None:
        submission.review_notes = review_notes.strip() or None
    db.commit()
    db.refresh(submission)
    return submission, _normalize_shared_outcome(submission.match_status)


def retry_submission_match(
    db: Session,
    *,
    submission: FormSubmission,
    unlink_surrogate: bool,
    unlink_intake_lead: bool,
    rerun_auto_match: bool,
    create_intake_lead_if_unmatched: bool,
    reviewer_id: uuid.UUID | None,
    review_notes: str | None = None,
) -> tuple[FormSubmission, str]:
    """Reset and optionally reprocess matching for a shared submission."""
    if submission.source_mode != FormLinkMode.SHARED.value:
        raise ValueError("Only shared submissions can be reprocessed")
    if submission.status != FormSubmissionStatus.PENDING_REVIEW.value:
        raise ValueError("Only pending_review submissions can be reprocessed")

    previous_lead: IntakeLead | None = None
    if submission.intake_lead_id:
        previous_lead = (
            db.query(IntakeLead)
            .filter(
                IntakeLead.organization_id == submission.organization_id,
                IntakeLead.id == submission.intake_lead_id,
            )
            .first()
        )

    if unlink_surrogate:
        submission.surrogate_id = None
    if unlink_intake_lead:
        submission.intake_lead_id = None

    db.query(FormSubmissionMatchCandidate).filter(
        FormSubmissionMatchCandidate.submission_id == submission.id
    ).delete(synchronize_session=False)

    submission.match_status = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
    submission.match_reason = "manual_retry_reset"
    submission.matched_at = None
    if review_notes is not None:
        submission.review_notes = review_notes.strip() or None
    db.commit()
    db.refresh(submission)

    outcome = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
    if rerun_auto_match:
        submission, outcome = auto_match_submission(db=db, submission=submission)

    if (
        create_intake_lead_if_unmatched
        and outcome == FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
        and not submission.surrogate_id
        and not submission.intake_lead_id
    ):
        if (
            previous_lead
            and previous_lead.status == IntakeLeadStatus.PROMOTED.value
            and previous_lead.promoted_surrogate_id
        ):
            submission.match_reason = "manual_retry_requires_manual_link"
            if review_notes is not None:
                submission.review_notes = review_notes.strip() or None
            db.commit()
            db.refresh(submission)
            outcome = FormSubmissionMatchStatus.AMBIGUOUS_REVIEW.value
        elif (
            previous_lead
            and previous_lead.status == IntakeLeadStatus.PENDING_REVIEW.value
            and not previous_lead.promoted_surrogate_id
        ):
            submission.intake_lead_id = previous_lead.id
            submission.match_status = FormSubmissionMatchStatus.LEAD_CREATED.value
            submission.match_reason = "existing_lead_relinked"
            submission.matched_at = None
            if review_notes is not None:
                submission.review_notes = review_notes.strip() or None
            db.query(FormSubmissionMatchCandidate).filter(
                FormSubmissionMatchCandidate.submission_id == submission.id
            ).delete(synchronize_session=False)
            db.commit()
            db.refresh(submission)
            outcome = FormSubmissionMatchStatus.LEAD_CREATED.value
        else:
            submission, _ = create_intake_lead_for_submission(
                db=db,
                submission=submission,
                user_id=reviewer_id,
                source="manual_retry_resolution",
                allow_ambiguous=False,
            )
            submission.match_reason = "manual_retry_lead_creation"
            if review_notes is not None:
                submission.review_notes = review_notes.strip() or None
            db.commit()
            db.refresh(submission)
            outcome = _normalize_shared_outcome(submission.match_status)

    return submission, outcome


def get_intake_lead(
    db: Session,
    *,
    org_id: uuid.UUID,
    lead_id: uuid.UUID,
) -> IntakeLead | None:
    return (
        db.query(IntakeLead)
        .filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id == lead_id,
        )
        .first()
    )


def promote_intake_lead(
    db: Session,
    *,
    lead: IntakeLead,
    user_id: uuid.UUID | None,
    source: str | None = None,
    is_priority: bool = False,
    assign_to_user: bool | None = None,
) -> tuple[Surrogate, int]:
    if lead.status == IntakeLeadStatus.PROMOTED.value and lead.promoted_surrogate_id:
        surrogate = (
            db.query(Surrogate)
            .filter(
                Surrogate.organization_id == lead.organization_id,
                Surrogate.id == lead.promoted_surrogate_id,
            )
            .first()
        )
        if surrogate:
            linked_count = (
                db.query(FormSubmission)
                .filter(
                    FormSubmission.intake_lead_id == lead.id,
                    FormSubmission.surrogate_id == surrogate.id,
                )
                .count()
            )
            return surrogate, linked_count

    if not lead.email:
        raise ValueError("Intake lead is missing email")

    mapped_payload: dict[str, Any] = {}
    linked_submissions = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == lead.organization_id,
            or_(
                FormSubmission.intake_lead_id == lead.id,
                FormSubmission.id == lead.form_submission_id,
            ),
        )
        .order_by(FormSubmission.submitted_at.asc())
        .all()
    )
    for submission in linked_submissions:
        mapped_payload.update(
            form_submission_service.build_surrogate_updates_for_submission(
                db,
                submission,
                strict=False,
            )
        )

    source_value = source or "manual"
    mapped_payload.update(
        {
            "full_name": lead.full_name,
            "email": lead.email,
            "phone": lead.phone,
            "date_of_birth": lead.date_of_birth,
            "source": source_value,
            "is_priority": is_priority,
            "assign_to_user": assign_to_user,
        }
    )
    surrogate_payload, dropped_invalid_fields = (
        surrogate_input_normalization_service.build_surrogate_create_from_payload(
            mapped_payload,
            lenient=True,
        )
    )
    from app.services import surrogate_service

    surrogate = surrogate_service.create_surrogate(
        db=db,
        org_id=lead.organization_id,
        user_id=user_id,
        data=surrogate_payload,
    )
    if dropped_invalid_fields:
        surrogate.import_metadata = {
            **(surrogate.import_metadata or {}),
            "dropped_invalid_submission_fields": dropped_invalid_fields,
        }

    lead.status = IntakeLeadStatus.PROMOTED.value
    lead.promoted_surrogate_id = surrogate.id
    lead.promoted_at = datetime.now(timezone.utc)

    linked_count = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == lead.organization_id,
            FormSubmission.intake_lead_id == lead.id,
            FormSubmission.surrogate_id.is_(None),
        )
        .update(
            {
                FormSubmission.surrogate_id: surrogate.id,
                FormSubmission.match_status: FormSubmissionMatchStatus.LINKED.value,
                FormSubmission.match_reason: "lead_promoted_to_surrogate",
                FormSubmission.matched_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    submission_ids = [
        row[0]
        for row in db.query(FormSubmission.id)
        .filter(FormSubmission.intake_lead_id == lead.id)
        .all()
    ]
    if submission_ids:
        db.query(FormSubmissionMatchCandidate).filter(
            FormSubmissionMatchCandidate.submission_id.in_(submission_ids)
        ).delete(synchronize_session=False)

    db.commit()
    db.refresh(lead)
    return surrogate, int(linked_count or 0)
