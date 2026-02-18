"""Platform admin service for ops console operations.

Handles cross-org operations for platform administrators.
Do NOT reuse org-scoped services - this service operates across all tenants.
"""

import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from app.core.config import settings
from app.db.models import (
    AdminActionLog,
    Organization,
    OrganizationSubscription,
    User,
    Membership,
    OrgInvite,
    EmailLog,
    SystemAlert,
    SupportSession,
)
from app.db.enums import Role, JobType
from app.core.security import create_support_session_token
from app.services import mfa_service, session_service, job_service
from app.utils.normalization import escape_like_string
from app.utils.presentation import humanize_identifier

logger = logging.getLogger(__name__)

ORG_DELETE_GRACE_DAYS = 30


class MissingTargetsError(ValueError):
    def __init__(self, detail: dict):
        super().__init__("Missing targets")
        self.detail = detail


# =============================================================================
# HMAC Helpers for PII-Safe Logging
# =============================================================================


def hmac_hash(value: str) -> str:
    """Salted HMAC for PII-safe but traceable logging."""
    secret = settings.AUDIT_HMAC_SECRET or settings.JWT_SECRET
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _get_ip_from_request(request: Request | None) -> str | None:
    """Extract client IP from request."""
    from app.services import audit_service

    return audit_service.get_client_ip(request)


# =============================================================================
# Admin Action Logging
# =============================================================================


def log_admin_action(
    db: Session,
    actor_id: UUID | None,
    action: str,
    target_org_id: UUID | None = None,
    target_user_id: UUID | None = None,
    metadata: dict | None = None,
    request: Request | None = None,
) -> AdminActionLog:
    """
    Log platform admin action.

    Actor can be None for system-triggered actions (e.g., auto-extend).
    IP and user agent are stored as HMACs for PII safety while maintaining traceability.
    """
    ip_address = _get_ip_from_request(request)
    user_agent = request.headers.get("user-agent") if request else None
    request_id = request.headers.get("x-request-id") if request else None

    log = AdminActionLog(
        actor_user_id=actor_id,
        action=action,
        target_organization_id=target_org_id,
        target_user_id=target_user_id,
        metadata_=metadata,
        request_id=request_id,
        ip_address_hmac=hmac_hash(ip_address) if ip_address else None,
        user_agent_hmac=hmac_hash(user_agent) if user_agent else None,
    )
    db.add(log)
    return log


# =============================================================================
# Platform Stats
# =============================================================================


def get_platform_stats(db: Session) -> dict:
    """Get platform-wide statistics for ops dashboard."""
    # Count organizations
    agency_count = (
        db.query(func.count(Organization.id)).filter(Organization.deleted_at.is_(None)).scalar()
        or 0
    )

    # Count active users (logged in within last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_user_count = (
        db.query(func.count(User.id))
        .filter(
            User.is_active.is_(True),
            User.last_login_at >= thirty_days_ago,
        )
        .scalar()
        or 0
    )

    # Count open alerts across all orgs
    open_alerts = (
        db.query(func.count(SystemAlert.id)).filter(SystemAlert.status == "open").scalar() or 0
    )

    return {
        "agency_count": agency_count,
        "active_user_count": active_user_count,
        "open_alerts": open_alerts,
    }


# =============================================================================
# Organization Management
# =============================================================================


