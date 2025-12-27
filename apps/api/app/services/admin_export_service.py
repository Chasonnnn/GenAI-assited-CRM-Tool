"""Admin export helpers for dev-only data exports."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timedelta
from typing import Any, Iterable, Iterator, Sequence
from uuid import UUID

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session, aliased

from app.core.config import settings
from app.db.enums import OwnerType
from app.db.models import (
    AISettings,
    AutomationWorkflow,
    Case,
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
)
from app.services import ai_usage_service, analytics_service, pipeline_service, meta_api


CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def _csv_safe(value: str) -> str:
    if value and value.startswith(CSV_DANGEROUS_PREFIXES):
        return f"'{value}"
    return value


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


def stream_cases_csv(db: Session, org_id: UUID) -> Iterator[str]:
    owner_user = aliased(User)
    owner_queue = aliased(Queue)
    created_by = aliased(User)
    archived_by = aliased(User)

    headers = [
        "id",
        "case_number",
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
        "meta_ad_id",
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

    query = db.query(
        Case,
        PipelineStage,
        owner_user,
        owner_queue,
        created_by,
        archived_by,
        meta_lead,
    ).join(
        PipelineStage, Case.stage_id == PipelineStage.id
    ).outerjoin(
        owner_user,
        and_(Case.owner_type == OwnerType.USER.value, Case.owner_id == owner_user.id),
    ).outerjoin(
        owner_queue,
        and_(Case.owner_type == OwnerType.QUEUE.value, Case.owner_id == owner_queue.id),
    ).outerjoin(
        created_by, Case.created_by_user_id == created_by.id
    ).outerjoin(
        archived_by, Case.archived_by_user_id == archived_by.id
    ).outerjoin(
        meta_lead, Case.meta_lead_id == meta_lead.id
    ).filter(
        Case.organization_id == org_id
    ).order_by(
        Case.created_at.asc()
    )

    for case, stage, owner_user_row, owner_queue_row, created_by_row, archived_by_row, meta_lead_row in query.yield_per(500):
        owner_name = owner_user_row.display_name if owner_user_row else None
        owner_email = owner_user_row.email if owner_user_row else None
        owner_queue_name = owner_queue_row.name if owner_queue_row else None

        yield _write_csv_row([
            case.id,
            case.case_number,
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
            case.meta_ad_id,
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
        ])


def build_org_config_zip(db: Session, org_id: UUID) -> bytes:
    org = db.query(Organization).filter(Organization.id == org_id).first()

    pipelines = db.query(Pipeline).filter(Pipeline.organization_id == org_id).order_by(
        Pipeline.is_default.desc(), Pipeline.name
    ).all()
    pipeline_payload = []
    for pipeline in pipelines:
        stages = db.query(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline.id
        ).order_by(PipelineStage.order).all()
        pipeline_payload.append({
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
        })

    templates = db.query(EmailTemplate).filter(
        EmailTemplate.organization_id == org_id
    ).order_by(EmailTemplate.name).all()
    template_payload = [
        {
            "id": str(t.id),
            "name": t.name,
            "subject": t.subject,
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

    workflows = db.query(AutomationWorkflow).filter(
        AutomationWorkflow.organization_id == org_id
    ).order_by(AutomationWorkflow.created_at.asc()).all()
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

    members = db.query(User, Membership).join(
        Membership, Membership.user_id == User.id
    ).filter(Membership.organization_id == org_id).order_by(User.email).all()

    user_payload = [
        {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "signature_name": user.signature_name,
            "signature_title": user.signature_title,
            "signature_company": user.signature_company,
            "signature_phone": user.signature_phone,
            "signature_email": user.signature_email,
            "signature_address": user.signature_address,
            "signature_website": user.signature_website,
            "signature_logo_url": user.signature_logo_url,
            "signature_html": user.signature_html,
        }
        for user, _membership in members
    ]

    membership_payload = [
        {
            "id": str(membership.id),
            "user_id": str(membership.user_id),
            "organization_id": str(membership.organization_id),
            "role": membership.role,
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

    queue_members = db.query(QueueMember).join(
        Queue, QueueMember.queue_id == Queue.id
    ).filter(Queue.organization_id == org_id).all()
    queue_member_payload = [
        {
            "id": str(member.id),
            "queue_id": str(member.queue_id),
            "user_id": str(member.user_id),
            "created_at": member.created_at,
        }
        for member in queue_members
    ]

    notification_settings = db.query(UserNotificationSettings, User).join(
        User, UserNotificationSettings.user_id == User.id
    ).filter(UserNotificationSettings.organization_id == org_id).order_by(User.email).all()
    notification_payload = [
        {
            "user_id": str(settings_row.user_id),
            "email": user.email,
            "case_assigned": settings_row.case_assigned,
            "case_status_changed": settings_row.case_status_changed,
            "case_handoff": settings_row.case_handoff,
            "task_assigned": settings_row.task_assigned,
            "task_reminders": settings_row.task_reminders,
            "appointments": settings_row.appointments,
            "updated_at": settings_row.updated_at,
        }
        for settings_row, user in notification_settings
    ]

    integrations = db.query(UserIntegration, User, Membership).join(
        User, UserIntegration.user_id == User.id
    ).join(
        Membership, Membership.user_id == User.id
    ).filter(Membership.organization_id == org_id).order_by(User.email, UserIntegration.integration_type).all()
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

    ai_settings = db.query(AISettings).filter(
        AISettings.organization_id == org_id
    ).first()
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
            "consent_accepted_by": str(ai_settings.consent_accepted_by) if ai_settings.consent_accepted_by else None,
            "anonymize_pii": ai_settings.anonymize_pii,
            "current_version": ai_settings.current_version,
            "has_api_key": ai_settings.api_key_encrypted is not None,
            "created_at": ai_settings.created_at,
            "updated_at": ai_settings.updated_at,
        }

    role_permissions = db.query(RolePermission).filter(
        RolePermission.organization_id == org_id
    ).order_by(RolePermission.role, RolePermission.permission).all()
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

    user_overrides = db.query(UserPermissionOverride).filter(
        UserPermissionOverride.organization_id == org_id
    ).order_by(UserPermissionOverride.user_id, UserPermissionOverride.permission).all()
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

    meta_pages = db.query(MetaPageMapping).filter(
        MetaPageMapping.organization_id == org_id
    ).order_by(MetaPageMapping.created_at.desc()).all()
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
            "timezone": org.timezone,
            "ai_enabled": org.ai_enabled,
            "current_version": org.current_version,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
        }

    manifest = {
        "organization_id": str(org_id),
        "exported_at": datetime.utcnow().isoformat(),
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
        archive.writestr("integrations.json", _write_json(integration_payload))
        archive.writestr("meta_pages.json", _write_json(meta_page_payload))
        archive.writestr("ai_settings.json", _write_json(ai_payload))

    buffer.seek(0)
    return buffer.read()


def parse_date_range(from_date: str | None, to_date: str | None) -> tuple[datetime, datetime]:
    if to_date:
        end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
    else:
        end = datetime.utcnow()

    if from_date:
        start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
    else:
        start = end - timedelta(days=30)

    return start, end


def build_analytics_zip(
    db: Session,
    org_id: UUID,
    start: datetime,
    end: datetime,
    ad_id: str | None,
    meta_spend: dict[str, Any],
) -> bytes:
    summary = _get_summary(db, org_id, start, end)
    cases_by_status = _get_cases_by_status(db, org_id)
    cases_by_assignee = _get_cases_by_assignee(db, org_id)
    cases_trend = _get_cases_trend(db, org_id, start, end)
    meta_performance = _get_meta_performance(db, org_id, start, end)
    campaigns = analytics_service.get_campaigns(db, org_id)
    funnel = analytics_service.get_funnel_with_filter(
        db,
        org_id,
        start.date(),
        end.date(),
        ad_id,
    )
    cases_by_state = analytics_service.get_cases_by_state_with_filter(
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
            "cases_by_status.csv",
            _write_csv(
                ["status", "count"],
                [(item["status"], item["count"]) for item in cases_by_status],
            ),
        )
        archive.writestr(
            "cases_by_assignee.csv",
            _write_csv(
                ["user_id", "user_email", "count"],
                [(item["user_id"], item["user_email"], item["count"]) for item in cases_by_assignee],
            ),
        )
        archive.writestr(
            "cases_trend.csv",
            _write_csv(
                ["date", "count"],
                [(item["date"], item["count"]) for item in cases_trend],
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
                ["campaign_id", "campaign_name", "spend", "impressions", "reach", "clicks", "leads", "cost_per_lead"],
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
                ["date_start", "date_stop", "spend", "impressions", "reach", "clicks", "leads", "cost_per_lead"],
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
                ["breakdown_values", "spend", "impressions", "reach", "clicks", "leads", "cost_per_lead"],
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
                [(item["stage"], item["label"], item["count"], item["percentage"]) for item in funnel],
            ),
        )
        archive.writestr(
            "cases_by_state.csv",
            _write_csv(
                ["state", "count"],
                [(item["state"], item["count"]) for item in cases_by_state],
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


def _get_summary(db: Session, org_id: UUID, start: datetime, end: datetime) -> dict[str, Any]:
    total_cases = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
    ).count()

    new_this_period = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.created_at >= start,
        Case.created_at < end,
    ).count()

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    if qualified_stage:
        qualified_stage_ids = [s.id for s in stages if s.order >= qualified_stage.order and s.is_active]
    else:
        qualified_stage_ids = [s.id for s in stages if s.stage_type in ("post_approval", "terminal") and s.is_active]

    qualified_count = db.query(Case).filter(
        Case.organization_id == org_id,
        Case.is_archived == False,
        Case.stage_id.in_(qualified_stage_ids),
    ).count()

    qualified_rate = (qualified_count / total_cases * 100) if total_cases > 0 else 0.0

    avg_time_to_qualified_hours = None
    if qualified_stage:
        result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - c.created_at)) / 3600) as avg_hours
                FROM cases c
                JOIN case_status_history csh ON c.id = csh.case_id
                WHERE c.organization_id = :org_id
                  AND c.is_archived = false
                  AND csh.to_stage_id = :qualified_stage_id
                  AND csh.changed_at >= :start
                  AND csh.changed_at < :end
            """),
            {"org_id": org_id, "start": start, "end": end, "qualified_stage_id": qualified_stage.id},
        )
        row = result.fetchone()
        avg_time_to_qualified_hours = round(row[0], 1) if row and row[0] else None

    return {
        "total_cases": total_cases,
        "new_this_period": new_this_period,
        "qualified_rate": round(qualified_rate, 1),
        "avg_time_to_qualified_hours": avg_time_to_qualified_hours,
    }


