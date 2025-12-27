"""Developer-only import helpers for org restore."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import OwnerType
from app.db.models import (
    AISettings,
    AutomationWorkflow,
    Case,
    EmailTemplate,
    Membership,
    MetaLead,
    MetaPageMapping,
    Organization,
    Pipeline,
    PipelineStage,
    Queue,
    QueueMember,
    RolePermission,
    User,
    UserIntegration,
    UserNotificationSettings,
    UserPermissionOverride,
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


def _load_json(archive: zipfile.ZipFile, name: str, default: Any) -> Any:
    if name not in archive.namelist():
        return default
    with archive.open(name) as handle:
        return json.loads(handle.read().decode("utf-8"))


def _ensure_empty_org(db: Session, org_id: UUID) -> None:
    checks = {
        "cases": db.query(Case).filter(Case.organization_id == org_id).count(),
        "pipelines": db.query(Pipeline).filter(Pipeline.organization_id == org_id).count(),
        "pipeline_stages": db.query(PipelineStage).join(
            Pipeline, PipelineStage.pipeline_id == Pipeline.id
        ).filter(Pipeline.organization_id == org_id).count(),
        "workflows": db.query(AutomationWorkflow).filter(AutomationWorkflow.organization_id == org_id).count(),
        "email_templates": db.query(EmailTemplate).filter(EmailTemplate.organization_id == org_id).count(),
        "meta_leads": db.query(MetaLead).filter(MetaLead.organization_id == org_id).count(),
        "queues": db.query(Queue).filter(Queue.organization_id == org_id).count(),
        "queue_members": db.query(QueueMember).join(
            Queue, QueueMember.queue_id == Queue.id
        ).filter(Queue.organization_id == org_id).count(),
        "notification_settings": db.query(UserNotificationSettings).filter(
            UserNotificationSettings.organization_id == org_id
        ).count(),
        "integrations": db.query(UserIntegration).join(
            User, UserIntegration.user_id == User.id
        ).join(
            Membership, Membership.user_id == User.id
        ).filter(Membership.organization_id == org_id).count(),
        "ai_settings": db.query(AISettings).filter(AISettings.organization_id == org_id).count(),
        "meta_pages": db.query(MetaPageMapping).filter(MetaPageMapping.organization_id == org_id).count(),
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

    existing_memberships = db.query(Membership).filter(Membership.organization_id == org_id).all()
    export_user_ids = {UUID(item["id"]) for item in users_payload if item.get("id")}
    for membership in existing_memberships:
        if membership.user_id not in export_user_ids:
            raise ValueError("Existing member not present in export; import requires matching user IDs.")

    existing_users_by_id = {
        user.id: user
        for user in db.query(User).filter(User.id.in_(export_user_ids)).all()
    }
    existing_users_by_email = {
        user.email.lower(): user
        for user in db.query(User).filter(func.lower(User.email).in_([item.get("email", "").lower() for item in users_payload])).all()
    }

    for user_data in users_payload:
        user_id = UUID(user_data["id"])
        email = user_data.get("email", "").lower()
        if not email:
            raise ValueError("User email is required in export")

        existing_by_email = existing_users_by_email.get(email)
        if existing_by_email and existing_by_email.id != user_id:
            raise ValueError(f"User email conflict for {email}; UUID preservation requires matching IDs.")

        user = existing_users_by_id.get(user_id)
        if user:
            user.email = user_data.get("email", user.email)
            user.display_name = user_data.get("display_name", user.display_name)
            user.avatar_url = user_data.get("avatar_url")
            user.is_active = user_data.get("is_active", user.is_active)
            user.signature_name = user_data.get("signature_name")
            user.signature_title = user_data.get("signature_title")
            user.signature_company = user_data.get("signature_company")
            user.signature_phone = user_data.get("signature_phone")
            user.signature_email = user_data.get("signature_email")
            user.signature_address = user_data.get("signature_address")
            user.signature_website = user_data.get("signature_website")
            user.signature_logo_url = user_data.get("signature_logo_url")
            user.signature_html = user_data.get("signature_html")
        else:
            user = User(
                id=user_id,
                email=user_data.get("email"),
                display_name=user_data.get("display_name"),
                avatar_url=user_data.get("avatar_url"),
                is_active=user_data.get("is_active", True),
                signature_name=user_data.get("signature_name"),
                signature_title=user_data.get("signature_title"),
                signature_company=user_data.get("signature_company"),
                signature_phone=user_data.get("signature_phone"),
                signature_email=user_data.get("signature_email"),
                signature_address=user_data.get("signature_address"),
                signature_website=user_data.get("signature_website"),
                signature_logo_url=user_data.get("signature_logo_url"),
                signature_html=user_data.get("signature_html"),
                created_at=_parse_datetime(user_data.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(user_data.get("updated_at")) or datetime.utcnow(),
            )
            db.add(user)

    db.flush()

    existing_memberships_by_user = {
        membership.user_id: membership
        for membership in db.query(Membership).filter(Membership.organization_id == org_id).all()
    }

    for membership_data in memberships_payload:
        user_id = UUID(membership_data["user_id"])
        membership = existing_memberships_by_user.get(user_id)
        if membership:
            if membership.id != UUID(membership_data["id"]):
                raise ValueError("Existing membership ID does not match export; UUID preservation required.")
            membership.role = membership_data.get("role", membership.role)
        else:
            membership = Membership(
                id=UUID(membership_data["id"]),
                user_id=user_id,
                organization_id=org_id,
                role=membership_data.get("role"),
                created_at=_parse_datetime(membership_data.get("created_at")) or datetime.utcnow(),
            )
            db.add(membership)

    for queue_data in queues_payload:
        queue = Queue(
            id=UUID(queue_data["id"]),
            organization_id=org_id,
            name=queue_data.get("name"),
            description=queue_data.get("description"),
            is_active=queue_data.get("is_active", True),
            created_at=_parse_datetime(queue_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(queue_data.get("updated_at")) or datetime.utcnow(),
        )
        db.add(queue)

    for queue_member_data in queue_members_payload:
        member = QueueMember(
            id=UUID(queue_member_data["id"]),
            queue_id=UUID(queue_member_data["queue_id"]),
            user_id=UUID(queue_member_data["user_id"]),
            created_at=_parse_datetime(queue_member_data.get("created_at")) or datetime.utcnow(),
        )
        db.add(member)

    for pipeline_data in pipelines_payload:
        pipeline = Pipeline(
            id=UUID(pipeline_data["id"]),
            organization_id=org_id,
            name=pipeline_data.get("name"),
            is_default=pipeline_data.get("is_default", False),
            current_version=pipeline_data.get("current_version") or 1,
            created_at=_parse_datetime(pipeline_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(pipeline_data.get("updated_at")) or datetime.utcnow(),
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
                created_at=_parse_datetime(stage_data.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_datetime(stage_data.get("updated_at")) or datetime.utcnow(),
            )
            db.add(stage)

    for template_data in templates_payload:
        template = EmailTemplate(
            id=UUID(template_data["id"]),
            organization_id=org_id,
            created_by_user_id=_parse_uuid(template_data.get("created_by_user_id")),
            name=template_data.get("name"),
            subject=template_data.get("subject"),
            body=template_data.get("body"),
            is_active=template_data.get("is_active", True),
            is_system_template=template_data.get("is_system_template", False),
            system_key=template_data.get("system_key"),
            category=template_data.get("category"),
            current_version=template_data.get("current_version") or 1,
            created_at=_parse_datetime(template_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(template_data.get("updated_at")) or datetime.utcnow(),
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
            reviewed_by_user_id=_parse_uuid(workflow_data.get("reviewed_by_user_id")),
            created_by_user_id=_parse_uuid(workflow_data.get("created_by_user_id")),
            updated_by_user_id=_parse_uuid(workflow_data.get("updated_by_user_id")),
            created_at=_parse_datetime(workflow_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(workflow_data.get("updated_at")) or datetime.utcnow(),
        )
        db.add(workflow)

    for settings_data in notification_payload:
        settings_row = UserNotificationSettings(
            user_id=UUID(settings_data["user_id"]),
            organization_id=org_id,
            case_assigned=settings_data.get("case_assigned", True),
            case_status_changed=settings_data.get("case_status_changed", True),
            case_handoff=settings_data.get("case_handoff", True),
            task_assigned=settings_data.get("task_assigned", True),
            task_reminders=settings_data.get("task_reminders", True),
            appointments=settings_data.get("appointments", True),
            updated_at=_parse_datetime(settings_data.get("updated_at")) or datetime.utcnow(),
        )
        db.merge(settings_row)

    if ai_settings_payload:
        ai_settings = AISettings(
            id=UUID(ai_settings_payload["id"]),
            organization_id=org_id,
            is_enabled=ai_settings_payload.get("is_enabled", False),
            provider=ai_settings_payload.get("provider", "openai"),
            model=ai_settings_payload.get("model"),
            context_notes_limit=ai_settings_payload.get("context_notes_limit"),
            conversation_history_limit=ai_settings_payload.get("conversation_history_limit"),
            consent_accepted_at=_parse_datetime(ai_settings_payload.get("consent_accepted_at")),
            consent_accepted_by=_parse_uuid(ai_settings_payload.get("consent_accepted_by")),
            anonymize_pii=ai_settings_payload.get("anonymize_pii", True),
            current_version=ai_settings_payload.get("current_version") or 1,
            api_key_encrypted=None,
            created_at=_parse_datetime(ai_settings_payload.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(ai_settings_payload.get("updated_at")) or datetime.utcnow(),
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
            created_at=_parse_datetime(meta_page_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(meta_page_data.get("updated_at")) or datetime.utcnow(),
            access_token_encrypted=None,
        )
        db.add(meta_page)

    db.query(RolePermission).filter(RolePermission.organization_id == org_id).delete()
    for permission_data in role_permissions_payload:
        permission = RolePermission(
            id=UUID(permission_data["id"]),
            organization_id=org_id,
            role=permission_data.get("role"),
            permission=permission_data.get("permission"),
            is_granted=permission_data.get("is_granted", True),
            created_at=_parse_datetime(permission_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(permission_data.get("updated_at")) or datetime.utcnow(),
        )
        db.add(permission)

    db.query(UserPermissionOverride).filter(UserPermissionOverride.organization_id == org_id).delete()
    for override_data in user_overrides_payload:
        override = UserPermissionOverride(
            id=UUID(override_data["id"]),
            organization_id=org_id,
            user_id=UUID(override_data["user_id"]),
            permission=override_data.get("permission"),
            override_type=override_data.get("override_type"),
            created_at=_parse_datetime(override_data.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(override_data.get("updated_at")) or datetime.utcnow(),
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
        "notification_settings": len(notification_payload),
        "role_permissions": len(role_permissions_payload),
        "user_permission_overrides": len(user_overrides_payload),
        "meta_pages": len(meta_pages_payload),
        "ai_settings": 1 if ai_settings_payload else 0,
        "integrations_skipped": len(integrations_payload),
    }


def import_cases_csv(db: Session, org_id: UUID, content: bytes) -> int:
    if db.query(Case).filter(Case.organization_id == org_id).count():
        raise ValueError("Organization already has cases; import requires an empty org.")
    text_content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_content))
    if not reader.fieldnames:
        raise ValueError("CSV has no headers")

    stage_ids = {
        stage.id
        for stage in db.query(PipelineStage).join(
            Pipeline, PipelineStage.pipeline_id == Pipeline.id
        ).filter(Pipeline.organization_id == org_id).all()
    }
    user_ids = {user.id for user in db.query(User).join(
        Membership, Membership.user_id == User.id
    ).filter(Membership.organization_id == org_id).all()}
    queue_ids = {queue.id for queue in db.query(Queue).filter(Queue.organization_id == org_id).all()}

    meta_leads_to_link: list[tuple[UUID, UUID]] = []
    imported = 0

    for row in reader:
        case_id = _parse_uuid(row.get("id"))
        if not case_id:
            raise ValueError("Case id is required")

        stage_id = _parse_uuid(row.get("stage_id"))
        if not stage_id:
            raise ValueError(f"Stage id is required for case {case_id}")
        if stage_id not in stage_ids:
            raise ValueError(f"Stage {stage_id} not found for case {case_id}")

        owner_type = row.get("owner_type")
        if owner_type not in (OwnerType.USER.value, OwnerType.QUEUE.value):
            raise ValueError(f"Invalid owner_type for case {case_id}")
        owner_id = _parse_uuid(row.get("owner_id"))
        if not owner_id:
            raise ValueError(f"Owner id required for case {case_id}")
        if owner_type == OwnerType.USER.value and owner_id not in user_ids:
            raise ValueError(f"Owner user {owner_id} not found for case {case_id}")
        if owner_type == OwnerType.QUEUE.value and owner_id not in queue_ids:
            raise ValueError(f"Owner queue {owner_id} not found for case {case_id}")

        meta_lead_id = _parse_uuid(row.get("meta_lead_id"))
        meta_lead_external_id = row.get("meta_lead_external_id")
        meta_lead_form_id = row.get("meta_lead_form_id")
        meta_lead_page_id = row.get("meta_lead_page_id")

        if meta_lead_id and not meta_lead_external_id:
            raise ValueError(f"Missing meta_lead_external_id for case {case_id}")

        created_by_user_id = _parse_uuid(row.get("created_by_user_id"))
        if created_by_user_id and created_by_user_id not in user_ids:
            raise ValueError(f"Created-by user {created_by_user_id} not found for case {case_id}")

        archived_by_user_id = _parse_uuid(row.get("archived_by_user_id"))
        if archived_by_user_id and archived_by_user_id not in user_ids:
            raise ValueError(f"Archived-by user {archived_by_user_id} not found for case {case_id}")

        if not row.get("case_number"):
            raise ValueError(f"Missing case_number for case {case_id}")
        if not row.get("status_label"):
            raise ValueError(f"Missing status_label for case {case_id}")
        if not row.get("source"):
            raise ValueError(f"Missing source for case {case_id}")
        if not row.get("full_name"):
            raise ValueError(f"Missing full_name for case {case_id}")
        if not row.get("email"):
            raise ValueError(f"Missing email for case {case_id}")

        if meta_lead_id and meta_lead_external_id:
            existing_meta = db.query(MetaLead).filter(MetaLead.id == meta_lead_id).first()
            if not existing_meta:
                meta_lead = MetaLead(
                    id=meta_lead_id,
                    organization_id=org_id,
                    meta_lead_id=meta_lead_external_id,
                    meta_form_id=meta_lead_form_id,
                    meta_page_id=meta_lead_page_id,
                    is_converted=True,
                    converted_case_id=None,
                    status="converted",
                )
                db.add(meta_lead)
            meta_leads_to_link.append((meta_lead_id, case_id))

        case = Case(
            id=case_id,
            case_number=row.get("case_number"),
            organization_id=org_id,
            status_label=row.get("status_label"),
            stage_id=stage_id,
            source=row.get("source"),
            is_priority=_parse_bool(row.get("is_priority")) or False,
            owner_type=owner_type,
            owner_id=owner_id,
            created_by_user_id=created_by_user_id,
            meta_lead_id=meta_lead_id,
            meta_ad_id=row.get("meta_ad_id"),
            meta_form_id=row.get("meta_form_id"),
            full_name=row.get("full_name"),
            email=row.get("email"),
            phone=row.get("phone"),
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
            created_at=_parse_datetime(row.get("created_at")) or datetime.utcnow(),
            updated_at=_parse_datetime(row.get("updated_at")) or datetime.utcnow(),
        )
        db.add(case)
        imported += 1

    db.flush()

    for meta_lead_id, case_id in meta_leads_to_link:
        db.query(MetaLead).filter(MetaLead.id == meta_lead_id).update({
            MetaLead.converted_case_id: case_id
        })

    db.commit()
    return imported
