"""Email templates router - CRUD for org email templates with personal scope support."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    get_current_session,
    require_permission,
    require_csrf_header,
)
from app.core.policies import POLICIES

from app.db.enums import Role
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateRead,
    EmailTemplateListItem,
    EmailSendRequest,
    EmailLogRead,
    EmailTemplateCopyRequest,
    EmailTemplateShareRequest,
    TemplateVariableRead,
    EmailTemplateTestSendRequest,
    EmailTemplateTestSendResponse,
)
from app.schemas.platform_templates import (
    EmailTemplateLibraryItem,
    EmailTemplateLibraryDetail,
)
from app.services import email_service, user_service

router = APIRouter(
    tags=["Email Templates"],
    dependencies=[Depends(require_permission(POLICIES["email_templates"].default))],
)


@router.get("/variables", response_model=list[TemplateVariableRead])
def list_template_variables():
    """List the supported template variables for org/personal email templates."""
    from app.services import template_variable_catalog

    return [
        TemplateVariableRead(
            name=v.name,
            description=v.description,
            category=v.category,
            required=v.required,
            value_type=v.value_type,
            html_safe=v.html_safe,
        )
        for v in template_variable_catalog.list_org_email_template_variables()
    ]


def _build_template_response(
    db: Session, template, include_body: bool = True
) -> EmailTemplateRead | EmailTemplateListItem:
    """Build template response with owner name populated."""
    owner_name = None
    if template.owner_user_id:
        owner = user_service.get_user_by_id(db, template.owner_user_id)
        owner_name = owner.display_name if owner else None

    if include_body:
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
    else:
        return EmailTemplateListItem(
            id=template.id,
            name=template.name,
            subject=template.subject,
            from_email=template.from_email,
            is_active=template.is_active,
            scope=template.scope,
            owner_user_id=template.owner_user_id,
            owner_name=owner_name,
            is_system_template=template.is_system_template,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )


@router.get("", response_model=list[EmailTemplateListItem])
def list_templates(
    active_only: bool = True,
    scope: Literal["org", "personal"] | None = Query(
        None, description="Filter by scope: 'org' or 'personal'"
    ),
    show_all_personal: bool = Query(
        False, description="Admin-only: view all users' personal templates (read-only)"
    ),
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    List email templates for the organization.

    - Without scope filter: returns org templates + user's personal templates
    - scope=org: returns only org/system templates
    - scope=personal: returns user's personal templates
    - show_all_personal=true (admin only): returns all personal templates (read-only)
    """
    # Check if user is admin for show_all_personal
    is_admin = session.role in (Role.ADMIN, Role.DEVELOPER)

    templates = email_service.list_templates_for_user(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        is_admin=is_admin,
        scope_filter=scope,
        show_all_personal=show_all_personal if is_admin else False,
        active_only=active_only,
    )

    return [_build_template_response(db, t, include_body=False) for t in templates]


