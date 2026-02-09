"""Search service - global full-text search across entities.

Provides:
- Global search across surrogates, notes, attachments, intended parents
- Org-scoped and permission-gated results
- Snippets via ts_headline for context
- websearch_to_tsquery with plainto_tsquery fallback
"""

import logging
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, case, func, literal, literal_column, or_, select, text, true, union_all, cast, String
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import OwnerType, Role
from app.db.models import Attachment, Surrogate, EntityNote, IntendedParent, PipelineStage
from app.utils.normalization import normalize_identifier, normalize_search_text


logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class SearchResult(TypedDict):
    """A single search result."""

    entity_type: str  # "surrogate", "note", "attachment", "intended_parent"
    entity_id: str
    title: str
    snippet: str
    rank: float
    # Additional context
    surrogate_id: str | None
    surrogate_name: str | None


class SearchResponse(TypedDict):
    """Search response with results grouped by type."""

    query: str
    total: int
    results: list[SearchResult]


# =============================================================================
# Query Helpers
# =============================================================================


def _extract_hashes(query: str) -> tuple[str | None, str | None]:
    """Extract deterministic hashes for email/phone queries."""
    email_hash = None
    phone_hash = None
    if "@" in query:
        try:
            email_hash = hash_email(query)
        except (RuntimeError, ValueError):
            email_hash = None
    digit_count = sum(1 for ch in query if ch.isdigit())
    if digit_count >= 7:
        try:
            phone_hash = hash_phone(query) or None
        except (RuntimeError, ValueError):
            phone_hash = None
    return email_hash, phone_hash


# =============================================================================
# Permission Helpers
# =============================================================================


def _user_can_view_notes(permissions: set[str]) -> bool:
    """Check if user has permission to view surrogate notes."""
    return "view_surrogate_notes" in permissions


def _user_can_view_intended_parents(permissions: set[str]) -> bool:
    """Check if user has permission to view intended parents."""
    return "view_intended_parents" in permissions


def _can_view_post_approval(permissions: set[str]) -> bool:
    """Check if user can view post-approval surrogates."""
    return "view_post_approval_surrogates" in permissions


def _build_surrogate_access_filter(
    role: str,
    user_id: UUID,
    can_view_post_approval: bool,
    surrogate_table,
    stage_table,
):
    """Build SQLAlchemy filter for surrogate access rules."""
    if role == Role.DEVELOPER.value:
        return true()

    if role in (Role.ADMIN.value, Role.CASE_MANAGER.value):
        ownership_filter = true()
    else:
        ownership_filter = and_(
            surrogate_table.c.owner_type == OwnerType.USER.value,
            surrogate_table.c.owner_id == user_id,
        )

    if can_view_post_approval:
        post_filter = true()
    else:
        post_filter = or_(
            stage_table.c.stage_type.is_(None),
            stage_table.c.stage_type != "post_approval",
        )

    return and_(ownership_filter, post_filter)


# =============================================================================
# Search Functions
# =============================================================================


