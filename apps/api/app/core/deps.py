"""FastAPI dependencies for authentication, authorization, and database access."""

from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Generator
from uuid import UUID
import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import PermissionKey
from app.core.security import decode_session_token
from app.core.csrf import CSRF_HEADER, CSRF_COOKIE_NAME, validate_csrf
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Cookie and header names
COOKIE_NAME = "crm_session"

# MFA enforcement allowlist (paths that can be accessed before MFA verification)
MFA_BYPASS_PREFIXES = ("/mfa",)
MFA_BYPASS_ROUTES = {
    ("GET", "/auth/me"),
    ("POST", "/auth/logout"),
}


def _is_mfa_bypass_allowed(request: Request) -> bool:
    path = request.url.path
    method = request.method.upper()
    if any(path.startswith(prefix) for prefix in MFA_BYPASS_PREFIXES):
        return True
    return (method, path) in MFA_BYPASS_ROUTES


def _is_dev_host(host: str) -> bool:
    """Allow common dev/test hosts to bypass strict host validation."""
    if settings.ENV.lower() in ("dev", "development", "test"):
        if host in ("localhost", "127.0.0.1", "test", "testserver"):
            return True
        if host.endswith(".localhost") or host.endswith(".test"):
            return True
    return False


def _get_origin_host(request: Request) -> str:
    """Extract hostname from Origin/Referer headers when present."""
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if not origin:
        return ""
    try:
        return (urlparse(origin).hostname or "").lower()
    except Exception:
        return ""


def _is_oauth_callback_request(request: Request) -> bool:
    """Allow OAuth callbacks from third-party providers on the API host."""
    path = request.url.path or ""
    if not (path.startswith("/integrations/") and path.endswith("/callback")):
        return False
    host = request.headers.get("host", "").split(":")[0].lower()
    api_host = f"api.{settings.PLATFORM_BASE_DOMAIN}" if settings.PLATFORM_BASE_DOMAIN else ""
    return bool(api_host) and host == api_host


def _allow_ops_mfa_fallback(request: Request, origin_host: str, is_platform_admin: bool) -> bool:
    """Allow ops MFA requests to bypass org membership checks for platform admins."""
    if not is_platform_admin:
        return False
    if not request.url.path.startswith("/mfa"):
        return False
    ops_host = f"ops.{settings.PLATFORM_BASE_DOMAIN}" if settings.PLATFORM_BASE_DOMAIN else ""
    if not ops_host:
        return False
    return origin_host == ops_host


def _validate_request_host(request: Request, org_slug: str) -> None:
    """
    Validate that the request host matches the organization's subdomain.

    This prevents cross-tenant session reuse when using a shared cookie domain.
    With .surrogacyforce.com cookie domain, a session cookie from ewi.surrogacyforce.com
    would be sent to agency2.surrogacyforce.com - this validation rejects that.

    Args:
        request: FastAPI request
        org_slug: Organization slug from the session

    Raises:
        HTTPException 403: If host doesn't match expected subdomain
    """
    host = request.headers.get("host", "").split(":")[0].lower()

    # Allow localhost/dev environments
    if _is_dev_host(host):
        return

    # Validate host matches expected subdomain
    expected_host = f"{org_slug}.{settings.PLATFORM_BASE_DOMAIN}"
    if host == expected_host:
        return

    # Allow API host when Origin/Referer matches the expected tenant host
    api_host = f"api.{settings.PLATFORM_BASE_DOMAIN}" if settings.PLATFORM_BASE_DOMAIN else ""
    origin_host = _get_origin_host(request)
    if host == api_host and origin_host == expected_host:
        return
    if _is_oauth_callback_request(request):
        return

    raise HTTPException(status_code=403, detail="Session invalid for this domain")


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Yields a database session and ensures it's closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_for_stream() -> Generator[Session, None, None]:
    """Database session for streaming endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Get authenticated user from session cookie.

    Validates:
    - Session cookie exists
    - JWT is valid and not expired
    - User exists and is active
    - Token version matches (for revocation support)

    Raises:
        HTTPException 401: Authentication failed
    """
    # Import here to avoid circular imports
    from app.db.models import User

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_session_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    # Token version check (revocation support)
    if user.token_version != payload.get("token_version"):
        raise HTTPException(status_code=401, detail="Session revoked")

    return user


