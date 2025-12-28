"""Search service - global full-text search across entities.

Provides:
- Global search across cases, notes, attachments, intended parents
- Org-scoped and permission-gated results
- Snippets via ts_headline for context
- websearch_to_tsquery with plainto_tsquery fallback
"""

import logging
from typing import TypedDict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class SearchResult(TypedDict):
    """A single search result."""

    entity_type: str  # "case", "note", "attachment", "intended_parent"
    entity_id: str
    title: str
    snippet: str
    rank: float
    # Additional context
    case_id: str | None
    case_name: str | None


class SearchResponse(TypedDict):
    """Search response with results grouped by type."""

    query: str
    total: int
    results: list[SearchResult]


# =============================================================================
# Query Helpers
# =============================================================================


def _build_tsquery(query: str, dictionary: str = "simple") -> str:
    """
    Build a safe tsquery from user input.

    Uses websearch_to_tsquery for user-friendly search syntax.
    Falls back to plainto_tsquery if websearch syntax fails.
    """
    # Escape single quotes for SQL safety
    safe_query = query.replace("'", "''")
    return f"websearch_to_tsquery('{dictionary}', '{safe_query}')"


def _build_tsquery_fallback(query: str, dictionary: str = "simple") -> str:
    """Fallback to plainto_tsquery for simple queries."""
    safe_query = query.replace("'", "''")
    return f"plainto_tsquery('{dictionary}', '{safe_query}')"


# =============================================================================
# Permission Helpers
# =============================================================================


def _user_can_view_notes(permissions: dict) -> bool:
    """Check if user has permission to view case notes."""
    return permissions.get("view_case_notes", False) or permissions.get(
        "is_admin", False
    )


def _user_can_view_intended_parents(permissions: dict) -> bool:
    """Check if user has permission to view intended parents."""
    return permissions.get("view_intended_parents", False) or permissions.get(
        "is_admin", False
    )


# =============================================================================
# Search Functions
# =============================================================================


