"""Invitation management endpoints for settings."""

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_role
from app.db.enums import Role
from app.db.models import User
from app.services import invite_service
# from app.services import email_service  # TODO: wire up invite email


router = APIRouter(prefix="/settings/invites", tags=["invites"])


# =============================================================================
# Schemas
# =============================================================================

class InviteCreate(BaseModel):
    email: EmailStr
    role: str  # member, manager


class InviteRead(BaseModel):
    id: str
    email: str
    role: str
    status: str
    invited_by_user_id: str | None
    expires_at: str | None
    resend_count: int
    can_resend: bool
    resend_cooldown_seconds: int | None
    created_at: str


class InviteListResponse(BaseModel):
    invites: list[InviteRead]
    pending_count: int


# =============================================================================
# Helpers
# =============================================================================

def _invite_to_read(invite) -> InviteRead:
    status = invite_service.get_invite_status(invite)
    can_resend, error = invite_service.can_resend(invite)
    
    # Calculate cooldown remaining
    cooldown_seconds = None
    if invite.last_resent_at and not can_resend and "Wait" in (error or ""):
        cooldown_end = invite.last_resent_at + invite_service.timedelta(
            minutes=invite_service.INVITE_RESEND_COOLDOWN_MINUTES
        )
        cooldown_seconds = max(0, int((cooldown_end - datetime.utcnow()).total_seconds()))
    
    return InviteRead(
        id=str(invite.id),
        email=invite.email,
        role=invite.role,
        status=status,
        invited_by_user_id=str(invite.invited_by_user_id) if invite.invited_by_user_id else None,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        resend_count=invite.resend_count,
        can_resend=can_resend,
        resend_cooldown_seconds=cooldown_seconds,
        created_at=invite.created_at.isoformat(),
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=InviteListResponse)
async def list_invites(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.MANAGER)),
):
    """List all invitations for the organization (Manager+ only)."""
    invites = invite_service.list_invites(db, user.active_org_id)
    pending_count = invite_service.count_pending_invites(db, user.active_org_id)
    
    return InviteListResponse(
        invites=[_invite_to_read(inv) for inv in invites],
        pending_count=pending_count,
    )


@router.post("", response_model=InviteRead)
async def create_invite(
    body: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.MANAGER)),
):
    """Create a new invitation (Manager+ only)."""
    # Validate role
    if body.role not in ("member", "manager"):
        raise HTTPException(status_code=400, detail="Invalid role")
    
    try:
        invite = invite_service.create_invite(
            db=db,
            org_id=user.active_org_id,
            email=body.email,
            role=body.role,
            invited_by_user_id=user.id,
        )
        db.commit()
        
        # TODO: Send invitation email
        # await email_service.send_invite_email(invite)
        
        return _invite_to_read(invite)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invite_id}/resend")
async def resend_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.MANAGER)),
):
    """Resend an invitation email (Manager+ only)."""
    invite = invite_service.get_invite(db, user.active_org_id, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    try:
        invite_service.resend_invite(db, invite)
        db.commit()
        
        # TODO: Resend invitation email
        # await email_service.send_invite_email(invite)
        
        return {"resent": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{invite_id}")
async def revoke_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.MANAGER)),
):
    """Revoke an invitation (Manager+ only)."""
    invite = invite_service.get_invite(db, user.active_org_id, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    try:
        invite_service.revoke_invite(db, invite, user.id)
        db.commit()
        return {"revoked": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
