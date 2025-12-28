"""Invitation management endpoints for settings."""

from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_permission,
    require_csrf_header,
)
from app.core.policies import POLICIES

from app.schemas.auth import UserSession
from app.services import invite_service
from app.services import invite_email_service


router = APIRouter(
    prefix="/settings/invites",
    tags=["invites"],
    dependencies=[Depends(require_permission(POLICIES["team"].default))],
)


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
        cooldown_end = invite.last_resent_at + timedelta(
            minutes=invite_service.INVITE_RESEND_COOLDOWN_MINUTES
        )
        cooldown_seconds = max(
            0, int((cooldown_end - datetime.utcnow()).total_seconds())
        )

    return InviteRead(
        id=str(invite.id),
        email=invite.email,
        role=invite.role,
        status=status,
        invited_by_user_id=str(invite.invited_by_user_id)
        if invite.invited_by_user_id
        else None,
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
    session: UserSession = Depends(get_current_session),
):
    """List all invitations for the organization (Manager+ only)."""
    invites = invite_service.list_invites(db, session.org_id)
    pending_count = invite_service.count_pending_invites(db, session.org_id)

    return InviteListResponse(
        invites=[_invite_to_read(inv) for inv in invites],
        pending_count=pending_count,
    )


@router.post("", response_model=InviteRead, dependencies=[Depends(require_csrf_header)])
async def create_invite(
    body: InviteCreate,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Create a new invitation (Manager+ only)."""
    # Validate role
    if body.role not in ("member", "manager"):
        raise HTTPException(status_code=400, detail="Invalid role")

    # Check if inviter has Gmail connected (required to send invite email)
    from app.services import oauth_service
    from app.services.google_oauth import validate_email_domain

    gmail_integration = oauth_service.get_user_integration(db, session.user_id, "gmail")
    if not gmail_integration:
        raise HTTPException(
            status_code=400,
            detail="Connect Gmail in Settings → Integrations to send invites",
        )

    # Validate invitee email is from allowed domain
    try:
        validate_email_domain(body.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        invite = invite_service.create_invite(
            db=db,
            org_id=session.org_id,
            email=body.email,
            role=body.role,
            invited_by_user_id=session.user_id,
        )
        db.commit()

        # Send invitation email (async, best-effort)
        try:
            email_result = await invite_email_service.send_invite_email(db, invite)
            if not email_result.get("success"):
                # Log but don't fail - invite is created
                import logging

                logging.warning(
                    f"Failed to send invite email: {email_result.get('error')}"
                )
        except Exception as e:
            import logging

            logging.exception(f"Error sending invite email: {e}")

        return _invite_to_read(invite)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invite_id}/resend", dependencies=[Depends(require_csrf_header)])
async def resend_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Resend an invitation email (Manager+ only)."""
    invite = invite_service.get_invite(db, session.org_id, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    try:
        invite_service.resend_invite(db, invite)
        db.commit()

        # Resend invitation email (async, best-effort)
        try:
            email_result = await invite_email_service.send_invite_email(db, invite)
            if not email_result.get("success"):
                import logging

                logging.warning(
                    f"Failed to resend invite email: {email_result.get('error')}"
                )
        except Exception as e:
            import logging

            logging.exception(f"Error resending invite email: {e}")

        return {"resent": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{invite_id}", dependencies=[Depends(require_csrf_header)])
async def revoke_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Revoke an invitation (Manager+ only)."""
    invite = invite_service.get_invite(db, session.org_id, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    try:
        invite_service.revoke_invite(db, invite, session.user_id)
        db.commit()
        return {"revoked": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Public Invite Endpoints (for accepting invites)
# =============================================================================


class InviteDetailsRead(BaseModel):
    """Public invite details (no sensitive info)."""

    id: str
    organization_name: str
    role: str
    inviter_name: str | None
    expires_at: str | None
    status: str


@router.get("/accept/{invite_id}", response_model=InviteDetailsRead)
async def get_invite_details(
    invite_id: UUID,
    db: Session = Depends(get_db),
):
    """Get invite details for accept page (public endpoint)."""
    invite, org_name, inviter_name = invite_service.get_invite_details(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    status = invite_service.get_invite_status(invite)

    return InviteDetailsRead(
        id=str(invite.id),
        organization_name=org_name,
        role=invite.role,
        inviter_name=inviter_name,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        status=status,
    )


@router.post("/accept/{invite_id}", dependencies=[Depends(require_csrf_header)])
async def accept_invite(
    invite_id: UUID,
    db: Session = Depends(get_db),
    session: UserSession = Depends(get_current_session),
):
    """Accept an invitation and create membership."""
    try:
        result = invite_service.accept_invite(db, invite_id, session.user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        detail = str(e)
        status_code = 404 if detail == "Invite not found" else 400
        raise HTTPException(status_code=status_code, detail=detail)

    return {
        "accepted": True,
        "organization_id": result["organization_id"],
        "organization_name": result["organization_name"],
    }