def list_organizations(
    db: Session,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List all organizations with summary info."""
    from app.db.models import Surrogate

    member_counts = (
        db.query(
            Membership.organization_id.label("org_id"),
            func.count(Membership.id).label("member_count"),
        )
        .filter(Membership.is_active.is_(True))
        .group_by(Membership.organization_id)
        .subquery()
    )

    surrogate_counts = (
        db.query(
            Surrogate.organization_id.label("org_id"),
            func.count(Surrogate.id).label("surrogate_count"),
        )
        .group_by(Surrogate.organization_id)
        .subquery()
    )

    query = (
        db.query(
            Organization,
            member_counts.c.member_count,
            surrogate_counts.c.surrogate_count,
            OrganizationSubscription.plan_key,
            OrganizationSubscription.status,
        )
        .outerjoin(member_counts, member_counts.c.org_id == Organization.id)
        .outerjoin(surrogate_counts, surrogate_counts.c.org_id == Organization.id)
        .outerjoin(
            OrganizationSubscription,
            OrganizationSubscription.organization_id == Organization.id,
        )
    )

    if search:
        search_term = f"%{escape_like_string(search)}%"
        query = query.filter(
            (Organization.name.ilike(search_term, escape="\\"))
            | (Organization.slug.ilike(search_term, escape="\\"))
        )

    # Filter by subscription status if specified
    if status:
        query = query.filter(OrganizationSubscription.status == status)

    total = query.with_entities(func.count(func.distinct(Organization.id))).scalar() or 0
    rows = query.order_by(Organization.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for org, member_count, surrogate_count, plan_key, subscription_status in rows:
        plan_value = plan_key or "starter"
        status_value = subscription_status or "active"

        from app.services import org_service

        items.append(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "portal_base_url": org_service.get_org_portal_base_url(org),
                "timezone": org.timezone,
                "member_count": member_count or 0,
                "surrogate_count": surrogate_count or 0,
                "subscription_plan": plan_value,
                "subscription_status": status_value,
                "created_at": org.created_at.isoformat(),
                "deleted_at": org.deleted_at.isoformat() if org.deleted_at else None,
                "purge_at": org.purge_at.isoformat() if org.purge_at else None,
            }
        )

    return items, total


def get_organization_detail(db: Session, org_id: UUID) -> dict | None:
    """Get detailed organization info."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return None

    # Get member count
    member_count = (
        db.query(func.count(Membership.id))
        .filter(Membership.organization_id == org.id, Membership.is_active.is_(True))
        .scalar()
        or 0
    )

    # Get surrogate count
    from app.db.models import Surrogate

    surrogate_count = (
        db.query(func.count(Surrogate.id)).filter(Surrogate.organization_id == org.id).scalar() or 0
    )

    # Get active match count
    from app.db.models import Match

    active_match_count = (
        db.query(func.count(Match.id))
        .filter(
            Match.organization_id == org.id,
            Match.status.in_(["pending", "active"]),
        )
        .scalar()
        or 0
    )

    # Get pending task count
    from app.db.models import Task

    pending_task_count = (
        db.query(func.count(Task.id))
        .filter(
            Task.organization_id == org.id,
            Task.status == "pending",
        )
        .scalar()
        or 0
    )

    # Get subscription info
    subscription = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org.id)
        .first()
    )

    from app.services import org_service

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "portal_base_url": org_service.get_org_portal_base_url(org),
        "timezone": org.timezone,
        "member_count": member_count,
        "surrogate_count": surrogate_count,
        "active_match_count": active_match_count,
        "pending_task_count": pending_task_count,
        "ai_enabled": org.ai_enabled,
        "subscription_plan": subscription.plan_key if subscription else "starter",
        "subscription_status": subscription.status if subscription else "active",
        "created_at": org.created_at.isoformat(),
        "deleted_at": org.deleted_at.isoformat() if org.deleted_at else None,
        "purge_at": org.purge_at.isoformat() if org.purge_at else None,
        "deleted_by_user_id": str(org.deleted_by_user_id) if org.deleted_by_user_id else None,
    }


def request_organization_deletion(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict:
    """Soft delete an organization and schedule hard delete after grace period."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")
    if org.deleted_at:
        raise ValueError("Organization is already scheduled for deletion")

    now = datetime.now(timezone.utc)
    org.deleted_at = now
    org.purge_at = now + timedelta(days=ORG_DELETE_GRACE_DAYS)
    org.deleted_by_user_id = actor_id
    org.updated_at = now

    # Revoke active sessions for all members
    member_ids = db.query(Membership.user_id).filter(Membership.organization_id == org.id).all()
    for (user_id,) in member_ids:
        if user_id == actor_id:
            continue
        session_service.revoke_all_user_sessions(db, user_id, org.id)

    # Schedule hard delete job
    job_service.enqueue_job(
        db=db,
        org_id=org.id,
        job_type=JobType.ORG_DELETE,
        payload={"org_id": str(org.id)},
        run_at=org.purge_at,
        idempotency_key=f"org_delete:{org.id}:{org.purge_at.isoformat()}",
        commit=False,
    )

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="org.delete_requested",
        target_org_id=org.id,
        metadata={"purge_at": org.purge_at.isoformat()},
        request=request,
    )
    db.commit()

    return get_organization_detail(db, org.id) or {}


def restore_organization_deletion(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict:
    """Restore an organization during the grace period."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")
    if not org.deleted_at:
        raise ValueError("Organization is not scheduled for deletion")
    if org.purge_at and org.purge_at <= datetime.now(timezone.utc):
        raise ValueError("Deletion window has expired")

    org.deleted_at = None
    org.purge_at = None
    org.deleted_by_user_id = None
    org.updated_at = datetime.now(timezone.utc)

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="org.delete_restored",
        target_org_id=org.id,
        metadata={},
        request=request,
    )
    db.commit()

    return get_organization_detail(db, org.id) or {}