def get_current_session(request: Request, db: Session = Depends(get_db)):
    """
    Get full session context: user_id, org_id, role, MFA status.

    This is the PRIMARY auth dependency for most endpoints.
    Returns a UserSession with all context needed for authorization.

    CRITICAL: This validates the session exists in the database,
    enabling session revocation. JWTs alone cannot be revoked.

    Raises:
        HTTPException 401: Not authenticated or session revoked
        HTTPException 403: No membership or unknown role
    """
    cached = getattr(request.state, "user_session", None)
    if cached:
        return cached

    # Import here to avoid circular imports
    from app.db.models import Membership, Organization
    from app.db.enums import Role
    from app.schemas.auth import UserSession
    from app.services import session_service

    # Parse JWT to get MFA status before calling get_current_user
    token = request.cookies.get(COOKIE_NAME)
    mfa_verified = False
    mfa_required = True
    token_hash = None

    payload: dict = {}
    if token:
        try:
            payload = decode_session_token(token)
            mfa_verified = payload.get("mfa_verified", False)
            mfa_required = payload.get("mfa_required", True)
            token_hash = session_service.hash_token(token)
        except Exception as exc:
            logger.debug("session_token_decode_failed", exc_info=exc)

    user = get_current_user(request, db)

    # Session table validation (enables revocation)
    if not token_hash:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db_session = session_service.get_session_by_token_hash(db, token_hash)
    if not db_session:
        raise HTTPException(status_code=401, detail="Session revoked or expired")

    # Update last_active_at (throttled to reduce DB writes)
    session_service.update_last_active(db, db_session)

    # Support session override (platform admin acting within org)
    if payload.get("support") is True:
        from app.db.models import SupportSession

        support_session_id = payload.get("support_session_id")
        if not support_session_id:
            raise HTTPException(status_code=401, detail="Invalid support session")

        try:
            support_session_uuid = UUID(str(support_session_id))
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid support session")

        support_session = (
            db.query(SupportSession).filter(SupportSession.id == support_session_uuid).first()
        )
        if not support_session:
            raise HTTPException(status_code=401, detail="Support session not found")

        now = datetime.now(timezone.utc)
        if support_session.revoked_at or support_session.expires_at <= now:
            raise HTTPException(status_code=401, detail="Support session expired or revoked")

        if support_session.actor_user_id != user.id:
            raise HTTPException(status_code=401, detail="Support session mismatch")

        if support_session.mode == "read_only":
            method = request.method.upper()
            if method not in ("GET", "HEAD", "OPTIONS"):
                # Allow logout to avoid trapping users in a read-only support session.
                if not (method == "POST" and request.url.path == "/auth/logout"):
                    raise HTTPException(
                        status_code=403,
                        detail="Support session is read-only; mutations not allowed",
                    )

        role_value = support_session.role_override
        if not Role.has_value(role_value):
            raise HTTPException(
                status_code=403,
                detail=f"Unknown role '{role_value}'. Contact administrator.",
            )

        role = Role(role_value)

        # Validate request host matches support session's org
        support_org = (
            db.query(Organization)
            .filter(Organization.id == support_session.organization_id)
            .first()
        )
        origin_host = _get_origin_host(request)
        if not (user.is_platform_admin and origin_host == f"ops.{settings.PLATFORM_BASE_DOMAIN}"):
            if support_org:
                _validate_request_host(request, support_org.slug)

        session = UserSession(
            user_id=user.id,
            org_id=support_session.organization_id,
            role=role,
            email=user.email,
            display_name=user.display_name,
            mfa_verified=mfa_verified,
            mfa_required=mfa_required,
            token_hash=token_hash,
        )

        if session.mfa_required and not session.mfa_verified:
            if not _is_mfa_bypass_allowed(request):
                raise HTTPException(status_code=403, detail="MFA verification required")

        request.state.support_session_id = support_session.id
        request.state.support_role = support_session.role_override
        request.state.support_mode = support_session.mode
        request.state.user_session = session
        return session

    origin_host = _get_origin_host(request)
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()

    def _build_session_from_payload() -> UserSession:
        org_id_value = payload.get("org_id")
        role_value = payload.get("role")
        if not org_id_value or not role_value or not Role.has_value(role_value):
            raise HTTPException(status_code=403, detail="No organization membership")
        try:
            org_id_uuid = UUID(str(org_id_value))
        except Exception as exc:
            raise HTTPException(status_code=403, detail="No organization membership") from exc

        return UserSession(
            user_id=user.id,
            org_id=org_id_uuid,
            role=Role(role_value),
            email=user.email,
            display_name=user.display_name,
            mfa_verified=mfa_verified,
            mfa_required=mfa_required,
            token_hash=token_hash,
        )

    if not membership or not membership.is_active:
        if _allow_ops_mfa_fallback(request, origin_host, user.is_platform_admin):
            session = _build_session_from_payload()
            if session.mfa_required and not session.mfa_verified:
                if not _is_mfa_bypass_allowed(request):
                    raise HTTPException(status_code=403, detail="MFA verification required")
            request.state.user_session = session
            return session
        if not membership:
            raise HTTPException(status_code=403, detail="No organization membership")
        raise HTTPException(status_code=403, detail="Membership inactive")

    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    if not org or org.deleted_at:
        if _allow_ops_mfa_fallback(request, origin_host, user.is_platform_admin):
            session = _build_session_from_payload()
            if session.mfa_required and not session.mfa_verified:
                if not _is_mfa_bypass_allowed(request):
                    raise HTTPException(status_code=403, detail="MFA verification required")
            request.state.user_session = session
            return session
        raise HTTPException(status_code=403, detail="Organization is scheduled for deletion")

    # Validate request host matches org's subdomain (cross-tenant protection)
    if not (user.is_platform_admin and origin_host == f"ops.{settings.PLATFORM_BASE_DOMAIN}"):
        _validate_request_host(request, org.slug)

    # Validate role is a known enum value - return 403 not 500
    if not Role.has_value(membership.role):
        raise HTTPException(
            status_code=403,
            detail=f"Unknown role '{membership.role}'. Contact administrator.",
        )

    role = Role(membership.role)

    session = UserSession(
        user_id=user.id,
        org_id=membership.organization_id,
        role=role,
        email=user.email,
        display_name=user.display_name,
        mfa_verified=mfa_verified,
        mfa_required=mfa_required,
        token_hash=token_hash,
    )

    if session.mfa_required and not session.mfa_verified:
        if not _is_mfa_bypass_allowed(request):
            raise HTTPException(status_code=403, detail="MFA verification required")

    request.state.user_session = session
    return session


