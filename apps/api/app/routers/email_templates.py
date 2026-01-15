"""Email templates router - CRUD for org email templates."""

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

from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateRead,
    EmailTemplateListItem,
    EmailSendRequest,
    EmailLogRead,
)
from app.services import email_service

router = APIRouter(
    tags=["Email Templates"],
    dependencies=[Depends(require_permission(POLICIES["email_templates"].default))],
)


@router.get("", response_model=list[EmailTemplateListItem])
def list_templates(
    active_only: bool = True,
    db: Session = Depends(get_db),
    session=Depends(get_current_session),
):
    """List email templates for the organization."""
    templates = email_service.list_templates(db, org_id=session.org_id, active_only=active_only)
    return templates


@router.post(
    "",
    response_model=EmailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Create a new email template (admin only)."""
    # Check for duplicate name
    existing = email_service.get_template_by_name(db, data.name, session.org_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{data.name}' already exists",
        )

    template = email_service.create_template(
        db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=data.name,
        subject=data.subject,
        body=data.body,
    )
    return template


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
    return template


@router.patch(
    "/{template_id}",
    response_model=EmailTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Update an email template (admin only). Creates version snapshot."""
    from app.services import version_service

    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check for duplicate name if changing
    if data.name and data.name != template.name:
        existing = email_service.get_template_by_name(db, data.name, session.org_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{data.name}' already exists",
            )

    try:
        updated = email_service.update_template(
            db,
            template,
            user_id=session.user_id,
            name=data.name,
            subject=data.subject,
            body=data.body,
            is_active=data.is_active,
            expected_version=data.expected_version,
        )
    except version_service.VersionConflictError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {e.expected}, got {e.actual}",
        )

    return updated


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session=Depends(require_permission(POLICIES["email_templates"].actions["manage"])),
):
    """Soft delete (deactivate) an email template (admin only)."""
    template = email_service.get_template(db, template_id, session.org_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    email_service.delete_template(db, template)


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

    return updated