def _get_cases_by_status(db: Session, org_id: UUID) -> list[dict[str, Any]]:
    results = db.execute(
        text("""
            SELECT status_label, COUNT(*) as count
            FROM cases
            WHERE organization_id = :org_id
              AND is_archived = false
            GROUP BY status_label
            ORDER BY count DESC
        """),
        {"org_id": org_id},
    )
    return [{"status": row[0], "count": row[1]} for row in results]


def _get_cases_by_assignee(db: Session, org_id: UUID) -> list[dict[str, Any]]:
    results = db.execute(
        text("""
            SELECT c.owner_id, u.email, COUNT(*) as count
            FROM cases c
            LEFT JOIN users u ON c.owner_id = u.id
            WHERE c.organization_id = :org_id
              AND c.owner_type = 'user'
              AND c.is_archived = false
            GROUP BY c.owner_id, u.email
            ORDER BY count DESC
        """),
        {"org_id": org_id},
    )
    return [
        {
            "user_id": str(row[0]) if row[0] else None,
            "user_email": row[1],
            "count": row[2],
        }
        for row in results
    ]


def _get_cases_trend(db: Session, org_id: UUID, start: datetime, end: datetime) -> list[dict[str, Any]]:
    results = db.execute(
        text("""
            SELECT date_trunc('day', created_at) as period_start, COUNT(*) as count
            FROM cases
            WHERE organization_id = :org_id
              AND is_archived = false
              AND created_at >= :start
              AND created_at < :end
            GROUP BY period_start
            ORDER BY period_start
        """),
        {"org_id": org_id, "start": start, "end": end},
    )
    return [{"date": row[0].strftime("%Y-%m-%d") if row[0] else "", "count": row[1]} for row in results]


