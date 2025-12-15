"""FastAPI dependencies for authentication, authorization, and database access."""

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_session_token
from app.db.session import SessionLocal


# Cookie and header names
COOKIE_NAME = "crm_session"
CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_VALUE = "XMLHttpRequest"

# TEMPORARY: Set to True to bypass auth for testing
DEV_BYPASS_AUTH = False


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


def get_current_user(
    request: Request, 
    db: Session = Depends(get_db)
):
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
    
    # DEV BYPASS: Return mock user for testing
    if DEV_BYPASS_AUTH:
        mock_user = db.query(User).filter(User.email == "manager@test.com").first()
        if mock_user:
            return mock_user
        # Fallback: get any active user
        any_user = db.query(User).filter(User.is_active == True).first()
        if any_user:
            return any_user
    
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


def get_current_session(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get full session context: user_id, org_id, role.
    
    This is the PRIMARY auth dependency for most endpoints.
    Returns a UserSession with all context needed for authorization.
    
    Raises:
        HTTPException 401: Not authenticated
        HTTPException 403: No membership or unknown role
    """
    # Import here to avoid circular imports
    from app.db.models import Membership
    from app.db.enums import Role
    from app.schemas.auth import UserSession
    
    user = get_current_user(request, db)
    
    membership = db.query(Membership).filter(
        Membership.user_id == user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")
    
    # Validate role is a known enum value - return 403 not 500
    if not Role.has_value(membership.role):
        raise HTTPException(
            status_code=403, 
            detail=f"Unknown role '{membership.role}'. Contact administrator."
        )
    
    role = Role(membership.role)
    
    return UserSession(
        user_id=user.id,
        org_id=membership.organization_id,
        role=role,
        email=user.email,
        display_name=user.display_name,
    )


def require_roles(allowed_roles: list):
    """
    Dependency factory for role-based authorization.
    
    Uses enum values (not strings) to prevent drift.
    
    Usage:
        @router.post("/admin", dependencies=[Depends(require_roles([Role.MANAGER, Role.DEVELOPER]))])
    """
    def dependency(request: Request, db: Session = Depends(get_db)):
        session = get_current_session(request, db)
        if session.role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Role '{session.role.value}' not authorized for this action"
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
            detail=f"Missing CSRF header. Include '{CSRF_HEADER}: {CSRF_HEADER_VALUE}'"
        )


def get_org_scope(
    request: Request,
    db: Session = Depends(get_db)
) -> UUID:
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
    """Check if user is the creator OR has manager+ permissions."""
    from app.db.enums import ROLES_CAN_ARCHIVE  # Manager+ can do anything
    return session.user_id == created_by_user_id or session.role in ROLES_CAN_ARCHIVE


def is_owner_or_assignee_or_manager(
    session, 
    created_by_user_id: UUID | None,
    assigned_to_user_id: UUID | None
) -> bool:
    """Check if user is creator, assignee, or manager+. For tasks."""
    from app.db.enums import ROLES_CAN_ARCHIVE
    return (
        session.user_id == created_by_user_id or
        session.user_id == assigned_to_user_id or
        session.role in ROLES_CAN_ARCHIVE
    )
