"""Admin export helpers for dev-only data exports."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from importlib.util import find_spec
from typing import Any, Iterable, Iterator, Sequence
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
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
    OrgCounter,
    Surrogate,
    EmailTemplate,
    Membership,
    MetaPageMapping,
    Organization,
    Pipeline,
    PipelineStage,
    Queue,
    QueueMember,
    RolePermission,
    UserPermissionOverride,
    User,
    UserIntegration,
    UserNotificationSettings,
    WorkflowTemplate,
)
from app.services import ai_usage_service, analytics_service


CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")

EXPORT_TYPE_FILENAMES = {
    "surrogates_csv": "surrogates_export",
    "org_config_zip": "org_config_export",
    "analytics_zip": "analytics_export",
}


def _csv_safe(value: str) -> str:
    if value and value.startswith(CSV_DANGEROUS_PREFIXES):
        return f"'{value}"
    return value


def _ensure_admin_export_dir(org_id: UUID) -> str:
    base_dir = os.path.abspath(settings.EXPORT_LOCAL_DIR)
    export_dir = os.path.join(base_dir, str(org_id), "admin_exports")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def _build_admin_export_key(org_id: UUID, filename: str) -> str:
    prefix = settings.EXPORT_S3_PREFIX.strip("/")
    return f"{prefix}/{org_id}/admin/{filename}"


def _upload_to_s3(file_path: str, key: str) -> None:
    if find_spec("boto3") is None:
        raise RuntimeError("boto3 is required for S3 export storage")
    if not settings.EXPORT_S3_BUCKET:
        raise RuntimeError("EXPORT_S3_BUCKET must be set for S3 export storage")

    from app.services import storage_client

    client = storage_client.get_export_s3_client()
    client.upload_file(file_path, settings.EXPORT_S3_BUCKET, key)


def store_export_bytes(org_id: UUID, filename: str, payload: bytes) -> str:
    """Store export payload and return file path/key."""
    if settings.EXPORT_STORAGE_BACKEND == "s3":
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "wb") as f:
                f.write(payload)
            key = _build_admin_export_key(org_id, filename)
            _upload_to_s3(file_path, key)
            return key

    export_dir = _ensure_admin_export_dir(org_id)
    file_path = os.path.join(export_dir, filename)
    with open(file_path, "wb") as f:
        f.write(payload)
    return os.path.relpath(file_path, os.path.abspath(settings.EXPORT_LOCAL_DIR))


def store_surrogates_csv(db: Session, org_id: UUID, filename: str) -> str:
    """Store streamed surrogates CSV and return file path/key."""
    if settings.EXPORT_STORAGE_BACKEND == "s3":
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                for row in stream_surrogates_csv(db, org_id):
                    f.write(row)
            key = _build_admin_export_key(org_id, filename)
            _upload_to_s3(file_path, key)
            return key

    export_dir = _ensure_admin_export_dir(org_id)
    file_path = os.path.join(export_dir, filename)
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        for row in stream_surrogates_csv(db, org_id):
            f.write(row)
    return os.path.relpath(file_path, os.path.abspath(settings.EXPORT_LOCAL_DIR))


def resolve_admin_export_path(file_path: str) -> str:
    """Resolve local admin export path from stored relative path."""
    return os.path.join(os.path.abspath(settings.EXPORT_LOCAL_DIR), file_path)


def build_export_filename(export_type: str) -> str:
    """Build a timestamped filename for admin exports."""
    prefix = EXPORT_TYPE_FILENAMES.get(export_type, "admin_export")
    extension = "csv" if export_type == "surrogates_csv" else "zip"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


def _serialize_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _write_csv_row(values: Sequence[Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([_csv_safe(_serialize_csv_value(value)) for value in values])
    return output.getvalue()


def _write_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_safe(_serialize_csv_value(value)) for value in row])
    return output.getvalue()


def _write_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def stream_surrogates_csv(db: Session, org_id: UUID) -> Iterator[str]:
    owner_user = aliased(User)
    owner_queue = aliased(Queue)
    created_by = aliased(User)
    archived_by = aliased(User)

    headers = [
        "id",
        "surrogate_number",
        "organization_id",
        "status_label",
        "stage_id",
        "stage_slug",
        "stage_label",
        "stage_order",
        "source",
        "is_priority",
        "owner_type",
        "owner_id",
        "owner_name",
        "owner_email",
        "owner_queue_name",
        "created_by_user_id",
        "created_by_name",
        "created_by_email",
        "meta_lead_id",
        "meta_lead_external_id",
        "meta_lead_form_id",
        "meta_lead_page_id",
        "meta_lead_status",
        "meta_lead_fetch_error",
        "meta_lead_conversion_error",
        "meta_lead_is_converted",
        "meta_lead_meta_created_time",
        "meta_lead_received_at",
        "meta_lead_converted_at",
        "meta_lead_field_data",
        "meta_lead_raw_payload",
        "meta_lead_field_data_raw",
        "meta_ad_external_id",
        "meta_form_id",
        "full_name",
        "email",
        "phone",
        "state",
        "date_of_birth",
        "race",
        "height_ft",
        "weight_lb",
        "is_age_eligible",
        "is_citizen_or_pr",
        "has_child",
        "is_non_smoker",
        "has_surrogate_experience",
        "num_deliveries",
        "num_csections",
        "is_archived",
        "archived_at",
        "archived_by_user_id",
        "archived_by_name",
        "archived_by_email",
        "last_contacted_at",
        "last_contact_method",
        "created_at",
        "updated_at",
    ]

    yield _write_csv_row(headers)

    from app.db.models import MetaLead

    meta_lead = aliased(MetaLead)

    query = (
        db.query(
            Surrogate,
            PipelineStage,
            owner_user,
            owner_queue,
            created_by,
            archived_by,
            meta_lead,
        )
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .outerjoin(
            owner_user,
            and_(Surrogate.owner_type == OwnerType.USER.value, Surrogate.owner_id == owner_user.id),
        )
        .outerjoin(
            owner_queue,
            and_(
                Surrogate.owner_type == OwnerType.QUEUE.value,
                Surrogate.owner_id == owner_queue.id,
            ),
        )
        .outerjoin(created_by, Surrogate.created_by_user_id == created_by.id)
        .outerjoin(archived_by, Surrogate.archived_by_user_id == archived_by.id)
        .outerjoin(meta_lead, Surrogate.meta_lead_id == meta_lead.id)
        .filter(Surrogate.organization_id == org_id)
        .order_by(Surrogate.created_at.asc())
    )

    for (
        case,
        stage,
        owner_user_row,
        owner_queue_row,
        created_by_row,
        archived_by_row,
        meta_lead_row,
    ) in query.yield_per(500):
        owner_name = owner_user_row.display_name if owner_user_row else None
        owner_email = owner_user_row.email if owner_user_row else None
        owner_queue_name = owner_queue_row.name if owner_queue_row else None

        yield _write_csv_row(
            [
                case.id,
                case.surrogate_number,
                case.organization_id,
                case.status_label,
                case.stage_id,
                stage.slug if stage else None,
                stage.label if stage else None,
                stage.order if stage else None,
                case.source,
                case.is_priority,
                case.owner_type,
                case.owner_id,
                owner_name,
                owner_email,
                owner_queue_name,
                case.created_by_user_id,
                created_by_row.display_name if created_by_row else None,
                created_by_row.email if created_by_row else None,
                case.meta_lead_id,
                meta_lead_row.meta_lead_id if meta_lead_row else None,
                meta_lead_row.meta_form_id if meta_lead_row else None,
                meta_lead_row.meta_page_id if meta_lead_row else None,
                meta_lead_row.status if meta_lead_row else None,
                meta_lead_row.fetch_error if meta_lead_row else None,
                meta_lead_row.conversion_error if meta_lead_row else None,
                meta_lead_row.is_converted if meta_lead_row else None,
                meta_lead_row.meta_created_time if meta_lead_row else None,
                meta_lead_row.received_at if meta_lead_row else None,
                meta_lead_row.converted_at if meta_lead_row else None,
                meta_lead_row.field_data if meta_lead_row else None,
                meta_lead_row.raw_payload if meta_lead_row else None,
                meta_lead_row.field_data_raw if meta_lead_row else None,
                case.meta_ad_external_id,
                case.meta_form_id,
                case.full_name,
                case.email,
                case.phone,
                case.state,
                case.date_of_birth,
                case.race,
                case.height_ft,
                case.weight_lb,
                case.is_age_eligible,
                case.is_citizen_or_pr,
                case.has_child,
                case.is_non_smoker,
                case.has_surrogate_experience,
                case.num_deliveries,
                case.num_csections,
                case.is_archived,
                case.archived_at,
                case.archived_by_user_id,
                archived_by_row.display_name if archived_by_row else None,
                archived_by_row.email if archived_by_row else None,
                case.last_contacted_at,
                case.last_contact_method,
                case.created_at,
                case.updated_at,
            ]
        )


def build_org_config_zip(db: Session, org_id: UUID) -> bytes:
    org = db.query(Organization).filter(Organization.id == org_id).first()

    pipelines = (
        db.query(Pipeline)
        .filter(Pipeline.organization_id == org_id)
        .order_by(Pipeline.is_default.desc(), Pipeline.name)
        .all()
    )
    pipeline_ids = [pipeline.id for pipeline in pipelines]
    stages_by_pipeline: dict[UUID, list[PipelineStage]] = {}
    if pipeline_ids:
        stages = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id.in_(pipeline_ids))
            .order_by(PipelineStage.pipeline_id, PipelineStage.order)
            .all()
        )
        for stage in stages:
            stages_by_pipeline.setdefault(stage.pipeline_id, []).append(stage)
    pipeline_payload = []
    for pipeline in pipelines:
        stages = stages_by_pipeline.get(pipeline.id, [])
        pipeline_payload.append(
            {
                "id": str(pipeline.id),
                "name": pipeline.name,
                "is_default": pipeline.is_default,
                "current_version": pipeline.current_version,
                "created_at": pipeline.created_at,
                "updated_at": pipeline.updated_at,
                "stages": [
                    {
                        "id": str(stage.id),
                        "slug": stage.slug,
                        "label": stage.label,
                        "color": stage.color,
                        "order": stage.order,
                        "stage_type": stage.stage_type,
                        "is_active": stage.is_active,
                        "deleted_at": stage.deleted_at,
                        "created_at": stage.created_at,
                        "updated_at": stage.updated_at,
                    }
                    for stage in stages
                ],
            }
        )

    templates = (
        db.query(EmailTemplate)
        .filter(EmailTemplate.organization_id == org_id)
        .order_by(EmailTemplate.name)
        .all()
    )
    template_payload = [
        {
            "id": str(t.id),
            "name": t.name,
            "subject": t.subject,
            "from_email": t.from_email,
            "body": t.body,
            "is_active": t.is_active,
            "is_system_template": t.is_system_template,
            "system_key": t.system_key,
            "category": t.category,
            "current_version": t.current_version,
            "created_by_user_id": str(t.created_by_user_id) if t.created_by_user_id else None,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in templates
    ]

    workflows = (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.organization_id == org_id)
        .order_by(AutomationWorkflow.created_at.asc())
        .all()
    )
    workflow_payload = [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "icon": w.icon,
            "schema_version": w.schema_version,
            "trigger_type": w.trigger_type,
            "trigger_config": w.trigger_config,
            "conditions": w.conditions,
            "condition_logic": w.condition_logic,
            "actions": w.actions,
            "is_enabled": w.is_enabled,
            "run_count": w.run_count,
            "last_run_at": w.last_run_at,
            "last_error": w.last_error,
            "recurrence_mode": w.recurrence_mode,
            "recurrence_interval_hours": w.recurrence_interval_hours,
            "recurrence_stop_on_status": w.recurrence_stop_on_status,
            "rate_limit_per_hour": w.rate_limit_per_hour,
            "rate_limit_per_entity_per_day": w.rate_limit_per_entity_per_day,
            "is_system_workflow": w.is_system_workflow,
            "system_key": w.system_key,
            "requires_review": w.requires_review,
            "reviewed_at": w.reviewed_at,
            "reviewed_by_user_id": str(w.reviewed_by_user_id) if w.reviewed_by_user_id else None,
            "created_by_user_id": str(w.created_by_user_id) if w.created_by_user_id else None,
            "updated_by_user_id": str(w.updated_by_user_id) if w.updated_by_user_id else None,
            "created_at": w.created_at,
            "updated_at": w.updated_at,
        }
        for w in workflows
    ]

    forms = (
        db.query(Form).filter(Form.organization_id == org_id).order_by(Form.created_at.asc()).all()
    )
    form_payload = [
        {
            "id": str(form.id),
            "organization_id": str(form.organization_id),
            "name": form.name,
            "description": form.description,
            "status": form.status,
            "schema_json": form.schema_json,
            "published_schema_json": form.published_schema_json,
            "max_file_size_bytes": form.max_file_size_bytes,
            "max_file_count": form.max_file_count,
            "allowed_mime_types": form.allowed_mime_types,
            "created_by_user_id": str(form.created_by_user_id) if form.created_by_user_id else None,
            "updated_by_user_id": str(form.updated_by_user_id) if form.updated_by_user_id else None,
            "created_at": form.created_at,
            "updated_at": form.updated_at,
        }
        for form in forms
    ]

    form_logos = (
        db.query(FormLogo)
        .filter(FormLogo.organization_id == org_id)
        .order_by(FormLogo.created_at.asc())
        .all()
    )
    form_logo_payload = [
        {
            "id": str(logo.id),
            "organization_id": str(logo.organization_id),
            "storage_key": logo.storage_key,
            "filename": logo.filename,
            "content_type": logo.content_type,
            "file_size": logo.file_size,
            "created_by_user_id": str(logo.created_by_user_id) if logo.created_by_user_id else None,
            "created_at": logo.created_at,
        }
        for logo in form_logos
    ]

    form_field_mappings = (
        db.query(FormFieldMapping)
        .join(Form, FormFieldMapping.form_id == Form.id)
        .filter(Form.organization_id == org_id)
        .order_by(FormFieldMapping.created_at.asc())
        .all()
    )
    form_field_mapping_payload = [
        {
            "id": str(mapping.id),
            "form_id": str(mapping.form_id),
            "field_key": mapping.field_key,
            "surrogate_field": mapping.surrogate_field,
            "created_at": mapping.created_at,
        }
        for mapping in form_field_mappings
    ]

    appointment_types = (
        db.query(AppointmentType)
        .filter(AppointmentType.organization_id == org_id)
        .order_by(AppointmentType.created_at.asc())
        .all()
    )
    appointment_type_payload = [
        {
            "id": str(appointment_type.id),
            "organization_id": str(appointment_type.organization_id),
            "user_id": str(appointment_type.user_id),
            "name": appointment_type.name,
            "slug": appointment_type.slug,
            "description": appointment_type.description,
            "duration_minutes": appointment_type.duration_minutes,
            "buffer_before_minutes": appointment_type.buffer_before_minutes,
            "buffer_after_minutes": appointment_type.buffer_after_minutes,
            "meeting_mode": appointment_type.meeting_mode,
            "reminder_hours_before": appointment_type.reminder_hours_before,
            "is_active": appointment_type.is_active,
            "created_at": appointment_type.created_at,
            "updated_at": appointment_type.updated_at,
        }
        for appointment_type in appointment_types
    ]

    availability_rules = (
        db.query(AvailabilityRule)
        .filter(AvailabilityRule.organization_id == org_id)
        .order_by(AvailabilityRule.created_at.asc())
        .all()
    )
    availability_rule_payload = [
        {
            "id": str(rule.id),
            "organization_id": str(rule.organization_id),
            "user_id": str(rule.user_id),
            "day_of_week": rule.day_of_week,
            "start_time": rule.start_time,
            "end_time": rule.end_time,
            "timezone": rule.timezone,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }
        for rule in availability_rules
    ]

    availability_overrides = (
        db.query(AvailabilityOverride)
        .filter(AvailabilityOverride.organization_id == org_id)
        .order_by(AvailabilityOverride.created_at.asc())
        .all()
    )
    availability_override_payload = [
        {
            "id": str(override.id),
            "organization_id": str(override.organization_id),
            "user_id": str(override.user_id),
            "override_date": override.override_date,
            "is_unavailable": override.is_unavailable,
            "start_time": override.start_time,
            "end_time": override.end_time,
            "reason": override.reason,
            "created_at": override.created_at,
        }
        for override in availability_overrides
    ]

    booking_links = (
        db.query(BookingLink)
        .filter(BookingLink.organization_id == org_id)
        .order_by(BookingLink.created_at.asc())
        .all()
    )
    booking_link_payload = [
        {
            "id": str(link.id),
            "organization_id": str(link.organization_id),
            "user_id": str(link.user_id),
            "public_slug": link.public_slug,
            "is_active": link.is_active,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
        }
        for link in booking_links
    ]

    workflow_templates = (
        db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.organization_id == org_id)
        .order_by(WorkflowTemplate.created_at.asc())
        .all()
    )
    workflow_template_payload = [
        {
            "id": str(template.id),
            "name": template.name,
            "description": template.description,
            "icon": template.icon,
            "category": template.category,
            "trigger_type": template.trigger_type,
            "trigger_config": template.trigger_config,
            "conditions": template.conditions,
            "condition_logic": template.condition_logic,
            "actions": template.actions,
            "is_global": template.is_global,
            "organization_id": str(template.organization_id) if template.organization_id else None,
            "usage_count": template.usage_count,
            "created_by_user_id": str(template.created_by_user_id)
            if template.created_by_user_id
            else None,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }
        for template in workflow_templates
    ]

    retention_policies = (
        db.query(DataRetentionPolicy)
        .filter(DataRetentionPolicy.organization_id == org_id)
        .order_by(DataRetentionPolicy.entity_type)
        .all()
    )
    retention_policy_payload = [
        {
            "id": str(policy.id),
            "organization_id": str(policy.organization_id),
            "entity_type": policy.entity_type,
            "retention_days": policy.retention_days,
            "is_active": policy.is_active,
            "created_by_user_id": str(policy.created_by_user_id)
            if policy.created_by_user_id
            else None,
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
        }
        for policy in retention_policies
    ]

    legal_holds = (
        db.query(LegalHold)
        .filter(LegalHold.organization_id == org_id)
        .order_by(LegalHold.created_at.asc())
        .all()
    )
    legal_hold_payload = [
        {
            "id": str(hold.id),
            "organization_id": str(hold.organization_id),
            "entity_type": hold.entity_type,
            "entity_id": str(hold.entity_id) if hold.entity_id else None,
            "reason": hold.reason,
            "created_by_user_id": str(hold.created_by_user_id) if hold.created_by_user_id else None,
            "released_by_user_id": str(hold.released_by_user_id)
            if hold.released_by_user_id
            else None,
            "created_at": hold.created_at,
            "released_at": hold.released_at,
        }
        for hold in legal_holds
    ]

    org_counters = (
        db.query(OrgCounter)
        .filter(OrgCounter.organization_id == org_id)
        .order_by(OrgCounter.counter_type)
        .all()
    )
    org_counter_payload = [
        {
            "organization_id": str(counter.organization_id),
            "counter_type": counter.counter_type,
            "current_value": counter.current_value,
            "updated_at": counter.updated_at,
        }
        for counter in org_counters
    ]

    members = (
        db.query(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .order_by(User.email)
        .all()
    )

    user_payload = [
        {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "phone": user.phone,
            "title": user.title,
            "signature_name": user.signature_name,
            "signature_title": user.signature_title,
            "signature_phone": user.signature_phone,
            "signature_photo_url": user.signature_photo_url,
            "signature_linkedin": user.signature_linkedin,
            "signature_twitter": user.signature_twitter,
            "signature_instagram": user.signature_instagram,
        }
        for user, _membership in members
    ]

    membership_payload = [
        {
            "id": str(membership.id),
            "user_id": str(membership.user_id),
            "organization_id": str(membership.organization_id),
            "role": membership.role,
            "is_active": membership.is_active,
            "created_at": membership.created_at,
        }
        for _user, membership in members
    ]

    queues = db.query(Queue).filter(Queue.organization_id == org_id).order_by(Queue.name).all()
    queue_payload = [
        {
            "id": str(queue.id),
            "organization_id": str(queue.organization_id),
            "name": queue.name,
            "description": queue.description,
            "is_active": queue.is_active,
            "created_at": queue.created_at,
            "updated_at": queue.updated_at,
        }
        for queue in queues
    ]

    queue_members = (
        db.query(QueueMember)
        .join(Queue, QueueMember.queue_id == Queue.id)
        .filter(Queue.organization_id == org_id)
        .all()
    )
    queue_member_payload = [
        {
            "id": str(member.id),
            "queue_id": str(member.queue_id),
            "user_id": str(member.user_id),
            "created_at": member.created_at,
        }
        for member in queue_members
    ]

    notification_settings = (
        db.query(UserNotificationSettings, User)
        .join(User, UserNotificationSettings.user_id == User.id)
        .filter(UserNotificationSettings.organization_id == org_id)
        .order_by(User.email)
        .all()
    )
    notification_payload = [
        {
            "user_id": str(settings_row.user_id),
            "email": user.email,
            "surrogate_assigned": settings_row.surrogate_assigned,
            "surrogate_status_changed": settings_row.surrogate_status_changed,
            "surrogate_claim_available": settings_row.surrogate_claim_available,
            "task_assigned": settings_row.task_assigned,
            "workflow_approvals": settings_row.workflow_approvals,
            "task_reminders": settings_row.task_reminders,
            "appointments": settings_row.appointments,
            "contact_reminder": settings_row.contact_reminder,
            "updated_at": settings_row.updated_at,
        }
        for settings_row, user in notification_settings
    ]

    integrations = (
        db.query(UserIntegration, User, Membership)
        .join(User, UserIntegration.user_id == User.id)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .order_by(User.email, UserIntegration.integration_type)
        .all()
    )
    integration_payload = [
        {
            "user_id": str(user.id),
            "email": user.email,
            "integration_type": integration.integration_type,
            "account_email": integration.account_email,
            "token_expires_at": integration.token_expires_at,
            "created_at": integration.created_at,
            "updated_at": integration.updated_at,
            "is_connected": integration.access_token_encrypted is not None,
        }
        for integration, user, _membership in integrations
    ]

    ai_settings = db.query(AISettings).filter(AISettings.organization_id == org_id).first()
    ai_payload = None
    if ai_settings:
        ai_payload = {
            "id": str(ai_settings.id),
            "is_enabled": ai_settings.is_enabled,
            "provider": ai_settings.provider,
            "model": ai_settings.model,
            "context_notes_limit": ai_settings.context_notes_limit,
            "conversation_history_limit": ai_settings.conversation_history_limit,
            "consent_accepted_at": ai_settings.consent_accepted_at,
            "consent_accepted_by": str(ai_settings.consent_accepted_by)
            if ai_settings.consent_accepted_by
            else None,
            "anonymize_pii": ai_settings.anonymize_pii,
            "current_version": ai_settings.current_version,
            "has_api_key": ai_settings.api_key_encrypted is not None,
            "created_at": ai_settings.created_at,
            "updated_at": ai_settings.updated_at,
        }

    role_permissions = (
        db.query(RolePermission)
        .filter(RolePermission.organization_id == org_id)
        .order_by(RolePermission.role, RolePermission.permission)
        .all()
    )
    role_permission_payload = [
        {
            "id": str(permission.id),
            "organization_id": str(permission.organization_id),
            "role": permission.role,
            "permission": permission.permission,
            "is_granted": permission.is_granted,
            "created_at": permission.created_at,
            "updated_at": permission.updated_at,
        }
        for permission in role_permissions
    ]

    user_overrides = (
        db.query(UserPermissionOverride)
        .filter(UserPermissionOverride.organization_id == org_id)
        .order_by(UserPermissionOverride.user_id, UserPermissionOverride.permission)
        .all()
    )
    user_override_payload = [
        {
            "id": str(override.id),
            "organization_id": str(override.organization_id),
            "user_id": str(override.user_id),
            "permission": override.permission,
            "override_type": override.override_type,
            "created_at": override.created_at,
            "updated_at": override.updated_at,
        }
        for override in user_overrides
    ]

    meta_pages = (
        db.query(MetaPageMapping)
        .filter(MetaPageMapping.organization_id == org_id)
        .order_by(MetaPageMapping.created_at.desc())
        .all()
    )
    meta_page_payload = [
        {
            "id": str(page.id),
            "organization_id": str(page.organization_id),
            "page_id": page.page_id,
            "page_name": page.page_name,
            "token_expires_at": page.token_expires_at,
            "is_active": page.is_active,
            "last_success_at": page.last_success_at,
            "last_error": page.last_error,
            "last_error_at": page.last_error_at,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
            "has_token": page.access_token_encrypted is not None,
        }
        for page in meta_pages
    ]

    org_payload = None
    if org:
        org_payload = {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "portal_domain": org.portal_domain,
            "timezone": org.timezone,
            "ai_enabled": org.ai_enabled,
            "current_version": org.current_version,
            "signature_template": org.signature_template,
            "signature_logo_url": org.signature_logo_url,
            "signature_primary_color": org.signature_primary_color,
            "signature_company_name": org.signature_company_name,
            "signature_address": org.signature_address,
            "signature_phone": org.signature_phone,
            "signature_website": org.signature_website,
            "signature_social_links": org.signature_social_links,
            "signature_disclaimer": org.signature_disclaimer,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
        }

    manifest = {
        "organization_id": str(org_id),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": settings.VERSION,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _write_json(manifest))
        archive.writestr("organization.json", _write_json(org_payload))
        archive.writestr("pipelines.json", _write_json(pipeline_payload))
        archive.writestr("users.json", _write_json(user_payload))
        archive.writestr("memberships.json", _write_json(membership_payload))
        archive.writestr("queues.json", _write_json(queue_payload))
        archive.writestr("queue_members.json", _write_json(queue_member_payload))
        archive.writestr("role_permissions.json", _write_json(role_permission_payload))
        archive.writestr("user_permission_overrides.json", _write_json(user_override_payload))
        archive.writestr("email_templates.json", _write_json(template_payload))
        archive.writestr("notification_settings.json", _write_json(notification_payload))
        archive.writestr("workflows.json", _write_json(workflow_payload))
        archive.writestr("forms.json", _write_json(form_payload))
        archive.writestr("form_logos.json", _write_json(form_logo_payload))
        archive.writestr("form_field_mappings.json", _write_json(form_field_mapping_payload))
        archive.writestr("appointment_types.json", _write_json(appointment_type_payload))
        archive.writestr("availability_rules.json", _write_json(availability_rule_payload))
        archive.writestr(
            "availability_overrides.json",
            _write_json(availability_override_payload),
        )
        archive.writestr("booking_links.json", _write_json(booking_link_payload))
        archive.writestr("workflow_templates.json", _write_json(workflow_template_payload))
        archive.writestr("data_retention_policies.json", _write_json(retention_policy_payload))
        archive.writestr("legal_holds.json", _write_json(legal_hold_payload))
        archive.writestr("org_counters.json", _write_json(org_counter_payload))
        archive.writestr("integrations.json", _write_json(integration_payload))
        archive.writestr("meta_pages.json", _write_json(meta_page_payload))
        archive.writestr("ai_settings.json", _write_json(ai_payload))

    buffer.seek(0)
    return buffer.read()


def build_analytics_zip(
    db: Session,
    org_id: UUID,
    start: datetime,
    end: datetime,
    ad_id: str | None,
    meta_spend: dict[str, Any],
) -> bytes:
    summary = analytics_service.get_cached_analytics_summary(db, org_id, start, end)
    surrogates_by_status = analytics_service.get_cached_surrogates_by_status(db, org_id)
    surrogates_by_assignee = analytics_service.get_cached_surrogates_by_assignee(db, org_id)
    surrogates_trend = analytics_service.get_cached_surrogates_trend(
        db, org_id, start=start, end=end, group_by="day"
    )
    meta_performance = analytics_service.get_cached_meta_performance(db, org_id, start, end)
    campaigns = analytics_service.get_campaigns(db, org_id)
    funnel = analytics_service.get_funnel_with_filter(
        db,
        org_id,
        start.date(),
        end.date(),
        ad_id,
    )
    surrogates_by_state = analytics_service.get_surrogates_by_state_with_filter(
        db,
        org_id,
        start.date(),
        end.date(),
        ad_id,
    )
    ai_usage = ai_usage_service.get_org_usage_summary(db, org_id, days=30)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "summary.csv",
            _write_csv(
                list(summary.keys()),
                [summary.values()],
            ),
        )
        archive.writestr(
            "surrogates_by_status.csv",
            _write_csv(
                ["status", "count"],
                [(item["status"], item["count"]) for item in surrogates_by_status],
            ),
        )
        archive.writestr(
            "surrogates_by_assignee.csv",
            _write_csv(
                ["user_id", "user_email", "count"],
                [
                    (item["user_id"], item["user_email"], item["count"])
                    for item in surrogates_by_assignee
                ],
            ),
        )
        archive.writestr(
            "surrogates_trend.csv",
            _write_csv(
                ["date", "count"],
                [(item["date"], item["count"]) for item in surrogates_trend],
            ),
        )
        archive.writestr(
            "meta_performance.csv",
            _write_csv(
                list(meta_performance.keys()),
                [meta_performance.values()],
            ),
        )
        archive.writestr(
            "meta_spend_campaigns.csv",
            _write_csv(
                [
                    "campaign_id",
                    "campaign_name",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "leads",
                    "cost_per_lead",
                ],
                [
                    (
                        item["campaign_id"],
                        item["campaign_name"],
                        item["spend"],
                        item["impressions"],
                        item["reach"],
                        item["clicks"],
                        item["leads"],
                        item["cost_per_lead"],
                    )
                    for item in meta_spend.get("campaigns", [])
                ],
            ),
        )
        archive.writestr(
            "meta_spend_time_series.csv",
            _write_csv(
                [
                    "date_start",
                    "date_stop",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "leads",
                    "cost_per_lead",
                ],
                [
                    (
                        item["date_start"],
                        item["date_stop"],
                        item["spend"],
                        item["impressions"],
                        item["reach"],
                        item["clicks"],
                        item["leads"],
                        item["cost_per_lead"],
                    )
                    for item in meta_spend.get("time_series", [])
                ],
            ),
        )
        archive.writestr(
            "meta_spend_breakdowns.csv",
            _write_csv(
                [
                    "breakdown_values",
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "leads",
                    "cost_per_lead",
                ],
                [
                    (
                        json.dumps(item.get("breakdown_values", {}), sort_keys=True),
                        item["spend"],
                        item["impressions"],
                        item["reach"],
                        item["clicks"],
                        item["leads"],
                        item["cost_per_lead"],
                    )
                    for item in meta_spend.get("breakdowns", [])
                ],
            ),
        )
        archive.writestr(
            "campaigns.csv",
            _write_csv(
                ["ad_id", "ad_name", "lead_count"],
                [(item["ad_id"], item["ad_name"], item["lead_count"]) for item in campaigns],
            ),
        )
        archive.writestr(
            "funnel.csv",
            _write_csv(
                ["stage", "label", "count", "percentage"],
                [
                    (item["stage"], item["label"], item["count"], item["percentage"])
                    for item in funnel
                ],
            ),
        )
        archive.writestr(
            "surrogates_by_state.csv",
            _write_csv(
                ["state", "count"],
                [(item["state"], item["count"]) for item in surrogates_by_state],
            ),
        )
        archive.writestr(
            "ai_usage_summary.csv",
            _write_csv(
                list(ai_usage.keys()),
                [ai_usage.values()],
            ),
        )

    buffer.seek(0)
    return buffer.read()
