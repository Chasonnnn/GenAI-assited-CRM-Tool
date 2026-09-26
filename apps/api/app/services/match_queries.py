"""Match read side: loaders, lists, stats, visibility, and response assembly."""

from uuid import UUID

from fastapi import Request
from sqlalchemy import and_, asc, desc, false, func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.enums import MatchStatus
from app.db.models import Donor, IntendedParent, Match, Surrogate
from app.schemas.auth import UserSession
from app.schemas.matches import MatchListItem, MatchListResponse, MatchRead
from app.utils.normalization import escape_like_string, normalize_identifier, normalize_search_text
from app.utils.pagination import paginate_query_by_offset

OPEN_STATUSES = tuple(
    status.value
    for status in MatchStatus
    if status not in {MatchStatus.REJECTED, MatchStatus.CANCELLED, MatchStatus.COMPLETED}
)
COMMITTED_STATUSES = (MatchStatus.ACCEPTED.value, MatchStatus.CANCEL_PENDING.value)
PENDING_STATUSES = (MatchStatus.PROPOSED.value, MatchStatus.REVIEWING.value)


# =============================================================================
# Loaders
# =============================================================================


def get_match(db: Session, match_id: UUID, org_id: UUID) -> Match | None:
    """Get match by ID (org-scoped)."""
    return db.query(Match).filter(Match.id == match_id, Match.organization_id == org_id).first()


def get_surrogate_with_stage(
    db: Session, surrogate_id: UUID | None, org_id: UUID | None = None
) -> Surrogate | None:
    """Get surrogate with stage loaded, optionally org-scoped."""
    filters = [Surrogate.id == surrogate_id]
    if org_id:
        filters.append(Surrogate.organization_id == org_id)
    return db.query(Surrogate).options(joinedload(Surrogate.stage)).filter(*filters).first()


def get_intended_parent(
    db: Session, intended_parent_id: UUID, org_id: UUID | None = None
) -> IntendedParent | None:
    """Get intended parent, optionally org-scoped."""
    filters = [IntendedParent.id == intended_parent_id]
    if org_id:
        filters.append(IntendedParent.organization_id == org_id)
    return (
        db.query(IntendedParent).options(joinedload(IntendedParent.stage)).filter(*filters).first()
    )


def get_donor(db: Session, donor_id: UUID | None, org_id: UUID) -> Donor | None:
    return (
        db.query(Donor)
        .options(joinedload(Donor.stage))
        .filter(Donor.id == donor_id, Donor.organization_id == org_id)
        .first()
    )


def get_existing_match(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID | None,
    intended_parent_id: UUID,
    donor_id: UUID | None = None,
) -> Match | None:
    """Find an open match for the same participants in org."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.donor_id == donor_id,
            Match.intended_parent_id == intended_parent_id,
            Match.status.in_(OPEN_STATUSES),
        )
        .first()
    )


def has_any_match_for_pair(
    db: Session, org_id: UUID, surrogate_id: UUID | None, intended_parent_id: UUID
) -> bool:
    return (
        db.query(Match.id)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.intended_parent_id == intended_parent_id,
        )
        .first()
        is not None
    )


def get_accepted_match_for_surrogate(
    db: Session, org_id: UUID, surrogate_id: UUID | None
) -> Match | None:
    """Get accepted match for a surrogate (org-scoped)."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.surrogate_id == surrogate_id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    )