def require_roles(allowed_roles: list):
    """
    Dependency factory for role-based authorization.

    Uses enum values (not strings) to prevent drift.

    Usage:
        @router.post("/admin", dependencies=[Depends(require_roles([Role.ADMIN, Role.DEVELOPER]))])
    """

    def dependency(request: Request, db: Session = Depends(get_db)):
        session = get_current_session(request, db)
        if session.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{session.role.value}' not authorized for this action",
            )
        return session

    return dependency


def _normalize_permission(permission: str | PermissionKey) -> str:
    return permission.value if isinstance(permission, PermissionKey) else permission


def require_permission(permission: str | PermissionKey):
    """
    Dependency factory for permission-based authorization.

    Uses the RBAC permission system with:
    - Role defaults
    - User-level overrides (grant/revoke)
    - Developer always has all permissions

    Usage:
        @router.get("/surrogates", dependencies=[Depends(require_permission("view_surrogates"))])
    """

    def dependency(request: Request, db: Session = Depends(get_db)):
        from app.services import permission_service

        session = get_current_session(request, db)
        permission_key = _normalize_permission(permission)

        if not permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, permission_key
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")
        return session

    return dependency


def require_ai_enabled(request: Request, db: Session = Depends(get_db)):
    """Ensure the organization has AI enabled."""
    from app.db.models import Organization

    session = get_current_session(request, db)
    org = db.query(Organization).filter(Organization.id == session.org_id).first()
    if not org or not org.ai_enabled:
        raise HTTPException(status_code=403, detail="AI is not enabled for this organization")
    return session