def force_delete_organization(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict:
    """Immediately hard delete an organization (bypass grace period)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")

    now = datetime.now(timezone.utc)
    if not org.deleted_at:
        org.deleted_at = now
        org.purge_at = now
        org.deleted_by_user_id = actor_id
        org.updated_at = now

    member_ids = db.query(Membership.user_id).filter(Membership.organization_id == org.id).all()
    for (user_id,) in member_ids:
        if user_id == actor_id:
            continue
        session_service.revoke_all_user_sessions(db, user_id, org.id)

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="org.delete_immediate",
        target_org_id=org.id,
        metadata={},
        request=request,
    )

    try:
        db.delete(org)
        db.commit()
        return {"org_id": str(org_id), "deleted": True}
    except Exception:
        db.rollback()
        # Fall back to scheduled deletion if hard delete fails.
        scheduled = request_organization_deletion(db, org_id, actor_id, request=request)
        return {
            "org_id": str(org_id),
            "deleted": False,
            "scheduled": True,
            "deleted_at": scheduled.get("deleted_at"),
            "purge_at": scheduled.get("purge_at"),
        }


def purge_organization(db: Session, org_id: UUID) -> bool:
    """Hard delete an organization if the grace period has elapsed."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or not org.deleted_at or not org.purge_at:
        return False
    if org.purge_at > datetime.now(timezone.utc):
        return False

    db.delete(org)
    db.commit()
    return True


def create_organization(
    db: Session,
    actor_id: UUID,
    name: str,
    slug: str,
    timezone_str: str,
    admin_email: str,
    request: Request | None = None,
) -> dict:
    """
    Create org + subscription placeholder + invite for first admin.

    Returns the created organization detail.
    """
    from app.services import org_service

    # Validate slug (checks format, reserved slugs, and normalizes to lowercase)
    try:
        validated_slug = org_service.validate_slug(slug)
    except ValueError as e:
        raise ValueError(str(e))

    # Check slug uniqueness
    existing = db.query(Organization).filter(Organization.slug == validated_slug).first()
    if existing:
        raise ValueError(f"Slug '{validated_slug}' is already taken.")

    normalized_admin_email = admin_email.lower().strip()

    # Ensure the admin email doesn't already have a pending invite
    pending_invite = (
        db.query(OrgInvite)
        .filter(
            OrgInvite.email == normalized_admin_email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
        )
        .first()
    )
    if pending_invite:
        raise ValueError(
            "Admin email already has a pending invite. Revoke it or use another email."
        )

    # Create org
    org = Organization(name=name, slug=validated_slug, timezone=timezone_str)
    db.add(org)
    db.flush()

    # Create subscription with concrete period (never NULL)
    subscription = OrganizationSubscription(
        organization_id=org.id,
        plan_key="starter",
        status="active",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(subscription)

    # Create invite for first admin
    invite = OrgInvite(
        organization_id=org.id,
        email=normalized_admin_email,
        role=Role.ADMIN.value,
        invited_by_user_id=actor_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)

    # Log action
    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="org.create",
        target_org_id=org.id,
        metadata={"slug": validated_slug},  # No PII - just slug
        request=request,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        error_text = str(exc.orig) if exc.orig else str(exc)
        if "uq_pending_invite_email" in error_text:
            raise ValueError(
                "Admin email already has a pending invite. Revoke it or use another email."
            ) from exc
        raise

    # Send invite email (best-effort)
    try:
        import asyncio
        from app.services import invite_email_service

        email_result = asyncio.run(invite_email_service.send_invite_email(db, invite))
        if not email_result.get("success"):
            logger.warning("Invite email failed: %s", email_result.get("error"))
    except Exception as exc:
        logger.warning("Invite email error: %s", exc)

    return get_organization_detail(db, org.id)


# =============================================================================
# Subscription Management
# =============================================================================


VALID_PLANS = {"starter", "professional", "enterprise"}
VALID_STATUSES = {"active", "trial", "past_due", "canceled"}


def get_subscription(db: Session, org_id: UUID) -> dict | None:
    """Get organization subscription details."""
    subscription = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org_id)
        .first()
    )
    if not subscription:
        return None

    return {
        "id": str(subscription.id),
        "organization_id": str(subscription.organization_id),
        "plan_key": subscription.plan_key,
        "status": subscription.status,
        "auto_renew": subscription.auto_renew,
        "current_period_end": subscription.current_period_end.isoformat(),
        "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
        "notes": subscription.notes,
        "created_at": subscription.created_at.isoformat(),
        "updated_at": subscription.updated_at.isoformat(),
    }


def update_subscription(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    plan_key: str | None = None,
    status: str | None = None,
    auto_renew: bool | None = None,
    notes: str | None = None,
    request: Request | None = None,
) -> dict:
    """Update organization subscription."""
    subscription = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org_id)
        .first()
    )
    if not subscription:
        raise ValueError("Subscription not found")

    changes = {}

    if plan_key is not None:
        if plan_key not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan_key}. Must be one of: {', '.join(VALID_PLANS)}")
        if subscription.plan_key != plan_key:
            changes["plan_key"] = {"old": subscription.plan_key, "new": plan_key}
            subscription.plan_key = plan_key

    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {status}. Must be one of: {', '.join(VALID_STATUSES)}"
            )
        if subscription.status != status:
            changes["status"] = {"old": subscription.status, "new": status}
            subscription.status = status

    if auto_renew is not None:
        if subscription.auto_renew != auto_renew:
            changes["auto_renew"] = {"old": subscription.auto_renew, "new": auto_renew}
            subscription.auto_renew = auto_renew

    if notes is not None:
        subscription.notes = notes

    if changes:
        log_admin_action(
            db=db,
            actor_id=actor_id,
            action="subscription.update",
            target_org_id=org_id,
            metadata=changes,
            request=request,
        )

    db.commit()
    return get_subscription(db, org_id)


