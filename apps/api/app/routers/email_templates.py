"""Email templates router - CRUD for org email templates."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_session, require_role
from app.db.enums import Role
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateRead,
    EmailTemplateListItem,
    EmailSendRequest,
    EmailLogRead,
)
from app.services import email_service

router = APIRouter(tags=["Email Templates"])


@router.get("", response_model=list[EmailTemplateListItem])
def list_templates(
    active_only: bool = True,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """List email templates for the organization."""
    templates = email_service.list_templates(
        db, org_id=session["org_id"], active_only=active_only
    )
    return templates


@router.post("", response_model=EmailTemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.MANAGER)),
):
    """Create a new email template (manager only)."""
    # Check for duplicate name
    existing = email_service.get_template_by_name(db, data.name, session["org_id"])
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{data.name}' already exists",
        )
    
    template = email_service.create_template(
        db,
        org_id=session["org_id"],
        user_id=session["user_id"],
        name=data.name,
        subject=data.subject,
        body=data.body,
    )
    return template


@router.get("/{template_id}", response_model=EmailTemplateRead)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Get an email template by ID."""
    template = email_service.get_template(db, template_id, session["org_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=EmailTemplateRead)
def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.MANAGER)),
):
    """Update an email template (manager only)."""
    template = email_service.get_template(db, template_id, session["org_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check for duplicate name if changing
    if data.name and data.name != template.name:
        existing = email_service.get_template_by_name(db, data.name, session["org_id"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Template with name '{data.name}' already exists",
            )
    
    updated = email_service.update_template(
        db, template,
        name=data.name,
        subject=data.subject,
        body=data.body,
        is_active=data.is_active,
    )
    return updated


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    session: dict = Depends(require_role(Role.MANAGER)),
):
    """Soft delete (deactivate) an email template (manager only)."""
    template = email_service.get_template(db, template_id, session["org_id"])
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    email_service.delete_template(db, template)


@router.post("/send", response_model=EmailLogRead, status_code=status.HTTP_201_CREATED)
def send_email(
    data: EmailSendRequest,
    db: Session = Depends(get_db),
    session: dict = Depends(get_current_session),
):
    """Send an email using a template (queues for async sending)."""
    result = email_service.send_from_template(
        db,
        org_id=session["org_id"],
        template_id=data.template_id,
        recipient_email=data.recipient_email,
        variables=data.variables,
        case_id=data.case_id,
        schedule_at=data.schedule_at,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    
    email_log, job = result
    return email_log
