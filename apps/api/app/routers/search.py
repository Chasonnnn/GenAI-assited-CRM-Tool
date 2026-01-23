"""Search router - global search endpoint."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES
from app.core.rate_limit import limiter
from app.schemas.auth import UserSession
from app.services import permission_service, search_service

router = APIRouter(
    prefix="/search",
    tags=["Search"],
    dependencies=[Depends(require_permission(POLICIES["surrogates"].default))],
)


@router.get("")
@limiter.limit(f"{settings.RATE_LIMIT_SEARCH}/minute")
def global_search(
    request: Request,  # Required for slowapi rate limiter
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    types: str = Query(
        "case,note,attachment,intended_parent",
        description="Comma-separated entity types to search",
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """
    Global search across surrogates, notes, attachments, and intended parents.

    Results are:
    - Org-scoped to the current user's organization
    - Permission-gated (notes require view_surrogate_notes, IPs require view_intended_parents)
    - Ranked by relevance
    - Include highlighted snippets

    Example queries:
    - Simple: "john smith"
    - Phrase: '"contract signed"'
    - Boolean: "john AND (smith OR doe)"
    """
    # Parse entity types
    entity_types = [t.strip() for t in types.split(",") if t.strip()]
    # Backwards-compat: "case" is the legacy name for "surrogate".
    valid_types = {"case", "surrogate", "note", "attachment", "intended_parent"}
    entity_types = [t for t in entity_types if t in valid_types]

    if not entity_types:
        entity_types = ["surrogate", "note", "attachment", "intended_parent"]

    # Normalize legacy type names to the service-layer expected values.
    entity_types = ["surrogate" if t == "case" else t for t in entity_types]
    # Preserve order, drop duplicates.
    entity_types = list(dict.fromkeys(entity_types))

    effective_permissions = permission_service.get_effective_permissions(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        role=session.role.value,
    )
    results = search_service.global_search(
        db=db,
        org_id=session.org_id,
        query=q,
        user_id=session.user_id,
        role=session.role.value,
        permissions=effective_permissions,
        entity_types=entity_types,
        limit=limit,
        offset=offset,
    )

    q_type = None
    if q:
        if "@" in q:
            q_type = "email"
        else:
            digit_count = sum(1 for ch in q if ch.isdigit())
            q_type = "phone" if digit_count >= 7 else "text"

    from app.services import audit_service

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="global_search",
        target_id=None,
        request=request,
        details={
            "query_length": len(q),
            "q_type": q_type,
            "types": entity_types,
            "limit": limit,
            "offset": offset,
            "result_count": results["total"],
        },
    )
    db.commit()

    return results
