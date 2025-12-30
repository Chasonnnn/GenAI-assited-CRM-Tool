"""Settings endpoints for organization and user preferences."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.services import org_service

router = APIRouter(prefix="/settings", tags=["settings"])


# =============================================================================
# Organization Settings
# =============================================================================


class OrgSettingsRead(BaseModel):
    """Organization settings response."""

    id: str
    name: str
    address: str | None
    phone: str | None
    email: str | None


class OrgSettingsUpdate(BaseModel):
    """Organization settings update request."""

    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


@router.get("/organization", response_model=OrgSettingsRead)
def get_org_settings(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get organization settings."""
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrgSettingsRead(
        id=str(org.id),
        name=org.name,
        address=getattr(org, "address", None),
        phone=getattr(org, "phone", None),
        email=getattr(org, "contact_email", None),
    )


@router.patch(
    "/organization",
    response_model=OrgSettingsRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_org_settings(
    body: OrgSettingsUpdate,
    request: Request,
    session: UserSession = Depends(
        require_permission(POLICIES["org_settings"].default)
    ),
    db: Session = Depends(get_db),
):
    """
    Update organization settings.

    Requires manage_org permission (Admin only).
    """
    org = org_service.get_org_by_id(db, session.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    changed_fields: list[str] = []
    if body.name is not None and body.name != org.name:
        changed_fields.append("name")
    if body.address is not None and body.address != getattr(org, "address", None):
        changed_fields.append("address")
    if body.phone is not None and body.phone != getattr(org, "phone", None):
        changed_fields.append("phone")
    if body.email is not None and body.email != getattr(org, "contact_email", None):
        changed_fields.append("email")
    org = org_service.update_org_contact(
        db=db,
        org=org,
        name=body.name,
        address=body.address,
        phone=body.phone,
        email=body.email,
    )
    if changed_fields:
        from app.services import audit_service

        audit_service.log_settings_changed(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            setting_area="org",
            changes={"fields": changed_fields},
            request=request,
        )
        db.commit()

    return OrgSettingsRead(
        id=str(org.id),
        name=org.name,
        address=getattr(org, "address", None),
        phone=getattr(org, "phone", None),
        email=getattr(org, "contact_email", None),
    )
