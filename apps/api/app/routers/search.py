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
    dependencies=[Depends(require_permission(POLICIES["cases"].default))],
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
    Global search across cases, notes, attachments, and intended parents.

    Results are:
    - Org-scoped to the current user's organization
    - Permission-gated (notes require view_case_notes, IPs require view_intended_parents)
    - Ranked by relevance
    - Include highlighted snippets

    Example queries:
    - Simple: "john smith"
    - Phrase: '"contract signed"'
    - Boolean: "john AND (smith OR doe)"
    """
    # Parse entity types
    entity_types = [t.strip() for t in types.split(",") if t.strip()]
    valid_types = {"case", "note", "attachment", "intended_parent"}
    entity_types = [t for t in entity_types if t in valid_types]

    if not entity_types:
        entity_types = list(valid_types)

    effective_permissions = permission_service.get_effective_permissions(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        role=session.role.value,
    )
    return search_service.global_search(
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
