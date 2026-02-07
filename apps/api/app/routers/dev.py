"""Development-only endpoints for testing and seeding."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import COOKIE_NAME, get_db
from app.core.csrf import set_csrf_cookie
from app.core.security import create_session_token, verify_secret
from app.services import (
    dev_service,
    membership_service,
    meta_lead_service,
    meta_page_service,
    org_service,
    session_service,
    user_service,
)

router = APIRouter()


def _verify_dev_secret(x_dev_secret: str = Header(...)):
    """
    Verify dev secret header.

    Provides an extra layer of protection for dev endpoints
    beyond just the ENV check.
    """
    if not settings.is_dev:
        raise HTTPException(status_code=403, detail="Dev endpoints are only available in dev/test.")
    if not settings.DEV_SECRET:
        raise HTTPException(status_code=501, detail="DEV_SECRET not configured")
    if not verify_secret(x_dev_secret, settings.DEV_SECRET):
        raise HTTPException(status_code=403, detail="Invalid dev secret")


@router.post("/seed", dependencies=[Depends(_verify_dev_secret)])
def seed_test_data(db: Session = Depends(get_db)):
    """
    Create test organization and users for local development.

    Requires X-Dev-Secret header matching DEV_SECRET env var.
    Idempotent - returns existing data if already seeded.
    """
    return dev_service.seed_test_data(db)


@router.post("/login-as/{user_id}", dependencies=[Depends(_verify_dev_secret)])
def login_as(
    user_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Bypass OAuth and directly set session cookie for testing.

    Requires X-Dev-Secret header matching DEV_SECRET env var.
    Useful for testing role-based access without real OAuth flow.
    """
    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is disabled")

    membership = membership_service.get_membership_by_user_id(db, user.id)
    if not membership:
        raise HTTPException(status_code=400, detail="User has no membership")

    token = create_session_token(
        user.id,
        membership.organization_id,
        membership.role,
        user.token_version,
        mfa_verified=True,
        mfa_required=False,
    )

    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=membership.organization_id,
        token=token,
        request=request,
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=settings.JWT_EXPIRES_HOURS * 3600,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    set_csrf_cookie(response)

    return {
        "status": "logged_in",
        "user_id": str(user.id),
        "email": user.email,
        "role": membership.role,
        "org_id": str(membership.organization_id),
    }


@router.get("/cors", dependencies=[Depends(_verify_dev_secret)])
def get_cors_config():
    """
    Return computed CORS settings (dev-only).

    Useful for verifying PLATFORM_BASE_DOMAIN and origin allowlists.
    """
    tenant_origin_regex = None
    if settings.PLATFORM_BASE_DOMAIN:
        scheme = "https?" if settings.is_dev else "https"
        tenant_origin_regex = (
            rf"^{scheme}://([a-z0-9-]+\.)?{re.escape(settings.PLATFORM_BASE_DOMAIN)}$"
        )

    cors_origins = set(settings.cors_origins_list)
    for origin in (settings.FRONTEND_URL, settings.OPS_FRONTEND_URL):
        if origin:
            cors_origins.add(origin)

    return {
        "env": settings.ENV,
        "platform_base_domain": settings.PLATFORM_BASE_DOMAIN,
        "frontend_url": settings.FRONTEND_URL,
        "ops_frontend_url": settings.OPS_FRONTEND_URL,
        "allow_origins": sorted(cors_origins),
        "allow_origin_regex": tenant_origin_regex,
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
    problem_leads = meta_lead_service.list_problem_leads(db, limit=limit)
    problem_pages = meta_page_service.list_problem_pages(db)
    total_leads = meta_lead_service.count_meta_leads(db)
    failed_leads = meta_lead_service.count_failed_meta_leads(db)

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
                "last_success_at": page.last_success_at.isoformat()
                if page.last_success_at
                else None,
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
    leads = meta_lead_service.list_meta_leads(db, limit=limit, status=status)

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
                "converted_surrogate_id": str(lead.converted_surrogate_id)
                if lead.converted_surrogate_id
                else None,
                "fetch_error": lead.fetch_error,
                "conversion_error": lead.conversion_error,
                "field_data": lead.field_data,
                "received_at": lead.received_at.isoformat() if lead.received_at else None,
            }
            for lead in leads
        ],
    }


# =============================================================================
# System Templates & Workflows Seeding
# =============================================================================


@router.post("/seed-templates", dependencies=[Depends(_verify_dev_secret)])
def seed_system_templates(
    org_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    """
    Seed system email templates and default workflows for an organization.

    If org_id is provided, seeds only that org.
    Otherwise, seeds all organizations.

    Idempotent - skips templates/workflows that already exist.
    """
    from app.services.template_seeder import seed_all

    results = []

    if org_id:
        # Seed specific org
        org = org_service.get_org_by_id(db, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        result = seed_all(db, org.id)
        results.append(
            {
                "org_id": str(org.id),
                "org_name": org.name,
                **result,
            }
        )
    else:
        # Seed all orgs
        orgs = org_service.list_orgs(db)
        for org in orgs:
            result = seed_all(db, org.id)
            results.append(
                {
                    "org_id": str(org.id),
                    "org_name": org.name,
                    **result,
                }
            )

    db.commit()

    total_templates = sum(r["templates_created"] for r in results)
    total_workflows = sum(r["workflows_created"] for r in results)

    return {
        "status": "seeded",
        "total_templates_created": total_templates,
        "total_workflows_created": total_workflows,
        "orgs": results,
    }


@router.post("/seed-templates/{org_id}", dependencies=[Depends(_verify_dev_secret)])
def seed_org_templates(
    org_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Seed system email templates and workflows for a specific organization.

    Convenience endpoint with org_id in path.
    """
    from app.services.template_seeder import seed_all

    org = org_service.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = seed_all(db, org.id)
    db.commit()

    return {
        "status": "seeded",
        "org_id": str(org.id),
        "org_name": org.name,
        **result,
    }