def _global_search_unified(
    db: Session,
    org_id: UUID,
    query: str,
    user_id: UUID,
    role: str,
    permissions: set[str],
    entity_types: list[str],
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """
    Perform a unified FTS search across multiple entity types using UNION ALL.
    """
    subqueries = []

    can_view_notes = _user_can_view_notes(permissions)
    can_view_ips = _user_can_view_intended_parents(permissions)
    can_view_post_approval = _can_view_post_approval(permissions)

    # 1. Surrogates
    if "surrogate" in entity_types:
        s_alias = Surrogate.__table__.alias("s")
        ps_alias = PipelineStage.__table__.alias("ps")

        access_filter = _build_surrogate_access_filter(
            role, user_id, can_view_post_approval, s_alias, ps_alias
        )

        tsquery = func.websearch_to_tsquery("simple", query)

        # Prepare fallback filters
        normalized_text = normalize_search_text(query)
        normalized_identifier = normalize_identifier(query)

        search_conditions = [s_alias.c.search_vector.op("@@")(tsquery)]
        if normalized_text:
            search_conditions.append(s_alias.c.full_name_normalized.ilike(f"%{normalized_text}%"))
        if normalized_identifier:
            search_conditions.append(s_alias.c.surrogate_number_normalized.ilike(f"%{normalized_identifier}%"))

        rank_expr = case(
            (s_alias.c.search_vector.op("@@")(tsquery), func.ts_rank(s_alias.c.search_vector, tsquery)),
            else_=literal(0.5)
        ).label("rank")

        # Determine title/snippet
        title_expr = func.coalesce(s_alias.c.full_name, "Surrogate " + func.coalesce(s_alias.c.surrogate_number, ""))
        snippet_expr = func.coalesce(s_alias.c.surrogate_number, "")

        stmt = (
            select(
                literal("surrogate").label("entity_type"),
                cast(s_alias.c.id, String).label("entity_id"),
                title_expr.label("title"),
                snippet_expr.label("snippet"),
                rank_expr,
                cast(s_alias.c.id, String).label("surrogate_id"),
                s_alias.c.full_name.label("surrogate_name"),
            )
            .select_from(
                s_alias.outerjoin(ps_alias, s_alias.c.stage_id == ps_alias.c.id)
            )
            .where(
                s_alias.c.organization_id == org_id,
                or_(*search_conditions),
                access_filter,
            )
        )
        subqueries.append(stmt)

    # 2. Intended Parents
    if "intended_parent" in entity_types and can_view_ips:
        ip_alias = IntendedParent.__table__.alias("ip")

        tsquery = func.websearch_to_tsquery("simple", query)
        rank_expr = func.ts_rank(ip_alias.c.search_vector, tsquery).label("rank")

        title_expr = func.coalesce(ip_alias.c.full_name, "Intended Parent " + func.coalesce(ip_alias.c.intended_parent_number, ""))
        snippet_expr = func.coalesce(ip_alias.c.intended_parent_number, "")

        stmt = (
            select(
                literal("intended_parent").label("entity_type"),
                cast(ip_alias.c.id, String).label("entity_id"),
                title_expr.label("title"),
                snippet_expr.label("snippet"),
                rank_expr,
                literal(None).label("surrogate_id"),
                literal(None).label("surrogate_name"),
            )
            .where(
                ip_alias.c.organization_id == org_id,
                ip_alias.c.search_vector.op("@@")(tsquery),
            )
        )
        subqueries.append(stmt)

    # 3. Notes (Surrogate & IP)
    if "note" in entity_types and can_view_notes:
        en_alias = EntityNote.__table__.alias("en")
        tsquery = func.websearch_to_tsquery("english", query)
        rank_expr = func.ts_rank(en_alias.c.search_vector, tsquery).label("rank")

        snippet_expr = func.ts_headline(
            "english",
            func.regexp_replace(
                func.coalesce(en_alias.c.content, ""),
                literal("<[^>]+>"),
                literal(" "),
                literal("g"),
            ),
            tsquery,
            literal("MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>"),
        ).label("snippet")

        # Surrogate Notes
        s_alias = Surrogate.__table__.alias("s")
        ps_alias = PipelineStage.__table__.alias("ps")
        access_filter = _build_surrogate_access_filter(
            role, user_id, can_view_post_approval, s_alias, ps_alias
        )

        surrogate_note_stmt = (
            select(
                literal("note").label("entity_type"),
                cast(en_alias.c.id, String).label("entity_id"),
                ("Note on " + func.coalesce(s_alias.c.full_name, "Surrogate")).label("title"),
                snippet_expr,
                rank_expr,
                cast(s_alias.c.id, String).label("surrogate_id"),
                s_alias.c.full_name.label("surrogate_name"),
            )
            .select_from(
                en_alias.join(
                    s_alias,
                    and_(
                        en_alias.c.entity_type == "surrogate",
                        en_alias.c.entity_id == s_alias.c.id,
                        s_alias.c.organization_id == en_alias.c.organization_id,
                    ),
                ).outerjoin(ps_alias, s_alias.c.stage_id == ps_alias.c.id)
            )
            .where(
                en_alias.c.organization_id == org_id,
                en_alias.c.search_vector.op("@@")(tsquery),
                access_filter,
            )
        )
        subqueries.append(surrogate_note_stmt)

        # IP Notes
        if can_view_ips:
            ip_alias = IntendedParent.__table__.alias("ip")
            ip_note_stmt = (
                select(
                    literal("note").label("entity_type"),
                    cast(en_alias.c.id, String).label("entity_id"),
                    ("Note on " + func.coalesce(ip_alias.c.full_name, "Intended Parent")).label("title"),
                    snippet_expr,
                    rank_expr,
                    literal(None).label("surrogate_id"),
                    literal(None).label("surrogate_name"),
                )
                .select_from(
                    en_alias.join(
                        ip_alias,
                        and_(
                            en_alias.c.entity_type == "intended_parent",
                            en_alias.c.entity_id == ip_alias.c.id,
                            ip_alias.c.organization_id == en_alias.c.organization_id,
                        ),
                    )
                )
                .where(
                    en_alias.c.organization_id == org_id,
                    en_alias.c.search_vector.op("@@")(tsquery),
                )
            )
            subqueries.append(ip_note_stmt)

    # 4. Attachments (Surrogate & IP)
    if "attachment" in entity_types:
        a_alias = Attachment.__table__.alias("a")
        tsquery = func.websearch_to_tsquery("simple", query)
        rank_expr = func.ts_rank(a_alias.c.search_vector, tsquery).label("rank")

        # Surrogate Attachments
        s_alias = Surrogate.__table__.alias("s")
        ps_alias = PipelineStage.__table__.alias("ps")
        access_filter = _build_surrogate_access_filter(
            role, user_id, can_view_post_approval, s_alias, ps_alias
        )

        surrogate_att_stmt = (
            select(
                literal("attachment").label("entity_type"),
                cast(a_alias.c.id, String).label("entity_id"),
                func.coalesce(a_alias.c.filename, "Attachment").label("title"),
                literal("").label("snippet"),
                rank_expr,
                cast(s_alias.c.id, String).label("surrogate_id"),
                s_alias.c.full_name.label("surrogate_name"),
            )
            .select_from(
                a_alias.join(
                    s_alias,
                    and_(
                        a_alias.c.surrogate_id == s_alias.c.id,
                        s_alias.c.organization_id == a_alias.c.organization_id,
                    ),
                ).outerjoin(ps_alias, s_alias.c.stage_id == ps_alias.c.id)
            )
            .where(
                a_alias.c.organization_id == org_id,
                a_alias.c.surrogate_id.is_not(None),
                a_alias.c.deleted_at.is_(None),
                a_alias.c.quarantined.is_(False),
                a_alias.c.search_vector.op("@@")(tsquery),
                access_filter,
            )
        )
        subqueries.append(surrogate_att_stmt)

        # IP Attachments
        if can_view_ips:
            ip_alias = IntendedParent.__table__.alias("ip")
            ip_att_stmt = (
                select(
                    literal("attachment").label("entity_type"),
                    cast(a_alias.c.id, String).label("entity_id"),
                    func.coalesce(a_alias.c.filename, "Attachment").label("title"),
                    literal("").label("snippet"),
                    rank_expr,
                    literal(None).label("surrogate_id"),
                    literal(None).label("surrogate_name"),
                )
                .select_from(
                    a_alias.join(
                        ip_alias,
                        and_(
                            a_alias.c.intended_parent_id == ip_alias.c.id,
                            ip_alias.c.organization_id == a_alias.c.organization_id,
                        ),
                    )
                )
                .where(
                    a_alias.c.organization_id == org_id,
                    a_alias.c.intended_parent_id.is_not(None),
                    a_alias.c.surrogate_id.is_(None),
                    a_alias.c.deleted_at.is_(None),
                    a_alias.c.quarantined.is_(False),
                    a_alias.c.search_vector.op("@@")(tsquery),
                )
            )
            subqueries.append(ip_att_stmt)

    if not subqueries:
        return []

    # Combine all queries
    union_stmt = union_all(*subqueries).order_by(text("rank DESC")).limit(limit).offset(offset)

    try:
        rows = db.execute(union_stmt).fetchall()
        results = []
        for row in rows:
            results.append(
                SearchResult(
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    title=row.title,
                    snippet=row.snippet,
                    rank=float(row.rank),
                    surrogate_id=row.surrogate_id,
                    surrogate_name=row.surrogate_name,
                )
            )
        return results
    except SQLAlchemyError as e:
        logger.warning(f"Unified search failed: {e}")
        return []


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
    seen_ids: set[str] = set()
    role_value = role.value if hasattr(role, "value") else role

    # Default to all types
    if not entity_types:
        entity_types = ["surrogate", "note", "attachment", "intended_parent"]

    # Normalize legacy "case" -> "surrogate"
    entity_types = ["surrogate" if t == "case" else t for t in entity_types]

    can_view_ips = _user_can_view_intended_parents(permissions)
    can_view_post_approval = _can_view_post_approval(permissions)

    # 1. Exact Match (Email/Phone) - Prioritize these
    # Only run exact match on first page (offset 0)
    if offset == 0:
        email_hash, phone_hash = _extract_hashes(query)
        if email_hash or phone_hash:
            # Surrogates Exact Match
            if "surrogate" in entity_types:
                surrogate_table = Surrogate.__table__.alias("s")
                stage_table = PipelineStage.__table__.alias("ps")
                access_filter = _build_surrogate_access_filter(
                    role_value,
                    user_id,
                    can_view_post_approval,
                    surrogate_table,
                    stage_table,
                )

                hash_clauses = []
                if email_hash:
                    hash_clauses.append(surrogate_table.c.email_hash == email_hash)
                if phone_hash:
                    hash_clauses.append(surrogate_table.c.phone_hash == phone_hash)

                stmt = (
                    select(
                        surrogate_table.c.id,
                        surrogate_table.c.full_name,
                        surrogate_table.c.surrogate_number,
                    )
                    .select_from(
                        surrogate_table.outerjoin(
                            stage_table, surrogate_table.c.stage_id == stage_table.c.id
                        )
                    )
                    .where(
                        surrogate_table.c.organization_id == org_id,
                        or_(*hash_clauses),
                        access_filter,
                    )
                )
                rows = db.execute(stmt).fetchall()
                for row in rows:
                    if str(row.id) not in seen_ids:
                        results.append(SearchResult(
                            entity_type="surrogate",
                            entity_id=str(row.id),
                            title=row.full_name or f"Surrogate {row.surrogate_number}",
                            snippet=row.surrogate_number or "",
                            rank=2.0,  # Boosted rank for exact match
                            surrogate_id=str(row.id),
                            surrogate_name=row.full_name,
                        ))
                        seen_ids.add(str(row.id))

            # IPs Exact Match
            if "intended_parent" in entity_types and can_view_ips:
                ip_table = IntendedParent.__table__.alias("ip")
                hash_clauses = []
                if email_hash:
                    hash_clauses.append(ip_table.c.email_hash == email_hash)
                if phone_hash:
                    hash_clauses.append(ip_table.c.phone_hash == phone_hash)

                stmt = (
                    select(
                        ip_table.c.id,
                        ip_table.c.full_name,
                        ip_table.c.intended_parent_number,
                    )
                    .where(ip_table.c.organization_id == org_id, or_(*hash_clauses))
                )
                rows = db.execute(stmt).fetchall()
                for row in rows:
                    if str(row.id) not in seen_ids:
                        results.append(SearchResult(
                            entity_type="intended_parent",
                            entity_id=str(row.id),
                            title=row.full_name or f"Intended Parent {row.intended_parent_number or ''}".strip(),
                            snippet=row.intended_parent_number or "",
                            rank=2.0,
                            surrogate_id=None,
                            surrogate_name=None,
                        ))
                        seen_ids.add(str(row.id))

    # 2. Unified FTS Search
    # We fetch up to `limit` items. If we already have exact matches, we still fetch limit.
    # The merged list will be larger than limit, but that's fine (or we slice it).
    fts_results = _global_search_unified(
        db, org_id, query, user_id, role_value, permissions, entity_types, limit, offset
    )

    for res in fts_results:
        # Deduplicate if exact match already found this entity
        if res["entity_id"] not in seen_ids:
            results.append(res)
            seen_ids.add(res["entity_id"])

    # Slice to limit
    results = results[:limit]

    return SearchResponse(
        query=query,
        total=len(results),
        results=results,
    )
