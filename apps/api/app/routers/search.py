"""Search router - global search endpoint."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES
from app.core.rate_limit import limiter
from app.schemas.auth import UserSession
from app.services import search_service

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
    return search_service.global_search_for_session(
        db=db,
        request=request,
        session=session,
        q=q,
        types=types,
        limit=limit,
        offset=offset,
    )