def require_any_permissions(permissions: list[str | PermissionKey]):
    """
    Dependency factory for OR-based permission checks.

    Usage:
        @router.get("/reports", dependencies=[Depends(require_any_permissions([P.REPORTS_VIEW, P.OPS_MANAGE]))])
    """

    def dependency(request: Request, db: Session = Depends(get_db)):
        from app.services import permission_service

        session = get_current_session(request, db)
        permission_keys = [_normalize_permission(p) for p in permissions]
        effective = permission_service.get_effective_permissions(
            db, session.org_id, session.user_id, session.role.value
        )
        if not any(key in effective for key in permission_keys):
            raise HTTPException(
                status_code=403,
                detail=f"Missing one of permissions: {', '.join(permission_keys)}",
            )
        return session

    return dependency


def require_all_permissions(permissions: list[str | PermissionKey]):
    """
    Dependency factory for AND-based permission checks.

    Usage:
        @router.post("/exports", dependencies=[Depends(require_all_permissions([P.AUDIT_VIEW, P.EXPORT_DATA]))])
    """

    def dependency(request: Request, db: Session = Depends(get_db)):
        from app.services import permission_service

        session = get_current_session(request, db)
        permission_keys = [_normalize_permission(p) for p in permissions]
        effective = permission_service.get_effective_permissions(
            db, session.org_id, session.user_id, session.role.value
        )
        missing = [key for key in permission_keys if key not in effective]
        if missing:
            raise HTTPException(
                status_code=403, detail=f"Missing permissions: {', '.join(missing)}"
            )
        return session

    return dependency


def require_csrf_header(request: Request) -> None:
    """
    Verify CSRF header on mutations.

    Apply to state-changing endpoints (POST, PATCH, DELETE).

    Raises:
        HTTPException 403: Missing or invalid CSRF header
    """
    if not validate_csrf(request):
        raise HTTPException(
            status_code=403,
            detail=(
                "Missing or invalid CSRF token. "
                f"Include '{CSRF_HEADER}' header matching '{CSRF_COOKIE_NAME}' cookie."
            ),
        )


def get_org_scope(request: Request, db: Session = Depends(get_db)) -> UUID:
    """
    Get org_id for query scoping.

    Every list/detail query MUST filter by this value
    to ensure proper tenant isolation.
    """
    session = get_current_session(request, db)
    return session.org_id


# =============================================================================
# Permission Check Helpers (use enum sets from db.enums)
# =============================================================================


def can_assign(session) -> bool:
    """Check if user can assign cases to others."""
    from app.db.enums import ROLES_CAN_ASSIGN

    return session.role in ROLES_CAN_ASSIGN


def can_archive(session) -> bool:
    """Check if user can archive/restore cases."""
    from app.db.enums import ROLES_CAN_ARCHIVE

    return session.role in ROLES_CAN_ARCHIVE


def can_hard_delete(session) -> bool:
    """Check if user can permanently delete cases."""
    from app.db.enums import ROLES_CAN_HARD_DELETE

    return session.role in ROLES_CAN_HARD_DELETE


def can_manage_settings(session) -> bool:
    """Check if user can manage org settings."""
    from app.db.enums import ROLES_CAN_MANAGE_SETTINGS

    return session.role in ROLES_CAN_MANAGE_SETTINGS


def can_manage_integrations(session) -> bool:
    """Check if user can manage integrations (developer only)."""
    from app.db.enums import ROLES_CAN_MANAGE_INTEGRATIONS

    return session.role in ROLES_CAN_MANAGE_INTEGRATIONS


def can_invite(session) -> bool:
    """Check if user can invite new members."""
    from app.db.enums import ROLES_CAN_INVITE

    return session.role in ROLES_CAN_INVITE


def is_owner_or_can_manage(session, created_by_user_id: UUID) -> bool:
    """Check if user is the creator OR has admin+ permissions."""
    from app.db.enums import ROLES_CAN_ARCHIVE  # Manager+ can do anything

    return session.user_id == created_by_user_id or session.role in ROLES_CAN_ARCHIVE


