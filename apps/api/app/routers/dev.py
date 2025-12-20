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
        ("manager@test.com", "Test Manager", Role.ADMIN),
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


# =============================================================================
# Meta Lead Monitoring (for dev/admin visibility)
# =============================================================================

@router.get("/meta-leads/alerts", dependencies=[Depends(_verify_dev_secret)])
def get_meta_lead_alerts(
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """
    Get Meta leads with issues (failed conversion, fetch errors, etc).
    
    Dev-only endpoint for monitoring Meta lead ingestion health.
    """
    from app.db.models import MetaLead, MetaPageMapping
    from sqlalchemy import or_
    
    # Get problematic leads
    problem_leads = db.query(MetaLead).filter(
        or_(
            MetaLead.status.in_(["fetch_failed", "convert_failed"]),
            MetaLead.fetch_error.isnot(None),
            MetaLead.conversion_error.isnot(None),
        )
    ).order_by(MetaLead.received_at.desc()).limit(limit).all()
    
    # Get page mappings with recent errors
    problem_pages = db.query(MetaPageMapping).filter(
        MetaPageMapping.last_error.isnot(None)
    ).all()
    
    # Summary stats
    total_leads = db.query(MetaLead).count()
    failed_leads = db.query(MetaLead).filter(
        MetaLead.status.in_(["fetch_failed", "convert_failed"])
    ).count()
    
    return {
        "summary": {
            "total_leads": total_leads,
            "failed_leads": failed_leads,
            "problem_pages": len(problem_pages),
        },
        "problem_leads": [
            {
                "id": str(lead.id),
                "meta_lead_id": lead.meta_lead_id,
                "status": lead.status,
                "fetch_error": lead.fetch_error,
                "conversion_error": lead.conversion_error,
                "received_at": lead.received_at.isoformat() if lead.received_at else None,
                "field_data_preview": str(lead.field_data)[:200] if lead.field_data else None,
            }
            for lead in problem_leads
        ],
        "problem_pages": [
            {
                "page_id": page.page_id,
                "page_name": page.page_name,
                "is_active": page.is_active,
                "last_error": page.last_error,
                "last_error_at": page.last_error_at.isoformat() if page.last_error_at else None,
                "last_success_at": page.last_success_at.isoformat() if page.last_success_at else None,
            }
            for page in problem_pages
        ],
    }


@router.get("/meta-leads/all", dependencies=[Depends(_verify_dev_secret)])
def get_all_meta_leads(
    db: Session = Depends(get_db),
    limit: int = 100,
    status: str | None = None,
):
    """
    Get all Meta leads for debugging.
    
    Dev-only endpoint for viewing raw lead data.
    """
    from app.db.models import MetaLead
    
    query = db.query(MetaLead).order_by(MetaLead.received_at.desc())
    
    if status:
        query = query.filter(MetaLead.status == status)
    
    leads = query.limit(limit).all()
    
    return {
        "count": len(leads),
        "leads": [
            {
                "id": str(lead.id),
                "meta_lead_id": lead.meta_lead_id,
                "meta_form_id": lead.meta_form_id,
                "meta_page_id": lead.meta_page_id,
                "status": lead.status,
                "is_converted": lead.is_converted,
                "converted_case_id": str(lead.converted_case_id) if lead.converted_case_id else None,
                "fetch_error": lead.fetch_error,
                "conversion_error": lead.conversion_error,
                "field_data": lead.field_data,
                "received_at": lead.received_at.isoformat() if lead.received_at else None,
            }
            for lead in leads
        ],
    }
