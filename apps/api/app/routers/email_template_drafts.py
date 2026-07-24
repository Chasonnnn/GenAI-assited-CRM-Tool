"""Draft-first Template Studio API.

These endpoints never participate in production sends. Publishing is the only
operation that promotes draft content into the existing ``email_templates``
projection.
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.email import EmailTemplateRead
from app.schemas.email_template_drafts import (
    EmailTemplateDraftCreate,
    EmailTemplateDraftPublishRequest,
    EmailTemplateDraftRead,
    EmailTemplateDraftRestoreVersionRequest,
    EmailTemplateDraftUpdate,
)
from app.services import (
    email_service,
    email_template_draft_service,
    permission_service,
)


router = APIRouter(
    prefix="/email-template-drafts",
    tags=["Email Template Drafts"],
    dependencies=[Depends(require_permission(POLICIES["email_templates"].default))],
)


def _has_manage_permission(db: Session, session) -> bool:
    manage_permission = POLICIES["email_templates"].actions["manage"]
    permission_key = (
        manage_permission.value
        if hasattr(manage_permission, "value")
        else str(manage_permission)
    )
    return permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        permission_key,
    )


def _is_admin(session) -> bool:
    return session.role in (Role.ADMIN, Role.DEVELOPER)


def _require_template_editor(
    db: Session,
    session,
    *,
    scope: str,
    owner_user_id: UUID | None,
) -> None:
    if scope == "org":
        if not _has_manage_permission(db, session):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: manage_email_templates",
            )
        return
    if owner_user_id != session.user_id and not _is_admin(session):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )


def _require_draft_editor(db: Session, session, draft: Any) -> None:
    _require_template_editor(
        db,
        session,
        scope=draft.scope,
        owner_user_id=draft.owner_user_id,
    )


def _build_draft_response(draft: Any) -> EmailTemplateDraftRead:
    published_version = draft.template.current_version if draft.template else None
    return EmailTemplateDraftRead(
        id=draft.id,
        organization_id=draft.organization_id,
        template_id=draft.template_id,
        created_by_user_id=draft.created_by_user_id,
        updated_by_user_id=draft.updated_by_user_id,
        scope=draft.scope,
        owner_user_id=draft.owner_user_id,
        owner_name=draft.owner.display_name if draft.owner else None,
        name=draft.name,
        subject=draft.subject,
        from_email=draft.from_email,
        body=draft.body,
        is_active=draft.is_active,
        category=draft.category,
        base_version=draft.base_version,
        revision=draft.revision,
        published_version=published_version,
        is_stale=(
            published_version is not None and published_version != draft.base_version
        ),
        last_tested_revision=draft.last_tested_revision,
        last_tested_at=draft.last_tested_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _build_template_response(template: Any) -> EmailTemplateRead:
    owner_name = template.owner.display_name if template.owner else None
    return EmailTemplateRead(
        id=template.id,
        organization_id=template.organization_id,
        created_by_user_id=template.created_by_user_id,
        name=template.name,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        scope=template.scope,
        owner_user_id=template.owner_user_id,
        owner_name=owner_name,
        source_template_id=template.source_template_id,
        is_system_template=template.is_system_template,
        current_version=template.current_version,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("", response_model=list[EmailTemplateDraftRead])
def list_email_template_drafts(
    scope: Annotated[Literal["org", "personal"] | None, "fastapi_param"] = Query(None),
    show_all_personal: Annotated[bool, "fastapi_param"] = Query(False),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    can_manage = _has_manage_permission(db, session)
    if scope == "org" and not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing permission: manage_email_templates",
        )
    drafts = email_template_draft_service.list_drafts_for_user(
        db,
        org_id=session.org_id,
        user_id=session.user_id,
        is_admin=_is_admin(session),
        include_org=can_manage,
        scope_filter=scope,
        show_all_personal=show_all_personal and _is_admin(session),
    )
    return [_build_draft_response(draft) for draft in drafts]


@router.post(
    "",
    response_model=EmailTemplateDraftRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_email_template_draft(
    data: EmailTemplateDraftCreate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    _require_template_editor(
        db,
        session,
        scope=data.scope,
        owner_user_id=session.user_id if data.scope == "personal" else None,
    )
    try:
        draft = email_template_draft_service.create_new_draft(
            db,
            org_id=session.org_id,
            user_id=session.user_id,
            name=data.name,
            subject=data.subject,
            from_email=data.from_email,
            body=data.body,
            scope=data.scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _build_draft_response(draft)


@router.post(
    "/from-template/{template_id}",
    response_model=EmailTemplateDraftRead,
    dependencies=[Depends(require_csrf_header)],
)
def create_draft_from_template(
    template_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    template = email_service.get_template(db, template_id, session.org_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    _require_template_editor(
        db,
        session,
        scope=template.scope,
        owner_user_id=template.owner_user_id,
    )
    try:
        draft = email_template_draft_service.create_draft_from_template(
            db,
            template=template,
            user_id=session.user_id,
        )
    except IntegrityError:
        db.rollback()
        draft = email_template_draft_service.get_draft_for_template(
            db,
            org_id=session.org_id,
            template_id=template.id,
        )
        if draft is None:
            raise
    return _build_draft_response(draft)


@router.get("/{draft_id}", response_model=EmailTemplateDraftRead)
def get_email_template_draft(
    draft_id: UUID,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    return _build_draft_response(draft)


@router.patch(
    "/{draft_id}",
    response_model=EmailTemplateDraftRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_email_template_draft(
    draft_id: UUID,
    data: EmailTemplateDraftUpdate,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
        for_update=True,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    kwargs: dict = {
        "db": db,
        "draft": draft,
        "user_id": session.user_id,
        "expected_revision": data.expected_revision,
        "name": data.name,
        "subject": data.subject,
        "body": data.body,
        "is_active": data.is_active,
    }
    if "from_email" in data.model_fields_set:
        kwargs["from_email"] = data.from_email
    try:
        updated = email_template_draft_service.update_draft(**kwargs)
    except email_template_draft_service.DraftRevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _build_draft_response(updated)


@router.delete(
    "/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def discard_email_template_draft(
    draft_id: UUID,
    expected_revision: Annotated[int, Query(ge=1)],
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
) -> Response:
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
        for_update=True,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    try:
        email_template_draft_service.discard_draft(
            db,
            draft,
            expected_revision=expected_revision,
        )
    except email_template_draft_service.DraftRevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{draft_id}/restore-version",
    response_model=EmailTemplateDraftRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_email_template_draft_version(
    draft_id: UUID,
    data: EmailTemplateDraftRestoreVersionRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
        for_update=True,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    try:
        restored = email_template_draft_service.restore_version_to_draft(
            db,
            draft=draft,
            user_id=session.user_id,
            target_version=data.target_version,
            expected_revision=data.expected_revision,
        )
    except email_template_draft_service.DraftRevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except email_template_draft_service.DraftVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        email_template_draft_service.DraftVersionIntegrityError,
        ValueError,
    ) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _build_draft_response(restored)


@router.post(
    "/{draft_id}/publish",
    response_model=EmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def publish_email_template_draft(
    draft_id: UUID,
    data: EmailTemplateDraftPublishRequest,
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
    session: Annotated[object, "fastapi_param"] = Depends(get_current_session),
):
    draft = email_template_draft_service.get_draft(
        db,
        org_id=session.org_id,
        draft_id=draft_id,
        for_update=True,
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    _require_draft_editor(db, session, draft)
    try:
        template = email_template_draft_service.publish_draft(
            db,
            draft=draft,
            user_id=session.user_id,
            expected_revision=data.expected_revision,
            expected_published_version=data.expected_published_version,
        )
    except (
        email_template_draft_service.DraftRevisionConflictError,
        email_template_draft_service.PublishedTemplateConflictError,
        email_template_draft_service.DraftNameConflictError,
        email_service.TemplateVersionHistoryConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A published template with this name already exists",
        ) from exc
    return _build_template_response(template)