def get_accepted_match_for_intended_parent(
    db: Session, org_id: UUID, intended_parent_id: UUID
) -> Match | None:
    """Get accepted match for an intended parent (org-scoped)."""
    return (
        db.query(Match)
        .filter(
            Match.organization_id == org_id,
            Match.intended_parent_id == intended_parent_id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
    )


def has_other_committed_match_for_intended_parent(db: Session, match: Match) -> bool:
    return (
        db.query(Match.id)
        .filter(
            Match.organization_id == match.organization_id,
            Match.intended_parent_id == match.intended_parent_id,
            Match.id != match.id,
            Match.status.in_(COMMITTED_STATUSES),
        )
        .first()
        is not None
    )


def get_surrogates_with_stage_by_ids(
    db: Session, org_id: UUID, surrogate_ids: set[UUID]
) -> dict[UUID, Surrogate]:
    """Batch load surrogates with stages for match list."""
    if not surrogate_ids:
        return {}
    surrogates = (
        db.query(Surrogate)
        .options(joinedload(Surrogate.stage))
        .filter(Surrogate.organization_id == org_id, Surrogate.id.in_(surrogate_ids))
        .all()
    )
    return {surrogate.id: surrogate for surrogate in surrogates}


def get_intended_parents_by_ids(
    db: Session, org_id: UUID, intended_parent_ids: set[UUID]
) -> dict[UUID, IntendedParent]:
    """Batch load intended parents for match list."""
    if not intended_parent_ids:
        return {}
    ips = (
        db.query(IntendedParent)
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.id.in_(intended_parent_ids),
        )
        .all()
    )
    return {ip.id: ip for ip in ips}


def get_donors_by_ids(db: Session, org_id: UUID, donor_ids: set[UUID]) -> dict[UUID, Donor]:
    if not donor_ids:
        return {}
    return {
        donor.id: donor
        for donor in db.query(Donor)
        .options(joinedload(Donor.stage))
        .filter(Donor.organization_id == org_id, Donor.id.in_(donor_ids))
        .all()
    }


# =============================================================================
# Visibility, lists, and stats
# =============================================================================


def match_visibility_filter(db: Session, session: UserSession):
    """Filter authorized participants before case pagination and summary counts."""
    from app.services import permission_policy_service, record_scope_service

    if permission_policy_service.is_enabled(db, session.org_id):
        return record_scope_service.build_linked_visibility_filter(db, session, Match)

    from app.core.policies import POLICIES
    from app.core.surrogate_access import build_surrogate_visibility_filter
    from app.services import permission_service

    def allowed(resource):
        return permission_service.check_permission(
            db,
            session.org_id,
            session.user_id,
            session.role.value,
            POLICIES[resource].default.value,
        )

    if not allowed("intended_parents"):
        return false()
    clauses = []
    if allowed("donors"):
        clauses.append(
            and_(
                Match.donor_id.isnot(None),
                Match.donor_id.in_(
                    db.query(Donor.id).filter(Donor.organization_id == session.org_id)
                ),
            )
        )
    if allowed("surrogates"):
        visible = db.query(Surrogate.id).filter(
            Surrogate.organization_id == session.org_id,
            build_surrogate_visibility_filter(db, session.org_id, session.role, session.user_id),
        )
        clauses.append(Match.surrogate_id.in_(visible))
    return and_(
        Match.intended_parent_id.in_(
            db.query(IntendedParent.id).filter(IntendedParent.organization_id == session.org_id)
        ),
        or_(*clauses) if clauses else false(),
    )