def extend_subscription(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    days: int = 30,
    request: Request | None = None,
) -> dict:
    """Extend subscription by N days."""
    subscription = (
        db.query(OrganizationSubscription)
        .filter(OrganizationSubscription.organization_id == org_id)
        .first()
    )
    if not subscription:
        raise ValueError("Subscription not found")

    # Extend from current_period_end, not from now
    new_end = subscription.current_period_end + timedelta(days=days)
    subscription.current_period_end = new_end

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="subscription.extend",
        target_org_id=org_id,
        metadata={"days": days, "new_period_end": new_end.isoformat()},
        request=request,
    )

    db.commit()
    return get_subscription(db, org_id)


# =============================================================================
# Support Sessions (Role Override)
# =============================================================================


SUPPORT_SESSION_MODE_DEFAULT = "write"
SUPPORT_SESSION_ALLOWED_MODES = {"write", "read_only"}
SUPPORT_SESSION_REASON_CODES = {
    "onboarding_setup",
    "billing_help",
    "data_fix",
    "bug_repro",
    "incident_response",
    "other",
}


def _validate_role(role: str) -> str:
    """Validate role against enum values."""
    if not Role.has_value(role):
        raise ValueError(f"Invalid role: {role}")
    return role


def _validate_support_mode(mode: str) -> str:
    """Validate support session mode."""
    if mode not in SUPPORT_SESSION_ALLOWED_MODES:
        raise ValueError(f"Invalid mode: {mode}")
    if mode == "read_only" and not settings.SUPPORT_SESSION_ALLOW_READ_ONLY:
        raise ValueError("Read-only support sessions are not enabled")
    return mode


def _validate_reason_code(reason_code: str) -> str:
    """Validate support session reason code."""
    if reason_code not in SUPPORT_SESSION_REASON_CODES:
        raise ValueError(f"Invalid reason_code: {reason_code}")
    return reason_code