def _get_meta_performance(db: Session, org_id: UUID, start: datetime, end: datetime) -> dict[str, Any]:
    from app.db.models import MetaLead

    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stages = pipeline_service.get_stages(db, pipeline.id, include_inactive=True)
    qualified_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "qualified")
    converted_stage = pipeline_service.get_stage_by_slug(db, pipeline.id, "application_submitted")

    qualified_or_later_ids = []
    converted_or_later_ids = []
    if qualified_stage:
        qualified_or_later_ids = [s.id for s in stages if s.order >= qualified_stage.order and s.is_active]
    if converted_stage:
        converted_or_later_ids = [s.id for s in stages if s.order >= converted_stage.order and s.is_active]

    lead_time = func.coalesce(MetaLead.meta_created_time, MetaLead.received_at)
    leads_received = db.query(MetaLead).filter(
        MetaLead.organization_id == org_id,
        lead_time >= start,
        lead_time < end,
    ).count()

    leads_qualified = 0
    if qualified_or_later_ids:
        leads_qualified = db.execute(
            text("""
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
            {"org_id": org_id, "start": start, "end": end, "stage_ids": qualified_or_later_ids},
        ).scalar() or 0

    leads_converted = 0
    if converted_or_later_ids:
        leads_converted = db.execute(
            text("""
                SELECT COUNT(*)
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
                  AND c.stage_id = ANY(:stage_ids)
            """),
            {"org_id": org_id, "start": start, "end": end, "stage_ids": converted_or_later_ids},
        ).scalar() or 0

    qualification_rate = (leads_qualified / leads_received * 100) if leads_received > 0 else 0.0
    conversion_rate = (leads_converted / leads_received * 100) if leads_received > 0 else 0.0

    avg_hours = None
    if converted_stage:
        result = db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (csh.changed_at - COALESCE(ml.meta_created_time, ml.received_at))) / 3600) as avg_hours
                FROM meta_leads ml
                JOIN cases c ON ml.converted_case_id = c.id
                JOIN case_status_history csh ON c.id = csh.case_id AND csh.to_stage_id = :converted_stage_id
                WHERE ml.organization_id = :org_id
                  AND COALESCE(ml.meta_created_time, ml.received_at) >= :start
                  AND COALESCE(ml.meta_created_time, ml.received_at) < :end
                  AND ml.is_converted = true
            """),
            {"org_id": org_id, "start": start, "end": end, "converted_stage_id": converted_stage.id},
        )
        row = result.fetchone()
        avg_hours = round(row[0], 1) if row and row[0] else None

    return {
        "leads_received": leads_received,
        "leads_qualified": leads_qualified,
        "leads_converted": leads_converted,
        "qualification_rate": round(qualification_rate, 1),
        "conversion_rate": round(conversion_rate, 1),
        "avg_time_to_convert_hours": avg_hours,
    }


