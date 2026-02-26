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

from fastapi import Request
from sqlalchemy import and_, func, literal, or_, select, true, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.encryption import hash_email, hash_phone
from app.db.enums import OwnerType, Role
from app.db.models import Attachment, Surrogate, EntityNote, IntendedParent, PipelineStage
from app.schemas.auth import UserSession
from app.utils.normalization import escape_like_string, normalize_identifier, normalize_search_text


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


def normalize_entity_types(raw_types: str) -> list[str]:
    """Parse and normalize entity type filters from querystring input."""
    entity_types = [item.strip() for item in raw_types.split(",") if item.strip()]
    valid_types = {"case", "surrogate", "note", "attachment", "intended_parent"}
    entity_types = [item for item in entity_types if item in valid_types]
    if not entity_types:
        entity_types = ["surrogate", "note", "attachment", "intended_parent"]

    # Backwards-compat: "case" is the legacy name for "surrogate".
    normalized = ["surrogate" if item == "case" else item for item in entity_types]

    # Preserve order and drop duplicates.
    return list(dict.fromkeys(normalized))


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
    role_value = role.value if hasattr(role, "value") else role

    # Default to all types
    if not entity_types:
        entity_types = ["surrogate", "note", "attachment", "intended_parent"]

    can_view_notes = _user_can_view_notes(permissions)
    can_view_ips = _user_can_view_intended_parents(permissions)
    can_view_post_approval = _can_view_post_approval(permissions)
    results = _global_search_unified(
        db=db,
        org_id=org_id,
        query=query,
        user_id=user_id,
        role=role_value,
        entity_types=entity_types,
        can_view_notes=can_view_notes,
        can_view_intended_parents=can_view_ips,
        can_view_post_approval=can_view_post_approval,
        limit=limit,
        offset=offset,
    )

    return SearchResponse(
        query=query,
        total=len(results),
        results=results,
    )


def global_search_for_session(
    db: Session,
    request: Request | None,
    session: UserSession,
    *,
    q: str,
    types: str,
    limit: int,
    offset: int,
) -> SearchResponse:
    """Orchestrate a global search for the current session and audit PHI access."""
    from app.services import permission_service, phi_access_service

    entity_types = normalize_entity_types(types)
    effective_permissions = permission_service.get_effective_permissions(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        role=session.role.value,
    )

    results = global_search(
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

    phi_access_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="global_search",
        target_id=None,
        request=request,
        query=q,
        details={
            "query_length": len(q),
            "types": entity_types,
            "limit": limit,
            "offset": offset,
            "result_count": results["total"],
        },
    )
    return results


