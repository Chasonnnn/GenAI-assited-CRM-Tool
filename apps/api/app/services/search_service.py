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

from sqlalchemy import and_, func, literal, or_, select, true
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
        entity_types = ["surrogate", "note", "attachment", "intended_parent"]

    can_view_notes = _user_can_view_notes(permissions)
    can_view_ips = _user_can_view_intended_parents(permissions)
    can_view_post_approval = _can_view_post_approval(permissions)
    # Search surrogates
    if "surrogate" in entity_types:
        surrogate_results = _search_surrogates(
            db,
            org_id,
            query,
            limit,
            offset,
            role_value,
            user_id,
            can_view_post_approval,
        )
        results.extend(surrogate_results)

    # Search notes (permission-gated)
    if "note" in entity_types and can_view_notes:
        note_results = _search_notes(
            db,
            org_id,
            query,
            limit,
            offset,
            role_value,
            user_id,
            can_view_post_approval,
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
            role_value,
            user_id,
            can_view_post_approval,
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


def _search_surrogates(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
    role: str,
    user_id: UUID,
    can_view_post_approval: bool,
) -> list[SearchResult]:
    """Search surrogates by full_name, surrogate_number, and exact email/phone matches."""
    results: list[SearchResult] = []
    seen_ids: set[str] = set()

    surrogate_table = Surrogate.__table__.alias("s")
    stage_table = PipelineStage.__table__.alias("ps")
    surrogate_access_filter = _build_surrogate_access_filter(
        role,
        user_id,
        can_view_post_approval,
        surrogate_table,
        stage_table,
    )
    base_from = surrogate_table.outerjoin(
        stage_table, surrogate_table.c.stage_id == stage_table.c.id
    )

    email_hash, phone_hash = _extract_hashes(query)
    if email_hash or phone_hash:
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
                literal(1.0).label("rank"),
            )
            .select_from(base_from)
            .where(
                surrogate_table.c.organization_id == org_id,
                or_(*hash_clauses),
                surrogate_access_filter,
            )
            .order_by(surrogate_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.execute(stmt).fetchall()
        for row in rows:
            result = SearchResult(
                entity_type="surrogate",
                entity_id=str(row.id),
                title=row.full_name or f"Surrogate {row.surrogate_number}",
                snippet=row.surrogate_number or "",
                rank=float(row.rank),
                surrogate_id=str(row.id),
                surrogate_name=row.full_name,
            )
            results.append(result)
            seen_ids.add(str(row.id))

    try:
        tsquery = func.websearch_to_tsquery("simple", query)
        rank_expr = func.ts_rank(surrogate_table.c.search_vector, tsquery).label("rank")
        stmt = (
            select(
                surrogate_table.c.id,
                surrogate_table.c.full_name,
                surrogate_table.c.surrogate_number,
                rank_expr,
            )
            .select_from(base_from)
            .where(
                surrogate_table.c.organization_id == org_id,
                surrogate_table.c.search_vector.op("@@")(tsquery),
                surrogate_access_filter,
            )
            .order_by(rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = db.execute(stmt).fetchall()

        for row in rows:
            if str(row.id) in seen_ids:
                continue
            results.append(
                SearchResult(
                    entity_type="surrogate",
                    entity_id=str(row.id),
                    title=row.full_name or f"Surrogate {row.surrogate_number}",
                    snippet=row.surrogate_number or "",
                    rank=float(row.rank),
                    surrogate_id=str(row.id),
                    surrogate_name=row.full_name,
                )
            )
    except SQLAlchemyError as e:
        logger.warning(f"Surrogate search failed, trying fallback: {e}")
        # Try fallback
        try:
            tsquery = func.plainto_tsquery("simple", query)
            rank_expr = func.ts_rank(surrogate_table.c.search_vector, tsquery).label("rank")
            snippet_expr = func.ts_headline(
                "simple",
                func.coalesce(surrogate_table.c.full_name, ""),
                tsquery,
            ).label("snippet")
            stmt = (
                select(
                    surrogate_table.c.id,
                    surrogate_table.c.full_name,
                    surrogate_table.c.surrogate_number,
                    rank_expr,
                    snippet_expr,
                )
                .select_from(base_from)
                .where(
                    surrogate_table.c.organization_id == org_id,
                    surrogate_table.c.search_vector.op("@@")(tsquery),
                    surrogate_access_filter,
                )
                .order_by(rank_expr.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = db.execute(stmt).fetchall()
            for row in rows:
                if str(row.id) in seen_ids:
                    continue
                results.append(
                    SearchResult(
                        entity_type="surrogate",
                        entity_id=str(row.id),
                        title=row.full_name or f"Surrogate {row.surrogate_number}",
                        snippet=row.snippet or "",
                        rank=float(row.rank),
                        surrogate_id=str(row.id),
                        surrogate_name=row.full_name,
                    )
                )
        except SQLAlchemyError:
            pass

    if len(results) < limit:
        normalized_text = normalize_search_text(query)
        normalized_identifier = normalize_identifier(query)
        fallback_filters = []
        if normalized_text:
            fallback_filters.append(
                surrogate_table.c.full_name_normalized.ilike(f"%{normalized_text}%")
            )
        if normalized_identifier:
            fallback_filters.append(
                surrogate_table.c.surrogate_number_normalized.ilike(f"%{normalized_identifier}%")
            )
        if fallback_filters:
            fallback_stmt = (
                select(
                    surrogate_table.c.id,
                    surrogate_table.c.full_name,
                    surrogate_table.c.surrogate_number,
                    literal(0.5).label("rank"),
                )
                .select_from(base_from)
                .where(
                    surrogate_table.c.organization_id == org_id,
                    or_(*fallback_filters),
                    surrogate_access_filter,
                )
                .order_by(surrogate_table.c.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = db.execute(fallback_stmt).fetchall()
            for row in rows:
                if str(row.id) in seen_ids:
                    continue
                results.append(
                    SearchResult(
                        entity_type="surrogate",
                        entity_id=str(row.id),
                        title=row.full_name or f"Surrogate {row.surrogate_number}",
                        snippet=row.surrogate_number or "",
                        rank=float(row.rank),
                        surrogate_id=str(row.id),
                        surrogate_name=row.full_name,
                    )
                )

    return results


def _search_notes(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
    role: str,
    user_id: UUID,
    can_view_post_approval: bool,
    can_view_intended_parents: bool,
) -> list[SearchResult]:
    """Search entity notes by content (HTML stripped)."""
    results = []

    notes_table = EntityNote.__table__.alias("en")
    surrogate_table = Surrogate.__table__.alias("s")
    stage_table = PipelineStage.__table__.alias("ps")
    surrogate_access_filter = _build_surrogate_access_filter(
        role,
        user_id,
        can_view_post_approval,
        surrogate_table,
        stage_table,
    )
    surrogate_from = notes_table.join(
        surrogate_table,
        and_(
            notes_table.c.entity_type == "surrogate",
            notes_table.c.entity_id == surrogate_table.c.id,
            surrogate_table.c.organization_id == notes_table.c.organization_id,
        ),
    ).outerjoin(stage_table, surrogate_table.c.stage_id == stage_table.c.id)

    def _run_queries(tsquery_expr) -> None:
        rank_expr = func.ts_rank(notes_table.c.search_vector, tsquery_expr).label("rank")
        snippet_expr = func.ts_headline(
            "english",
            func.regexp_replace(
                func.coalesce(notes_table.c.content, ""),
                literal("<[^>]+>"),
                literal(" "),
                literal("g"),
            ),
            tsquery_expr,
            literal("MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>"),
        ).label("snippet")

        surrogate_stmt = (
            select(
                notes_table.c.id,
                rank_expr,
                snippet_expr,
                surrogate_table.c.id.label("surrogate_id"),
                surrogate_table.c.full_name.label("surrogate_name"),
            )
            .select_from(surrogate_from)
            .where(
                notes_table.c.organization_id == org_id,
                notes_table.c.search_vector.op("@@")(tsquery_expr),
                surrogate_access_filter,
            )
            .order_by(rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = db.execute(surrogate_stmt).fetchall()

        for row in rows:
            title = f"Note on {row.surrogate_name}" if row.surrogate_name else "Surrogate Note"
            results.append(
                SearchResult(
                    entity_type="note",
                    entity_id=str(row.id),
                    title=title,
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    surrogate_id=str(row.surrogate_id),
                    surrogate_name=row.surrogate_name,
                )
            )

        if not can_view_intended_parents:
            return

        ip_table = IntendedParent.__table__.alias("ip")
        ip_from = notes_table.join(
            ip_table,
            and_(
                notes_table.c.entity_type == "intended_parent",
                notes_table.c.entity_id == ip_table.c.id,
                ip_table.c.organization_id == notes_table.c.organization_id,
            ),
        )

        ip_rank_expr = func.ts_rank(notes_table.c.search_vector, tsquery_expr).label("rank")
        ip_snippet_expr = func.ts_headline(
            "english",
            func.regexp_replace(
                func.coalesce(notes_table.c.content, ""),
                literal("<[^>]+>"),
                literal(" "),
                literal("g"),
            ),
            tsquery_expr,
            literal("MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>"),
        ).label("snippet")

        ip_stmt = (
            select(
                notes_table.c.id,
                ip_rank_expr,
                ip_snippet_expr,
                ip_table.c.full_name.label("ip_name"),
            )
            .select_from(ip_from)
            .where(
                notes_table.c.organization_id == org_id,
                notes_table.c.search_vector.op("@@")(tsquery_expr),
            )
            .order_by(ip_rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        ip_rows = db.execute(ip_stmt).fetchall()

        for row in ip_rows:
            title = f"Note on {row.ip_name}" if row.ip_name else "Intended Parent Note"
            results.append(
                SearchResult(
                    entity_type="note",
                    entity_id=str(row.id),
                    title=title,
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    surrogate_id=None,
                    surrogate_name=None,
                )
            )

    try:
        # Use 'english' dictionary for notes (with stemming)
        tsquery = func.websearch_to_tsquery("english", query)
        _run_queries(tsquery)
    except SQLAlchemyError as e:
        logger.warning(f"Note search failed, trying fallback: {e}")
        try:
            tsquery = func.plainto_tsquery("english", query)
            _run_queries(tsquery)
        except SQLAlchemyError as fallback_error:
            logger.warning(f"Note search fallback failed: {fallback_error}")

    return results


def _search_attachments(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
    role: str,
    user_id: UUID,
    can_view_post_approval: bool,
    can_view_intended_parents: bool,
) -> list[SearchResult]:
    """Search attachments by filename."""
    results = []

    attachments_table = Attachment.__table__.alias("a")
    surrogate_table = Surrogate.__table__.alias("s")
    stage_table = PipelineStage.__table__.alias("ps")
    surrogate_access_filter = _build_surrogate_access_filter(
        role,
        user_id,
        can_view_post_approval,
        surrogate_table,
        stage_table,
    )
    surrogate_from = attachments_table.join(
        surrogate_table,
        and_(
            attachments_table.c.surrogate_id == surrogate_table.c.id,
            surrogate_table.c.organization_id == attachments_table.c.organization_id,
        ),
    ).outerjoin(stage_table, surrogate_table.c.stage_id == stage_table.c.id)

    def _run_queries(tsquery_expr) -> None:
        rank_expr = func.ts_rank(attachments_table.c.search_vector, tsquery_expr).label("rank")
        surrogate_stmt = (
            select(
                attachments_table.c.id,
                attachments_table.c.filename,
                attachments_table.c.surrogate_id,
                rank_expr,
                surrogate_table.c.full_name.label("surrogate_name"),
            )
            .select_from(surrogate_from)
            .where(
                attachments_table.c.organization_id == org_id,
                attachments_table.c.surrogate_id.is_not(None),
                attachments_table.c.deleted_at.is_(None),
                attachments_table.c.quarantined.is_(False),
                attachments_table.c.search_vector.op("@@")(tsquery_expr),
                surrogate_access_filter,
            )
            .order_by(rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = db.execute(surrogate_stmt).fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    entity_type="attachment",
                    entity_id=str(row.id),
                    title=row.filename or "Attachment",
                    snippet="",
                    rank=float(row.rank),
                    surrogate_id=str(row.surrogate_id),
                    surrogate_name=row.surrogate_name,
                )
            )

        if not can_view_intended_parents:
            return

        ip_table = IntendedParent.__table__.alias("ip")
        ip_from = attachments_table.join(
            ip_table,
            and_(
                attachments_table.c.intended_parent_id == ip_table.c.id,
                ip_table.c.organization_id == attachments_table.c.organization_id,
            ),
        )
        ip_rank_expr = func.ts_rank(attachments_table.c.search_vector, tsquery_expr).label("rank")
        ip_stmt = (
            select(
                attachments_table.c.id,
                attachments_table.c.filename,
                attachments_table.c.intended_parent_id,
                ip_rank_expr,
                ip_table.c.full_name.label("ip_name"),
            )
            .select_from(ip_from)
            .where(
                attachments_table.c.organization_id == org_id,
                attachments_table.c.intended_parent_id.is_not(None),
                attachments_table.c.surrogate_id.is_(None),
                attachments_table.c.deleted_at.is_(None),
                attachments_table.c.quarantined.is_(False),
                attachments_table.c.search_vector.op("@@")(tsquery_expr),
            )
            .order_by(ip_rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        ip_rows = db.execute(ip_stmt).fetchall()

        for row in ip_rows:
            title = row.filename or "Attachment"
            results.append(
                SearchResult(
                    entity_type="attachment",
                    entity_id=str(row.id),
                    title=title,
                    snippet="",
                    rank=float(row.rank),
                    surrogate_id=None,
                    surrogate_name=None,
                )
            )

    try:
        tsquery = func.websearch_to_tsquery("simple", query)
        _run_queries(tsquery)
    except SQLAlchemyError as e:
        logger.warning(f"Attachment search failed, trying fallback: {e}")
        try:
            tsquery = func.plainto_tsquery("simple", query)
            _run_queries(tsquery)
        except SQLAlchemyError as fallback_error:
            logger.warning(f"Attachment search fallback failed: {fallback_error}")

    return results


def _search_intended_parents(
    db: Session,
    org_id: UUID,
    query: str,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Search intended parents by name, number, and exact email/phone matches."""
    results: list[SearchResult] = []
    seen_ids: set[str] = set()
    ip_table = IntendedParent.__table__.alias("ip")

    email_hash, phone_hash = _extract_hashes(query)
    if email_hash or phone_hash:
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
                literal(1.0).label("rank"),
            )
            .where(ip_table.c.organization_id == org_id, or_(*hash_clauses))
            .order_by(ip_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.execute(stmt).fetchall()
        for row in rows:
            results.append(
                SearchResult(
                    entity_type="intended_parent",
                    entity_id=str(row.id),
                    title=row.full_name
                    or f"Intended Parent {row.intended_parent_number or ''}".strip(),
                    snippet=row.intended_parent_number or "",
                    rank=float(row.rank),
                    surrogate_id=None,
                    surrogate_name=None,
                )
            )
            seen_ids.add(str(row.id))

    try:
        tsquery = func.websearch_to_tsquery("simple", query)
        rank_expr = func.ts_rank(ip_table.c.search_vector, tsquery).label("rank")
        stmt = (
            select(
                ip_table.c.id, ip_table.c.full_name, ip_table.c.intended_parent_number, rank_expr
            )
            .where(
                ip_table.c.organization_id == org_id,
                ip_table.c.search_vector.op("@@")(tsquery),
            )
            .order_by(rank_expr.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = db.execute(stmt).fetchall()

        for row in rows:
            if str(row.id) in seen_ids:
                continue
            results.append(
                SearchResult(
                    entity_type="intended_parent",
                    entity_id=str(row.id),
                    title=row.full_name
                    or f"Intended Parent {row.intended_parent_number or ''}".strip(),
                    snippet=row.intended_parent_number or "",
                    rank=float(row.rank),
                    surrogate_id=None,
                    surrogate_name=None,
                )
            )
    except SQLAlchemyError as e:
        logger.warning(f"Intended parent search failed, trying fallback: {e}")
        try:
            tsquery = func.plainto_tsquery("simple", query)
            rank_expr = func.ts_rank(ip_table.c.search_vector, tsquery).label("rank")
            stmt = (
                select(
                    ip_table.c.id,
                    ip_table.c.full_name,
                    ip_table.c.intended_parent_number,
                    rank_expr,
                )
                .where(
                    ip_table.c.organization_id == org_id,
                    ip_table.c.search_vector.op("@@")(tsquery),
                )
                .order_by(rank_expr.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = db.execute(stmt).fetchall()
            for row in rows:
                if str(row.id) in seen_ids:
                    continue
                results.append(
                    SearchResult(
                        entity_type="intended_parent",
                        entity_id=str(row.id),
                        title=row.full_name
                        or f"Intended Parent {row.intended_parent_number or ''}".strip(),
                        snippet=row.intended_parent_number or "",
                        rank=float(row.rank),
                        surrogate_id=None,
                        surrogate_name=None,
                    )
                )
        except SQLAlchemyError as fallback_error:
            logger.warning(f"Intended parent search fallback failed: {fallback_error}")

    return results