async def get_meta_spend_summary(
    start: datetime,
    end: datetime,
    time_increment: int | None = None,
    breakdowns: list[str] | None = None,
) -> dict[str, Any]:
    ad_account_id = settings.META_AD_ACCOUNT_ID
    access_token = settings.META_SYSTEM_TOKEN

    if not settings.META_TEST_MODE and (not ad_account_id or not access_token):
        return {
            "total_spend": 0.0,
            "total_impressions": 0,
            "total_leads": 0,
            "cost_per_lead": None,
            "campaigns": [],
            "time_series": [],
            "breakdowns": [],
        }

    date_start = start.strftime("%Y-%m-%d")
    date_end = end.strftime("%Y-%m-%d")

    insights, error = await meta_api.fetch_ad_account_insights(
        ad_account_id=ad_account_id or "act_mock",
        access_token=access_token or "mock_token",
        date_start=date_start,
        date_end=date_end,
        level="campaign",
        time_increment=time_increment,
        breakdowns=breakdowns or None,
    )

    if error or not insights:
        return {
            "total_spend": 0.0,
            "total_impressions": 0,
            "total_leads": 0,
            "cost_per_lead": None,
            "campaigns": [],
            "time_series": [],
            "breakdowns": [],
        }

    def safe_float(val, default=0.0) -> float:
        if val is None or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0) -> int:
        if val is None or val == "":
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    lead_action_types = {"lead", "leadgen", "onsite_conversion.lead_grouped", "offsite_conversion.fb_pixel_lead"}

    campaigns_by_id: dict[str, dict[str, float | int | str]] = {}
    total_spend = 0.0
    total_impressions = 0
    total_leads = 0
    time_series: dict[tuple[str, str], dict[str, float | int]] = {}
    breakdown_totals: dict[tuple[str, ...], dict[str, float | int | dict[str, str]]] = {}

    for insight in insights:
        spend = safe_float(insight.get("spend"))
        impressions = safe_int(insight.get("impressions"))
        reach = safe_int(insight.get("reach"))
        clicks = safe_int(insight.get("clicks"))

        leads = 0
        actions = insight.get("actions") or []
        for action in actions:
            action_type = action.get("action_type", "")
            if action_type in lead_action_types:
                leads += safe_int(action.get("value"))

        campaign_id = insight.get("campaign_id", "") or "unknown"
        campaign_name = insight.get("campaign_name", "Unknown")
        campaign_totals = campaigns_by_id.get(campaign_id)
        if not campaign_totals:
            campaign_totals = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "spend": 0.0,
                "impressions": 0,
                "reach": 0,
                "clicks": 0,
                "leads": 0,
            }
            campaigns_by_id[campaign_id] = campaign_totals
        campaign_totals["spend"] = float(campaign_totals["spend"]) + spend
        campaign_totals["impressions"] = int(campaign_totals["impressions"]) + impressions
        campaign_totals["reach"] = int(campaign_totals["reach"]) + reach
        campaign_totals["clicks"] = int(campaign_totals["clicks"]) + clicks
        campaign_totals["leads"] = int(campaign_totals["leads"]) + leads

        total_spend += spend
        total_impressions += impressions
        total_leads += leads

        if time_increment:
            date_start_value = insight.get("date_start") or date_start
            date_stop_value = insight.get("date_stop") or date_end
            time_key = (str(date_start_value), str(date_stop_value))
            point = time_series.get(time_key)
            if not point:
                point = {"spend": 0.0, "impressions": 0, "reach": 0, "clicks": 0, "leads": 0}
                time_series[time_key] = point
            point["spend"] = float(point["spend"]) + spend
            point["impressions"] = int(point["impressions"]) + impressions
            point["reach"] = int(point["reach"]) + reach
            point["clicks"] = int(point["clicks"]) + clicks
            point["leads"] = int(point["leads"]) + leads

        if breakdowns:
            breakdown_values = {key: str(insight.get(key, "unknown")) for key in breakdowns}
            breakdown_key = tuple(breakdown_values.get(key, "unknown") for key in breakdowns)
            breakdown = breakdown_totals.get(breakdown_key)
            if not breakdown:
                breakdown = {
                    "breakdown_values": breakdown_values,
                    "spend": 0.0,
                    "impressions": 0,
                    "reach": 0,
                    "clicks": 0,
                    "leads": 0,
                }
                breakdown_totals[breakdown_key] = breakdown
            breakdown["spend"] = float(breakdown["spend"]) + spend
            breakdown["impressions"] = int(breakdown["impressions"]) + impressions
            breakdown["reach"] = int(breakdown["reach"]) + reach
            breakdown["clicks"] = int(breakdown["clicks"]) + clicks
            breakdown["leads"] = int(breakdown["leads"]) + leads

    overall_cpl = round(total_spend / total_leads, 2) if total_leads > 0 else None

    campaigns = []
    for totals in campaigns_by_id.values():
        campaign_spend = float(totals["spend"])
        campaign_leads = int(totals["leads"])
        cpl = round(campaign_spend / campaign_leads, 2) if campaign_leads > 0 else None
        campaigns.append({
            "campaign_id": str(totals["campaign_id"]),
            "campaign_name": str(totals["campaign_name"]),
            "spend": campaign_spend,
            "impressions": int(totals["impressions"]),
            "reach": int(totals["reach"]),
            "clicks": int(totals["clicks"]),
            "leads": campaign_leads,
            "cost_per_lead": cpl,
        })

    time_series_points = []
    if time_increment:
        for (start_key, stop_key), totals in sorted(time_series.items()):
            point_spend = float(totals["spend"])
            point_leads = int(totals["leads"])
            point_cpl = round(point_spend / point_leads, 2) if point_leads > 0 else None
            time_series_points.append({
                "date_start": start_key,
                "date_stop": stop_key,
                "spend": point_spend,
                "impressions": int(totals["impressions"]),
                "reach": int(totals["reach"]),
                "clicks": int(totals["clicks"]),
                "leads": point_leads,
                "cost_per_lead": point_cpl,
            })

    breakdown_points = []
    if breakdowns:
        for breakdown in breakdown_totals.values():
            breakdown_spend = float(breakdown["spend"])
            breakdown_leads = int(breakdown["leads"])
            breakdown_cpl = round(breakdown_spend / breakdown_leads, 2) if breakdown_leads > 0 else None
            breakdown_points.append({
                "breakdown_values": breakdown["breakdown_values"],
                "spend": breakdown_spend,
                "impressions": int(breakdown["impressions"]),
                "reach": int(breakdown["reach"]),
                "clicks": int(breakdown["clicks"]),
                "leads": breakdown_leads,
                "cost_per_lead": breakdown_cpl,
            })

    breakdown_points.sort(key=lambda item: item["spend"], reverse=True)

    return {
        "total_spend": round(total_spend, 2),
        "total_impressions": total_impressions,
        "total_leads": total_leads,
        "cost_per_lead": overall_cpl,
        "campaigns": campaigns,
        "time_series": time_series_points,
        "breakdowns": breakdown_points,
    }
