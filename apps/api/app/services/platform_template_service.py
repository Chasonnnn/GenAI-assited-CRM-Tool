"""Platform template studio service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import (
    PlatformEmailTemplate,
    PlatformEmailTemplateTarget,
    PlatformFormTemplate,
    PlatformFormTemplateTarget,
    WorkflowTemplate,
    WorkflowTemplateTarget,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_UNSET = object()


def _require_targets(publish_all: bool, org_ids: list[UUID] | None) -> None:
    if not publish_all and not org_ids:
        raise ValueError("org_ids is required when publish_all is false")


# =============================================================================
# Platform Email Templates
# =============================================================================


def list_platform_email_templates(db: Session) -> list[PlatformEmailTemplate]:
    return db.query(PlatformEmailTemplate).order_by(PlatformEmailTemplate.updated_at.desc()).all()


def get_platform_email_template(db: Session, template_id: UUID) -> PlatformEmailTemplate | None:
    return db.query(PlatformEmailTemplate).filter(PlatformEmailTemplate.id == template_id).first()


def get_platform_email_template_target_org_ids(db: Session, template_id: UUID) -> list[UUID]:
    return [
        row[0]
        for row in (
            db.query(PlatformEmailTemplateTarget.organization_id)
            .filter(PlatformEmailTemplateTarget.template_id == template_id)
            .all()
        )
    ]


def create_platform_email_template(
    db: Session,
    *,
    name: str,
    subject: str,
    body: str,
    from_email: str | None,
    category: str | None,
) -> PlatformEmailTemplate:
    template = PlatformEmailTemplate(
        name=name,
        subject=subject,
        body=body,
        from_email=from_email,
        category=category,
        status="draft",
        current_version=1,
        published_version=0,
        is_published_globally=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_platform_email_template(
    db: Session,
    template: PlatformEmailTemplate,
    *,
    name: str | None,
    subject: str | None,
    body: str | None,
    from_email: str | None | object,
    category: str | None | object,
    expected_version: int | None,
) -> PlatformEmailTemplate:
    if expected_version is not None and template.current_version != expected_version:
        raise ValueError("Template version mismatch")

    if name is not None:
        template.name = name
    if subject is not None:
        template.subject = subject
    if body is not None:
        template.body = body
    if from_email is not _UNSET:
        template.from_email = from_email  # type: ignore[assignment]
    if category is not _UNSET:
        template.category = category  # type: ignore[assignment]

    template.status = "draft"
    template.current_version += 1
    db.commit()
    db.refresh(template)
    return template


def publish_platform_email_template(
    db: Session,
    template: PlatformEmailTemplate,
    *,
    publish_all: bool,
    org_ids: list[UUID] | None,
) -> PlatformEmailTemplate:
    _require_targets(publish_all, org_ids)

    template.published_name = template.name
    template.published_subject = template.subject
    template.published_body = template.body
    template.published_from_email = template.from_email
    template.published_category = template.category
    template.published_version = (template.published_version or 0) + 1
    template.published_at = _utc_now()
    template.status = "published"
    template.is_published_globally = publish_all

    db.query(PlatformEmailTemplateTarget).filter(
        PlatformEmailTemplateTarget.template_id == template.id
    ).delete()
    if not publish_all:
        for org_id in org_ids or []:
            db.add(
                PlatformEmailTemplateTarget(
                    template_id=template.id,
                    organization_id=org_id,
                )
            )
    db.commit()
    db.refresh(template)
    return template


def list_published_email_templates_for_org(
    db: Session, org_id: UUID
) -> list[PlatformEmailTemplate]:
    target_exists = (
        db.query(PlatformEmailTemplateTarget)
        .filter(
            PlatformEmailTemplateTarget.template_id == PlatformEmailTemplate.id,
            PlatformEmailTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(PlatformEmailTemplate)
        .filter(
            PlatformEmailTemplate.published_version > 0,
            or_(
                PlatformEmailTemplate.is_published_globally.is_(True),
                target_exists,
            ),
        )
        .order_by(PlatformEmailTemplate.published_at.desc().nullslast())
        .all()
    )


def get_published_email_template_for_org(
    db: Session, template_id: UUID, org_id: UUID
) -> PlatformEmailTemplate | None:
    target_exists = (
        db.query(PlatformEmailTemplateTarget)
        .filter(
            PlatformEmailTemplateTarget.template_id == PlatformEmailTemplate.id,
            PlatformEmailTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(PlatformEmailTemplate)
        .filter(
            PlatformEmailTemplate.id == template_id,
            PlatformEmailTemplate.published_version > 0,
            or_(
                PlatformEmailTemplate.is_published_globally.is_(True),
                target_exists,
            ),
        )
        .first()
    )


# =============================================================================
# Platform Form Templates
# =============================================================================


def list_platform_form_templates(db: Session) -> list[PlatformFormTemplate]:
    return db.query(PlatformFormTemplate).order_by(PlatformFormTemplate.updated_at.desc()).all()


def get_platform_form_template(db: Session, template_id: UUID) -> PlatformFormTemplate | None:
    return db.query(PlatformFormTemplate).filter(PlatformFormTemplate.id == template_id).first()


def get_platform_form_template_target_org_ids(db: Session, template_id: UUID) -> list[UUID]:
    return [
        row[0]
        for row in (
            db.query(PlatformFormTemplateTarget.organization_id)
            .filter(PlatformFormTemplateTarget.template_id == template_id)
            .all()
        )
    ]


def create_platform_form_template(
    db: Session,
    *,
    name: str,
    description: str | None,
    schema_json: dict | None,
    settings_json: dict | None,
) -> PlatformFormTemplate:
    template = PlatformFormTemplate(
        name=name,
        description=description,
        schema_json=schema_json,
        settings_json=settings_json,
        status="draft",
        current_version=1,
        published_version=0,
        is_published_globally=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_platform_form_template(
    db: Session,
    template: PlatformFormTemplate,
    *,
    name: str | None,
    description: str | None,
    schema_json: dict | None | object,
    settings_json: dict | None | object,
    expected_version: int | None,
) -> PlatformFormTemplate:
    if expected_version is not None and template.current_version != expected_version:
        raise ValueError("Template version mismatch")

    if name is not None:
        template.name = name
    if description is not None:
        template.description = description
    if schema_json is not _UNSET:
        template.schema_json = schema_json  # type: ignore[assignment]
    if settings_json is not _UNSET:
        template.settings_json = settings_json  # type: ignore[assignment]

    template.status = "draft"
    template.current_version += 1
    db.commit()
    db.refresh(template)
    return template


def publish_platform_form_template(
    db: Session,
    template: PlatformFormTemplate,
    *,
    publish_all: bool,
    org_ids: list[UUID] | None,
) -> PlatformFormTemplate:
    _require_targets(publish_all, org_ids)

    template.published_name = template.name
    template.published_description = template.description
    template.published_schema_json = template.schema_json
    template.published_settings_json = template.settings_json
    template.published_version = (template.published_version or 0) + 1
    template.published_at = _utc_now()
    template.status = "published"
    template.is_published_globally = publish_all

    db.query(PlatformFormTemplateTarget).filter(
        PlatformFormTemplateTarget.template_id == template.id
    ).delete()
    if not publish_all:
        for org_id in org_ids or []:
            db.add(
                PlatformFormTemplateTarget(
                    template_id=template.id,
                    organization_id=org_id,
                )
            )
    db.commit()
    db.refresh(template)
    return template


def list_published_form_templates_for_org(db: Session, org_id: UUID) -> list[PlatformFormTemplate]:
    target_exists = (
        db.query(PlatformFormTemplateTarget)
        .filter(
            PlatformFormTemplateTarget.template_id == PlatformFormTemplate.id,
            PlatformFormTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(PlatformFormTemplate)
        .filter(
            PlatformFormTemplate.published_version > 0,
            or_(
                PlatformFormTemplate.is_published_globally.is_(True),
                target_exists,
            ),
        )
        .order_by(PlatformFormTemplate.published_at.desc().nullslast())
        .all()
    )


def get_published_form_template_for_org(
    db: Session, template_id: UUID, org_id: UUID
) -> PlatformFormTemplate | None:
    target_exists = (
        db.query(PlatformFormTemplateTarget)
        .filter(
            PlatformFormTemplateTarget.template_id == PlatformFormTemplate.id,
            PlatformFormTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(PlatformFormTemplate)
        .filter(
            PlatformFormTemplate.id == template_id,
            PlatformFormTemplate.published_version > 0,
            or_(
                PlatformFormTemplate.is_published_globally.is_(True),
                target_exists,
            ),
        )
        .first()
    )


# =============================================================================
# Platform Workflow Templates
# =============================================================================


def list_platform_workflow_templates(db: Session) -> list[WorkflowTemplate]:
    return (
        db.query(WorkflowTemplate)
        .filter(WorkflowTemplate.is_global.is_(True))
        .order_by(WorkflowTemplate.updated_at.desc())
        .all()
    )


def get_platform_workflow_template(db: Session, template_id: UUID) -> WorkflowTemplate | None:
    return (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.is_global.is_(True),
        )
        .first()
    )


def get_platform_workflow_template_target_org_ids(db: Session, template_id: UUID) -> list[UUID]:
    return [
        row[0]
        for row in (
            db.query(WorkflowTemplateTarget.organization_id)
            .filter(WorkflowTemplateTarget.template_id == template_id)
            .all()
        )
    ]


def _workflow_payload_from_template(template: WorkflowTemplate) -> dict:
    return {
        "name": template.name,
        "description": template.description,
        "icon": template.icon,
        "category": template.category,
        "trigger_type": template.trigger_type,
        "trigger_config": template.trigger_config or {},
        "conditions": template.conditions or [],
        "condition_logic": template.condition_logic,
        "actions": template.actions or [],
    }


def create_platform_workflow_template(
    db: Session,
    *,
    user_id: UUID | None,
    payload: dict,
) -> WorkflowTemplate:
    template = WorkflowTemplate(
        organization_id=None,
        created_by_user_id=user_id,
        name=payload["name"],
        description=payload.get("description"),
        icon=payload.get("icon") or "template",
        category=payload.get("category") or "general",
        trigger_type=payload["trigger_type"],
        trigger_config=payload.get("trigger_config") or {},
        conditions=payload.get("conditions") or [],
        condition_logic=payload.get("condition_logic") or "AND",
        actions=payload.get("actions") or [],
        is_global=True,
        usage_count=0,
        draft_config=payload,
        status="draft",
        published_version=0,
        is_published_globally=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_platform_workflow_template(
    db: Session,
    template: WorkflowTemplate,
    *,
    payload: dict,
    expected_version: int | None,
) -> WorkflowTemplate:
    if expected_version is not None and template.published_version != expected_version:
        raise ValueError("Template version mismatch")

    current = template.draft_config or _workflow_payload_from_template(template)
    updated = {**current, **payload}
    template.draft_config = updated
    template.status = "draft"
    db.commit()
    db.refresh(template)
    return template


def publish_platform_workflow_template(
    db: Session,
    template: WorkflowTemplate,
    *,
    publish_all: bool,
    org_ids: list[UUID] | None,
) -> WorkflowTemplate:
    _require_targets(publish_all, org_ids)

    payload = template.draft_config or _workflow_payload_from_template(template)

    template.name = payload["name"]
    template.description = payload.get("description")
    template.icon = payload.get("icon") or "template"
    template.category = payload.get("category") or "general"
    template.trigger_type = payload["trigger_type"]
    template.trigger_config = payload.get("trigger_config") or {}
    template.conditions = payload.get("conditions") or []
    template.condition_logic = payload.get("condition_logic") or "AND"
    template.actions = payload.get("actions") or []
    template.draft_config = None

    template.published_version = (template.published_version or 0) + 1
    template.published_at = _utc_now()
    template.status = "published"
    template.is_published_globally = publish_all

    db.query(WorkflowTemplateTarget).filter(
        WorkflowTemplateTarget.template_id == template.id
    ).delete()
    if not publish_all:
        for org_id in org_ids or []:
            db.add(
                WorkflowTemplateTarget(
                    template_id=template.id,
                    organization_id=org_id,
                )
            )

    db.commit()
    db.refresh(template)
    return template


def list_published_workflow_templates_for_org(db: Session, org_id: UUID) -> list[WorkflowTemplate]:
    target_exists = (
        db.query(WorkflowTemplateTarget)
        .filter(
            WorkflowTemplateTarget.template_id == WorkflowTemplate.id,
            WorkflowTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    return (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.is_global.is_(True),
            WorkflowTemplate.published_version > 0,
            or_(
                WorkflowTemplate.is_published_globally.is_(True),
                target_exists,
            ),
        )
        .order_by(WorkflowTemplate.updated_at.desc())
        .all()
    )
