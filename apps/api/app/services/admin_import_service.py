"""Developer-only import helpers for org restore."""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import OwnerType
from app.db.models import (
    AISettings,
    AppointmentType,
    Attachment,
    AutomationWorkflow,
    AvailabilityOverride,
    AvailabilityRule,
    BookingLink,
    DataRetentionPolicy,
    Donor,
    DonorStatusHistory,
    EmailTemplate,
    Form,
    FormFieldMapping,
    FormLogo,
    LegalHold,
    Membership,
    MetaLead,
    MetaPageMapping,
    Organization,
    OrgCounter,
    Pipeline,
    PipelineStage,
    Queue,
    QueueMember,
    RolePermission,
    Surrogate,
    User,
    UserIntegration,
    UserNotificationSettings,
    UserPermissionOverride,
    WorkflowTemplate,
)
from app.services import attachment_service
from app.services.import_transformers import transform_height_flexible, transform_int_flexible
from app.utils.height import canonicalize_height_ft
from app.utils.journey_timing import normalize_journey_timing_preference
from app.utils.normalization import (
    extract_email_domain,
    extract_phone_last4,
    normalize_email,
    normalize_identifier,
    normalize_phone,
    normalize_search_text,
)

LEGACY_WORKFLOW_SUBJECT_TYPES = {
    "form_submitted": "form_submission",
    "intake_lead_created": "intake_lead",
    "match_proposed": "match",
    "match_accepted": "match",
    "match_rejected": "match",
    "appointment_scheduled": "appointment",
    "appointment_completed": "appointment",
}

DONOR_PHOTO_BASE64_FIELD_LIMIT = (
    (attachment_service.MAX_FILE_SIZE_BYTES + 2) // 3
) * 4
MAX_DONOR_STATUS_HISTORY_JSON_BYTES = 1_048_576
MIN_DONOR_NUMBER_VALUE = 10_001


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    return UUID(value)


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.lower() in ("true", "1", "yes", "y")


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    transformed = transform_int_flexible(value)
    if transformed.success:
        return transformed.value
    return int(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return canonicalize_height_ft(Decimal(value))
    except Exception:
        pass
    transformed = transform_height_flexible(value)
    if transformed.success and transformed.value is not None:
        return transformed.value
    return canonicalize_height_ft(Decimal(value))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_json(value: str | None) -> dict | list | None:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed or trimmed.lower() == "null":
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _load_json(archive: zipfile.ZipFile, name: str, default: Any) -> Any:
    if name not in archive.namelist():
        return default
    with archive.open(name) as handle:
        return json.loads(handle.read().decode("utf-8"))


def _ensure_empty_org(db: Session, org_id: UUID) -> None:
    checks = {
        "donors": db.scalar(
            select(func.count(1)).select_from(Donor).where(Donor.organization_id == org_id)
        )
        or 0,
        "surrogates": db.scalar(
            select(func.count(1)).select_from(Surrogate).where(Surrogate.organization_id == org_id)
        )
        or 0,
        "forms": db.scalar(
            select(func.count(1)).select_from(Form).where(Form.organization_id == org_id)
        )
        or 0,
        "form_logos": db.scalar(
            select(func.count(1)).select_from(FormLogo).where(FormLogo.organization_id == org_id)
        )
        or 0,
        "form_field_mappings": db.scalar(
            select(func.count(1))
            .select_from(FormFieldMapping)
            .join(Form, FormFieldMapping.form_id == Form.id)
            .where(Form.organization_id == org_id)
        )
        or 0,
        "appointment_types": db.scalar(
            select(func.count(1))
            .select_from(AppointmentType)
            .where(AppointmentType.organization_id == org_id)
        )
        or 0,
        "availability_rules": db.scalar(
            select(func.count(1))
            .select_from(AvailabilityRule)
            .where(AvailabilityRule.organization_id == org_id)
        )
        or 0,
        "availability_overrides": db.scalar(
            select(func.count(1))
            .select_from(AvailabilityOverride)
            .where(AvailabilityOverride.organization_id == org_id)
        )
        or 0,
        "booking_links": db.scalar(
            select(func.count(1))
            .select_from(BookingLink)
            .where(BookingLink.organization_id == org_id)
        )
        or 0,
        "pipelines": db.scalar(
            select(func.count(1)).select_from(Pipeline).where(Pipeline.organization_id == org_id)
        )
        or 0,
        "pipeline_stages": db.scalar(
            select(func.count(1))
            .select_from(PipelineStage)
            .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
            .where(Pipeline.organization_id == org_id)
        )
        or 0,
        "workflows": db.scalar(
            select(func.count(1))
            .select_from(AutomationWorkflow)
            .where(AutomationWorkflow.organization_id == org_id)
        )
        or 0,
        "workflow_templates": db.scalar(
            select(func.count(1))
            .select_from(WorkflowTemplate)
            .where(WorkflowTemplate.organization_id == org_id)
        )
        or 0,
        "email_templates": db.scalar(
            select(func.count(1))
            .select_from(EmailTemplate)
            .where(EmailTemplate.organization_id == org_id)
        )
        or 0,
        "meta_leads": db.scalar(
            select(func.count(1)).select_from(MetaLead).where(MetaLead.organization_id == org_id)
        )
        or 0,
        "queues": db.scalar(
            select(func.count(1)).select_from(Queue).where(Queue.organization_id == org_id)
        )
        or 0,
        "queue_members": db.scalar(
            select(func.count(1))
            .select_from(QueueMember)
            .join(Queue, QueueMember.queue_id == Queue.id)
            .where(Queue.organization_id == org_id)
        )
        or 0,
        "notification_settings": db.scalar(
            select(func.count(1))
            .select_from(UserNotificationSettings)
            .where(UserNotificationSettings.organization_id == org_id)
        )
        or 0,
        "integrations": db.scalar(
            select(func.count(1))
            .select_from(UserIntegration)
            .join(User, UserIntegration.user_id == User.id)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == org_id)
        )
        or 0,
        "ai_settings": db.scalar(
            select(func.count(1))
            .select_from(AISettings)
            .where(AISettings.organization_id == org_id)
        )
        or 0,
        "meta_pages": db.scalar(
            select(func.count(1))
            .select_from(MetaPageMapping)
            .where(MetaPageMapping.organization_id == org_id)
        )
        or 0,
    }

    blocking = {key: value for key, value in checks.items() if value}
    if blocking:
        raise ValueError(f"Organization is not empty: {blocking}")


