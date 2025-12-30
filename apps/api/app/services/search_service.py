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

from app.db.enums import OwnerType, Role


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


def _build_tsquery(dictionary: str = "simple", param_name: str = "query") -> str:
    """
    Build a safe tsquery from user input.

    Uses websearch_to_tsquery for user-friendly search syntax.
    Falls back to plainto_tsquery if websearch syntax fails.
    """
    return f"websearch_to_tsquery('{dictionary}', :{param_name})"


def _build_tsquery_fallback(
    dictionary: str = "simple", param_name: str = "query"
) -> str:
    """Fallback to plainto_tsquery for simple queries."""
    return f"plainto_tsquery('{dictionary}', :{param_name})"


# =============================================================================
# Permission Helpers
# =============================================================================


def _user_can_view_notes(permissions: set[str]) -> bool:
    """Check if user has permission to view case notes."""
    return "view_case_notes" in permissions


def _user_can_view_intended_parents(permissions: set[str]) -> bool:
    """Check if user has permission to view intended parents."""
    return "view_intended_parents" in permissions


def _can_view_post_approval(permissions: set[str]) -> bool:
    """Check if user can view post-approval cases."""
    return "view_post_approval_cases" in permissions


def _build_case_access_clause(
    role: str,
    user_id: UUID,
    can_view_post_approval: bool,
    case_alias: str,
    stage_alias: str,
) -> tuple[str, dict]:
    """Build SQL WHERE clause for case access rules."""
    if role == Role.DEVELOPER.value:
        return "TRUE", {}

    params: dict[str, str] = {}
    if role in (Role.ADMIN.value, Role.CASE_MANAGER.value):
        ownership_clause = "TRUE"
    else:
        ownership_clause = (
            f"({case_alias}.owner_type = :owner_type_user "
            f"AND {case_alias}.owner_id = :user_id)"
        )
        params["owner_type_user"] = OwnerType.USER.value
        params["user_id"] = str(user_id)

    if can_view_post_approval:
        post_clause = "TRUE"
    else:
        post_clause = (
            f"({stage_alias}.stage_type IS NULL "
            f"OR {stage_alias}.stage_type != 'post_approval')"
        )

    return f"{ownership_clause} AND {post_clause}", params


# =============================================================================
# Search Functions
# =============================================================================


