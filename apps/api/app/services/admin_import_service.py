"""Developer-only import helpers for org restore."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, date, time, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import OwnerType
from app.db.models import (
    AISettings,
    AutomationWorkflow,
    AvailabilityOverride,
    AvailabilityRule,
    AppointmentType,
    BookingLink,
    DataRetentionPolicy,
    Form,
    FormFieldMapping,
    FormLogo,
    LegalHold,
    Surrogate,
    EmailTemplate,
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
    User,
    UserIntegration,
    UserNotificationSettings,
    UserPermissionOverride,
    WorkflowTemplate,
)
from app.utils.normalization import (
    extract_email_domain,
    extract_phone_last4,
    normalize_email,
    normalize_phone,
    normalize_search_text,
    normalize_identifier,
)


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
    return int(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(value)


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
        "surrogates": db.query(Surrogate).filter(Surrogate.organization_id == org_id).count(),
        "forms": db.query(Form).filter(Form.organization_id == org_id).count(),
        "form_logos": db.query(FormLogo).filter(FormLogo.organization_id == org_id).count(),
        "form_field_mappings": db.query(FormFieldMapping)
        .join(Form, FormFieldMapping.form_id == Form.id)
        .filter(Form.organization_id == org_id)
        .count(),
        "appointment_types": db.query(AppointmentType)
        .filter(AppointmentType.organization_id == org_id)
        .count(),
        "availability_rules": db.query(AvailabilityRule)
        .filter(AvailabilityRule.organization_id == org_id)
        .count(),
        "availability_overrides": db.query(AvailabilityOverride)
        .filter(AvailabilityOverride.organization_id == org_id)
        .count(),
        "booking_links": db.query(BookingLink)
        .filter(BookingLink.organization_id == org_id)
        .count(),
        "pipelines": db.query(Pipeline).filter(Pipeline.organization_id == org_id).count(),
        "pipeline_stages": db.query(PipelineStage)
        .join(Pipeline, PipelineStage.pipeline_id == Pipeline.id)
        .filter(Pipeline.organization_id == org_id)
        .count(),
        "workflows": db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == org_id)
        .count(),
        "workflow_templates": db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.organization_id == org_id)
        .count(),
        "email_templates": db.query(EmailTemplate)
        .filter(EmailTemplate.organization_id == org_id)
        .count(),
        "meta_leads": db.query(MetaLead).filter(MetaLead.organization_id == org_id).count(),
        "queues": db.query(Queue).filter(Queue.organization_id == org_id).count(),
        "queue_members": db.query(QueueMember)
        .join(Queue, QueueMember.queue_id == Queue.id)
        .filter(Queue.organization_id == org_id)
        .count(),
        "notification_settings": db.query(UserNotificationSettings)
        .filter(UserNotificationSettings.organization_id == org_id)
        .count(),
        "integrations": db.query(UserIntegration)
        .join(User, UserIntegration.user_id == User.id)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .count(),
        "ai_settings": db.query(AISettings).filter(AISettings.organization_id == org_id).count(),
        "meta_pages": db.query(MetaPageMapping)
        .filter(MetaPageMapping.organization_id == org_id)
        .count(),
    }

    blocking = {key: value for key, value in checks.items() if value}
    if blocking:
        raise ValueError(f"Organization is not empty: {blocking}")


def import_org_config_zip(db: Session, org_id: UUID, content: bytes) -> dict[str, int]:
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
                created_at=_parse_datetime(user_data.get("created_at"))
                or datetime.now(timezone.utc),
                updated_at=_parse_datetime(user_data.get("updated_at"))
                or datetime.now(timezone.utc),
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
                created_at=_parse_datetime(membership_data.get("created_at"))
                or datetime.now(timezone.utc),
            )
            db.add(membership)

    for queue_data in queues_payload:
        queue = Queue(
            id=UUID(queue_data["id"]),
            organization_id=org_id,
            name=queue_data.get("name"),
            description=queue_data.get("description"),
            is_active=queue_data.get("is_active", True),
            created_at=_parse_datetime(queue_data.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(queue_data.get("updated_at")) or datetime.now(timezone.utc),
        )
        db.add(queue)

    for queue_member_data in queue_members_payload:
        member = QueueMember(
            id=UUID(queue_member_data["id"]),
            queue_id=UUID(queue_member_data["queue_id"]),
            user_id=_map_user_id(UUID(queue_member_data["user_id"])),
            created_at=_parse_datetime(queue_member_data.get("created_at"))
            or datetime.now(timezone.utc),
        )
        db.add(member)

    for pipeline_data in pipelines_payload:
        pipeline = Pipeline(
            id=UUID(pipeline_data["id"]),
            organization_id=org_id,
            name=pipeline_data.get("name"),
            is_default=pipeline_data.get("is_default", False),
            current_version=pipeline_data.get("current_version") or 1,
            created_at=_parse_datetime(pipeline_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(pipeline_data.get("updated_at"))
            or datetime.now(timezone.utc),
        )
        db.add(pipeline)
        for stage_data in pipeline_data.get("stages", []):
            stage = PipelineStage(
                id=UUID(stage_data["id"]),
                pipeline_id=pipeline.id,
                slug=stage_data.get("slug"),
                label=stage_data.get("label"),
                color=stage_data.get("color"),
                order=stage_data.get("order") or 1,
                stage_type=stage_data.get("stage_type"),
                is_active=stage_data.get("is_active", True),
                deleted_at=_parse_datetime(stage_data.get("deleted_at")),
                created_at=_parse_datetime(stage_data.get("created_at"))
                or datetime.now(timezone.utc),
                updated_at=_parse_datetime(stage_data.get("updated_at"))
                or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(template_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(template_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(workflow_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(workflow_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            schema_json=schema_json,
            published_schema_json=published_schema_json,
            max_file_size_bytes=form_data.get("max_file_size_bytes"),
            max_file_count=form_data.get("max_file_count"),
            allowed_mime_types=allowed_mime_types,
            created_by_user_id=_map_user_id(_parse_uuid(form_data.get("created_by_user_id"))),
            updated_by_user_id=_map_user_id(_parse_uuid(form_data.get("updated_by_user_id"))),
            created_at=_parse_datetime(form_data.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(form_data.get("updated_at")) or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(logo_data.get("created_at")) or datetime.now(timezone.utc),
        )
        db.add(logo)

    for mapping_data in form_field_mappings_payload:
        mapping = FormFieldMapping(
            id=UUID(mapping_data["id"]),
            form_id=UUID(mapping_data["form_id"]),
            field_key=mapping_data.get("field_key"),
            surrogate_field=mapping_data.get("surrogate_field"),
            created_at=_parse_datetime(mapping_data.get("created_at"))
            or datetime.now(timezone.utc),
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
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(appointment_type_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(rule_data.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(rule_data.get("updated_at")) or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(override_data.get("created_at"))
            or datetime.now(timezone.utc),
        )
        db.add(override)

    for link_data in booking_links_payload:
        link = BookingLink(
            id=UUID(link_data["id"]),
            organization_id=org_id,
            user_id=_map_user_id(UUID(link_data["user_id"])),
            public_slug=link_data.get("public_slug"),
            is_active=link_data.get("is_active", True),
            created_at=_parse_datetime(link_data.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(link_data.get("updated_at")) or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(template_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(template_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            updated_at=_parse_datetime(settings_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(ai_settings_payload.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(ai_settings_payload.get("updated_at"))
            or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(meta_page_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(meta_page_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
                created_at=_parse_datetime(policy_data.get("created_at"))
                or datetime.now(timezone.utc),
                updated_at=_parse_datetime(policy_data.get("updated_at"))
                or datetime.now(timezone.utc),
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
                created_at=_parse_datetime(hold_data.get("created_at"))
                or datetime.now(timezone.utc),
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
                updated_at=_parse_datetime(counter_data.get("updated_at"))
                or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(permission_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(permission_data.get("updated_at"))
            or datetime.now(timezone.utc),
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
            created_at=_parse_datetime(override_data.get("created_at"))
            or datetime.now(timezone.utc),
            updated_at=_parse_datetime(override_data.get("updated_at"))
            or datetime.now(timezone.utc),
        )
        db.add(override)

    db.commit()

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


def import_surrogates_csv(db: Session, org_id: UUID, content: bytes) -> int:
    if db.query(Surrogate).filter(Surrogate.organization_id == org_id).count():
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
            received_at=_parse_datetime(row.get("meta_lead_received_at"))
            or datetime.now(timezone.utc),
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
            num_deliveries=_parse_int(row.get("num_deliveries")),
            num_csections=_parse_int(row.get("num_csections")),
            is_archived=_parse_bool(row.get("is_archived")) or False,
            archived_at=_parse_datetime(row.get("archived_at")),
            archived_by_user_id=archived_by_user_id,
            last_contacted_at=_parse_datetime(row.get("last_contacted_at")),
            last_contact_method=row.get("last_contact_method"),
            created_at=_parse_datetime(row.get("created_at")) or datetime.now(timezone.utc),
            updated_at=_parse_datetime(row.get("updated_at")) or datetime.now(timezone.utc),
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

    db.commit()
    return imported