def global_search(
    db: Session,
    org_id: UUID,
    query: str,
    permissions: dict,
    entity_types: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    """
    Search across cases, notes, attachments, and intended parents.

    Args:
        db: Database session
        org_id: Organization ID (for scoping)
        query: Search query
        permissions: User permissions dict
        entity_types: Optional filter for entity types ["case", "note", "attachment", "intended_parent"]
        limit: Max results per type
        offset: Pagination offset

    Returns:
        SearchResponse with ranked results and snippets
    """
    if not query or not query.strip():
        return SearchResponse(query=query, total=0, results=[])

    query = query.strip()
    results: list[SearchResult] = []

    # Default to all types
    if not entity_types:
        entity_types = ["case", "note", "attachment", "intended_parent"]

    # Search cases
    if "case" in entity_types:
        case_results = _search_cases(db, org_id, query, limit, offset)
        results.extend(case_results)

    # Search notes (permission-gated)
    if "note" in entity_types and _user_can_view_notes(permissions):
        note_results = _search_notes(db, org_id, query, limit, offset)
        results.extend(note_results)

    # Search attachments
    if "attachment" in entity_types:
        attachment_results = _search_attachments(db, org_id, query, limit, offset)
        results.extend(attachment_results)

    # Search intended parents (permission-gated)
    if "intended_parent" in entity_types and _user_can_view_intended_parents(
        permissions
    ):
        ip_results = _search_intended_parents(db, org_id, query, limit, offset)
        results.extend(ip_results)

    # Sort by rank (descending)
    results.sort(key=lambda r: r["rank"], reverse=True)

    # Apply overall limit
    results = results[:limit]

    return SearchResponse(
        query=query,
        total=len(results),
        results=results,
    )


def _search_cases(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Search cases by full_name, case_number, email, phone."""
    results = []

    try:
        tsquery = _build_tsquery(query, "simple")
        # Minimal results for cases - no heavy ts_headline
        sql = text(f"""
            SELECT 
                id,
                full_name,
                case_number,
                email,
                ts_rank(search_vector, {tsquery}) as rank
            FROM cases
            WHERE organization_id = :org_id
              AND search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            sql, {"org_id": str(org_id), "limit": limit, "offset": offset}
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="case",
                    entity_id=str(row.id),
                    title=row.full_name or f"Case {row.case_number}",
                    snippet=row.email or "",  # Minimal: just email as context
                    rank=float(row.rank),
                    case_id=str(row.id),
                    case_name=row.full_name,
                )
            )
    except Exception as e:
        logger.warning(f"Case search failed, trying fallback: {e}")
        # Try fallback
        try:
            tsquery = _build_tsquery_fallback(query)
            sql = text(f"""
                SELECT 
                    id,
                    full_name,
                    case_number,
                    ts_rank(search_vector, {tsquery}) as rank,
                    ts_headline('simple', coalesce(full_name, ''), {tsquery}) as snippet
                FROM cases
                WHERE organization_id = :org_id
                  AND search_vector @@ {tsquery}
                ORDER BY rank DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(
                sql, {"org_id": str(org_id), "limit": limit, "offset": offset}
            ).fetchall()
            for row in rows:
                results.append(
                    SearchResult(
                        entity_type="case",
                        entity_id=str(row.id),
                        title=row.full_name or f"Case {row.case_number}",
                        snippet=row.snippet or "",
                        rank=float(row.rank),
                        case_id=str(row.id),
                        case_name=row.full_name,
                    )
                )
        except Exception:
            pass

    return results


def _search_notes(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Search entity notes by content (HTML stripped)."""
    results = []

    try:
        # Use 'english' dictionary for notes (with stemming)
        tsquery = _build_tsquery(query, "english")
        sql = text(f"""
            SELECT 
                en.id,
                en.entity_type,
                en.entity_id,
                en.content,
                ts_rank(en.search_vector, {tsquery}) as rank,
                ts_headline('english', 
                    regexp_replace(coalesce(en.content, ''), '<[^>]+>', ' ', 'g'),
                    {tsquery},
                    'MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>'
                ) as snippet,
                c.id as case_id,
                c.full_name as case_name
            FROM entity_notes en
            LEFT JOIN cases c ON en.entity_type = 'case' AND en.entity_id = c.id
            WHERE en.organization_id = :org_id
              AND en.search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            sql, {"org_id": str(org_id), "limit": limit, "offset": offset}
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="note",
                    entity_id=str(row.id),
                    title=f"Note on {row.entity_type}",
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    case_id=str(row.case_id) if row.case_id else None,
                    case_name=row.case_name,
                )
            )
    except Exception as e:
        logger.warning(f"Note search failed: {e}")

    return results


def _search_attachments(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Search attachments by filename."""
    results = []

    try:
        tsquery = _build_tsquery(query, "simple")
        # Minimal results for attachments - no heavy ts_headline
        sql = text(f"""
            SELECT 
                a.id,
                a.filename,
                a.case_id,
                ts_rank(a.search_vector, {tsquery}) as rank,
                c.full_name as case_name
            FROM attachments a
            LEFT JOIN cases c ON a.case_id = c.id
            WHERE a.organization_id = :org_id
              AND a.search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            sql, {"org_id": str(org_id), "limit": limit, "offset": offset}
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="attachment",
                    entity_id=str(row.id),
                    title=row.filename or "Attachment",
                    snippet="",  # Minimal: no snippet for attachments
                    rank=float(row.rank),
                    case_id=str(row.case_id) if row.case_id else None,
                    case_name=row.case_name,
                )
            )
    except Exception as e:
        logger.warning(f"Attachment search failed: {e}")

    return results


def _search_intended_parents(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Search intended parents by full_name, email, phone."""
    results = []

    try:
        tsquery = _build_tsquery(query, "simple")
        # Minimal results for IPs - no heavy ts_headline
        sql = text(f"""
            SELECT 
                id,
                full_name,
                email,
                ts_rank(search_vector, {tsquery}) as rank
            FROM intended_parents
            WHERE organization_id = :org_id
              AND search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            sql, {"org_id": str(org_id), "limit": limit, "offset": offset}
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="intended_parent",
                    entity_id=str(row.id),
                    title=row.full_name or row.email or "Intended Parent",
                    snippet=row.email or "",  # Minimal: just email
                    rank=float(row.rank),
                    case_id=None,
                    case_name=None,
                )
            )
    except Exception as e:
        logger.warning(f"Intended parent search failed: {e}")

    return results
