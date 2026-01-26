"""Public endpoints that don't require authentication.

These endpoints are used by frontend middleware and other public-facing features.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.rate_limit import limiter
from app.services import org_service


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/org-by-domain")
@limiter.limit("60/minute")
def get_org_by_domain(
    request: Request,
    response: Response,
    domain: str = Query(..., min_length=1, max_length=255, description="Hostname to resolve"),
    db: Session = Depends(get_db),
):
    """
    Resolve organization by domain for frontend middleware.

    Used by Next.js middleware to resolve {slug}.surrogacyforce.com to org context.

    Returns org summary with portal_base_url for the resolved organization.
    Returns 404 if domain doesn't match any organization.
    """
    # Normalize hostname (case-insensitive)
    domain = domain.lower()

    org = org_service.get_org_by_host(db, domain)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Cache for 60s to reduce DB hits from middleware
    response.headers["Cache-Control"] = "public, max-age=60"

    return {
        "id": str(org.id),
        "slug": org.slug,
        "name": org.name,
        "portal_base_url": org_service.get_org_portal_base_url(org),
    }