def create_support_session(
    db: Session,
    actor_id: UUID,
    org_id: UUID,
    role: str,
    reason_code: str,
    reason_text: str | None,
    mode: str,
    token_version: int,
    mfa_verified: bool,
    mfa_required: bool,
    request: Request | None = None,
) -> tuple[dict, str, int]:
    """
    Create a support session with role override.

    Returns (session_data, token, ttl_seconds).
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")
    if org.deleted_at:
        raise ValueError("Organization is scheduled for deletion")

    role_value = _validate_role(role)
    reason_code_value = _validate_reason_code(reason_code)
    mode_value = _validate_support_mode(mode)
    reason_text_value = reason_text.strip() if reason_text else None

    ttl_minutes = settings.SUPPORT_SESSION_TTL_MINUTES
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    support_session = SupportSession(
        actor_user_id=actor_id,
        organization_id=org.id,
        role_override=role_value,
        mode=mode_value,
        reason_code=reason_code_value,
        reason_text=reason_text_value,
        expires_at=expires_at,
    )
    db.add(support_session)
    db.flush()

    token = create_support_session_token(
        user_id=actor_id,
        org_id=org.id,
        role=role_value,
        token_version=token_version,
        support_session_id=support_session.id,
        mode=mode_value,
        ttl_minutes=ttl_minutes,
        mfa_verified=mfa_verified,
        mfa_required=mfa_required,
    )

    session_service.create_session(
        db=db,
        user_id=actor_id,
        org_id=org.id,
        token=token,
        request=request,
    )

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="support_session.create",
        target_org_id=org.id,
        metadata={
            "support_session_id": str(support_session.id),
            "role": role_value,
            "mode": mode_value,
            "reason_code": reason_code_value,
            "expires_at": expires_at.isoformat(),
        },
        request=request,
    )

    db.commit()
    db.refresh(support_session)

    return (
        {
            "id": str(support_session.id),
            "org_id": str(org.id),
            "role": role_value,
            "mode": mode_value,
            "reason_code": support_session.reason_code,
            "reason_text": support_session.reason_text,
            "expires_at": support_session.expires_at.isoformat(),
            "created_at": support_session.created_at.isoformat(),
        },
        token,
        ttl_minutes * 60,
    )


def revoke_support_session(
    db: Session,
    session_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> SupportSession | None:
    """Revoke a support session."""
    support_session = db.query(SupportSession).filter(SupportSession.id == session_id).first()
    if not support_session:
        return None

    if support_session.revoked_at is None:
        support_session.revoked_at = datetime.now(timezone.utc)

        log_admin_action(
            db=db,
            actor_id=actor_id,
            action="support_session.revoke",
            target_org_id=support_session.organization_id,
            metadata={
                "support_session_id": str(support_session.id),
                "role": support_session.role_override,
                "mode": support_session.mode,
            },
            request=request,
        )

        db.commit()

    return support_session


# =============================================================================
# Member Management
# =============================================================================


def list_members(db: Session, org_id: UUID) -> list[dict]:
    """List all members of an organization."""
    members = (
        db.query(Membership)
        .join(User, Membership.user_id == User.id)
        .filter(Membership.organization_id == org_id)
        .all()
    )

    return [
        {
            "id": str(m.id),
            "user_id": str(m.user_id),
            "email": m.user.email,
            "display_name": m.user.display_name,
            "role": m.role,
            "is_active": m.is_active,
            "last_login_at": m.user.last_login_at.isoformat() if m.user.last_login_at else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in members
    ]


def update_member(
    db: Session,
    org_id: UUID,
    member_id: UUID,
    actor_id: UUID,
    role: str | None = None,
    is_active: bool | None = None,
    request: Request | None = None,
) -> dict:
    """Update member role or status."""
    membership = (
        db.query(Membership)
        .filter(
            Membership.id == member_id,
            Membership.organization_id == org_id,
        )
        .first()
    )
    if not membership:
        raise ValueError("Member not found")

    changes = {}

    if role is not None and membership.role != role:
        role_value = _validate_role(role)
        changes["role"] = {"old": membership.role, "new": role_value}
        membership.role = role_value

    if is_active is not None and membership.is_active != is_active:
        changes["is_active"] = {"old": membership.is_active, "new": is_active}
        membership.is_active = is_active

    if changes:
        log_admin_action(
            db=db,
            actor_id=actor_id,
            action="member.update",
            target_org_id=org_id,
            target_user_id=membership.user_id,
            metadata=changes,
            request=request,
        )

    db.commit()

    return {
        "id": str(membership.id),
        "user_id": str(membership.user_id),
        "email": membership.user.email,
        "display_name": membership.user.display_name,
        "role": membership.role,
        "is_active": membership.is_active,
        "last_login_at": membership.user.last_login_at.isoformat()
        if membership.user.last_login_at
        else None,
        "created_at": membership.created_at.isoformat(),
    }


def reset_member_mfa(
    db: Session,
    org_id: UUID,
    member_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict:
    """Reset MFA enrollment for a member and revoke their sessions."""
    membership = (
        db.query(Membership)
        .options(joinedload(Membership.user))
        .filter(
            Membership.id == member_id,
            Membership.organization_id == org_id,
        )
        .first()
    )
    if not membership or not membership.user:
        raise ValueError("Member not found")

    user = membership.user

    mfa_service.disable_mfa(db, user)
    user.token_version += 1

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="member.mfa.reset",
        target_org_id=org_id,
        target_user_id=user.id,
        metadata={"member_id": str(member_id)},
        request=request,
    )

    db.commit()

    session_service.revoke_all_user_sessions(db, user.id, org_id)

    return {"message": "MFA reset successfully"}


# =============================================================================
# Invite Management
# =============================================================================


def list_invites(db: Session, org_id: UUID) -> list[dict]:
    """List all invites for an organization."""
    invites = (
        db.query(OrgInvite)
        .options(joinedload(OrgInvite.invited_by))
        .filter(OrgInvite.organization_id == org_id)
        .order_by(OrgInvite.created_at.desc())
        .all()
    )

    from app.services import invite_service

    invite_log_keys = {f"invite:{invite.id}:v{invite.resend_count}" for invite in invites}
    email_logs: dict[str, EmailLog] = {}
    if invite_log_keys:
        logs = (
            db.query(EmailLog)
            .filter(
                EmailLog.organization_id == org_id,
                EmailLog.idempotency_key.in_(invite_log_keys),
            )
            .all()
        )
        email_logs = {log.idempotency_key: log for log in logs}

    now = datetime.now(timezone.utc)

    results = []
    for inv in invites:
        # Determine status
        if inv.revoked_at:
            status = "revoked"
        elif inv.accepted_at:
            status = "accepted"
        elif inv.expires_at and inv.expires_at < now:
            status = "expired"
        else:
            status = "pending"

        # Get invited_by name if available
        invited_by_name = None
        if inv.invited_by:
            invited_by_name = inv.invited_by.display_name

        can_resend, error = invite_service.can_resend(inv)
        cooldown_seconds = None
        if inv.last_resent_at and not can_resend and "Wait" in (error or ""):
            cooldown_end = inv.last_resent_at + timedelta(
                minutes=invite_service.INVITE_RESEND_COOLDOWN_MINUTES
            )
            cooldown_seconds = max(0, int((cooldown_end - now).total_seconds()))

        log_key = f"invite:{inv.id}:v{inv.resend_count}"
        email_log = email_logs.get(log_key)

        results.append(
            {
                "id": str(inv.id),
                "email": inv.email,
                "role": inv.role,
                "status": status,
                "invited_by_name": invited_by_name,
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
                "created_at": inv.created_at.isoformat(),
                "resend_count": inv.resend_count,
                "can_resend": can_resend,
                "resend_cooldown_seconds": cooldown_seconds,
                "open_count": email_log.open_count if email_log else 0,
                "opened_at": (
                    email_log.opened_at.isoformat() if email_log and email_log.opened_at else None
                ),
                "click_count": email_log.click_count if email_log else 0,
                "clicked_at": (
                    email_log.clicked_at.isoformat() if email_log and email_log.clicked_at else None
                ),
            }
        )

    return results


def create_invite(
    db: Session,
    org_id: UUID,
    actor_id: UUID,
    email: str,
    role: str,
    request: Request | None = None,
) -> dict:
    """Create a new invite for an organization."""
    email = email.lower().strip()
    from app.services import invite_service, platform_email_service

    if not platform_email_service.platform_sender_configured():
        raise ValueError("Platform email sender is not configured")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise ValueError("Organization not found")
    if org.deleted_at:
        raise ValueError("Organization is scheduled for deletion")

    role_value = invite_service.validate_invite_role(role, allow_developer=True)

    # Check for existing pending invite (global uniqueness by email).
    now = datetime.now(timezone.utc)
    existing = (
        db.query(OrgInvite)
        .filter(
            OrgInvite.email == email,
            OrgInvite.accepted_at.is_(None),
            OrgInvite.revoked_at.is_(None),
        )
        .first()
    )
    invite: OrgInvite | None = None
    if existing:
        existing_active = existing.expires_at is None or existing.expires_at > now
        if existing_active:
            raise ValueError(f"An active invite already exists for {email}")

        if existing.organization_id == org_id:
            # Re-activate the expired invite instead of inserting a duplicate row.
            existing.role = role_value
            existing.invited_by_user_id = actor_id
            existing.expires_at = now + timedelta(days=7)
            existing.last_resent_at = now
            existing.resend_count = (existing.resend_count or 0) + 1
            invite = existing
        else:
            # Release the global pending-invite uniqueness slot for this email.
            existing.revoked_at = now
            existing.revoked_by_user_id = actor_id

    # Check if user already exists and is a member
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        existing_membership = (
            db.query(Membership)
            .filter(
                Membership.user_id == existing_user.id,
                Membership.organization_id == org_id,
            )
            .first()
        )
        if existing_membership:
            raise ValueError(f"{email} is already a member of this organization")

    if invite is None:
        invite = OrgInvite(
            organization_id=org_id,
            email=email,
            role=role_value,
            invited_by_user_id=actor_id,
            expires_at=now + timedelta(days=7),
        )
        db.add(invite)

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="invite.create",
        target_org_id=org_id,
        metadata={
            "email_domain": email.split("@")[1],
            "role": role_value,
        },  # Domain only, not full email
        request=request,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_pending_invite_email" in str(exc.orig):
            raise ValueError(f"An active invite already exists for {email}") from exc
        raise

    # Send invite email (best-effort)
    try:
        import asyncio
        from app.services import invite_email_service

        email_result = asyncio.run(invite_email_service.send_invite_email(db, invite))
        if not email_result.get("success"):
            logger.warning("Invite email failed: %s", email_result.get("error"))
    except Exception as exc:
        logger.warning("Invite email error: %s", exc)

    return {
        "id": str(invite.id),
        "email": invite.email,
        "role": invite.role,
        "status": "pending",
        "invited_by_name": None,  # Would need to fetch actor's name
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "created_at": invite.created_at.isoformat(),
        "resend_count": invite.resend_count,
        "can_resend": True,
        "resend_cooldown_seconds": None,
    }


def revoke_invite(
    db: Session,
    org_id: UUID,
    invite_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> None:
    """Revoke an invite."""
    invite = (
        db.query(OrgInvite)
        .filter(
            OrgInvite.id == invite_id,
            OrgInvite.organization_id == org_id,
        )
        .first()
    )
    if not invite:
        raise ValueError("Invite not found")

    if invite.accepted_at:
        raise ValueError("Cannot revoke an accepted invite")

    if invite.revoked_at:
        raise ValueError("Invite is already revoked")

    invite.revoked_at = datetime.now(timezone.utc)
    invite.revoked_by_user_id = actor_id

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="invite.revoke",
        target_org_id=org_id,
        metadata={"email_domain": invite.email.split("@")[1]},  # Domain only
        request=request,
    )

    db.commit()


def resend_invite(
    db: Session,
    org_id: UUID,
    invite_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict:
    """Resend an invite email for an organization."""
    from app.services import platform_email_service

    if not platform_email_service.platform_sender_configured():
        raise ValueError("Platform email sender is not configured")
    invite = (
        db.query(OrgInvite)
        .filter(
            OrgInvite.id == invite_id,
            OrgInvite.organization_id == org_id,
        )
        .first()
    )
    if not invite:
        raise ValueError("Invite not found")

    from app.services import invite_service

    invite_service.resend_invite(db, invite)

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="invite.resend",
        target_org_id=org_id,
        metadata={"email_domain": invite.email.split("@")[1]},
        request=request,
    )

    db.commit()

    try:
        import asyncio
        from app.services import invite_email_service

        email_result = asyncio.run(invite_email_service.send_invite_email(db, invite))
        if not email_result.get("success"):
            logger.warning("Invite resend email failed: %s", email_result.get("error"))
    except Exception as exc:
        logger.warning("Invite resend email error: %s", exc)

    can_resend, error = invite_service.can_resend(invite)
    cooldown_seconds = None
    if invite.last_resent_at and not can_resend and "Wait" in (error or ""):
        cooldown_end = invite.last_resent_at + timedelta(
            minutes=invite_service.INVITE_RESEND_COOLDOWN_MINUTES
        )
        cooldown_seconds = max(0, int((cooldown_end - datetime.now(timezone.utc)).total_seconds()))

    status = "pending"
    if invite.revoked_at:
        status = "revoked"
    elif invite.accepted_at:
        status = "accepted"
    elif invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
        status = "expired"

    return {
        "id": str(invite.id),
        "email": invite.email,
        "role": invite.role,
        "status": status,
        "invited_by_name": invite.invited_by.display_name if invite.invited_by else None,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "created_at": invite.created_at.isoformat(),
        "resend_count": invite.resend_count,
        "can_resend": can_resend,
        "resend_cooldown_seconds": cooldown_seconds,
    }


async def send_system_email_campaign(
    *,
    db: Session,
    system_key: str,
    targets: list[dict],
    actor_id: UUID,
    actor_display_name: str | None,
    request: Request | None = None,
) -> dict:
    """Send a system email template to selected org/users."""
    from app.db.models import Membership, User
    from app.services import (
        audit_service,
        email_service,
        org_service,
        platform_branding_service,
        platform_email_service,
        system_email_template_service,
        unsubscribe_service,
    )

    if not platform_email_service.platform_sender_configured():
        raise ValueError("Platform email sender is not configured")

    template = system_email_template_service.ensure_system_template(db, system_key=system_key)
    if not template.is_active:
        raise ValueError("System template is inactive")

    resolved_from = (template.from_email or "").strip() or (
        settings.PLATFORM_EMAIL_FROM or ""
    ).strip()
    if not resolved_from:
        raise ValueError(
            "Template From address is not configured (set from_email in Ops before sending)"
        )

    branding = platform_branding_service.get_branding(db)
    platform_logo_url = (branding.logo_url or "").strip()
    platform_logo_block = (
        f'<img src="{platform_logo_url}" alt="Platform logo" style="max-width: 180px; height: auto; display: block; margin: 0 auto 6px auto;" />'
        if platform_logo_url
        else ""
    )
    inviter_text = f" by {actor_display_name}" if actor_display_name else ""

    missing_targets: list[dict] = []
    recipients: list[tuple[UUID, User, Membership]] = []

    for target in targets:
        org_id = target["org_id"]
        user_ids = target["user_ids"]

        org = org_service.get_org_by_id(db, org_id, include_deleted=True)
        if not org:
            missing_targets.append(
                {
                    "org_id": str(org_id),
                    "missing_user_ids": [str(uid) for uid in user_ids],
                }
            )
            continue

        rows = (
            db.query(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .filter(
                Membership.organization_id == org_id,
                User.id.in_(user_ids),
            )
            .all()
        )
        found_ids = {row[0].id for row in rows}
        missing_ids = [str(uid) for uid in user_ids if uid not in found_ids]
        if missing_ids:
            missing_targets.append({"org_id": str(org_id), "missing_user_ids": missing_ids})
        recipients.extend([(org_id, user, membership) for user, membership in rows])

    if missing_targets:
        raise MissingTargetsError({"missing_targets": missing_targets})

    sent = 0
    suppressed = 0
    failed = 0
    failures: list[dict] = []

    for org_id, user, membership in recipients:
        if not user.is_active or not membership.is_active:
            suppressed += 1
            continue

        org = org_service.get_org_by_id(db, org_id, include_deleted=True)
        if not org:
            failed += 1
            failures.append(
                {
                    "org_id": str(org_id),
                    "user_id": str(user.id),
                    "email": audit_service.hash_email(user.email),
                    "error": "organization_not_found",
                }
            )
            continue

        org_name = org_service.get_org_display_name(org)
        full_name = user.display_name or ""
        first_name = full_name.split()[0] if full_name else ""
        unsubscribe_url = unsubscribe_service.build_unsubscribe_url(
            org_id=org_id,
            email=user.email,
            base_url=org_service.get_org_portal_base_url(org),
        )

        variables = {
            "org_name": org_name,
            "org_slug": org.slug,
            "first_name": first_name,
            "full_name": full_name,
            "email": user.email,
            "role_title": humanize_identifier(membership.role),
            "inviter_text": inviter_text,
            "platform_logo_url": platform_logo_url,
            "platform_logo_block": platform_logo_block,
            "unsubscribe_url": unsubscribe_url,
        }

        rendered_subject, rendered_body = email_service.render_template(
            template.subject,
            template.body,
            variables,
            safe_html_vars={"platform_logo_block"},
        )

        result = await platform_email_service.send_email_logged(
            db=db,
            org_id=org_id,
            to_email=user.email,
            subject=rendered_subject,
            from_email=resolved_from,
            html=rendered_body,
            text=None,
            template_id=None,
            surrogate_id=None,
            idempotency_key=f"platform-campaign:{system_key}:{org_id}:{user.id}",
        )

        if result.get("success"):
            sent += 1
        else:
            error = str(result.get("error") or "")
            if "suppressed" in error.lower():
                suppressed += 1
            else:
                failed += 1
                failures.append(
                    {
                        "org_id": str(org_id),
                        "user_id": str(user.id),
                        "email": audit_service.hash_email(user.email),
                        "error": error,
                    }
                )

    log_admin_action(
        db=db,
        actor_id=actor_id,
        action="email_template.system.campaign_send",
        target_org_id=None,
        metadata={
            "system_key": system_key,
            "sent": sent,
            "suppressed": suppressed,
            "failed": failed,
            "recipients": len(recipients),
        },
        request=request,
    )
    db.commit()

    return {
        "sent": sent,
        "suppressed": suppressed,
        "failed": failed,
        "recipients": len(recipients),
        "failures": failures[:50],
    }


# =============================================================================
# Admin Action Log Queries
# =============================================================================


def get_admin_action_logs(
    db: Session,
    org_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Get admin action logs, optionally filtered by org."""
    actor = aliased(User)
    target_user = aliased(User)
    target_org = aliased(Organization)

    query = (
        db.query(
            AdminActionLog,
            actor.email,
            target_org.name,
            target_user.email,
        )
        .outerjoin(actor, AdminActionLog.actor_user_id == actor.id)
        .outerjoin(target_org, AdminActionLog.target_organization_id == target_org.id)
        .outerjoin(target_user, AdminActionLog.target_user_id == target_user.id)
    )

    if org_id:
        query = query.filter(AdminActionLog.target_organization_id == org_id)

    total = query.with_entities(func.count(AdminActionLog.id)).scalar() or 0
    logs = query.order_by(AdminActionLog.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for log, actor_email, target_org_name, target_user_email in logs:
        items.append(
            {
                "id": str(log.id),
                "actor_email": actor_email,
                "action": log.action,
                "target_org_name": target_org_name,
                "target_user_email": target_user_email,
                "metadata": log.metadata_,
                "created_at": log.created_at.isoformat(),
            }
        )

    return items, total


# =============================================================================
# Platform Alerts (Cross-Org)
# =============================================================================


def list_platform_alerts(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    org_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List all alerts across organizations with filters."""
    query = db.query(SystemAlert, Organization.name).outerjoin(
        Organization, Organization.id == SystemAlert.organization_id
    )

    if status:
        query = query.filter(SystemAlert.status == status)
    if severity:
        query = query.filter(SystemAlert.severity == severity)
    if org_id:
        query = query.filter(SystemAlert.organization_id == org_id)

    total = query.with_entities(func.count(SystemAlert.id)).scalar() or 0
    alerts = query.order_by(SystemAlert.last_seen_at.desc()).offset(offset).limit(limit).all()

    items = []
    for alert, org_name in alerts:
        org_label = org_name or "Unknown"

        items.append(
            {
                "id": str(alert.id),
                "organization_id": str(alert.organization_id),
                "org_name": org_label,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "status": alert.status,
                "title": alert.title,
                "message": alert.message,
                "occurrence_count": alert.occurrence_count,
                "first_seen_at": alert.first_seen_at.isoformat(),
                "last_seen_at": alert.last_seen_at.isoformat(),
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            }
        )

    return items, total


def acknowledge_alert(
    db: Session,
    alert_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict | None:
    """Acknowledge an alert."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
    if not alert:
        return None

    if alert.status == "open":
        alert.status = "acknowledged"

        log_admin_action(
            db=db,
            actor_id=actor_id,
            action="alert.acknowledge",
            target_org_id=alert.organization_id,
            metadata={"alert_id": str(alert_id), "alert_type": alert.alert_type},
            request=request,
        )

        db.commit()

    return {
        "id": str(alert.id),
        "status": alert.status,
    }


def resolve_alert(
    db: Session,
    alert_id: UUID,
    actor_id: UUID,
    request: Request | None = None,
) -> dict | None:
    """Resolve an alert."""
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
    if not alert:
        return None

    if alert.status != "resolved":
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by_user_id = actor_id

        log_admin_action(
            db=db,
            actor_id=actor_id,
            action="alert.resolve",
            target_org_id=alert.organization_id,
            metadata={"alert_id": str(alert_id), "alert_type": alert.alert_type},
            request=request,
        )

        db.commit()

    return {
        "id": str(alert.id),
        "status": alert.status,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }
