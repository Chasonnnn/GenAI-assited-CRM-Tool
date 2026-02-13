"""Developer-only surrogate mass edit helpers.

Provides:
- Previewing a filter selection (count + sample)
- Applying a bulk stage change with strict safety checks

Notes:
- Mass edit stage changes are always effective now (no backdating).
- Activity/audit trail is recorded via SurrogateStatusHistory (canonical).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import Float, and_, case, cast, func, or_
from sqlalchemy.orm import Session, load_only

from app.core.encryption import hash_email, hash_phone
from app.db.enums import OwnerType, Role
from app.db.models import Surrogate
from app.schemas.surrogate_mass_edit import (
    SurrogateMassEditOptionsResponse,
    SurrogateMassEditStageApplyResponse,
    SurrogateMassEditStageFailure,
    SurrogateMassEditStageFilters,
    SurrogateMassEditStagePreviewItem,
    SurrogateMassEditStagePreviewResponse,
)
from app.utils.normalization import (
    MASS_EDIT_RACE_FILTER_KEYS,
    RACE_KEY_ALIASES,
    escape_like_string,
    normalize_identifier,
    normalize_phone,
    normalize_search_text,
)


MAX_APPLY = 2000
MAX_DERIVED_SCAN = 5000  # Age requires decrypting DOB; force narrowing to avoid scanning huge sets
MAX_PREVIEW_LIMIT = 100


def _compute_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _created_from_dt(d: date) -> datetime:
    return datetime.combine(d, time(0, 0, 0))


def _created_to_exclusive_dt(d: date) -> datetime:
    # Exclusive end boundary: next-day midnight
    return datetime.combine(d, time(0, 0, 0)) + timedelta(days=1)


def _build_base_query(db: Session, org_id: UUID, filters: SurrogateMassEditStageFilters):
    """Build a SQLAlchemy query for Surrogate rows with DB-filterable criteria applied."""
    query = db.query(Surrogate).filter(Surrogate.organization_id == org_id)

    # Always exclude archived for mass stage changes (status change endpoint forbids it).
    query = query.filter(Surrogate.is_archived.is_(False))

    if filters.stage_ids:
        query = query.filter(Surrogate.stage_id.in_(filters.stage_ids))

    if filters.source:
        query = query.filter(Surrogate.source == filters.source.value)

    if filters.queue_id:
        query = query.filter(
            Surrogate.owner_type == OwnerType.QUEUE.value,
            Surrogate.owner_id == filters.queue_id,
        )

    if filters.created_from:
        query = query.filter(Surrogate.created_at >= _created_from_dt(filters.created_from))

    if filters.created_to:
        query = query.filter(Surrogate.created_at < _created_to_exclusive_dt(filters.created_to))

    if filters.states:
        query = query.filter(Surrogate.state.in_(filters.states))

    if filters.races:
        race_key = _race_key_expr()
        query = query.filter(race_key.in_(filters.races))

    if filters.is_priority is not None:
        query = query.filter(Surrogate.is_priority.is_(bool(filters.is_priority)))

    # Checklist booleans
    for field_name in (
        "is_age_eligible",
        "is_citizen_or_pr",
        "has_child",
        "is_non_smoker",
        "has_surrogate_experience",
    ):
        value = getattr(filters, field_name)
        if value is not None:
            query = query.filter(getattr(Surrogate, field_name).is_(bool(value)))

    # Numeric checklist ranges
    if filters.num_deliveries_min is not None:
        query = query.filter(Surrogate.num_deliveries >= filters.num_deliveries_min)
    if filters.num_deliveries_max is not None:
        query = query.filter(Surrogate.num_deliveries <= filters.num_deliveries_max)
    if filters.num_csections_min is not None:
        query = query.filter(Surrogate.num_csections >= filters.num_csections_min)
    if filters.num_csections_max is not None:
        query = query.filter(Surrogate.num_csections <= filters.num_csections_max)

    # Search (name, email, phone, surrogate_number)
    if filters.q:
        q = filters.q
        normalized_text = normalize_search_text(q)
        normalized_identifier = normalize_identifier(q)
        clauses = []

        if normalized_text:
            escaped_text = escape_like_string(normalized_text)
            clauses.append(Surrogate.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\"))
        if normalized_identifier:
            escaped_identifier = escape_like_string(normalized_identifier)
            clauses.append(
                Surrogate.surrogate_number_normalized.ilike(f"%{escaped_identifier}%", escape="\\")
            )
        if "@" in q:
            try:
                clauses.append(Surrogate.email_hash == hash_email(q))
            except Exception:
                pass
        try:
            normalized_phone = normalize_phone(q)
            clauses.append(Surrogate.phone_hash == hash_phone(normalized_phone))
        except Exception:
            pass

        if clauses:
            query = query.filter(or_(*clauses))

    # BMI range (DB-filterable)
    if filters.bmi_min is not None or filters.bmi_max is not None:
        height_inches = cast(Surrogate.height_ft, Float) * 12.0
        bmi_expr = (cast(Surrogate.weight_lb, Float) / (height_inches * height_inches)) * 703.0
        query = query.filter(
            and_(
                Surrogate.height_ft.is_not(None),
                Surrogate.weight_lb.is_not(None),
                height_inches > 0,
            )
        )
        if filters.bmi_min is not None:
            query = query.filter(bmi_expr >= float(filters.bmi_min))
        if filters.bmi_max is not None:
            query = query.filter(bmi_expr <= float(filters.bmi_max))

    return query


def _race_key_expr():
    raw_key = func.btrim(
        func.regexp_replace(
            func.lower(func.trim(Surrogate.race)),
            r"[^a-z0-9]+",
            "_",
            "g",
        ),
        "_",
    )

    alias_whens = [(raw_key == alias, canonical) for alias, canonical in RACE_KEY_ALIASES.items()]
    return case(*alias_whens, else_=raw_key)


def _apply_age_filter_in_memory(
    surrogates: list[Surrogate],
    *,
    age_min: int | None,
    age_max: int | None,
) -> list[Surrogate]:
    if age_min is None and age_max is None:
        return surrogates

    filtered: list[Surrogate] = []
    for s in surrogates:
        age = _compute_age(s.date_of_birth)
        if age is None:
            continue
        if age_min is not None and age < age_min:
            continue
        if age_max is not None and age > age_max:
            continue
        filtered.append(s)
    return filtered


def preview_stage_change(
    db: Session,
    org_id: UUID,
    filters: SurrogateMassEditStageFilters,
    *,
    limit: int = 25,
) -> SurrogateMassEditStagePreviewResponse:
    limit = max(1, min(int(limit), MAX_PREVIEW_LIMIT))

    query = _build_base_query(db, org_id, filters)
    needs_age_scan = filters.age_min is not None or filters.age_max is not None

    if needs_age_scan:
        base_count = query.count()
        if base_count > MAX_DERIVED_SCAN:
            raise ValueError(
                f"Too many candidates ({base_count}) to evaluate age filter. Add more filters."
            )

        candidates = (
            query.options(
                load_only(
                    Surrogate.id,
                    Surrogate.surrogate_number,
                    Surrogate.full_name,
                    Surrogate.state,
                    Surrogate.stage_id,
                    Surrogate.status_label,
                    Surrogate.created_at,
                    Surrogate.date_of_birth,
                )
            )
            .order_by(Surrogate.created_at.desc())
            .all()
        )
        matched = _apply_age_filter_in_memory(
            candidates, age_min=filters.age_min, age_max=filters.age_max
        )
        total = len(matched)
        sample = matched[:limit]
    else:
        total = query.count()
        sample = (
            query.options(
                load_only(
                    Surrogate.id,
                    Surrogate.surrogate_number,
                    Surrogate.full_name,
                    Surrogate.state,
                    Surrogate.stage_id,
                    Surrogate.status_label,
                    Surrogate.created_at,
                    Surrogate.date_of_birth,
                )
            )
            .order_by(Surrogate.created_at.desc())
            .limit(limit)
            .all()
        )

    items = [
        SurrogateMassEditStagePreviewItem(
            id=s.id,
            surrogate_number=s.surrogate_number,
            full_name=s.full_name,
            state=s.state,
            stage_id=s.stage_id,
            status_label=s.status_label,
            created_at=s.created_at,
            age=_compute_age(s.date_of_birth),
        )
        for s in sample
    ]

    return SurrogateMassEditStagePreviewResponse(
        total=total,
        over_limit=total > MAX_APPLY,
        max_apply=MAX_APPLY,
        items=items,
    )


def apply_stage_change(
    db: Session,
    org_id: UUID,
    *,
    stage_id: UUID,
    filters: SurrogateMassEditStageFilters,
    expected_total: int,
    user_id: UUID,
    user_role: Role,
    trigger_workflows: bool,
    reason: str | None,
) -> SurrogateMassEditStageApplyResponse:
    from app.services import dashboard_events, surrogate_service, surrogate_status_service

    query = _build_base_query(db, org_id, filters)
    needs_age_scan = filters.age_min is not None or filters.age_max is not None

    if needs_age_scan:
        base_count = query.count()
        if base_count > MAX_DERIVED_SCAN:
            raise ValueError(
                f"Too many candidates ({base_count}) to evaluate age filter. Add more filters."
            )
        candidates = (
            query.options(load_only(Surrogate.id, Surrogate.date_of_birth))
            .order_by(Surrogate.created_at.desc())
            .all()
        )
        matched_surrogates = _apply_age_filter_in_memory(
            candidates, age_min=filters.age_min, age_max=filters.age_max
        )
        matching_ids = [s.id for s in matched_surrogates]
        matched_total = len(matching_ids)
    else:
        matched_total = query.count()

    if matched_total != expected_total:
        raise ValueError(
            f"Selection changed (expected {expected_total}, now {matched_total}). Re-run preview."
        )

    if matched_total > MAX_APPLY:
        raise ValueError(f"Too many surrogates matched ({matched_total}). Narrow filters.")

    if not needs_age_scan:
        matching_ids = [row[0] for row in query.with_entities(Surrogate.id).all()]

    applied = 0
    pending_approval = 0
    failed: list[SurrogateMassEditStageFailure] = []

    # Apply one-by-one to preserve canonical status history and validation logic.
    for sid in matching_ids:
        surrogate = surrogate_service.get_surrogate(db, org_id, sid)
        if not surrogate:
            failed.append(
                SurrogateMassEditStageFailure(surrogate_id=sid, reason="Surrogate not found")
            )
            continue
        if surrogate.is_archived:
            failed.append(
                SurrogateMassEditStageFailure(
                    surrogate_id=sid, reason="Cannot change status of archived surrogate"
                )
            )
            continue

        try:
            result = surrogate_status_service.change_status(
                db=db,
                surrogate=surrogate,
                new_stage_id=stage_id,
                user_id=user_id,
                user_role=user_role,
                reason=reason,
                effective_at=None,  # Mass edits are always effective now
                trigger_workflows=trigger_workflows,
                emit_events=False,  # Push dashboard stats once at the end
            )
            if result["status"] == "applied":
                applied += 1
            elif result["status"] == "pending_approval":
                pending_approval += 1
        except Exception as exc:
            failed.append(SurrogateMassEditStageFailure(surrogate_id=sid, reason=str(exc)))

    # Best-effort dashboard refresh
    try:
        dashboard_events.push_dashboard_stats(db, org_id)
    except Exception:
        pass

    return SurrogateMassEditStageApplyResponse(
        matched=matched_total,
        applied=applied,
        pending_approval=pending_approval,
        failed=failed,
    )


def get_filter_options(db: Session, org_id: UUID) -> SurrogateMassEditOptionsResponse:
    """
    Return distinct option values for filterable fields.

    This is dev-only and intended to power UI selects (not user-entered free text).
    """
    return SurrogateMassEditOptionsResponse(races=list(MASS_EDIT_RACE_FILTER_KEYS))
