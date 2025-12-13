"""Development-only endpoints for testing and seeding."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.security import create_session_token
from app.db.enums import AuthProvider, Role
from app.db.models import AuthIdentity, Membership, Organization, User

router = APIRouter()


def _verify_dev_secret(x_dev_secret: str = Header(...)):
    """
    Verify dev secret header.
    
    Provides an extra layer of protection for dev endpoints
    beyond just the ENV check.
    """
    if x_dev_secret != settings.DEV_SECRET:
        raise HTTPException(status_code=403, detail="Invalid dev secret")


@router.post("/seed", dependencies=[Depends(_verify_dev_secret)])
def seed_test_data(db: Session = Depends(get_db)):
    """
    Create test organization and users for local development.
    
    Requires X-Dev-Secret header matching DEV_SECRET env var.
    Idempotent - returns existing data if already seeded.
    """
    # Check if already seeded
    existing = db.query(Organization).filter(Organization.slug == "test-org").first()
    if existing:
        return {"status": "already_seeded", "org_id": str(existing.id)}
    
    # Create test org
    org = Organization(name="Test Organization", slug="test-org")
    db.add(org)
    db.flush()
    
    # Create test users with different roles
    users_data = [
        ("manager@test.com", "Test Manager", Role.MANAGER),
        ("intake@test.com", "Test Intake", Role.INTAKE_SPECIALIST),
        ("specialist@test.com", "Test Case Manager", Role.CASE_MANAGER),
    ]
    
    created_users = []
    for email, name, role in users_data:
        user = User(email=email, display_name=name)
        db.add(user)
        db.flush()
        
        # Create fake auth identity
        identity = AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.GOOGLE.value,
            provider_subject=f"test-sub-{email}",
            email=email,
        )
        db.add(identity)
        
        # Create membership
        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role=role.value,
        )
        db.add(membership)
        
        created_users.append({
            "email": email, 
            "user_id": str(user.id), 
            "role": role.value
        })
    
    db.commit()
    
    return {
        "status": "seeded",
        "org_id": str(org.id),
        "org_slug": "test-org",
        "users": created_users,
    }


@router.post("/login-as/{user_id}", dependencies=[Depends(_verify_dev_secret)])
def login_as(
    user_id: UUID, 
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Bypass OAuth and directly set session cookie for testing.
    
    Requires X-Dev-Secret header matching DEV_SECRET env var.
    Useful for testing role-based access without real OAuth flow.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is disabled")
    
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not membership:
        raise HTTPException(status_code=400, detail="User has no membership")
    
    token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
    )
    
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    
    return {
        "status": "logged_in",
        "user_id": str(user.id),
        "email": user.email,
        "role": membership.role,
        "org_id": str(membership.organization_id),
    }