def global_search(
    db: Session,
    org_id: UUID,
    query: str,
    user_id: UUID,
    role: str,
    permissions: set[str],
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
        user_id: User ID
        role: User role (string value)
        permissions: User permissions set
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
    role_value = role.value if hasattr(role, "value") else role

    # Default to all types
    if not entity_types:
        entity_types = ["case", "note", "attachment", "intended_parent"]

    can_view_notes = _user_can_view_notes(permissions)
    can_view_ips = _user_can_view_intended_parents(permissions)
    can_view_post_approval = _can_view_post_approval(permissions)
    case_access_clause, case_access_params = _build_case_access_clause(
        role_value,
        user_id,
        can_view_post_approval,
        case_alias="c",
        stage_alias="ps",
    )

    # Search cases
    if "case" in entity_types:
        case_results = _search_cases(
            db,
            org_id,
            query,
            limit,
            offset,
            case_access_clause,
            case_access_params,
        )
        results.extend(case_results)

    # Search notes (permission-gated)
    if "note" in entity_types and can_view_notes:
        note_results = _search_notes(
            db,
            org_id,
            query,
            limit,
            offset,
            case_access_clause,
            case_access_params,
            can_view_ips,
        )
        results.extend(note_results)

    # Search attachments
    if "attachment" in entity_types:
        attachment_results = _search_attachments(
            db,
            org_id,
            query,
            limit,
            offset,
            case_access_clause,
            case_access_params,
            can_view_ips,
        )
        results.extend(attachment_results)

    # Search intended parents (permission-gated)
    if "intended_parent" in entity_types and can_view_ips:
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
    case_access_clause: str,
    case_access_params: dict,
) -> list[SearchResult]:
    """Search cases by full_name, case_number, email, phone."""
    results = []

    try:
        tsquery = _build_tsquery(dictionary="simple")
        # Minimal results for cases - no heavy ts_headline
        sql = text(f"""
            SELECT 
                c.id,
                c.full_name,
                c.case_number,
                c.email,
                ts_rank(c.search_vector, {tsquery}) as rank
            FROM cases c
            LEFT JOIN pipeline_stages ps ON c.stage_id = ps.id
            WHERE c.organization_id = :org_id
              AND c.search_vector @@ {tsquery}
              AND {case_access_clause}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
                **case_access_params,
            },
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
            tsquery = _build_tsquery_fallback(dictionary="simple")
            sql = text(f"""
                SELECT 
                    c.id,
                    c.full_name,
                    c.case_number,
                    ts_rank(c.search_vector, {tsquery}) as rank,
                    ts_headline('simple', coalesce(c.full_name, ''), {tsquery}) as snippet
                FROM cases c
                LEFT JOIN pipeline_stages ps ON c.stage_id = ps.id
                WHERE c.organization_id = :org_id
                  AND c.search_vector @@ {tsquery}
                  AND {case_access_clause}
                ORDER BY rank DESC
                LIMIT :limit OFFSET :offset
            """)
            rows = db.execute(
                sql,
                {
                    "org_id": str(org_id),
                    "query": query,
                    "limit": limit,
                    "offset": offset,
                    **case_access_params,
                },
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
    case_access_clause: str,
    case_access_params: dict,
    can_view_intended_parents: bool,
) -> list[SearchResult]:
    """Search entity notes by content (HTML stripped)."""
    results = []

    def _run_queries(tsquery: str) -> None:
        case_sql = text(f"""
            SELECT
                en.id,
                ts_rank(en.search_vector, {tsquery}) as rank,
                ts_headline('english',
                    regexp_replace(coalesce(en.content, ''), '<[^>]+>', ' ', 'g'),
                    {tsquery},
                    'MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>'
                ) as snippet,
                c.id as case_id,
                c.full_name as case_name
            FROM entity_notes en
            JOIN cases c
              ON en.entity_type = 'case'
             AND en.entity_id = c.id
             AND c.organization_id = en.organization_id
            LEFT JOIN pipeline_stages ps ON c.stage_id = ps.id
            WHERE en.organization_id = :org_id
              AND en.search_vector @@ {tsquery}
              AND {case_access_clause}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            case_sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
                **case_access_params,
            },
        ).fetchall()

        for row in rows:
            title = f"Note on {row.case_name}" if row.case_name else "Case Note"
            results.append(
                SearchResult(
                    entity_type="note",
                    entity_id=str(row.id),
                    title=title,
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    case_id=str(row.case_id),
                    case_name=row.case_name,
                )
            )

        if not can_view_intended_parents:
            return

        ip_sql = text(f"""
            SELECT
                en.id,
                ts_rank(en.search_vector, {tsquery}) as rank,
                ts_headline('english',
                    regexp_replace(coalesce(en.content, ''), '<[^>]+>', ' ', 'g'),
                    {tsquery},
                    'MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>'
                ) as snippet,
                ip.full_name as ip_name
            FROM entity_notes en
            JOIN intended_parents ip
              ON en.entity_type = 'intended_parent'
             AND en.entity_id = ip.id
             AND ip.organization_id = en.organization_id
            WHERE en.organization_id = :org_id
              AND en.search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        ip_rows = db.execute(
            ip_sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
            },
        ).fetchall()

        for row in ip_rows:
            title = f"Note on {row.ip_name}" if row.ip_name else "Intended Parent Note"
            results.append(
                SearchResult(
                    entity_type="note",
                    entity_id=str(row.id),
                    title=title,
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    case_id=None,
                    case_name=None,
                )
            )

    try:
        # Use 'english' dictionary for notes (with stemming)
        tsquery = _build_tsquery(dictionary="english")
        _run_queries(tsquery)
    except Exception as e:
        logger.warning(f"Note search failed, trying fallback: {e}")
        try:
            tsquery = _build_tsquery_fallback(dictionary="english")
            _run_queries(tsquery)
        except Exception as fallback_error:
            logger.warning(f"Note search fallback failed: {fallback_error}")

    return results


def _search_attachments(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
    case_access_clause: str,
    case_access_params: dict,
    can_view_intended_parents: bool,
) -> list[SearchResult]:
    """Search attachments by filename."""
    results = []

    def _run_queries(tsquery: str) -> None:
        case_sql = text(f"""
            SELECT
                a.id,
                a.filename,
                a.case_id,
                ts_rank(a.search_vector, {tsquery}) as rank,
                c.full_name as case_name
            FROM attachments a
            JOIN cases c
              ON a.case_id = c.id
             AND c.organization_id = a.organization_id
            LEFT JOIN pipeline_stages ps ON c.stage_id = ps.id
            WHERE a.organization_id = :org_id
              AND a.case_id IS NOT NULL
              AND a.deleted_at IS NULL
              AND a.quarantined = FALSE
              AND a.search_vector @@ {tsquery}
              AND {case_access_clause}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = db.execute(
            case_sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
                **case_access_params,
            },
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="attachment",
                    entity_id=str(row.id),
                    title=row.filename or "Attachment",
                    snippet="",
                    rank=float(row.rank),
                    case_id=str(row.case_id),
                    case_name=row.case_name,
                )
            )

        if not can_view_intended_parents:
            return

        ip_sql = text(f"""
            SELECT
                a.id,
                a.filename,
                a.intended_parent_id,
                ts_rank(a.search_vector, {tsquery}) as rank,
                ip.full_name as ip_name
            FROM attachments a
            JOIN intended_parents ip
              ON a.intended_parent_id = ip.id
             AND ip.organization_id = a.organization_id
            WHERE a.organization_id = :org_id
              AND a.intended_parent_id IS NOT NULL
              AND a.case_id IS NULL
              AND a.deleted_at IS NULL
              AND a.quarantined = FALSE
              AND a.search_vector @@ {tsquery}
            ORDER BY rank DESC
            LIMIT :limit OFFSET :offset
        """)

        ip_rows = db.execute(
            ip_sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
            },
        ).fetchall()

        for row in ip_rows:
            title = row.filename or "Attachment"
            results.append(
                SearchResult(
                    entity_type="attachment",
                    entity_id=str(row.id),
                    title=title,
                    snippet="",
                    rank=float(row.rank),
                    case_id=None,
                    case_name=None,
                )
            )

    try:
        tsquery = _build_tsquery(dictionary="simple")
        _run_queries(tsquery)
    except Exception as e:
        logger.warning(f"Attachment search failed, trying fallback: {e}")
        try:
            tsquery = _build_tsquery_fallback(dictionary="simple")
            _run_queries(tsquery)
        except Exception as fallback_error:
            logger.warning(f"Attachment search fallback failed: {fallback_error}")

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
        tsquery = _build_tsquery(dictionary="simple")
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
            sql,
            {
                "org_id": str(org_id),
                "query": query,
                "limit": limit,
                "offset": offset,
            },
        ).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="intended_parent",
                    entity_id=str(row.id),
                    title=row.full_name or row.email or "Intended Parent",
                    snippet=row.email or "",
                    rank=float(row.rank),
                    case_id=None,
                    case_name=None,
                )
            )
    except Exception as e:
        logger.warning(f"Intended parent search failed, trying fallback: {e}")
        try:
            tsquery = _build_tsquery_fallback(dictionary="simple")
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
                sql,
                {
                    "org_id": str(org_id),
                    "query": query,
                    "limit": limit,
                    "offset": offset,
                },
            ).fetchall()
            for row in rows:
                results.append(
                    SearchResult(
                        entity_type="intended_parent",
                        entity_id=str(row.id),
                        title=row.full_name or row.email or "Intended Parent",
                        snippet=row.email or "",
                        rank=float(row.rank),
                        case_id=None,
                        case_name=None,
                    )
                )
        except Exception as fallback_error:
            logger.warning(f"Intended parent search fallback failed: {fallback_error}")

    return results