def _global_search_unified(
    db: Session,
    org_id: UUID,
    query: str,
    user_id: UUID,
    role: str,
    entity_types: list[str],
    can_view_notes: bool,
    can_view_intended_parents: bool,
    can_view_post_approval: bool,
    limit: int,
    offset: int,
) -> list[SearchResult]:
    """Run one unified UNION ALL query and paginate globally by relevance."""

    def _run_with_tsquery(tsquery_factory) -> list[SearchResult]:
        surrogate_table = Surrogate.__table__.alias("s")
        stage_table = PipelineStage.__table__.alias("ps")
        notes_table = EntityNote.__table__.alias("en")
        attachments_table = Attachment.__table__.alias("a")
        ip_table = IntendedParent.__table__.alias("ip")

        surrogate_access_filter = _build_surrogate_access_filter(
            role,
            user_id,
            can_view_post_approval,
            surrogate_table,
            stage_table,
        )

        tsquery_simple = tsquery_factory("simple", query)
        tsquery_english = tsquery_factory("english", query)
        normalized_text = normalize_search_text(query)
        normalized_identifier = normalize_identifier(query)
        email_hash, phone_hash = _extract_hashes(query)

        subqueries = []

        if "surrogate" in entity_types:
            surrogate_from = surrogate_table.outerjoin(
                stage_table, surrogate_table.c.stage_id == stage_table.c.id
            )
            hash_filters = []
            if email_hash:
                hash_filters.append(surrogate_table.c.email_hash == email_hash)
            if phone_hash:
                hash_filters.append(surrogate_table.c.phone_hash == phone_hash)
            if hash_filters:
                subqueries.append(
                    select(
                        literal("surrogate").label("entity_type"),
                        surrogate_table.c.id.label("entity_id"),
                        func.coalesce(
                            surrogate_table.c.full_name,
                            func.concat(
                                literal("Surrogate "),
                                func.coalesce(surrogate_table.c.surrogate_number, literal("")),
                            ),
                        ).label("title"),
                        func.coalesce(surrogate_table.c.surrogate_number, literal("")).label(
                            "snippet"
                        ),
                        literal(2.0).label("rank"),
                        surrogate_table.c.id.label("surrogate_id"),
                        surrogate_table.c.full_name.label("surrogate_name"),
                        surrogate_table.c.created_at.label("created_at"),
                    )
                    .select_from(surrogate_from)
                    .where(
                        surrogate_table.c.organization_id == org_id,
                        surrogate_access_filter,
                        or_(*hash_filters),
                    )
                    .order_by(surrogate_table.c.created_at.desc())
                    .limit(limit + offset)
                )

            surrogate_rank = func.ts_rank(surrogate_table.c.search_vector, tsquery_simple).label(
                "rank"
            )
            subqueries.append(
                select(
                    literal("surrogate").label("entity_type"),
                    surrogate_table.c.id.label("entity_id"),
                    func.coalesce(
                        surrogate_table.c.full_name,
                        func.concat(
                            literal("Surrogate "),
                            func.coalesce(surrogate_table.c.surrogate_number, literal("")),
                        ),
                    ).label("title"),
                    func.coalesce(surrogate_table.c.surrogate_number, literal("")).label("snippet"),
                    surrogate_rank,
                    surrogate_table.c.id.label("surrogate_id"),
                    surrogate_table.c.full_name.label("surrogate_name"),
                    surrogate_table.c.created_at.label("created_at"),
                )
                .select_from(surrogate_from)
                .where(
                    surrogate_table.c.organization_id == org_id,
                    surrogate_table.c.search_vector.op("@@")(tsquery_simple),
                    surrogate_access_filter,
                )
                .order_by(surrogate_rank.desc(), surrogate_table.c.created_at.desc())
                .limit(limit + offset)
            )

            fallback_filters = []
            if normalized_text:
                escaped_text = escape_like_string(normalized_text)
                fallback_filters.append(
                    surrogate_table.c.full_name_normalized.ilike(
                        f"%{escaped_text}%",
                        escape="\\",
                    )
                )
            if normalized_identifier:
                escaped_identifier = escape_like_string(normalized_identifier)
                fallback_filters.append(
                    surrogate_table.c.surrogate_number_normalized.ilike(
                        f"%{escaped_identifier}%",
                        escape="\\",
                    )
                )
            if fallback_filters:
                subqueries.append(
                    select(
                        literal("surrogate").label("entity_type"),
                        surrogate_table.c.id.label("entity_id"),
                        func.coalesce(
                            surrogate_table.c.full_name,
                            func.concat(
                                literal("Surrogate "),
                                func.coalesce(surrogate_table.c.surrogate_number, literal("")),
                            ),
                        ).label("title"),
                        func.coalesce(surrogate_table.c.surrogate_number, literal("")).label(
                            "snippet"
                        ),
                        literal(0.5).label("rank"),
                        surrogate_table.c.id.label("surrogate_id"),
                        surrogate_table.c.full_name.label("surrogate_name"),
                        surrogate_table.c.created_at.label("created_at"),
                    )
                    .select_from(surrogate_from)
                    .where(
                        surrogate_table.c.organization_id == org_id,
                        surrogate_access_filter,
                        or_(*fallback_filters),
                    )
                    .order_by(surrogate_table.c.created_at.desc())
                    .limit(limit + offset)
                )

        if "note" in entity_types and can_view_notes:
            note_snippet = func.ts_headline(
                "english",
                func.regexp_replace(
                    func.coalesce(notes_table.c.content, ""),
                    literal("<[^>]+>"),
                    literal(" "),
                    literal("g"),
                ),
                tsquery_english,
                literal("MaxWords=30, MinWords=15, StartSel=<mark>, StopSel=</mark>"),
            ).label("snippet")
            note_rank = func.ts_rank(notes_table.c.search_vector, tsquery_english).label("rank")

            surrogate_note_from = notes_table.join(
                surrogate_table,
                and_(
                    notes_table.c.entity_type == "surrogate",
                    notes_table.c.entity_id == surrogate_table.c.id,
                    surrogate_table.c.organization_id == notes_table.c.organization_id,
                ),
            ).outerjoin(stage_table, surrogate_table.c.stage_id == stage_table.c.id)

            subqueries.append(
                select(
                    literal("note").label("entity_type"),
                    notes_table.c.id.label("entity_id"),
                    func.coalesce(
                        func.concat(literal("Note on "), surrogate_table.c.full_name),
                        literal("Surrogate Note"),
                    ).label("title"),
                    note_snippet,
                    note_rank,
                    surrogate_table.c.id.label("surrogate_id"),
                    surrogate_table.c.full_name.label("surrogate_name"),
                    notes_table.c.created_at.label("created_at"),
                )
                .select_from(surrogate_note_from)
                .where(
                    notes_table.c.organization_id == org_id,
                    notes_table.c.search_vector.op("@@")(tsquery_english),
                    surrogate_access_filter,
                )
                .order_by(note_rank.desc(), notes_table.c.created_at.desc())
                .limit(limit + offset)
            )

            if can_view_intended_parents:
                ip_note_from = notes_table.join(
                    ip_table,
                    and_(
                        notes_table.c.entity_type == "intended_parent",
                        notes_table.c.entity_id == ip_table.c.id,
                        ip_table.c.organization_id == notes_table.c.organization_id,
                    ),
                )
                subqueries.append(
                    select(
                        literal("note").label("entity_type"),
                        notes_table.c.id.label("entity_id"),
                        func.coalesce(
                            func.concat(literal("Note on "), ip_table.c.full_name),
                            literal("Intended Parent Note"),
                        ).label("title"),
                        note_snippet,
                        note_rank,
                        literal(None).label("surrogate_id"),
                        literal(None).label("surrogate_name"),
                        notes_table.c.created_at.label("created_at"),
                    )
                    .select_from(ip_note_from)
                    .where(
                        notes_table.c.organization_id == org_id,
                        notes_table.c.search_vector.op("@@")(tsquery_english),
                    )
                    .order_by(note_rank.desc(), notes_table.c.created_at.desc())
                    .limit(limit + offset)
                )

        if "attachment" in entity_types:
            attachment_rank = func.ts_rank(attachments_table.c.search_vector, tsquery_simple).label(
                "rank"
            )
            surrogate_attachment_from = attachments_table.join(
                surrogate_table,
                and_(
                    attachments_table.c.surrogate_id == surrogate_table.c.id,
                    surrogate_table.c.organization_id == attachments_table.c.organization_id,
                ),
            ).outerjoin(stage_table, surrogate_table.c.stage_id == stage_table.c.id)
            subqueries.append(
                select(
                    literal("attachment").label("entity_type"),
                    attachments_table.c.id.label("entity_id"),
                    func.coalesce(attachments_table.c.filename, literal("Attachment")).label(
                        "title"
                    ),
                    literal("").label("snippet"),
                    attachment_rank,
                    attachments_table.c.surrogate_id.label("surrogate_id"),
                    surrogate_table.c.full_name.label("surrogate_name"),
                    attachments_table.c.created_at.label("created_at"),
                )
                .select_from(surrogate_attachment_from)
                .where(
                    attachments_table.c.organization_id == org_id,
                    attachments_table.c.surrogate_id.is_not(None),
                    attachments_table.c.deleted_at.is_(None),
                    attachments_table.c.quarantined.is_(False),
                    attachments_table.c.search_vector.op("@@")(tsquery_simple),
                    surrogate_access_filter,
                )
                .order_by(attachment_rank.desc(), attachments_table.c.created_at.desc())
                .limit(limit + offset)
            )

            if can_view_intended_parents:
                ip_attachment_from = attachments_table.join(
                    ip_table,
                    and_(
                        attachments_table.c.intended_parent_id == ip_table.c.id,
                        ip_table.c.organization_id == attachments_table.c.organization_id,
                    ),
                )
                subqueries.append(
                    select(
                        literal("attachment").label("entity_type"),
                        attachments_table.c.id.label("entity_id"),
                        func.coalesce(attachments_table.c.filename, literal("Attachment")).label(
                            "title"
                        ),
                        literal("").label("snippet"),
                        attachment_rank,
                        literal(None).label("surrogate_id"),
                        literal(None).label("surrogate_name"),
                        attachments_table.c.created_at.label("created_at"),
                    )
                    .select_from(ip_attachment_from)
                    .where(
                        attachments_table.c.organization_id == org_id,
                        attachments_table.c.intended_parent_id.is_not(None),
                        attachments_table.c.surrogate_id.is_(None),
                        attachments_table.c.deleted_at.is_(None),
                        attachments_table.c.quarantined.is_(False),
                        attachments_table.c.search_vector.op("@@")(tsquery_simple),
                    )
                    .order_by(attachment_rank.desc(), attachments_table.c.created_at.desc())
                    .limit(limit + offset)
                )

        if "intended_parent" in entity_types and can_view_intended_parents:
            hash_filters = []
            if email_hash:
                hash_filters.append(ip_table.c.email_hash == email_hash)
            if phone_hash:
                hash_filters.append(ip_table.c.phone_hash == phone_hash)

            if hash_filters:
                subqueries.append(
                    select(
                        literal("intended_parent").label("entity_type"),
                        ip_table.c.id.label("entity_id"),
                        func.coalesce(
                            ip_table.c.full_name,
                            func.concat(
                                literal("Intended Parent "),
                                func.coalesce(ip_table.c.intended_parent_number, literal("")),
                            ),
                        ).label("title"),
                        func.coalesce(ip_table.c.intended_parent_number, literal("")).label(
                            "snippet"
                        ),
                        literal(2.0).label("rank"),
                        literal(None).label("surrogate_id"),
                        literal(None).label("surrogate_name"),
                        ip_table.c.created_at.label("created_at"),
                    )
                    .where(ip_table.c.organization_id == org_id, or_(*hash_filters))
                    .order_by(ip_table.c.created_at.desc())
                    .limit(limit + offset)
                )

            ip_rank = func.ts_rank(ip_table.c.search_vector, tsquery_simple).label("rank")
            subqueries.append(
                select(
                    literal("intended_parent").label("entity_type"),
                    ip_table.c.id.label("entity_id"),
                    func.coalesce(
                        ip_table.c.full_name,
                        func.concat(
                            literal("Intended Parent "),
                            func.coalesce(ip_table.c.intended_parent_number, literal("")),
                        ),
                    ).label("title"),
                    func.coalesce(ip_table.c.intended_parent_number, literal("")).label("snippet"),
                    ip_rank,
                    literal(None).label("surrogate_id"),
                    literal(None).label("surrogate_name"),
                    ip_table.c.created_at.label("created_at"),
                )
                .where(
                    ip_table.c.organization_id == org_id,
                    ip_table.c.search_vector.op("@@")(tsquery_simple),
                )
                .order_by(ip_rank.desc(), ip_table.c.created_at.desc())
                .limit(limit + offset)
            )

            ip_fallback_filters = []
            if normalized_text:
                escaped_text = escape_like_string(normalized_text)
                ip_fallback_filters.append(
                    ip_table.c.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\")
                )
            if normalized_identifier:
                escaped_identifier = escape_like_string(normalized_identifier)
                ip_fallback_filters.append(
                    ip_table.c.intended_parent_number_normalized.ilike(
                        f"%{escaped_identifier}%",
                        escape="\\",
                    )
                )
            if ip_fallback_filters:
                subqueries.append(
                    select(
                        literal("intended_parent").label("entity_type"),
                        ip_table.c.id.label("entity_id"),
                        func.coalesce(
                            ip_table.c.full_name,
                            func.concat(
                                literal("Intended Parent "),
                                func.coalesce(ip_table.c.intended_parent_number, literal("")),
                            ),
                        ).label("title"),
                        func.coalesce(ip_table.c.intended_parent_number, literal("")).label(
                            "snippet"
                        ),
                        literal(0.5).label("rank"),
                        literal(None).label("surrogate_id"),
                        literal(None).label("surrogate_name"),
                        ip_table.c.created_at.label("created_at"),
                    )
                    .where(
                        ip_table.c.organization_id == org_id,
                        or_(*ip_fallback_filters),
                    )
                    .order_by(ip_table.c.created_at.desc())
                    .limit(limit + offset)
                )

        if not subqueries:
            return []

        unioned = union_all(*subqueries).subquery("search_union")
        deduped = select(
            unioned.c.entity_type,
            unioned.c.entity_id,
            unioned.c.title,
            unioned.c.snippet,
            unioned.c.rank,
            unioned.c.surrogate_id,
            unioned.c.surrogate_name,
            unioned.c.created_at,
            func.row_number()
            .over(
                partition_by=(unioned.c.entity_type, unioned.c.entity_id),
                order_by=(unioned.c.rank.desc(), unioned.c.created_at.desc()),
            )
            .label("row_num"),
        ).subquery("search_ranked")
        stmt = (
            select(
                deduped.c.entity_type,
                deduped.c.entity_id,
                deduped.c.title,
                deduped.c.snippet,
                deduped.c.rank,
                deduped.c.surrogate_id,
                deduped.c.surrogate_name,
            )
            .where(deduped.c.row_num == 1)
            .order_by(deduped.c.rank.desc(), deduped.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        rows = db.execute(stmt).fetchall()
        results: list[SearchResult] = []
        for row in rows:
            results.append(
                SearchResult(
                    entity_type=row.entity_type,
                    entity_id=str(row.entity_id),
                    title=row.title or "",
                    snippet=row.snippet or "",
                    rank=float(row.rank),
                    surrogate_id=str(row.surrogate_id) if row.surrogate_id else None,
                    surrogate_name=row.surrogate_name,
                )
            )
        return results

    try:
        return _run_with_tsquery(
            lambda dictionary, text: func.websearch_to_tsquery(dictionary, text)
        )
    except SQLAlchemyError as exc:
        logger.warning("Unified search failed, retrying with plainto_tsquery: %s", exc)
        try:
            return _run_with_tsquery(
                lambda dictionary, text: func.plainto_tsquery(dictionary, text)
            )
        except SQLAlchemyError as fallback_exc:
            logger.warning("Unified search fallback failed: %s", fallback_exc)
            return []


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
