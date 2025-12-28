"""Search router - global search endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db
from app.schemas.auth import UserSession
from app.services import search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("")
def global_search(
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

    # Build permissions dict from session
    permissions = {
        "view_case_notes": session.has_permission("view_case_notes"),
        "view_intended_parents": session.has_permission("view_intended_parents"),
        "is_admin": "admin" in (session.roles or []),
    }

    return search_service.global_search(
        db=db,
        org_id=session.organization_id,
        query=q,
        permissions=permissions,
        entity_types=entity_types,
        limit=limit,
        offset=offset,
    )
