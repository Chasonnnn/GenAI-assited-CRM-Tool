"""Platform admin router for ops console operations.

All endpoints require platform admin access via require_platform_admin dependency.
Platform admins can manage organizations, users, and subscriptions across all tenants.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.deps import (
    get_db,
    require_platform_admin,
    require_csrf_header,
    PlatformUserSession,
    COOKIE_NAME,
)
from app.core.csrf import set_csrf_cookie, CSRF_COOKIE_NAME, get_csrf_cookie
from app.core.config import settings
from app.services import platform_service, session_service
from app.db.enums import Role

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateOrgRequest(BaseModel):
    name: str
    slug: str
    timezone: str = "America/Los_Angeles"
    admin_email: EmailStr

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Slug must be between 3 and 50 characters")
        return v


class UpdateSubscriptionRequest(BaseModel):
    plan_key: str | None = None
    status: str | None = None
    auto_renew: bool | None = None
    notes: str | None = None


class ExtendSubscriptionRequest(BaseModel):
    days: int = 30

    @field_validator("days")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError("Days must be between 1 and 365")
        return v


class UpdateMemberRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class CreateInviteRequest(BaseModel):
    email: EmailStr
    role: str


class CreateSupportSessionRequest(BaseModel):
    org_id: UUID
    role: str
    reason_code: str
    reason_text: str | None = None
    mode: str = "write"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if not Role.has_value(v):
            raise ValueError("Invalid role")
        return v

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        if v not in platform_service.SUPPORT_SESSION_REASON_CODES:
            raise ValueError("Invalid reason_code")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in platform_service.SUPPORT_SESSION_ALLOWED_MODES:
            raise ValueError("Invalid mode")
        return v

    @field_validator("reason_text")
    @classmethod
    def validate_reason_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        text = v.strip()
        if len(text) > 500:
            raise ValueError("Reason text must be 500 characters or less")
        return text


# =============================================================================
# Platform Email (System Sender + Templates)
# =============================================================================


class PlatformEmailStatusResponse(BaseModel):
    configured: bool
    from_email: str | None
    provider: str


class SystemEmailTemplateRead(BaseModel):
    system_key: str
    subject: str
    from_email: str | None = None
    body: str
    is_active: bool
    current_version: int
    updated_at: str | None


class UpdateSystemEmailTemplateRequest(BaseModel):
    subject: str
    from_email: str | None = None
    body: str
    is_active: bool = True
    expected_version: int | None = None


class SendTestSystemEmailRequest(BaseModel):
    to_email: EmailStr


# =============================================================================
# Platform User Info
# =============================================================================


@router.get("/me")
def get_platform_me(
    session: PlatformUserSession = Depends(require_platform_admin),
) -> dict:
    """
    Get current platform admin info.

    Used by ops console frontend to verify platform admin access
    and display user info in the header.
    """
    return {
        "user_id": str(session.user_id),
        "email": session.email,
        "display_name": session.display_name,
        "is_platform_admin": session.is_platform_admin,
    }


@router.get("/email/status", response_model=PlatformEmailStatusResponse)
def get_platform_email_status(
    session: PlatformUserSession = Depends(require_platform_admin),
) -> PlatformEmailStatusResponse:
    """Get platform/system email sender status (Resend)."""
    from app.services import platform_email_service

    configured = platform_email_service.platform_sender_configured()
    return PlatformEmailStatusResponse(
        configured=configured,
        from_email=settings.PLATFORM_EMAIL_FROM or None,
        provider="resend",
    )


# =============================================================================
# Platform Stats
# =============================================================================


@router.get("/stats")
def get_platform_stats(
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get platform-wide statistics for ops dashboard."""
    return platform_service.get_platform_stats(db)


# =============================================================================
# Support Sessions (Role Override)
# =============================================================================