def list_matches(
    db: Session,
    org_id: UUID,
    status_filter: str | None = None,
    donor_id: UUID | None = None,
    match_kind: str | None = None,
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
    session: UserSession | None = None,
) -> tuple[list[Match], int]:
    """List matches with filters and pagination."""
    query = db.query(Match).filter(Match.organization_id == org_id)
    if session is not None:
        query = query.filter(match_visibility_filter(db, session))

    if donor_id:
        query = query.filter(Match.donor_id == donor_id)
    if match_kind:
        query = query.filter(Match.match_kind == match_kind)
    if status_filter:
        query = query.filter(Match.status == status_filter)
    if surrogate_id:
        query = query.filter(Match.surrogate_id == surrogate_id)
    if intended_parent_id:
        query = query.filter(Match.intended_parent_id == intended_parent_id)

    if q:
        normalized_text = normalize_search_text(q)
        normalized_identifier = normalize_identifier(q) or q
        escaped_identifier = escape_like_string(normalized_identifier)
        escaped_text = escape_like_string(normalized_text or normalized_identifier)
        query = (
            query.join(Surrogate, Match.surrogate_id == Surrogate.id, isouter=True)
            .join(Donor, Match.donor_id == Donor.id, isouter=True)
            .join(IntendedParent, Match.intended_parent_id == IntendedParent.id, isouter=True)
            .filter(
                or_(
                    Donor.full_name.ilike(f"%{escaped_text}%", escape="\\"),
                    Donor.donor_number.ilike(f"%{escaped_identifier}%", escape="\\"),
                    Match.match_number.ilike(f"%{escaped_identifier}%", escape="\\"),
                    Surrogate.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\"),
                    Surrogate.surrogate_number_normalized.ilike(
                        f"%{escaped_identifier}%", escape="\\"
                    ),
                    IntendedParent.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\"),
                    IntendedParent.intended_parent_number_normalized.ilike(
                        f"%{escaped_identifier}%", escape="\\"
                    ),
                )
            )
        )

    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "match_number": Match.match_number,
        "status": Match.status,
        "proposed_at": Match.proposed_at,
        "created_at": Match.created_at,
    }
    if sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        query = query.order_by(Match.proposed_at.desc())

    offset = (page - 1) * per_page
    return paginate_query_by_offset(query, offset=offset, limit=per_page)


def get_match_stats(
    db: Session, org_id: UUID, session: UserSession | None = None
) -> tuple[int, dict[str, int]]:
    """Return total matches and counts by status."""
    counts = {status.value: 0 for status in MatchStatus}
    rows = (
        db.query(Match.status, func.count(Match.id))
        .filter(
            Match.organization_id == org_id,
            match_visibility_filter(db, session) if session else True,
        )
        .group_by(Match.status)
        .all()
    )
    for status, count in rows:
        status_key = status.value if hasattr(status, "value") else status
        counts[status_key] = count
    return sum(counts.values()), counts


# =============================================================================
# Response assembly
# =============================================================================


def to_read(db: Session, match: Match, org_id: UUID | None = None) -> MatchRead:
    """Convert a match to MatchRead with org-scoped party lookups."""
    surrogate = get_surrogate_with_stage(db, match.surrogate_id, org_id)
    ip = get_intended_parent(db, match.intended_parent_id, org_id)
    donor = (
        get_donor(db, match.donor_id, org_id or match.organization_id) if match.donor_id else None
    )
    return MatchRead(
        id=str(match.id),
        match_number=match.match_number,
        surrogate_id=str(match.surrogate_id) if match.surrogate_id else None,
        donor_id=str(match.donor_id) if match.donor_id else None,
        donor_name=donor.full_name if donor else None,
        donor_number=donor.donor_number if donor else None,
        donor_stage_label=donor.stage.label if donor and donor.stage else None,
        match_kind=match.match_kind,
        closed_at=match.closed_at.isoformat() if match.closed_at else None,
        closure_reason=match.closure_reason,
        outcome=match.outcome,
        intended_parent_id=str(match.intended_parent_id),
        status=match.status,
        proposed_by_user_id=str(match.proposed_by_user_id) if match.proposed_by_user_id else None,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else None,
        reviewed_by_user_id=str(match.reviewed_by_user_id) if match.reviewed_by_user_id else None,
        reviewed_at=match.reviewed_at.isoformat() if match.reviewed_at else None,
        notes=match.notes,
        rejection_reason=match.rejection_reason,
        created_at=match.created_at.isoformat(),
        updated_at=match.updated_at.isoformat(),
        surrogate_number=surrogate.surrogate_number if surrogate else None,
        surrogate_name=surrogate.full_name if surrogate else None,
        ip_name=ip.full_name if ip else None,
        ip_number=ip.intended_parent_number if ip else None,
        surrogate_stage_id=str(surrogate.stage.id) if surrogate and surrogate.stage else None,
        surrogate_stage_slug=surrogate.stage.slug if surrogate and surrogate.stage else None,
        surrogate_stage_label=surrogate.stage.label if surrogate and surrogate.stage else None,
    )


