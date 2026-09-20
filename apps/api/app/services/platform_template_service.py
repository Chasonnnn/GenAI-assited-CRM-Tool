"""Platform template studio service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import (
    PlatformEmailTemplate,
    PlatformEmailTemplateTarget,
    PlatformFormTemplate,
    PlatformFormTemplateHiddenOrg,
    PlatformFormTemplateTarget,
    WorkflowTemplate,
    WorkflowTemplateTarget,
)

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


def list_published_form_templates_for_org(db: Session, org_id: UUID) -> list[PlatformFormTemplate]:
    target_exists = (
        db.query(PlatformFormTemplateTarget)
        .filter(
            PlatformFormTemplateTarget.template_id == PlatformFormTemplate.id,
            PlatformFormTemplateTarget.organization_id == org_id,
        )
        .exists()
    )
    hidden_exists = (
        db.query(PlatformFormTemplateHiddenOrg)
        .filter(
            PlatformFormTemplateHiddenOrg.template_id == PlatformFormTemplate.id,
            PlatformFormTemplateHiddenOrg.organization_id == org_id,
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
            ~hidden_exists,
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
    hidden_exists = (
        db.query(PlatformFormTemplateHiddenOrg)
        .filter(
            PlatformFormTemplateHiddenOrg.template_id == PlatformFormTemplate.id,
            PlatformFormTemplateHiddenOrg.organization_id == org_id,
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
            ~hidden_exists,
        )
        .first()
    )


def hide_published_form_template_for_org(
    db: Session,
    *,
    template_id: UUID,
    org_id: UUID,
    hidden_by_user_id: UUID | None,
) -> None:
    existing = (
        db.query(PlatformFormTemplateHiddenOrg)
        .filter(
            PlatformFormTemplateHiddenOrg.template_id == template_id,
            PlatformFormTemplateHiddenOrg.organization_id == org_id,
        )
        .first()
    )
    if existing:
        return

    db.add(
        PlatformFormTemplateHiddenOrg(
            template_id=template_id,
            organization_id=org_id,
            hidden_by_user_id=hidden_by_user_id,
        )
    )
    db.flush()


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