@router.post("/support-sessions", dependencies=[Depends(require_csrf_header)])
def create_support_session(
    body: CreateSupportSessionRequest,
    request: Request,
    response: Response,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a support session with role override and set session cookies."""
    try:
        data, token, ttl_seconds = platform_service.create_support_session(
            db=db,
            actor_id=session.user_id,
            org_id=body.org_id,
            role=body.role,
            reason_code=body.reason_code,
            reason_text=body.reason_text,
            mode=body.mode,
            token_version=session.token_version,
            mfa_verified=session.mfa_verified,
            mfa_required=session.mfa_required,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Revoke the previous session token to prevent fallback to old org context.
    previous_token = request.cookies.get(COOKIE_NAME)
    if previous_token:
        session_service.delete_session_by_token(db, previous_token)

    # Clear host-only cookies when using domain cookies (migration safety)
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=ttl_seconds,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    # Preserve existing CSRF token to avoid invalidating the current header.
    set_csrf_cookie(response, token=get_csrf_cookie(request))

    return data


@router.post(
    "/support-sessions/{session_id}/revoke",
    dependencies=[Depends(require_csrf_header)],
)
def revoke_support_session(
    session_id: UUID,
    request: Request,
    response: Response,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Revoke a support session."""
    result = platform_service.revoke_support_session(
        db=db,
        session_id=session_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Support session not found")

    # Revoke current session token and clear cookies to enforce support session exit.
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session_service.delete_session_by_token(db, token)
    if settings.COOKIE_DOMAIN:
        response.delete_cookie(COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, domain=settings.COOKIE_DOMAIN, path="/")
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")

    return {"status": "revoked"}


# =============================================================================
# Organization Management
# =============================================================================


@router.get("/orgs")
def list_organizations(
    search: str | None = Query(None, description="Search by name or slug"),
    status: str | None = Query(None, description="Filter by subscription status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all organizations with summary info."""
    items, total = platform_service.list_organizations(
        db, search=search, status=status, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.post("/orgs", dependencies=[Depends(require_csrf_header)])
def create_organization(
    body: CreateOrgRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new organization with subscription and first admin invite."""
    try:
        return platform_service.create_organization(
            db=db,
            actor_id=session.user_id,
            name=body.name,
            slug=body.slug,
            timezone_str=body.timezone,
            admin_email=body.admin_email,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}")
def get_organization(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get organization detail."""
    result = platform_service.get_organization_detail(db, org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Organization not found")
    return result


# =============================================================================
# Subscription Management
# =============================================================================


@router.get("/orgs/{org_id}/subscription")
def get_subscription(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get organization subscription details."""
    result = platform_service.get_subscription(db, org_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return result


@router.put("/orgs/{org_id}/subscription", dependencies=[Depends(require_csrf_header)])
def update_subscription(
    org_id: UUID,
    body: UpdateSubscriptionRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update organization subscription."""
    try:
        return platform_service.update_subscription(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            plan_key=body.plan_key,
            status=body.status,
            auto_renew=body.auto_renew,
            notes=body.notes,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orgs/{org_id}/subscription/extend", dependencies=[Depends(require_csrf_header)])
def extend_subscription(
    org_id: UUID,
    body: ExtendSubscriptionRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Extend subscription by N days."""
    try:
        return platform_service.extend_subscription(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            days=body.days,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Member Management
# =============================================================================


@router.get("/orgs/{org_id}/members")
def list_members(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List organization members."""
    return platform_service.list_members(db, org_id)


@router.patch("/orgs/{org_id}/members/{member_id}", dependencies=[Depends(require_csrf_header)])
def update_member(
    org_id: UUID,
    member_id: UUID,
    body: UpdateMemberRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update member role or status."""
    try:
        return platform_service.update_member(
            db=db,
            org_id=org_id,
            member_id=member_id,
            actor_id=session.user_id,
            role=body.role,
            is_active=body.is_active,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orgs/{org_id}/members/{member_id}/mfa/reset",
    dependencies=[Depends(require_csrf_header)],
)
def reset_member_mfa(
    org_id: UUID,
    member_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Reset MFA for a member and revoke their sessions."""
    try:
        return platform_service.reset_member_mfa(
            db=db,
            org_id=org_id,
            member_id=member_id,
            actor_id=session.user_id,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Invite Management
# =============================================================================


@router.get("/orgs/{org_id}/invites")
def list_invites(
    org_id: UUID,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List organization invites."""
    return platform_service.list_invites(db, org_id)


@router.post("/orgs/{org_id}/invites", dependencies=[Depends(require_csrf_header)])
def create_invite(
    org_id: UUID,
    body: CreateInviteRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new invite."""
    try:
        return platform_service.create_invite(
            db=db,
            org_id=org_id,
            actor_id=session.user_id,
            email=body.email,
            role=body.role,
            request=request,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/orgs/{org_id}/invites/{invite_id}/revoke", dependencies=[Depends(require_csrf_header)]
)
def revoke_invite(
    org_id: UUID,
    invite_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Revoke an invite."""
    try:
        platform_service.revoke_invite(
            db=db,
            org_id=org_id,
            invite_id=invite_id,
            actor_id=session.user_id,
            request=request,
        )
        return {"status": "revoked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# System Email Templates (Org-Scoped, Managed by Ops)
# =============================================================================


@router.get(
    "/orgs/{org_id}/email/system-templates/{system_key}",
    response_model=SystemEmailTemplateRead,
)
def get_org_system_email_template(
    org_id: UUID,
    system_key: str,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Get (and ensure) an org-scoped system email template by system_key."""
    from app.services import system_email_template_service

    template = system_email_template_service.ensure_system_template(
        db, org_id=org_id, system_key=system_key
    )
    db.commit()
    db.refresh(template)

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.put(
    "/orgs/{org_id}/email/system-templates/{system_key}",
    dependencies=[Depends(require_csrf_header)],
    response_model=SystemEmailTemplateRead,
)
def update_org_system_email_template(
    org_id: UUID,
    system_key: str,
    body: UpdateSystemEmailTemplateRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SystemEmailTemplateRead:
    """Update an org-scoped system email template by system_key."""
    from app.services import email_service, system_email_template_service

    template = system_email_template_service.ensure_system_template(
        db, org_id=org_id, system_key=system_key
    )

    try:
        kwargs: dict = {
            "db": db,
            "template": template,
            "user_id": session.user_id,
            "subject": body.subject,
            "body": body.body,
            "is_active": body.is_active,
            "expected_version": body.expected_version,
            "comment": f"Updated system template {system_key} via ops",
        }
        if "from_email" in body.model_fields_set:
            kwargs["from_email"] = body.from_email

        template = email_service.update_template(**kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_template.system.update",
        target_org_id=org_id,
        metadata={"system_key": system_key},
        request=request,
    )
    db.commit()

    return SystemEmailTemplateRead(
        system_key=template.system_key or system_key,
        subject=template.subject,
        from_email=template.from_email,
        body=template.body,
        is_active=template.is_active,
        current_version=template.current_version,
        updated_at=template.updated_at.isoformat() if template.updated_at else None,
    )


@router.post(
    "/orgs/{org_id}/email/system-templates/{system_key}/test",
    dependencies=[Depends(require_csrf_header)],
)
async def send_test_org_system_email_template(
    org_id: UUID,
    system_key: str,
    body: SendTestSystemEmailRequest,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Send a test email using the org-scoped system template + platform sender."""
    from app.db.models import Organization
    from app.services import (
        audit_service,
        email_service,
        org_service,
        platform_email_service,
        system_email_template_service,
    )

    if not platform_email_service.platform_sender_configured():
        raise HTTPException(status_code=400, detail="Platform email sender is not configured")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    template = system_email_template_service.ensure_system_template(
        db, org_id=org_id, system_key=system_key
    )
    resolved_from = (template.from_email or "").strip() or (
        settings.PLATFORM_EMAIL_FROM or ""
    ).strip()
    if not resolved_from:
        raise HTTPException(
            status_code=400,
            detail="Template From address is not configured (set from_email in Ops before sending test emails)",
        )

    org_name = org_service.get_org_display_name(org)
    base_url = org_service.get_org_portal_base_url(org)
    invite_url = f"{base_url.rstrip('/')}/invite/test"
    inviter_text = f" by {session.display_name}" if session.display_name else ""

    variables = {
        "org_name": org_name,
        "invite_url": invite_url,
        "role_title": "Admin",
        "inviter_text": inviter_text,
        "expires_block": "<p>This is a test email. Expiration text would appear here.</p>",
    }

    rendered_subject, rendered_body = email_service.render_template(
        template.subject, template.body, variables
    )

    result = await platform_email_service.send_email_logged(
        db=db,
        org_id=org_id,
        to_email=str(body.to_email),
        subject=rendered_subject,
        from_email=resolved_from,
        html=rendered_body,
        text=(
            f"Test email for {org_name}\n"
            f"Invite URL: {invite_url}\n"
            f"Role: Admin\n"
            f"Invited by: {session.display_name or ''}\n"
        ),
        template_id=template.id,
        surrogate_id=None,
        idempotency_key=None,
    )

    platform_service.log_admin_action(
        db=db,
        actor_id=session.user_id,
        action="email_template.system.test_send",
        target_org_id=org_id,
        metadata={
            "system_key": system_key,
            "email_hash": audit_service.hash_email(str(body.to_email)),
        },
        request=request,
    )
    db.commit()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=str(result.get("error") or "Send failed"))

    return {
        "sent": True,
        "message_id": result.get("message_id"),
        "email_log_id": result.get("email_log_id"),
    }


# =============================================================================
# Admin Action Logs
# =============================================================================


@router.get("/orgs/{org_id}/admin-actions")
def get_org_admin_actions(
    org_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get admin action logs for an organization."""
    items, total = platform_service.get_admin_action_logs(
        db, org_id=org_id, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


# =============================================================================
# Platform Alerts (Cross-Org)
# =============================================================================


@router.get("/alerts")
def list_alerts(
    status: str | None = Query(None, description="Filter by status (open, acknowledged, resolved)"),
    severity: str | None = Query(
        None, description="Filter by severity (critical, error, warn, info)"
    ),
    org_id: UUID | None = Query(None, description="Filter by organization"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all alerts across organizations with optional filters."""
    items, total = platform_service.list_platform_alerts(
        db,
        status=status,
        severity=severity,
        org_id=org_id,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.post("/alerts/{alert_id}/acknowledge", dependencies=[Depends(require_csrf_header)])
def acknowledge_alert(
    alert_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Acknowledge an alert."""
    result = platform_service.acknowledge_alert(
        db=db,
        alert_id=alert_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/alerts/{alert_id}/resolve", dependencies=[Depends(require_csrf_header)])
def resolve_alert(
    alert_id: UUID,
    request: Request,
    session: PlatformUserSession = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Resolve an alert."""
    result = platform_service.resolve_alert(
        db=db,
        alert_id=alert_id,
        actor_id=session.user_id,
        request=request,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result