@router.post(
    "",
    response_model=EmailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    Create a new email template.

    - scope=org: requires manage permission
    - scope=personal: any user can create their own personal templates
    """
    # Check permissions based on scope
    if data.scope == "org":
        # Org templates require manage permission
        if not session.has_permission(POLICIES["email_templates"].actions["manage"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create organization templates",
            )

        if email_service.template_name_exists(
            db=db,
            org_id=session.org_id,
            name=data.name,
            scope="org",
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An organization template named '{data.name}' already exists",
            )
    else:
        if email_service.template_name_exists(
            db=db,
            org_id=session.org_id,
            name=data.name,
            scope="personal",
            owner_user_id=session.user_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a personal template named '{data.name}'",
            )

    template = email_service.create_template(
        db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=data.name,
        subject=data.subject,
        from_email=data.from_email,
        body=data.body,
        scope=data.scope,
    )
    return _build_template_response(db, template)


# =============================================================================
# Platform Template Library (Read + Copy)
# =============================================================================


@router.get("/library", response_model=list[EmailTemplateLibraryItem])
def list_platform_email_library(
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """List published platform email templates visible to this org."""
    from app.services import platform_template_service

    templates = platform_template_service.list_published_email_templates_for_org(db, session.org_id)
    return [
        EmailTemplateLibraryItem(
            id=t.id,
            name=t.published_name or t.name,
            subject=t.published_subject or t.subject,
            from_email=t.published_from_email,
            category=t.published_category,
            published_at=t.published_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.get("/library/{template_id}", response_model=EmailTemplateLibraryDetail)
def get_platform_email_library_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    from app.services import platform_template_service

    template = platform_template_service.get_published_email_template_for_org(
        db, template_id, session.org_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return EmailTemplateLibraryDetail(
        id=template.id,
        name=template.published_name or template.name,
        subject=template.published_subject or template.subject,
        body=template.published_body or template.body,
        from_email=template.published_from_email,
        category=template.published_category,
        published_at=template.published_at,
        updated_at=template.updated_at,
    )


@router.get("/{template_id}", response_model=EmailTemplateRead)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """Get an email template by ID."""
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check visibility for personal templates
    if template.scope == "personal" and template.owner_user_id != session.user_id:
        is_admin = session.role in ("admin", "developer")
        if not is_admin:
            raise HTTPException(status_code=404, detail="Template not found")

    return _build_template_response(db, template)


@router.patch(
    "/{template_id}",
    response_model=EmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    Update an email template. Creates version snapshot.

    - Org templates: requires manage permission
    - Personal templates: only owner can edit
    """
    from app.services import version_service

    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check permissions based on scope
    if template.scope == "org":
        if not session.has_permission(POLICIES["email_templates"].actions["manage"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to edit organization templates",
            )
    else:
        # Personal templates: only owner can edit
        if template.owner_user_id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own personal templates",
            )

    # Check for duplicate name if changing
    if data.name and data.name != template.name:
        if email_service.template_name_exists(
            db=db,
            org_id=session.org_id,
            name=data.name,
            scope=template.scope,
            owner_user_id=template.owner_user_id,
            exclude_id=template_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{data.name}' already exists",
            )

    try:
        kwargs: dict = {
            "db": db,
            "template": template,
            "user_id": session.user_id,
            "name": data.name,
            "subject": data.subject,
            "body": data.body,
            "is_active": data.is_active,
            "expected_version": data.expected_version,
        }
        if "from_email" in data.model_fields_set:
            kwargs["from_email"] = data.from_email

        updated = email_service.update_template(**kwargs)
    except version_service.VersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {e.expected}, got {e.actual}",
        )

    return _build_template_response(db, updated)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    Soft delete (deactivate) an email template.

    - Org templates: requires manage permission
    - Personal templates: only owner can delete
    """
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check permissions based on scope
    if template.scope == "org":
        if not session.has_permission(POLICIES["email_templates"].actions["manage"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete organization templates",
            )
    else:
        # Personal templates: only owner can delete
        if template.owner_user_id != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own personal templates",
            )

    email_service.delete_template(db, template)


# =============================================================================
# Copy & Share Endpoints
# =============================================================================


@router.post(
    "/{template_id}/copy",
    response_model=EmailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def copy_template(
    template_id: UUID,
    data: EmailTemplateCopyRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    Copy an org/system template to your personal templates.

    PERMISSION EXCEPTION: Any authenticated user can copy org templates to personal.
    This does not require email_templates.manage permission.
    """
    try:
        template = email_service.copy_template_to_personal(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            template_id=template_id,
            new_name=data.name,
        )
        return _build_template_response(db, template)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/{template_id}/share",
    response_model=EmailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def share_template(
    template_id: UUID,
    data: EmailTemplateShareRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """
    Share your personal template with the organization.

    Creates an org copy while keeping your personal template.

    PERMISSION EXCEPTION: Any user can share their own personal templates.
    This does not require email_templates.manage permission.
    """
    try:
        template = email_service.share_template_with_org(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            template_id=template_id,
            new_name=data.name,
        )
        return _build_template_response(db, template)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post(
    "/send",
    response_model=EmailLogRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def send_email(
    data: EmailSendRequest,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Send an email using a template (queues for async sending). Manager only."""
    result = email_service.send_from_template(
        db,
        org_id=session.org_id,
        template_id=data.template_id,
        recipient_email=data.recipient_email,
        variables=data.variables,
        surrogate_id=data.surrogate_id,
        schedule_at=data.schedule_at,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Template not found")

    email_log, job = result
    return email_log


@router.post(
    "/{template_id}/test",
    response_model=EmailTemplateTestSendResponse,
    dependencies=[Depends(require_csrf_header)],
)
async def send_test_email(
    template_id: UUID,
    body: EmailTemplateTestSendRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
) -> EmailTemplateTestSendResponse:
    """Send a test email for a given template.

    - Org templates require manage_email_templates permission.
    - Personal templates can only be test-sent by the owner (no admin override).
    """
    from app.services import email_test_send_service, permission_service

    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Authorization based on scope
    if template.scope == "org":
        manage_perm = POLICIES["email_templates"].actions["manage"]
        perm_key = manage_perm.value if hasattr(manage_perm, "value") else str(manage_perm)
        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, perm_key
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {perm_key}")
    else:
        if template.owner_user_id != session.user_id:
            raise HTTPException(
                status_code=403, detail="You can only send tests for your templates"
            )

    variables_used = email_test_send_service.extract_variables(template.subject, template.body)
    base_vars = email_test_send_service.build_sample_variables(
        db=db,
        org_id=session.org_id,
        to_email=str(body.to_email),
        actor_display_name=session.display_name,
    )
    base_vars = email_test_send_service.apply_unknown_variable_fallbacks(
        variables_used=variables_used, variables=base_vars
    )
    final_vars = {**base_vars, **(body.variables or {})}

    rendered_subject, rendered_body = email_service.render_template(
        template.subject,
        template.body,
        final_vars,
    )

    if template.scope == "personal":
        result = await email_test_send_service.send_test_via_user_gmail(
            db=db,
            org_id=session.org_id,
            sender_user_id=session.user_id,
            to_email=str(body.to_email),
            subject=rendered_subject,
            html=rendered_body,
            template_id=template.id,
            idempotency_key=body.idempotency_key,
        )
    else:
        result = await email_test_send_service.send_test_via_org_provider(
            db=db,
            org_id=session.org_id,
            to_email=str(body.to_email),
            subject=rendered_subject,
            html=rendered_body,
            template_id=template.id,
            idempotency_key=body.idempotency_key,
            template_from_email=template.from_email,
        )

    return EmailTemplateTestSendResponse(**result)


# =============================================================================
# Version Control Endpoints (Developer-only)
# =============================================================================
class TemplateVersionRead(BaseModel):
    """Version history entry."""

    id: UUID
    version: int
    created_by_user_id: UUID | None
    comment: str | None
    created_at: str


class RollbackRequest(BaseModel):
    """Rollback request."""

    target_version: int


@router.get("/{template_id}/versions", response_model=list[TemplateVersionRead])
def get_template_versions(
    template_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Get version history for a template. Developer-only."""
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    versions = email_service.get_template_versions(db, session.org_id, template_id, limit)
    return [
        TemplateVersionRead(
            id=v.id,
            version=v.version,
            created_by_user_id=v.created_by_user_id,
            comment=v.comment,
            created_at=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post(
    "/{template_id}/rollback",
    response_model=EmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def rollback_template(
    template_id: UUID,
    data: RollbackRequest,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Rollback template to a previous version. Developer-only."""
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    updated, error = email_service.rollback_template(
        db=db,
        template=template,
        target_version=data.target_version,
        user_id=session.user_id,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return _build_template_response(db, updated)


@router.post(
    "/library/{template_id}/copy",
    response_model=EmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def copy_platform_email_template(
    template_id: UUID,
    data: EmailTemplateCopyRequest,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """Copy a platform template into org templates."""
    if not session.has_permission(POLICIES["email_templates"].actions["manage"]):
        raise HTTPException(status_code=403, detail="Missing permission: manage_email_templates")

    from app.services import platform_template_service

    template = platform_template_service.get_published_email_template_for_org(
        db, template_id, session.org_id
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        created = email_service.create_template(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            name=data.name,
            subject=template.published_subject or template.subject,
            body=template.published_body or template.body,
            from_email=template.published_from_email,
            is_active=True,
            scope="org",
            comment=f"Copied from platform template {template.id}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_template_response(db, created)