def is_owner_or_assignee_or_admin(
    session,
    created_by_user_id: UUID | None,
    owner_type: str | None,
    owner_id: UUID | None,
) -> bool:
    """Check if user is creator, owner (user), or admin+. For tasks."""
    from app.db.enums import ROLES_CAN_ARCHIVE, OwnerType

    is_owner = owner_type == OwnerType.USER.value and owner_id == session.user_id
    return session.user_id == created_by_user_id or is_owner or session.role in ROLES_CAN_ARCHIVE


# =============================================================================
# Platform Admin Dependencies (Cross-Org Access)
# =============================================================================


class PlatformUserSession:
    """Session context for platform admin users (cross-org)."""

    def __init__(
        self,
        user_id: UUID,
        email: str,
        display_name: str,
        is_platform_admin: bool,
        token_version: int,
        mfa_verified: bool,
        mfa_required: bool,
    ):
        self.user_id = user_id
        self.email = email
        self.display_name = display_name
        self.is_platform_admin = is_platform_admin
        self.token_version = token_version
        self.mfa_verified = mfa_verified
        self.mfa_required = mfa_required


def require_platform_admin(request: Request, db: Session = Depends(get_db)) -> PlatformUserSession:
    """
    Require platform admin access for cross-org operations.

    Platform admins do NOT need org membership - the ops console is cross-org by design.

    Access rules:
    - Production: is_platform_admin AND email in allowlist (defense in depth)
    - Non-prod: is_platform_admin OR email in allowlist (easier testing)

    This ensures production has break-glass protection while allowing
    easier development and testing.
    """
    from app.core.config import settings
    from app.db.models import User
    from app.services import session_service

    # Get and validate session cookie
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_session_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Validate session exists in DB (for revocation support)
    token_hash = session_service.hash_token(token)
    db_session = session_service.get_session_by_token_hash(db, token_hash)
    if not db_session:
        raise HTTPException(status_code=401, detail="Session revoked or expired")

    # Get user from DB
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    # Token version check (revocation support)
    if user.token_version != payload.get("token_version"):
        raise HTTPException(status_code=401, detail="Session revoked")

    # Enforce MFA if required (matches get_current_session behavior)
    mfa_verified = payload.get("mfa_verified", False)
    mfa_required = payload.get("mfa_required", True)
    if mfa_required and not mfa_verified:
        if not _is_mfa_bypass_allowed(request):
            raise HTTPException(status_code=403, detail="MFA verification required")

    # Check platform admin access
    has_db_flag = user.is_platform_admin
    in_allowlist = user.email.lower() in settings.platform_admin_emails_list

    # Prod: require BOTH (break-glass pattern for safety)
    # Non-prod: require EITHER (easier testing)
    if settings.is_prod:
        is_admin = has_db_flag and in_allowlist
    else:
        is_admin = has_db_flag or in_allowlist

    if not is_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required")

    host = request.headers.get("host", "").split(":")[0].lower()
    origin_host = _get_origin_host(request)
    if not _is_dev_host(host):
        if host == f"ops.{settings.PLATFORM_BASE_DOMAIN}":
            return PlatformUserSession(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_platform_admin=user.is_platform_admin,
                token_version=user.token_version,
                mfa_verified=mfa_verified,
                mfa_required=mfa_required,
            )
        if (
            host == f"api.{settings.PLATFORM_BASE_DOMAIN}"
            and origin_host == f"ops.{settings.PLATFORM_BASE_DOMAIN}"
        ):
            return PlatformUserSession(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                is_platform_admin=user.is_platform_admin,
                token_version=user.token_version,
                mfa_verified=mfa_verified,
                mfa_required=mfa_required,
            )
        from app.services import org_service

        org = org_service.get_org_by_host(db, host)
        if not org:
            raise HTTPException(status_code=403, detail="Session invalid for this domain")

    return PlatformUserSession(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_platform_admin=user.is_platform_admin,
        token_version=user.token_version,
        mfa_verified=mfa_verified,
        mfa_required=mfa_required,
    )
