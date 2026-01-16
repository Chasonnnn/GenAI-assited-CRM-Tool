"""FastAPI dependencies for authentication, authorization, and database access."""

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.permissions import PermissionKey
from app.core.security import decode_session_token
from app.db.session import SessionLocal


# Cookie and header names
COOKIE_NAME = "crm_session"
CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "XMLHttpRequest"

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
    from app.db.models import Membership
    from app.db.enums import Role
    from app.schemas.auth import UserSession
    from app.services import session_service

    # Parse JWT to get MFA status before calling get_current_user
    token = request.cookies.get(COOKIE_NAME)
    mfa_verified = False
    mfa_required = True
    token_hash = None

    if token:
        try:
            payload = decode_session_token(token)
            mfa_verified = payload.get("mfa_verified", False)
            mfa_required = payload.get("mfa_required", True)
            token_hash = session_service.hash_token(token)
        except Exception:
            pass  # Let get_current_user handle the error

    user = get_current_user(request, db)

    # Session table validation (enables revocation)
    if not token_hash:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db_session = session_service.get_session_by_token_hash(db, token_hash)
    if not db_session:
        raise HTTPException(status_code=401, detail="Session revoked or expired")

    # Update last_active_at (throttled to reduce DB writes)
    session_service.update_last_active(db, db_session)

    membership = db.query(Membership).filter(Membership.user_id == user.id).first()

    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")
    if not membership.is_active:
        raise HTTPException(status_code=403, detail="Membership inactive")

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
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=403,
            detail=f"Missing CSRF header. Include '{CSRF_HEADER}: {CSRF_HEADER_VALUE}'",
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
