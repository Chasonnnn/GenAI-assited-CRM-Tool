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
        HTTPException 403: No organization membership
        HTTPException 500: Invalid role in database
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
    
    # Validate role is a known enum value
    try:
        role = Role(membership.role)
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid role in membership")
    
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
    
    Usage:
        @router.post("/admin-only", dependencies=[Depends(require_roles([Role.MANAGER]))])
        def admin_endpoint(...): ...
    
    Or as a direct dependency:
        def admin_endpoint(session = Depends(require_roles([Role.MANAGER]))): ...
    """
    def dependency(request: Request, db: Session = Depends(get_db)):
        session = get_current_session(request, db)
        if session.role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Role '{session.role.value}' not authorized"
            )
        return session
    return dependency


def require_csrf_header(request: Request) -> None:
    """
    Verify CSRF header on mutations.
    
    Apply to state-changing endpoints:
        @router.post("/leads", dependencies=[Depends(require_csrf_header)])
    
    Do NOT apply to:
        - OAuth redirects/callbacks
        - GET endpoints
        - Health checks
    
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
    
    Usage:
        def list_leads(org_id: UUID = Depends(get_org_scope), db: Session = Depends(get_db)):
            return db.query(Lead).filter(Lead.organization_id == org_id).all()
    """
    session = get_current_session(request, db)
    return session.org_id
