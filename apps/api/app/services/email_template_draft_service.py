"""Isolated draft lifecycle for organization and personal email templates."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.db.models import EmailTemplate, EmailTemplateDraft
from app.services import email_service


class DraftRevisionConflictError(Exception):
    """The draft changed after the caller loaded it."""


class PublishedTemplateConflictError(Exception):
    """The published template changed after the draft was forked."""


class DraftNameConflictError(Exception):
    """The draft name conflicts with another published template."""


_UNSET = object()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_draft(
    db: Session,
    *,
    org_id: UUID,
    draft_id: UUID,
    for_update: bool = False,
) -> EmailTemplateDraft | None:
    query = (
        db.query(EmailTemplateDraft)
        .options(
            joinedload(EmailTemplateDraft.template),
            joinedload(EmailTemplateDraft.owner),
        )
        .filter(
            EmailTemplateDraft.id == draft_id,
            EmailTemplateDraft.organization_id == org_id,
        )
    )
    if for_update:
        query = query.with_for_update(of=EmailTemplateDraft)
    return query.first()


def list_drafts_for_user(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    is_admin: bool,
    include_org: bool = True,
    scope_filter: str | None = None,
    show_all_personal: bool = False,
) -> list[EmailTemplateDraft]:
    query = (
        db.query(EmailTemplateDraft)
        .options(
            joinedload(EmailTemplateDraft.template),
            joinedload(EmailTemplateDraft.owner),
        )
        .filter(EmailTemplateDraft.organization_id == org_id)
    )
    if scope_filter == "org":
        if not include_org:
            return []
        query = query.filter(EmailTemplateDraft.scope == "org")
    elif scope_filter == "personal":
        if is_admin and show_all_personal:
            query = query.filter(EmailTemplateDraft.scope == "personal")
        else:
            query = query.filter(
                EmailTemplateDraft.scope == "personal",
                EmailTemplateDraft.owner_user_id == user_id,
            )
    elif is_admin and show_all_personal:
        if not include_org:
            query = query.filter(EmailTemplateDraft.scope == "personal")
    else:
        visibility = and_(
            EmailTemplateDraft.scope == "personal",
            EmailTemplateDraft.owner_user_id == user_id,
        )
        if include_org:
            visibility = or_(EmailTemplateDraft.scope == "org", visibility)
        query = query.filter(visibility)
    return query.order_by(EmailTemplateDraft.updated_at.desc()).all()


def create_new_draft(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    name: str,
    subject: str,
    body: str,
    from_email: str | None,
    scope: str,
) -> EmailTemplateDraft:
    draft = EmailTemplateDraft(
        organization_id=org_id,
        template_id=None,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
        scope=scope,
        owner_user_id=user_id if scope == "personal" else None,
        name=name,
        subject=subject,
        from_email=email_service.normalize_template_from_email(from_email),
        body=email_service.sanitize_template_html(body),
        is_active=True,
        category=None,
        base_version=0,
        revision=1,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def create_draft_from_template(
    db: Session,
    *,
    template: EmailTemplate,
    user_id: UUID,
) -> EmailTemplateDraft:
    existing = (
        db.query(EmailTemplateDraft)
        .options(
            joinedload(EmailTemplateDraft.template),
            joinedload(EmailTemplateDraft.owner),
        )
        .filter(
            EmailTemplateDraft.organization_id == template.organization_id,
            EmailTemplateDraft.template_id == template.id,
        )
        .first()
    )
    if existing is not None:
        return existing

    # Clone exact canonical values. In particular, do not sanitize or normalize
    # legacy body/from values merely by opening them in Studio.
    draft = EmailTemplateDraft(
        organization_id=template.organization_id,
        template_id=template.id,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
        scope=template.scope,
        owner_user_id=template.owner_user_id,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        category=template.category,
        base_version=template.current_version,
        revision=1,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def update_draft(
    db: Session,
    *,
    draft: EmailTemplateDraft,
    user_id: UUID,
    expected_revision: int,
    name: str | None = None,
    subject: str | None = None,
    from_email: str | None | object = _UNSET,
    body: str | None = None,
    is_active: bool | None = None,
) -> EmailTemplateDraft:
    if draft.revision != expected_revision:
        raise DraftRevisionConflictError(
            f"Draft revision mismatch: expected {expected_revision}, got {draft.revision}"
        )

    if name is not None:
        draft.name = name
    if subject is not None:
        draft.subject = subject
    if from_email is not _UNSET:
        draft.from_email = email_service.normalize_template_from_email(
            from_email if isinstance(from_email, str) else None
        )
    if body is not None:
        draft.body = email_service.sanitize_template_html(body)
    if is_active is not None:
        draft.is_active = is_active

    draft.revision += 1
    draft.updated_by_user_id = user_id
    draft.updated_at = _utc_now()
    db.commit()
    db.refresh(draft)
    return draft


def discard_draft(db: Session, draft: EmailTemplateDraft) -> None:
    db.delete(draft)
    db.commit()


def record_successful_test(
    db: Session,
    *,
    org_id: UUID,
    draft_id: UUID,
    tested_revision: int,
) -> EmailTemplateDraft | None:
    """Mark a test only if the draft did not change while it was being sent."""
    draft = (
        db.query(EmailTemplateDraft)
        .filter(
            EmailTemplateDraft.id == draft_id,
            EmailTemplateDraft.organization_id == org_id,
        )
        .with_for_update()
        .first()
    )
    if draft is None or draft.revision != tested_revision:
        return draft
    draft.last_tested_revision = tested_revision
    draft.last_tested_at = _utc_now()
    db.commit()
    db.refresh(draft)
    return draft


def _assert_name_available(
    db: Session,
    *,
    draft: EmailTemplateDraft,
    exclude_id: UUID | None,
) -> None:
    if email_service.template_name_exists(
        db=db,
        org_id=draft.organization_id,
        name=draft.name,
        scope=draft.scope,
        owner_user_id=draft.owner_user_id,
        exclude_id=exclude_id,
    ):
        raise DraftNameConflictError(
            f"A {draft.scope} template named '{draft.name}' already exists"
        )


def publish_draft(
    db: Session,
    *,
    draft: EmailTemplateDraft,
    user_id: UUID,
    expected_revision: int,
    expected_published_version: int | None,
) -> EmailTemplate:
    if draft.revision != expected_revision:
        raise DraftRevisionConflictError(
            f"Draft revision mismatch: expected {expected_revision}, got {draft.revision}"
        )

    with db.begin_nested():
        if draft.template_id is None:
            if expected_published_version is not None:
                raise PublishedTemplateConflictError(
                    "New drafts do not have a published version"
                )
            _assert_name_available(db, draft=draft, exclude_id=None)
            template = email_service.create_template(
                db,
                org_id=draft.organization_id,
                user_id=user_id,
                name=draft.name,
                subject=draft.subject,
                from_email=draft.from_email,
                body=draft.body,
                scope=draft.scope,
                category=draft.category,
                commit=False,
            )
            if not draft.is_active:
                template.is_active = False
        else:
            template = (
                db.query(EmailTemplate)
                .filter(
                    EmailTemplate.id == draft.template_id,
                    EmailTemplate.organization_id == draft.organization_id,
                )
                .with_for_update()
                .first()
            )
            if template is None:
                raise PublishedTemplateConflictError("Published template no longer exists")
            if (
                expected_published_version is None
                or expected_published_version != template.current_version
                or draft.base_version != template.current_version
            ):
                raise PublishedTemplateConflictError(
                    "Published template changed after this draft was created"
                )

            _assert_name_available(db, draft=draft, exclude_id=template.id)

            changes: dict[str, object] = {}
            if draft.name != template.name:
                changes["name"] = draft.name
            if draft.subject != template.subject:
                changes["subject"] = draft.subject
            if draft.from_email != template.from_email:
                changes["from_email"] = draft.from_email
            if draft.body != template.body:
                changes["body"] = draft.body
            if draft.is_active != template.is_active:
                changes["is_active"] = draft.is_active

            if changes:
                template = email_service.update_template(
                    db,
                    template=template,
                    user_id=user_id,
                    expected_version=template.current_version,
                    comment=f"Published Studio draft r{draft.revision}",
                    commit=False,
                    **changes,
                )

        db.delete(draft)
        db.flush()

    db.commit()
    db.refresh(template)
    return template