def to_list_item(
    match: Match,
    surrogate: Surrogate | None,
    ip: IntendedParent | None,
    donor: Donor | None = None,
) -> MatchListItem:
    """Convert a match and its preloaded parties to a list item."""
    return MatchListItem(
        id=str(match.id),
        match_number=match.match_number,
        surrogate_id=str(match.surrogate_id) if match.surrogate_id else None,
        donor_id=str(match.donor_id) if match.donor_id else None,
        donor_name=donor.full_name if donor else None,
        donor_number=donor.donor_number if donor else None,
        donor_stage_label=donor.stage.label if donor and donor.stage else None,
        match_kind=match.match_kind,
        closed_at=match.closed_at.isoformat() if match.closed_at else None,
        closure_reason=match.closure_reason,
        outcome=match.outcome,
        surrogate_number=surrogate.surrogate_number if surrogate else None,
        surrogate_name=surrogate.full_name if surrogate else None,
        intended_parent_id=str(match.intended_parent_id),
        ip_name=ip.full_name if ip else None,
        ip_number=ip.intended_parent_number if ip else None,
        status=match.status,
        proposed_at=match.proposed_at.isoformat() if match.proposed_at else "",
        surrogate_stage_id=str(surrogate.stage.id) if surrogate and surrogate.stage else None,
        surrogate_stage_slug=surrogate.stage.slug if surrogate and surrogate.stage else None,
        surrogate_stage_label=surrogate.stage.label if surrogate and surrogate.stage else None,
    )


def list_for_session(
    db: Session,
    session: UserSession,
    request: Request,
    *,
    status_filter: str | None,
    surrogate_id: UUID | None,
    intended_parent_id: UUID | None,
    donor_id: UUID | None,
    match_kind: str | None,
    q: str | None,
    page: int,
    per_page: int,
    sort_by: str | None,
    sort_order: str,
) -> MatchListResponse:
    """Visible matches for the member, with the list PHI access recorded."""
    from app.services import audit_service

    matches, total = list_matches(
        db=db,
        org_id=session.org_id,
        status_filter=status_filter,
        donor_id=donor_id,
        match_kind=match_kind,
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        q=q,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
        session=session,
    )
    surrogates = get_surrogates_with_stage_by_ids(
        db, session.org_id, {m.surrogate_id for m in matches}
    )
    ips = get_intended_parents_by_ids(db, session.org_id, {m.intended_parent_id for m in matches})
    donors = get_donors_by_ids(db, session.org_id, {m.donor_id for m in matches if m.donor_id})
    items = [
        to_list_item(
            m,
            surrogates.get(m.surrogate_id),
            ips.get(m.intended_parent_id),
            donors.get(m.donor_id),
        )
        for m in matches
    ]

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="match_list",
        target_id=None,
        request=request,
        details={
            "count": len(matches),
            "page": page,
            "per_page": per_page,
            "status": status_filter,
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "intended_parent_id": str(intended_parent_id) if intended_parent_id else None,
            "q_type": "text" if q else None,
        },
    )
    db.commit()
    return MatchListResponse(items=items, total=total, page=page, per_page=per_page)


def get_detail(db: Session, session: UserSession, match_id: UUID) -> MatchRead:
    """One match for the member, with the PHI access recorded. Viewing never changes status."""
    from app.services import audit_service, match_access

    match = match_access.load(db, session, match_id, "view", allow_archived=True)
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="match",
        target_id=match.id,
        details={
            "surrogate_id": str(match.surrogate_id),
            "intended_parent_id": str(match.intended_parent_id),
        },
    )
    db.commit()
    return to_read(db, match, session.org_id)