def import_org_config_zip(
    db: Session,
    org_id: UUID,
    content: bytes,
    *,
    commit: bool = True,
) -> dict[str, int]:
    _ensure_empty_org(db, org_id)

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        organization_payload = _load_json(archive, "organization.json", None)
        users_payload = _load_json(archive, "users.json", [])
        memberships_payload = _load_json(archive, "memberships.json", [])
        queues_payload = _load_json(archive, "queues.json", [])
        queue_members_payload = _load_json(archive, "queue_members.json", [])
        role_permissions_payload = _load_json(archive, "role_permissions.json", [])
        user_overrides_payload = _load_json(archive, "user_permission_overrides.json", [])
        pipelines_payload = _load_json(archive, "pipelines.json", [])
        templates_payload = _load_json(archive, "email_templates.json", [])
        workflows_payload = _load_json(archive, "workflows.json", [])
        notification_payload = _load_json(archive, "notification_settings.json", [])
        meta_pages_payload = _load_json(archive, "meta_pages.json", [])
        integrations_payload = _load_json(archive, "integrations.json", [])
        ai_settings_payload = _load_json(archive, "ai_settings.json", None)
        forms_payload = _load_json(archive, "forms.json", [])
        form_logos_payload = _load_json(archive, "form_logos.json", [])
        form_field_mappings_payload = _load_json(archive, "form_field_mappings.json", [])
        appointment_types_payload = _load_json(archive, "appointment_types.json", [])
        availability_rules_payload = _load_json(archive, "availability_rules.json", [])
        availability_overrides_payload = _load_json(archive, "availability_overrides.json", [])
        booking_links_payload = _load_json(archive, "booking_links.json", [])
        workflow_templates_payload = _load_json(archive, "workflow_templates.json", [])
        retention_policies_payload = _load_json(archive, "data_retention_policies.json", [])
        legal_holds_payload = _load_json(archive, "legal_holds.json", [])
        org_counters_payload = _load_json(archive, "org_counters.json", [])

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")

    if organization_payload:
        org.name = organization_payload.get("name", org.name)
        org.slug = organization_payload.get("slug", org.slug)
        org.timezone = organization_payload.get("timezone", org.timezone)
        org.ai_enabled = organization_payload.get("ai_enabled", org.ai_enabled)
        if organization_payload.get("current_version"):
            org.current_version = organization_payload["current_version"]
        # Note: portal_domain is no longer supported - URLs are computed from slug
        if "signature_template" in organization_payload:
            org.signature_template = organization_payload.get("signature_template")
        if "signature_logo_url" in organization_payload:
            org.signature_logo_url = organization_payload.get("signature_logo_url")
        if "signature_primary_color" in organization_payload:
            org.signature_primary_color = organization_payload.get("signature_primary_color")
        if "signature_company_name" in organization_payload:
            org.signature_company_name = organization_payload.get("signature_company_name")
        if "signature_address" in organization_payload:
            org.signature_address = organization_payload.get("signature_address")
        if "signature_phone" in organization_payload:
            org.signature_phone = organization_payload.get("signature_phone")
        if "signature_website" in organization_payload:
            org.signature_website = organization_payload.get("signature_website")
        if "signature_social_links" in organization_payload:
            org.signature_social_links = organization_payload.get("signature_social_links")
        if "signature_disclaimer" in organization_payload:
            org.signature_disclaimer = organization_payload.get("signature_disclaimer")

    export_user_ids = {UUID(item["id"]) for item in users_payload if item.get("id")}
    export_emails = {item.get("email", "").lower() for item in users_payload if item.get("email")}

    # Consolidate into single query (avoids 2 separate queries)
    all_users = (
        db.query(User)
        .filter(User.id.in_(export_user_ids) | func.lower(User.email).in_(export_emails))
        .all()
    )
    existing_users_by_id = {user.id: user for user in all_users}
    existing_users_by_email = {user.email.lower(): user for user in all_users if user.email}

    user_id_map: dict[UUID, UUID] = {}

    for user_data in users_payload:
        user_id = UUID(user_data["id"])
        email = user_data.get("email", "").lower()
        if not email:
            raise ValueError("User email is required in export")

        existing_by_email = existing_users_by_email.get(email)
        if existing_by_email and existing_by_email.id != user_id:
            user_id_map[user_id] = existing_by_email.id
            user = existing_by_email
        else:
            user_id_map[user_id] = user_id
            user = existing_users_by_id.get(user_id)

        if user:
            user.email = user_data.get("email", user.email)
            user.display_name = user_data.get("display_name", user.display_name)
            user.avatar_url = user_data.get("avatar_url")
            user.is_active = user_data.get("is_active", user.is_active)
            user.phone = user_data.get("phone")
            user.title = user_data.get("title")
            user.signature_name = user_data.get("signature_name")
            user.signature_title = user_data.get("signature_title")
            user.signature_phone = user_data.get("signature_phone")
            user.signature_photo_url = user_data.get("signature_photo_url")
            user.signature_linkedin = user_data.get("signature_linkedin")
            user.signature_twitter = user_data.get("signature_twitter")
            user.signature_instagram = user_data.get("signature_instagram")
        else:
            user = User(
                id=user_id,
                email=user_data.get("email"),
                display_name=user_data.get("display_name"),
                avatar_url=user_data.get("avatar_url"),
                is_active=user_data.get("is_active", True),
                phone=user_data.get("phone"),
                title=user_data.get("title"),
                signature_name=user_data.get("signature_name"),
                signature_title=user_data.get("signature_title"),
                signature_phone=user_data.get("signature_phone"),
                signature_photo_url=user_data.get("signature_photo_url"),
                signature_linkedin=user_data.get("signature_linkedin"),
                signature_twitter=user_data.get("signature_twitter"),
                signature_instagram=user_data.get("signature_instagram"),
                created_at=_parse_datetime(user_data.get("created_at")) or datetime.now(UTC),
                updated_at=_parse_datetime(user_data.get("updated_at")) or datetime.now(UTC),
            )
            db.add(user)

    db.flush()

    def _map_user_id(value: UUID | None) -> UUID | None:
        if not value:
            return None
        return user_id_map.get(value, value)

    existing_memberships_by_user = {
        membership.user_id: membership
        for membership in db.query(Membership).filter(Membership.organization_id == org_id).all()
    }

    for membership_data in memberships_payload:
        export_user_id = UUID(membership_data["user_id"])
        user_id = _map_user_id(export_user_id)
        if not user_id:
            raise ValueError("Membership user_id is required")
        membership = existing_memberships_by_user.get(user_id)
        if membership:
            membership.role = membership_data.get("role", membership.role)
            membership.is_active = membership_data.get("is_active", membership.is_active)
        else:
            membership = Membership(
                id=UUID(membership_data["id"]),
                user_id=user_id,
                organization_id=org_id,
                role=membership_data.get("role"),
                is_active=membership_data.get("is_active", True),
                created_at=_parse_datetime(membership_data.get("created_at")) or datetime.now(UTC),
            )
            db.add(membership)

    for queue_data in queues_payload:
        queue = Queue(
            id=UUID(queue_data["id"]),
            organization_id=org_id,
            name=queue_data.get("name"),
            description=queue_data.get("description"),
            is_active=queue_data.get("is_active", True),
            created_at=_parse_datetime(queue_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(queue_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(queue)

    for queue_member_data in queue_members_payload:
        member = QueueMember(
            id=UUID(queue_member_data["id"]),
            queue_id=UUID(queue_member_data["queue_id"]),
            user_id=_map_user_id(UUID(queue_member_data["user_id"])),
            created_at=_parse_datetime(queue_member_data.get("created_at")) or datetime.now(UTC),
        )
        db.add(member)

    for pipeline_data in pipelines_payload:
        pipeline = Pipeline(
            id=UUID(pipeline_data["id"]),
            organization_id=org_id,
            entity_type=pipeline_data.get("entity_type", "surrogate"),
            name=pipeline_data.get("name"),
            is_default=pipeline_data.get("is_default", False),
            current_version=pipeline_data.get("current_version") or 1,
            feature_config=pipeline_data.get("feature_config") or {},
            created_at=_parse_datetime(pipeline_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(pipeline_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(pipeline)
        for stage_data in pipeline_data.get("stages", []):
            stage = PipelineStage(
                id=UUID(stage_data["id"]),
                pipeline_id=pipeline.id,
                stage_key=stage_data.get("stage_key") or stage_data.get("slug"),
                slug=stage_data.get("slug"),
                label=stage_data.get("label"),
                color=stage_data.get("color"),
                order=stage_data.get("order") or 1,
                stage_type=stage_data.get("stage_type"),
                semantics=stage_data.get("semantics") or {},
                is_active=stage_data.get("is_active", True),
                is_intake_stage=stage_data.get("is_intake_stage", False),
                allowed_next_slugs=stage_data.get("allowed_next_slugs"),
                deleted_at=_parse_datetime(stage_data.get("deleted_at")),
                created_at=_parse_datetime(stage_data.get("created_at")) or datetime.now(UTC),
                updated_at=_parse_datetime(stage_data.get("updated_at")) or datetime.now(UTC),
            )
            db.add(stage)

    for template_data in templates_payload:
        template = EmailTemplate(
            id=UUID(template_data["id"]),
            organization_id=org_id,
            created_by_user_id=_map_user_id(_parse_uuid(template_data.get("created_by_user_id"))),
            name=template_data.get("name"),
            subject=template_data.get("subject"),
            from_email=template_data.get("from_email"),
            body=template_data.get("body"),
            is_active=template_data.get("is_active", True),
            is_system_template=template_data.get("is_system_template", False),
            system_key=template_data.get("system_key"),
            category=template_data.get("category"),
            current_version=template_data.get("current_version") or 1,
            created_at=_parse_datetime(template_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(template_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(template)

    for workflow_data in workflows_payload:
        workflow = AutomationWorkflow(
            id=UUID(workflow_data["id"]),
            organization_id=org_id,
            name=workflow_data.get("name"),
            description=workflow_data.get("description"),
            icon=workflow_data.get("icon", "workflow"),
            schema_version=workflow_data.get("schema_version") or 1,
            trigger_type=workflow_data.get("trigger_type"),
            subject_type=workflow_data.get("subject_type")
            or LEGACY_WORKFLOW_SUBJECT_TYPES.get(
                workflow_data.get("trigger_type"), "surrogate"
            ),
            trigger_config=workflow_data.get("trigger_config") or {},
            conditions=workflow_data.get("conditions") or [],
            condition_logic=workflow_data.get("condition_logic", "AND"),
            actions=workflow_data.get("actions") or [],
            is_enabled=workflow_data.get("is_enabled", True),
            run_count=workflow_data.get("run_count") or 0,
            last_run_at=_parse_datetime(workflow_data.get("last_run_at")),
            last_error=workflow_data.get("last_error"),
            recurrence_mode=workflow_data.get("recurrence_mode", "one_time"),
            recurrence_interval_hours=workflow_data.get("recurrence_interval_hours"),
            recurrence_stop_on_status=workflow_data.get("recurrence_stop_on_status"),
            rate_limit_per_hour=workflow_data.get("rate_limit_per_hour"),
            rate_limit_per_entity_per_day=workflow_data.get("rate_limit_per_entity_per_day"),
            is_system_workflow=workflow_data.get("is_system_workflow", False),
            system_key=workflow_data.get("system_key"),
            requires_review=workflow_data.get("requires_review", False),
            reviewed_at=_parse_datetime(workflow_data.get("reviewed_at")),
            reviewed_by_user_id=_map_user_id(_parse_uuid(workflow_data.get("reviewed_by_user_id"))),
            created_by_user_id=_map_user_id(_parse_uuid(workflow_data.get("created_by_user_id"))),
            updated_by_user_id=_map_user_id(_parse_uuid(workflow_data.get("updated_by_user_id"))),
            created_at=_parse_datetime(workflow_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(workflow_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(workflow)

    for form_data in forms_payload:
        schema_json = form_data.get("schema_json")
        if isinstance(schema_json, str):
            schema_json = _parse_json(schema_json)
        published_schema_json = form_data.get("published_schema_json")
        if isinstance(published_schema_json, str):
            published_schema_json = _parse_json(published_schema_json)
        allowed_mime_types = form_data.get("allowed_mime_types")
        if isinstance(allowed_mime_types, str):
            allowed_mime_types = _parse_json(allowed_mime_types)

        form = Form(
            id=UUID(form_data["id"]),
            organization_id=org_id,
            name=form_data.get("name"),
            description=form_data.get("description"),
            status=form_data.get("status"),
            purpose=form_data.get("purpose", "surrogate_application"),
            lead_kind=form_data.get("lead_kind", "surrogate"),
            schema_json=schema_json,
            published_schema_json=published_schema_json,
            max_file_size_bytes=form_data.get("max_file_size_bytes"),
            max_file_count=form_data.get("max_file_count"),
            allowed_mime_types=allowed_mime_types,
            default_application_email_template_id=_parse_uuid(
                form_data.get("default_application_email_template_id")
            ),
            created_by_user_id=_map_user_id(_parse_uuid(form_data.get("created_by_user_id"))),
            updated_by_user_id=_map_user_id(_parse_uuid(form_data.get("updated_by_user_id"))),
            created_at=_parse_datetime(form_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(form_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(form)

    for logo_data in form_logos_payload:
        logo = FormLogo(
            id=UUID(logo_data["id"]),
            organization_id=org_id,
            storage_key=logo_data.get("storage_key"),
            filename=logo_data.get("filename"),
            content_type=logo_data.get("content_type"),
            file_size=logo_data.get("file_size"),
            created_by_user_id=_map_user_id(_parse_uuid(logo_data.get("created_by_user_id"))),
            created_at=_parse_datetime(logo_data.get("created_at")) or datetime.now(UTC),
        )
        db.add(logo)

    for mapping_data in form_field_mappings_payload:
        mapping = FormFieldMapping(
            id=UUID(mapping_data["id"]),
            form_id=UUID(mapping_data["form_id"]),
            field_key=mapping_data.get("field_key"),
            surrogate_field=mapping_data.get("surrogate_field"),
            created_at=_parse_datetime(mapping_data.get("created_at")) or datetime.now(UTC),
        )
        db.add(mapping)

    for appointment_type_data in appointment_types_payload:
        appointment_type = AppointmentType(
            id=UUID(appointment_type_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(appointment_type_data["user_id"])),
            name=appointment_type_data.get("name"),
            slug=appointment_type_data.get("slug"),
            description=appointment_type_data.get("description"),
            duration_minutes=appointment_type_data.get("duration_minutes") or 30,
            buffer_before_minutes=appointment_type_data.get("buffer_before_minutes") or 0,
            buffer_after_minutes=appointment_type_data.get("buffer_after_minutes") or 0,
            meeting_mode=appointment_type_data.get("meeting_mode"),
            meeting_modes=appointment_type_data.get("meeting_modes")
            or (
                [appointment_type_data.get("meeting_mode")]
                if appointment_type_data.get("meeting_mode")
                else None
            ),
            meeting_location=appointment_type_data.get("meeting_location"),
            dial_in_number=appointment_type_data.get("dial_in_number"),
            auto_approve=appointment_type_data.get("auto_approve", False),
            reminder_hours_before=appointment_type_data.get("reminder_hours_before") or 24,
            is_active=appointment_type_data.get("is_active", True),
            created_at=_parse_datetime(appointment_type_data.get("created_at"))
            or datetime.now(UTC),
            updated_at=_parse_datetime(appointment_type_data.get("updated_at"))
            or datetime.now(UTC),
        )
        db.add(appointment_type)

    for rule_data in availability_rules_payload:
        rule = AvailabilityRule(
            id=UUID(rule_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(rule_data["user_id"])),
            day_of_week=rule_data.get("day_of_week") or 0,
            start_time=_parse_time(rule_data.get("start_time")) or time(9, 0),
            end_time=_parse_time(rule_data.get("end_time")) or time(17, 0),
            timezone=rule_data.get("timezone") or "America/Los_Angeles",
            created_at=_parse_datetime(rule_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(rule_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(rule)

    for override_data in availability_overrides_payload:
        override = AvailabilityOverride(
            id=UUID(override_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(override_data["user_id"])),
            override_date=_parse_date(override_data.get("override_date")) or date.today(),
            is_unavailable=override_data.get("is_unavailable", True),
            start_time=_parse_time(override_data.get("start_time")),
            end_time=_parse_time(override_data.get("end_time")),
            reason=override_data.get("reason"),
            created_at=_parse_datetime(override_data.get("created_at")) or datetime.now(UTC),
        )
        db.add(override)

    for link_data in booking_links_payload:
        link = BookingLink(
            id=UUID(link_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(link_data["user_id"])),
            public_slug=link_data.get("public_slug"),
            is_active=link_data.get("is_active", True),
            created_at=_parse_datetime(link_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(link_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(link)

    for template_data in workflow_templates_payload:
        template = WorkflowTemplate(
            id=UUID(template_data["id"]),
            name=template_data.get("name"),
            description=template_data.get("description"),
            icon=template_data.get("icon", "template"),
            category=template_data.get("category", "general"),
            trigger_type=template_data.get("trigger_type"),
            trigger_config=template_data.get("trigger_config") or {},
            conditions=template_data.get("conditions") or [],
            condition_logic=template_data.get("condition_logic", "AND"),
            actions=template_data.get("actions") or [],
            is_global=template_data.get("is_global", False),
            organization_id=org_id,
            usage_count=template_data.get("usage_count") or 0,
            created_by_user_id=_map_user_id(_parse_uuid(template_data.get("created_by_user_id"))),
            created_at=_parse_datetime(template_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(template_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(template)

    for settings_data in notification_payload:
        settings_row = UserNotificationSettings(
            user_id=_map_user_id(UUID(settings_data["user_id"])),
            organization_id=org_id,
            surrogate_assigned=settings_data.get("surrogate_assigned", True),
            surrogate_status_changed=settings_data.get("surrogate_status_changed", True),
            surrogate_claim_available=settings_data.get("surrogate_claim_available", True),
            task_assigned=settings_data.get("task_assigned", True),
            workflow_approvals=settings_data.get("workflow_approvals", True),
            task_reminders=settings_data.get("task_reminders", True),
            appointments=settings_data.get("appointments", True),
            contact_reminder=settings_data.get("contact_reminder", True),
            status_change_decisions=settings_data.get("status_change_decisions", True),
            approval_timeouts=settings_data.get("approval_timeouts", True),
            security_alerts=settings_data.get("security_alerts", True),
            updated_at=_parse_datetime(settings_data.get("updated_at")) or datetime.now(UTC),
        )
        db.merge(settings_row)

    if ai_settings_payload:
        ai_settings = AISettings(
            id=UUID(ai_settings_payload["id"]),
            organization_id=org_id,
            is_enabled=ai_settings_payload.get("is_enabled", False),
            provider=ai_settings_payload.get("provider", "gemini"),
            model=ai_settings_payload.get("model"),
            vertex_project_id=ai_settings_payload.get("vertex_project_id"),
            vertex_location=ai_settings_payload.get("vertex_location"),
            vertex_audience=ai_settings_payload.get("vertex_audience"),
            vertex_service_account_email=ai_settings_payload.get("vertex_service_account_email"),
            context_notes_limit=ai_settings_payload.get("context_notes_limit"),
            conversation_history_limit=ai_settings_payload.get("conversation_history_limit"),
            consent_accepted_at=_parse_datetime(ai_settings_payload.get("consent_accepted_at")),
            consent_accepted_by=_map_user_id(
                _parse_uuid(ai_settings_payload.get("consent_accepted_by"))
            ),
            anonymize_pii=ai_settings_payload.get("anonymize_pii", True),
            current_version=ai_settings_payload.get("current_version") or 1,
            api_key_encrypted=None,
            created_at=_parse_datetime(ai_settings_payload.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(ai_settings_payload.get("updated_at")) or datetime.now(UTC),
        )
        if ai_settings_payload.get("has_api_key") and ai_settings.is_enabled:
            ai_settings.is_enabled = False
        db.add(ai_settings)

    for meta_page_data in meta_pages_payload:
        meta_page = MetaPageMapping(
            id=UUID(meta_page_data["id"]),
            organization_id=org_id,
            page_id=meta_page_data.get("page_id"),
            page_name=meta_page_data.get("page_name"),
            token_expires_at=_parse_datetime(meta_page_data.get("token_expires_at")),
            is_active=False,
            last_success_at=_parse_datetime(meta_page_data.get("last_success_at")),
            last_error=meta_page_data.get("last_error"),
            last_error_at=_parse_datetime(meta_page_data.get("last_error_at")),
            created_at=_parse_datetime(meta_page_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(meta_page_data.get("updated_at")) or datetime.now(UTC),
            access_token_encrypted=None,
        )
        db.add(meta_page)

    if retention_policies_payload:
        db.query(DataRetentionPolicy).filter(DataRetentionPolicy.organization_id == org_id).delete()
        for policy_data in retention_policies_payload:
            policy = DataRetentionPolicy(
                id=UUID(policy_data["id"]),
                organization_id=org_id,
                entity_type=policy_data.get("entity_type"),
                retention_days=policy_data.get("retention_days") or 0,
                is_active=policy_data.get("is_active", True),
                created_by_user_id=_map_user_id(_parse_uuid(policy_data.get("created_by_user_id"))),
                created_at=_parse_datetime(policy_data.get("created_at")) or datetime.now(UTC),
                updated_at=_parse_datetime(policy_data.get("updated_at")) or datetime.now(UTC),
            )
            db.add(policy)

    if legal_holds_payload:
        db.query(LegalHold).filter(LegalHold.organization_id == org_id).delete()
        for hold_data in legal_holds_payload:
            hold = LegalHold(
                id=UUID(hold_data["id"]),
                organization_id=org_id,
                entity_type=hold_data.get("entity_type"),
                entity_id=_parse_uuid(hold_data.get("entity_id")),
                reason=hold_data.get("reason") or "",
                created_by_user_id=_map_user_id(_parse_uuid(hold_data.get("created_by_user_id"))),
                released_by_user_id=_map_user_id(_parse_uuid(hold_data.get("released_by_user_id"))),
                created_at=_parse_datetime(hold_data.get("created_at")) or datetime.now(UTC),
                released_at=_parse_datetime(hold_data.get("released_at")),
            )
            db.add(hold)

    if org_counters_payload:
        db.query(OrgCounter).filter(OrgCounter.organization_id == org_id).delete()
        for counter_data in org_counters_payload:
            counter = OrgCounter(
                organization_id=org_id,
                counter_type=counter_data.get("counter_type"),
                current_value=counter_data.get("current_value") or 0,
                updated_at=_parse_datetime(counter_data.get("updated_at")) or datetime.now(UTC),
            )
            db.add(counter)

    db.query(RolePermission).filter(RolePermission.organization_id == org_id).delete()
    for permission_data in role_permissions_payload:
        permission = RolePermission(
            id=UUID(permission_data["id"]),
            organization_id=org_id,
            role=permission_data.get("role"),
            permission=permission_data.get("permission"),
            is_granted=permission_data.get("is_granted", True),
            created_at=_parse_datetime(permission_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(permission_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(permission)

    db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id
    ).delete()
    for override_data in user_overrides_payload:
        override = UserPermissionOverride(
            id=UUID(override_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(override_data["user_id"])),
            permission=override_data.get("permission"),
            override_type=override_data.get("override_type"),
            created_at=_parse_datetime(override_data.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(override_data.get("updated_at")) or datetime.now(UTC),
        )
        db.add(override)

    if commit:
        db.commit()
    else:
        db.flush()

    return {
        "users": len(users_payload),
        "memberships": len(memberships_payload),
        "queues": len(queues_payload),
        "queue_members": len(queue_members_payload),
        "pipelines": len(pipelines_payload),
        "templates": len(templates_payload),
        "workflows": len(workflows_payload),
        "forms": len(forms_payload),
        "form_logos": len(form_logos_payload),
        "form_field_mappings": len(form_field_mappings_payload),
        "appointment_types": len(appointment_types_payload),
        "availability_rules": len(availability_rules_payload),
        "availability_overrides": len(availability_overrides_payload),
        "booking_links": len(booking_links_payload),
        "workflow_templates": len(workflow_templates_payload),
        "notification_settings": len(notification_payload),
        "role_permissions": len(role_permissions_payload),
        "user_permission_overrides": len(user_overrides_payload),
        "meta_pages": len(meta_pages_payload),
        "ai_settings": 1 if ai_settings_payload else 0,
        "data_retention_policies": len(retention_policies_payload),
        "legal_holds": len(legal_holds_payload),
        "org_counters": len(org_counters_payload),
        "integrations_skipped": len(integrations_payload),
    }


def import_surrogates_csv(
    db: Session,
    org_id: UUID,
    content: bytes,
    *,
    commit: bool = True,
) -> int:
    if db.scalar(
        select(func.count(1)).select_from(Surrogate).where(Surrogate.organization_id == org_id)
    ):
        raise ValueError("Organization already has surrogates; import requires an empty org.")
    text_content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise ValueError("CSV has no headers")

    stage_ids = {
        stage.id
        for stage in db.query(PipelineStage)
        .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
        .filter(Pipeline.organization_id == org_id)
        .all()
    }
    users_in_org = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .all()
    )
    user_ids = {user.id for user in users_in_org}
    users_by_email = {user.email.lower(): user.id for user in users_in_org if user.email}
    queue_ids = {
        queue.id for queue in db.query(Queue).filter(Queue.organization_id == org_id).all()
    }

    meta_leads_to_link: list[tuple[UUID, UUID]] = []
    imported = 0

    def _resolve_user_id(user_id: UUID | None, email: str | None) -> UUID | None:
        if user_id and user_id in user_ids:
            return user_id
        if email:
            mapped = users_by_email.get(email.lower())
            if mapped:
                return mapped
        return user_id

    rows = list(reader)
    created_meta_leads: set[UUID] = set()
    meta_lead_ids: set[UUID] = set()
    for row in rows:
        meta_lead_id = _parse_uuid(row.get("meta_lead_id"))
        meta_lead_external_id = row.get("meta_lead_external_id")
        if meta_lead_id and meta_lead_external_id:
            meta_lead_ids.add(meta_lead_id)

    existing_meta_lead_ids: set[UUID] = set()
    if meta_lead_ids:
        existing_meta_lead_ids = {
            meta_id
            for (meta_id,) in (db.query(MetaLead.id).filter(MetaLead.id.in_(meta_lead_ids)).all())
        }

    for row in rows:
        meta_lead_id = _parse_uuid(row.get("meta_lead_id"))
        meta_lead_external_id = row.get("meta_lead_external_id")
        if meta_lead_id and not meta_lead_external_id:
            raise ValueError(
                f"Missing meta_lead_external_id for surrogate {row.get('id') or 'unknown'}"
            )
        if not meta_lead_id or not meta_lead_external_id:
            continue
        if meta_lead_id in created_meta_leads:
            continue
        if meta_lead_id in existing_meta_lead_ids:
            created_meta_leads.add(meta_lead_id)
            continue

        meta_lead_is_converted = _parse_bool(row.get("meta_lead_is_converted"))
        meta_lead = MetaLead(
            id=meta_lead_id,
            organization_id=org_id,
            meta_lead_id=meta_lead_external_id,
            meta_form_id=row.get("meta_lead_form_id"),
            meta_page_id=row.get("meta_lead_page_id"),
            field_data=_parse_json(row.get("meta_lead_field_data")),
            raw_payload=_parse_json(row.get("meta_lead_raw_payload")),
            field_data_raw=_parse_json(row.get("meta_lead_field_data_raw")),
            is_converted=meta_lead_is_converted if meta_lead_is_converted is not None else True,
            converted_surrogate_id=None,
            conversion_error=row.get("meta_lead_conversion_error"),
            status=row.get("meta_lead_status") or "converted",
            fetch_error=row.get("meta_lead_fetch_error"),
            meta_created_time=_parse_datetime(row.get("meta_lead_meta_created_time")),
            received_at=_parse_datetime(row.get("meta_lead_received_at")) or datetime.now(UTC),
            converted_at=_parse_datetime(row.get("meta_lead_converted_at")),
        )
        db.add(meta_lead)
        created_meta_leads.add(meta_lead_id)

    if created_meta_leads:
        db.flush()

    for row in rows:
        surrogate_id = _parse_uuid(row.get("id"))
        if not surrogate_id:
            raise ValueError("Surrogate id is required")

        stage_id = _parse_uuid(row.get("stage_id"))
        if not stage_id:
            raise ValueError(f"Stage id is required for surrogate {surrogate_id}")
        if stage_id not in stage_ids:
            raise ValueError(f"Stage {stage_id} not found for surrogate {surrogate_id}")

        owner_type = row.get("owner_type")
        if owner_type not in (OwnerType.USER.value, OwnerType.QUEUE.value):
            raise ValueError(f"Invalid owner_type for surrogate {surrogate_id}")
        owner_id = _parse_uuid(row.get("owner_id"))
        if not owner_id:
            raise ValueError(f"Owner id required for surrogate {surrogate_id}")
        if owner_type == OwnerType.USER.value:
            owner_id = _resolve_user_id(owner_id, row.get("owner_email"))
            if not owner_id or owner_id not in user_ids:
                raise ValueError(f"Owner user {owner_id} not found for surrogate {surrogate_id}")
        if owner_type == OwnerType.QUEUE.value and owner_id not in queue_ids:
            raise ValueError(f"Owner queue {owner_id} not found for surrogate {surrogate_id}")

        meta_lead_id = _parse_uuid(row.get("meta_lead_id"))
        meta_lead_external_id = row.get("meta_lead_external_id")

        if meta_lead_id and not meta_lead_external_id:
            raise ValueError(f"Missing meta_lead_external_id for surrogate {surrogate_id}")

        created_by_user_id = _parse_uuid(row.get("created_by_user_id"))
        if created_by_user_id:
            created_by_user_id = _resolve_user_id(created_by_user_id, row.get("created_by_email"))
            if created_by_user_id and created_by_user_id not in user_ids:
                raise ValueError(
                    f"Created-by user {created_by_user_id} not found for surrogate {surrogate_id}"
                )

        archived_by_user_id = _parse_uuid(row.get("archived_by_user_id"))
        if archived_by_user_id:
            archived_by_user_id = _resolve_user_id(
                archived_by_user_id, row.get("archived_by_email")
            )
            if archived_by_user_id and archived_by_user_id not in user_ids:
                raise ValueError(
                    f"Archived-by user {archived_by_user_id} not found for surrogate {surrogate_id}"
                )

        if not row.get("surrogate_number"):
            raise ValueError(f"Missing surrogate_number for surrogate {surrogate_id}")
        if not row.get("status_label"):
            raise ValueError(f"Missing status_label for surrogate {surrogate_id}")
        if not row.get("source"):
            raise ValueError(f"Missing source for surrogate {surrogate_id}")
        if not row.get("full_name"):
            raise ValueError(f"Missing full_name for surrogate {surrogate_id}")
        if not row.get("email"):
            raise ValueError(f"Missing email for surrogate {surrogate_id}")

        normalized_email = normalize_email(row.get("email"))
        raw_phone = row.get("phone")
        if raw_phone:
            try:
                normalized_phone = normalize_phone(raw_phone)
            except ValueError:
                normalized_phone = raw_phone.strip()
        else:
            normalized_phone = None
        normalized_full_name = normalize_search_text(row.get("full_name"))
        normalized_number = normalize_identifier(row.get("surrogate_number"))
        email_domain = extract_email_domain(normalized_email)
        phone_last4 = extract_phone_last4(normalized_phone)

        if meta_lead_id and meta_lead_external_id:
            meta_leads_to_link.append((meta_lead_id, surrogate_id))

        surrogate = Surrogate(
            id=surrogate_id,
            surrogate_number=row.get("surrogate_number"),
            surrogate_number_normalized=normalized_number,
            organization_id=org_id,
            status_label=row.get("status_label"),
            stage_id=stage_id,
            source=row.get("source"),
            is_priority=_parse_bool(row.get("is_priority")) or False,
            owner_type=owner_type,
            owner_id=owner_id,
            created_by_user_id=created_by_user_id,
            meta_lead_id=meta_lead_id,
            meta_ad_external_id=row.get("meta_ad_external_id"),
            meta_form_id=row.get("meta_form_id"),
            full_name=row.get("full_name"),
            full_name_normalized=normalized_full_name,
            email=normalized_email,
            email_hash=hash_email(normalized_email),
            email_domain=email_domain,
            phone=normalized_phone,
            phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
            phone_last4=phone_last4,
            state=row.get("state"),
            date_of_birth=_parse_date(row.get("date_of_birth")),
            race=row.get("race"),
            height_ft=_parse_decimal(row.get("height_ft")),
            weight_lb=_parse_int(row.get("weight_lb")),
            is_age_eligible=_parse_bool(row.get("is_age_eligible")),
            is_citizen_or_pr=_parse_bool(row.get("is_citizen_or_pr")),
            has_child=_parse_bool(row.get("has_child")),
            is_non_smoker=_parse_bool(row.get("is_non_smoker")),
            has_surrogate_experience=_parse_bool(row.get("has_surrogate_experience")),
            journey_timing_preference=normalize_journey_timing_preference(
                row.get("journey_timing_preference")
            ),
            num_deliveries=_parse_int(row.get("num_deliveries")),
            num_csections=_parse_int(row.get("num_csections")),
            is_archived=_parse_bool(row.get("is_archived")) or False,
            archived_at=_parse_datetime(row.get("archived_at")),
            archived_by_user_id=archived_by_user_id,
            last_contacted_at=_parse_datetime(row.get("last_contacted_at")),
            last_contact_method=row.get("last_contact_method"),
            created_at=_parse_datetime(row.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(row.get("updated_at")) or datetime.now(UTC),
        )
        db.add(surrogate)
        imported += 1

    db.flush()

    if meta_leads_to_link:
        db.bulk_update_mappings(
            MetaLead,
            [
                {"id": meta_lead_id, "converted_surrogate_id": surrogate_id}
                for meta_lead_id, surrogate_id in meta_leads_to_link
            ],
        )

    if commit:
        db.commit()
    else:
        db.flush()
    return imported


def _restore_donor_profile_photo(
    db: Session,
    *,
    org_id: UUID,
    donor: Donor,
    row: dict[str, str | None],
    user_ids: set[UUID],
    users_by_email: dict[str, UUID],
) -> UUID | None:
    attachment_id = _parse_uuid(row.get("profile_photo_attachment_id"))
    photo_fields = (
        "profile_photo_filename",
        "profile_photo_content_type",
        "profile_photo_file_size",
        "profile_photo_checksum_sha256",
        "profile_photo_scan_status",
        "profile_photo_scanned_at",
        "profile_photo_quarantined",
        "profile_photo_created_at",
        "profile_photo_uploaded_by_user_id",
        "profile_photo_uploaded_by_email",
        "profile_photo_bytes_base64",
    )
    has_photo_payload = any((row.get(field) or "").strip() for field in photo_fields)
    if attachment_id is None:
        if has_photo_payload:
            raise ValueError(f"Profile photo attachment id is required for donor {donor.id}")
        return None
    if db.get(Attachment, attachment_id) is not None:
        raise ValueError("Profile photo attachment id is unavailable")
    if not has_photo_payload:
        raise ValueError(f"Profile photo payload is required for donor {donor.id}")

    filename = (row.get("profile_photo_filename") or "").strip()
    content_type = (row.get("profile_photo_content_type") or "").strip().lower()
    expected_size = _parse_int(row.get("profile_photo_file_size"))
    expected_checksum = (row.get("profile_photo_checksum_sha256") or "").strip().lower()
    encoded_bytes = (row.get("profile_photo_bytes_base64") or "").strip()
    if not filename or not content_type or expected_size is None or not expected_checksum:
        raise ValueError(f"Incomplete profile photo metadata for donor {donor.id}")
    if not encoded_bytes:
        raise ValueError(f"Profile photo bytes are required for donor {donor.id}")
    scan_status = (row.get("profile_photo_scan_status") or "").strip().lower()
    quarantined_value = (row.get("profile_photo_quarantined") or "").strip().lower()
    if scan_status != "clean" or quarantined_value not in {"false", "0", "no", "n"}:
        raise ValueError(
            f"Profile photo must be clean and not quarantined for donor {donor.id}"
        )
    if expected_size < 0 or expected_size > attachment_service.MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Invalid profile photo size for donor {donor.id}")
    max_encoded_size = ((attachment_service.MAX_FILE_SIZE_BYTES + 2) // 3) * 4
    if len(encoded_bytes) > max_encoded_size:
        raise ValueError(f"Profile photo bytes exceed the size limit for donor {donor.id}")
    try:
        decoded_bytes = base64.b64decode(encoded_bytes, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid profile photo bytes for donor {donor.id}") from exc
    if len(decoded_bytes) != expected_size:
        raise ValueError(f"Profile photo size mismatch for donor {donor.id}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_checksum):
        raise ValueError(f"Invalid profile photo checksum for donor {donor.id}")
    if hashlib.sha256(decoded_bytes).hexdigest() != expected_checksum:
        raise ValueError(f"Profile photo checksum mismatch for donor {donor.id}")

    valid, validation_error = attachment_service.validate_file(
        filename,
        content_type,
        len(decoded_bytes),
        allowed_extensions={"png", "jpg", "jpeg"},
        allowed_mime_types={"image/png", "image/jpeg"},
    )
    if not valid:
        raise ValueError(validation_error or f"Invalid profile photo for donor {donor.id}")
    processed_file = attachment_service.sanitize_upload_content(
        filename,
        content_type,
        io.BytesIO(decoded_bytes),
    )
    processed_file.seek(0)
    processed_bytes = processed_file.read()
    processed_checksum = hashlib.sha256(processed_bytes).hexdigest()

    extension = "png" if content_type == "image/png" else "jpg"
    storage_key = f"{org_id}/donors/{donor.id}/profile/{attachment_id}.{extension}"
    attachment_service.store_file(storage_key, io.BytesIO(processed_bytes), content_type)
    attachment_service.register_storage_cleanup_on_rollback(db, storage_key)

    uploaded_by_user_id = _parse_uuid(row.get("profile_photo_uploaded_by_user_id"))
    if uploaded_by_user_id not in user_ids:
        uploaded_by_email = (row.get("profile_photo_uploaded_by_email") or "").strip().lower()
        uploaded_by_user_id = users_by_email.get(uploaded_by_email) if uploaded_by_email else None

    attachment = Attachment(
        id=attachment_id,
        organization_id=org_id,
        donor_id=donor.id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        file_size=len(processed_bytes),
        checksum_sha256=processed_checksum,
        scan_status="clean",
        scanned_at=_parse_datetime(row.get("profile_photo_scanned_at")),
        quarantined=False,
        created_at=_parse_datetime(row.get("profile_photo_created_at")) or datetime.now(UTC),
    )
    db.add(attachment)
    db.flush()
    return attachment.id


def _history_text(
    event: dict[str, Any],
    field: str,
    *,
    donor_id: UUID,
    required: bool = False,
    max_length: int | None = None,
) -> str | None:
    value = event.get(field)
    if value is None:
        if required:
            raise ValueError(f"Missing {field} in status history for donor {donor_id}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}")
    if required and not value.strip():
        raise ValueError(f"Missing {field} in status history for donor {donor_id}")
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}")
    return value


def _history_uuid(event: dict[str, Any], field: str, *, donor_id: UUID) -> UUID | None:
    value = event.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}") from exc


def _history_datetime(event: dict[str, Any], field: str, *, donor_id: UUID) -> datetime:
    value = _history_text(event, field, donor_id=donor_id, required=True)
    try:
        parsed = _parse_datetime(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}") from exc
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Invalid {field} in status history for donor {donor_id}")
    return parsed


def _resolve_history_stage(
    event: dict[str, Any],
    *,
    prefix: str,
    stable_status: str | None,
    donor: Donor,
    stage_details: dict[UUID, tuple[str, str, str, UUID, str]],
) -> UUID | None:
    stage_id = _history_uuid(event, f"{prefix}_stage_id", donor_id=donor.id)
    pipeline_id = _history_uuid(event, f"{prefix}_pipeline_id", donor_id=donor.id)
    pipeline_name = _history_text(event, f"{prefix}_pipeline_name", donor_id=donor.id)
    stable_key = _history_text(
        event,
        f"{prefix}_stage_key",
        donor_id=donor.id,
        max_length=80,
    )
    stable_key = (stable_key or stable_status or "").strip()
    expected_entity_type = donor.pipeline_entity_type

    if stage_id is not None and stage_id in stage_details:
        entity_type, target_key, _label, target_pipeline_id, target_pipeline_name = stage_details[
            stage_id
        ]
        if entity_type != expected_entity_type:
            raise ValueError(
                f"Status history stage {stage_id} is not in the {expected_entity_type} "
                f"pipeline for donor {donor.id}"
            )
        if stable_key and stable_key != target_key:
            raise ValueError(f"Status history stage key mismatch for donor {donor.id}")
        if pipeline_id is not None and pipeline_id != target_pipeline_id:
            raise ValueError(f"Status history pipeline mismatch for donor {donor.id}")
        if pipeline_name is not None and pipeline_name != target_pipeline_name:
            raise ValueError(f"Status history pipeline mismatch for donor {donor.id}")
        return stage_id

    if not stable_key:
        if stage_id is None:
            return None
        raise ValueError(f"Status history stage {stage_id} cannot be remapped for donor {donor.id}")

    candidates = [
        candidate_id
        for candidate_id, detail in stage_details.items()
        if detail[0] == expected_entity_type and detail[1] == stable_key
    ]
    matching_pipeline_ids = [
        candidate_id for candidate_id in candidates if stage_details[candidate_id][3] == pipeline_id
    ]
    if pipeline_id is not None and matching_pipeline_ids:
        candidates = matching_pipeline_ids
    matching_pipeline_names = [
        candidate_id
        for candidate_id in candidates
        if stage_details[candidate_id][4] == pipeline_name
    ]
    if pipeline_name is not None and matching_pipeline_names:
        candidates = matching_pipeline_names
    if len(candidates) != 1:
        qualifier = "cannot be remapped" if not candidates else "is ambiguous"
        raise ValueError(
            f"Status history stage {stable_key} {qualifier} in the {expected_entity_type} "
            f"pipeline for donor {donor.id}"
        )
    return candidates[0]


def _restore_donor_status_history(
    db: Session,
    *,
    org_id: UUID,
    donor: Donor,
    raw_history: str | None,
    stage_details: dict[UUID, tuple[str, str, str, UUID, str]],
    user_ids: set[UUID],
    users_by_email: dict[str, UUID],
    history_ids: set[UUID],
) -> bool:
    if raw_history is None or not raw_history.strip():
        return False
    if len(raw_history.encode("utf-8")) > MAX_DONOR_STATUS_HISTORY_JSON_BYTES:
        raise ValueError(f"Status history payload exceeds the limit for donor {donor.id}")
    try:
        payload = json.loads(raw_history)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid status history JSON for donor {donor.id}") from exc
    if isinstance(payload, dict):
        if payload.get("version") != 1:
            raise ValueError(f"Unsupported status history version for donor {donor.id}")
        events = payload.get("events")
    else:
        events = payload
    if not isinstance(events, list):
        raise ValueError(f"Invalid status history payload for donor {donor.id}")
    if not events:
        return False

    for event in events:
        if not isinstance(event, dict):
            raise ValueError(f"Invalid status history event for donor {donor.id}")
        history_id = _history_uuid(event, "id", donor_id=donor.id) or uuid4()
        if history_id in history_ids or db.get(DonorStatusHistory, history_id) is not None:
            raise ValueError(f"Status history id {history_id} is unavailable")
        history_ids.add(history_id)

        old_status = _history_text(
            event,
            "old_status",
            donor_id=donor.id,
            max_length=50,
        )
        new_status = _history_text(
            event,
            "new_status",
            donor_id=donor.id,
            required=True,
            max_length=50,
        )
        old_stage_id = _resolve_history_stage(
            event,
            prefix="old",
            stable_status=old_status,
            donor=donor,
            stage_details=stage_details,
        )
        new_stage_id = _resolve_history_stage(
            event,
            prefix="new",
            stable_status=new_status,
            donor=donor,
            stage_details=stage_details,
        )
        if old_stage_id is not None and old_status != stage_details[old_stage_id][1]:
            raise ValueError(f"Status history old status mismatch for donor {donor.id}")
        if new_stage_id is not None and new_status != stage_details[new_stage_id][1]:
            raise ValueError(f"Status history new status mismatch for donor {donor.id}")

        changed_by_user_id = _history_uuid(event, "changed_by_user_id", donor_id=donor.id)
        if changed_by_user_id not in user_ids:
            actor_email = _history_text(event, "changed_by_email", donor_id=donor.id)
            changed_by_user_id = (
                users_by_email.get(actor_email.strip().lower()) if actor_email else None
            )

        db.add(
            DonorStatusHistory(
                id=history_id,
                donor_id=donor.id,
                organization_id=org_id,
                changed_by_user_id=changed_by_user_id,
                old_stage_id=old_stage_id,
                new_stage_id=new_stage_id,
                old_status=old_status,
                new_status=new_status,
                old_label_snapshot=_history_text(
                    event,
                    "old_label_snapshot",
                    donor_id=donor.id,
                    max_length=100,
                ),
                new_label_snapshot=_history_text(
                    event,
                    "new_label_snapshot",
                    donor_id=donor.id,
                    required=True,
                    max_length=100,
                ),
                reason=_history_text(event, "reason", donor_id=donor.id),
                effective_at=_history_datetime(event, "effective_at", donor_id=donor.id),
                recorded_at=_history_datetime(event, "recorded_at", donor_id=donor.id),
            )
        )
    return True


def import_donors_csv(
    db: Session,
    org_id: UUID,
    content: bytes,
    *,
    actor_user_id: UUID | None = None,
    commit: bool = True,
) -> int:
    """Restore donor records from the organization-scoped donor CSV export."""
    if db.scalar(select(func.count(1)).select_from(Donor).where(Donor.organization_id == org_id)):
        raise ValueError("Organization already has donors; import requires an empty org.")
    csv.field_size_limit(
        max(
            csv.field_size_limit(),
            DONOR_PHOTO_BASE64_FIELD_LIMIT,
            MAX_DONOR_STATUS_HISTORY_JSON_BYTES,
        )
    )
    text_content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise ValueError("CSV has no headers")

    stage_details = {
        stage_id: (entity_type, stage_key, stage_label, pipeline_id, pipeline_name)
        for stage_id, entity_type, stage_key, stage_label, pipeline_id, pipeline_name in db.query(
            PipelineStage.id,
            Pipeline.entity_type,
            PipelineStage.stage_key,
            PipelineStage.label,
            Pipeline.id,
            Pipeline.name,
        )
        .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
        .filter(Pipeline.organization_id == org_id)
        .all()
    }
    users_in_org = (
        db.query(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .all()
    )
    user_ids = {user.id for user in users_in_org}
    users_by_email = {user.email.lower(): user.id for user in users_in_org if user.email}
    queue_ids = {
        queue.id for queue in db.query(Queue).filter(Queue.organization_id == org_id).all()
    }

    rows = list(reader)
    donor_ids: set[UUID] = set()
    donor_numbers: set[str] = set()
    highest_donor_number = 0
    active_email_hashes: set[str] = set()
    history_ids: set[UUID] = set()
    imported = 0

    for row in rows:
        donor_id = _parse_uuid(row.get("id"))
        if donor_id is None:
            raise ValueError("Donor id is required")
        if donor_id in donor_ids:
            raise ValueError(f"Duplicate donor id {donor_id}")
        donor_ids.add(donor_id)

        donor_number = (row.get("donor_number") or "").strip()
        if not donor_number:
            raise ValueError(f"Missing donor_number for donor {donor_id}")
        if donor_number in donor_numbers:
            raise ValueError(f"Duplicate donor_number {donor_number}")
        donor_numbers.add(donor_number)
        donor_number_match = re.fullmatch(r"D(\d{5,9})", donor_number)
        if donor_number_match is None:
            raise ValueError(f"Invalid donor_number {donor_number}")
        donor_number_value = int(donor_number_match.group(1))
        if donor_number_value < MIN_DONOR_NUMBER_VALUE:
            raise ValueError(f"Invalid donor_number {donor_number}")
        highest_donor_number = max(highest_donor_number, donor_number_value)

        donor_type = (row.get("donor_type") or "").strip().lower()
        if donor_type not in {"egg", "sperm"}:
            raise ValueError(f"Invalid donor_type for donor {donor_id}")
        stage_id = _parse_uuid(row.get("stage_id"))
        if stage_id is None:
            raise ValueError(f"Stage id is required for donor {donor_id}")
        expected_entity_type = f"{donor_type}_donor"
        stage_detail = stage_details.get(stage_id)
        if stage_detail is None or stage_detail[0] != expected_entity_type:
            raise ValueError(
                f"Stage {stage_id} is not in the {expected_entity_type} pipeline for donor "
                f"{donor_id}"
            )

        full_name = (row.get("full_name") or "").strip()
        email_value = (row.get("email") or "").strip()
        if not full_name:
            raise ValueError(f"Missing full_name for donor {donor_id}")
        if not email_value:
            raise ValueError(f"Missing email for donor {donor_id}")
        normalized_email = normalize_email(email_value)
        email_hash = hash_email(normalized_email)
        is_archived = _parse_bool(row.get("is_archived")) or False
        if not is_archived:
            if email_hash in active_email_hashes:
                raise ValueError(f"Duplicate active donor email for donor {donor_id}")
            active_email_hashes.add(email_hash)

        raw_phone = (row.get("phone") or "").strip()
        if raw_phone:
            try:
                normalized_phone = normalize_phone(raw_phone)
            except ValueError:
                normalized_phone = raw_phone
        else:
            normalized_phone = None

        owner_type = (row.get("owner_type") or "").strip() or None
        owner_id = _parse_uuid(row.get("owner_id"))
        if (owner_type is None) != (owner_id is None):
            raise ValueError(f"owner_type and owner_id must be provided together for {donor_id}")
        if owner_type == OwnerType.USER.value:
            if owner_id not in user_ids and row.get("owner_email"):
                owner_id = users_by_email.get(row["owner_email"].lower())
            if owner_id not in user_ids:
                raise ValueError(f"Owner user {owner_id} not found for donor {donor_id}")
        elif owner_type == OwnerType.QUEUE.value:
            if owner_id not in queue_ids:
                raise ValueError(f"Owner queue {owner_id} not found for donor {donor_id}")
        elif owner_type is not None:
            raise ValueError(f"Invalid owner_type for donor {donor_id}")

        donor = Donor(
            id=donor_id,
            organization_id=org_id,
            donor_number=donor_number,
            donor_type=donor_type,
            full_name=full_name,
            email=normalized_email,
            email_hash=email_hash,
            phone=normalized_phone,
            phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
            state=(row.get("state") or "").strip() or None,
            education=(row.get("education") or "").strip() or None,
            source=(row.get("source") or "").strip() or None,
            owner_type=owner_type,
            owner_id=owner_id,
            stage_id=stage_id,
            profile_photo_attachment_id=None,
            is_archived=is_archived,
            archived_at=_parse_datetime(row.get("archived_at")),
            created_at=_parse_datetime(row.get("created_at")) or datetime.now(UTC),
            updated_at=_parse_datetime(row.get("updated_at")) or datetime.now(UTC),
        )
        db.add(donor)
        db.flush()
        donor.profile_photo_attachment_id = _restore_donor_profile_photo(
            db,
            org_id=org_id,
            donor=donor,
            row=row,
            user_ids=user_ids,
            users_by_email=users_by_email,
        )
        if not _restore_donor_status_history(
            db,
            org_id=org_id,
            donor=donor,
            raw_history=row.get("status_history_json"),
            stage_details=stage_details,
            user_ids=user_ids,
            users_by_email=users_by_email,
            history_ids=history_ids,
        ):
            history_time = datetime.now(UTC)
            db.add(
                DonorStatusHistory(
                    donor_id=donor.id,
                    organization_id=org_id,
                    changed_by_user_id=actor_user_id if actor_user_id in user_ids else None,
                    old_stage_id=None,
                    new_stage_id=stage_id,
                    old_status=None,
                    new_status=stage_detail[1],
                    old_label_snapshot=None,
                    new_label_snapshot=stage_detail[2],
                    reason="Imported current stage",
                    effective_at=history_time,
                    recorded_at=history_time,
                )
            )
        imported += 1

    if highest_donor_number:
        donor_counter = (
            db.query(OrgCounter)
            .filter(
                OrgCounter.organization_id == org_id,
                OrgCounter.counter_type == "donor_number",
            )
            .first()
        )
        if donor_counter is None:
            db.add(
                OrgCounter(
                    organization_id=org_id,
                    counter_type="donor_number",
                    current_value=highest_donor_number,
                )
            )
        elif donor_counter.current_value < highest_donor_number:
            donor_counter.current_value = highest_donor_number

    if commit:
        db.commit()
    else:
        db.flush()
    return imported
