"""Intended Parent service - business logic for IP CRUD and status management."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import TypedDict
from uuid import UUID
import logging

from fastapi import Request
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.core.stage_definitions import INTENDED_PARENT_PIPELINE_ENTITY
from app.core.encryption import hash_email, hash_phone
from app.db.enums import IntendedParentStatus, Role
from app.db.models import IntendedParent, IntendedParentStatusHistory
from app.schemas.auth import UserSession
from app.utils.normalization import (
    escape_like_string,
    extract_email_domain,
    extract_phone_last4,
    normalize_email,
    normalize_identifier,
    normalize_phone,
    normalize_search_text,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Query Helpers
# =============================================================================


def _parse_created_before_filter(value: str) -> tuple[datetime, bool]:
    """Parse created_before value.

    Returns:
        (parsed_datetime, is_date_only)
    """
    normalized = value.strip()
    if "T" not in normalized:
        parsed_date = date.fromisoformat(normalized)
        return datetime.combine(parsed_date + timedelta(days=1), time(0, 0, 0)), True
    parsed_datetime = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return parsed_datetime, False


def _build_intended_parent_query(
    db: Session,
    org_id: UUID,
    *,
    status: list[str] | None = None,
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    include_archived: bool = False,
    created_after: str | None = None,
    created_before: str | None = None,
):
    query = (
        db.query(IntendedParent)
        .options(selectinload(IntendedParent.stage))
        .filter(IntendedParent.organization_id == org_id)
    )

    # Archive filter
    if not include_archived:
        query = query.filter(IntendedParent.is_archived.is_(False))

    # Status filter (multi-select)
    if status:
        query = query.filter(IntendedParent.status.in_(status))

    # State filter
    if state:
        query = query.filter(IntendedParent.state == state)

    # Budget range filter
    if budget_min is not None:
        query = query.filter(IntendedParent.budget >= budget_min)
    if budget_max is not None:
        query = query.filter(IntendedParent.budget <= budget_max)

    # Search filter (name, number, email, phone)
    if q:
        normalized_text = normalize_search_text(q)
        normalized_identifier = normalize_identifier(q)
        filters = []
        if normalized_text:
            escaped_text = escape_like_string(normalized_text)
            filters.append(
                IntendedParent.full_name_normalized.ilike(f"%{escaped_text}%", escape="\\")
            )
        if normalized_identifier:
            escaped_identifier = escape_like_string(normalized_identifier)
            filters.append(
                IntendedParent.intended_parent_number_normalized.ilike(
                    f"%{escaped_identifier}%", escape="\\"
                )
            )
        if "@" in q:
            try:
                filters.append(IntendedParent.email_hash == hash_email(q))
            except Exception as exc:
                logger.debug("ip_search_email_hash_failed", exc_info=exc)
        try:
            normalized_phone = normalize_phone(q)
            filters.append(IntendedParent.phone_hash == hash_phone(normalized_phone))
        except Exception as exc:
            logger.debug("ip_search_phone_hash_failed", exc_info=exc)
        if filters:
            query = query.filter(or_(*filters))

    # Owner filter
    if owner_id:
        query = query.filter(IntendedParent.owner_id == owner_id)

    # Created date range filter (ISO format)
    if created_after:
        try:
            after_date = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            query = query.filter(IntendedParent.created_at >= after_date)
        except (ValueError, AttributeError):
            logger.debug("ip_filter_invalid_created_after")
    if created_before:
        try:
            before_date, is_date_only = _parse_created_before_filter(created_before)
            if is_date_only:
                query = query.filter(IntendedParent.created_at < before_date)
            else:
                query = query.filter(IntendedParent.created_at <= before_date)
        except (ValueError, AttributeError):
            logger.debug("ip_filter_invalid_created_before")

    return query


# =============================================================================
# CRUD Operations
# =============================================================================


class StatusChangeResult(TypedDict):
    """Result of a status change operation."""

    status: str  # 'applied' or 'pending_approval'
    intended_parent: IntendedParent | None
    request_id: UUID | None
    message: str | None


def generate_intended_parent_number(db: Session, org_id: UUID) -> str:
    """
    Generate next sequential intended parent number for org (I10001+).

    Uses atomic INSERT...ON CONFLICT for race-condition-free counter increment.
    """
    result = db.execute(
        text("""
            INSERT INTO org_counters (organization_id, counter_type, current_value)
            VALUES (:org_id, 'intended_parent_number', 10001)
            ON CONFLICT (organization_id, counter_type)
            DO UPDATE SET current_value = org_counters.current_value + 1,
                          updated_at = now()
            RETURNING current_value
        """),
        {"org_id": org_id},
    ).scalar_one_or_none()
    if result is None:
        raise RuntimeError("Failed to generate intended parent number")

    return f"I{result:05d}"


def list_intended_parents(
    db: Session,
    org_id: UUID,
    *,
    status: list[str] | None = None,
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    include_archived: bool = False,
    created_after: str | None = None,
    created_before: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> tuple[list[IntendedParent], int]:
    """
    List intended parents with filters and pagination.

    Returns (items, total_count).
    """
    from sqlalchemy import asc, desc

    query = _build_intended_parent_query(
        db,
        org_id,
        status=status,
        state=state,
        budget_min=budget_min,
        budget_max=budget_max,
        q=q,
        owner_id=owner_id,
        include_archived=include_archived,
        created_after=created_after,
        created_before=created_before,
    )

    # Get total count before pagination
    total = query.count()

    # Dynamic sorting
    order_func = asc if sort_order == "asc" else desc
    sortable_columns = {
        "intended_parent_number": IntendedParent.intended_parent_number,
        "full_name": IntendedParent.full_name,
        "partner_name": IntendedParent.partner_name,
        "state": IntendedParent.state,
        "budget": IntendedParent.budget,
        "status": IntendedParent.status,
        "created_at": IntendedParent.created_at,
    }

    if sort_by == "status":
        from app.db.models import PipelineStage

        query = query.join(PipelineStage, IntendedParent.stage_id == PipelineStage.id).order_by(
            order_func(PipelineStage.order),
            order_func(IntendedParent.created_at),
        )
    elif sort_by and sort_by in sortable_columns:
        query = query.order_by(order_func(sortable_columns[sort_by]))
    else:
        query = query.order_by(IntendedParent.created_at.desc())

    # Pagination
    per_page = min(per_page, 100)  # Cap at 100
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()

    return items, total


def list_intended_parent_created_dates(
    db: Session,
    org_id: UUID,
    *,
    status: list[str] | None = None,
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    include_archived: bool = False,
) -> list[str]:
    """List distinct created_at dates (YYYY-MM-DD) for current filtered context."""
    query = _build_intended_parent_query(
        db,
        org_id,
        status=status,
        state=state,
        budget_min=budget_min,
        budget_max=budget_max,
        q=q,
        owner_id=owner_id,
        include_archived=include_archived,
    )

    rows = (
        query.with_entities(func.date(IntendedParent.created_at).label("created_date"))
        .distinct()
        .order_by(func.date(IntendedParent.created_at).asc())
        .all()
    )
    return [row.created_date.isoformat() for row in rows if row.created_date is not None]


def list_intended_parents_for_session(
    db: Session,
    request: Request | None,
    session: UserSession,
    *,
    status: list[str] | None = None,
    state: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    include_archived: bool = False,
    created_after: str | None = None,
    created_before: str | None = None,
    page: int = 1,
    per_page: int = 20,
    sort_by: str | None = None,
    sort_order: str = "desc",
) -> dict[str, object]:
    """List intended parents scoped to the current session with PHI auditing."""
    from app.schemas.intended_parent import IntendedParentListItem
    from app.services import phi_access_service

    items, total = list_intended_parents(
        db,
        org_id=session.org_id,
        status=status,
        state=state,
        budget_min=budget_min,
        budget_max=budget_max,
        q=q,
        owner_id=owner_id,
        include_archived=include_archived,
        created_after=created_after,
        created_before=created_before,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    pages = (total + per_page - 1) // per_page  # ceiling division

    phi_access_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="intended_parent_list",
        target_id=None,
        request=request,
        query=q,
        details={
            "count": len(items),
            "page": page,
            "per_page": per_page,
            "include_archived": include_archived,
            "status": status,
            "state": state,
            "owner_id": str(owner_id) if owner_id else None,
            "budget_min": str(budget_min) if budget_min is not None else None,
            "budget_max": str(budget_max) if budget_max is not None else None,
            "created_after": created_after,
            "created_before": created_before,
        },
    )

    return {
        "items": [IntendedParentListItem.model_validate(ip) for ip in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


def get_intended_parent(db: Session, ip_id: UUID, org_id: UUID) -> IntendedParent | None:
    """Get a single intended parent by ID, scoped to organization."""
    return (
        db.query(IntendedParent)
        .options(selectinload(IntendedParent.stage))
        .filter(IntendedParent.id == ip_id, IntendedParent.organization_id == org_id)
        .first()
    )


def create_intended_parent(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    *,
    full_name: str,
    email: str,
    phone: str | None = None,
    state: str | None = None,
    budget: Decimal | None = None,
    notes_internal: str | None = None,
    owner_type: str | None = None,
    owner_id: UUID | None = None,
    partner_name: str | None = None,
    partner_email: str | None = None,
    pronouns: str | None = None,
    partner_pronouns: str | None = None,
    date_of_birth: date | None = None,
    partner_date_of_birth: date | None = None,
    marital_status: str | None = None,
    embryo_count: int | None = None,
    pgs_tested: bool | None = None,
    egg_source: str | None = None,
    sperm_source: str | None = None,
    trust_provider_name: str | None = None,
    trust_primary_contact_name: str | None = None,
    trust_email: str | None = None,
    trust_phone: str | None = None,
    trust_address_line1: str | None = None,
    trust_address_line2: str | None = None,
    trust_city: str | None = None,
    trust_state: str | None = None,
    trust_postal: str | None = None,
    trust_case_reference: str | None = None,
    trust_funding_status: str | None = None,
    trust_portal_url: str | None = None,
    trust_notes: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    postal: str | None = None,
    ip_clinic_name: str | None = None,
    ip_clinic_address_line1: str | None = None,
    ip_clinic_address_line2: str | None = None,
    ip_clinic_city: str | None = None,
    ip_clinic_state: str | None = None,
    ip_clinic_postal: str | None = None,
    ip_clinic_phone: str | None = None,
    ip_clinic_fax: str | None = None,
    ip_clinic_email: str | None = None,
) -> IntendedParent:
    """Create a new intended parent and record initial status."""
    from app.services import pipeline_service

    now = datetime.now(timezone.utc)
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone) if phone else None
    email_domain = extract_email_domain(normalized_email)
    phone_last4 = extract_phone_last4(normalized_phone)
    intended_parent_number = generate_intended_parent_number(db, org_id)
    normalized_full_name = normalize_search_text(full_name)

    # Hash partner email if provided
    normalized_partner_email = normalize_email(partner_email) if partner_email else None
    partner_email_hash = hash_email(normalized_partner_email) if normalized_partner_email else None
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        user_id,
        entity_type=INTENDED_PARENT_PIPELINE_ENTITY,
    )
    default_stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    if not default_stage:
        raise RuntimeError("Default intended parent stage 'new' not found")

    ip = IntendedParent(
        intended_parent_number=intended_parent_number,
        intended_parent_number_normalized=normalize_identifier(intended_parent_number),
        organization_id=org_id,
        full_name=full_name,
        full_name_normalized=normalized_full_name,
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        email_domain=email_domain,
        phone=normalized_phone,
        phone_hash=hash_phone(normalized_phone) if normalized_phone else None,
        phone_last4=phone_last4,
        state=state,
        budget=budget,
        notes_internal=notes_internal,
        stage_id=default_stage.id,
        status=default_stage.stage_key,
        owner_type=owner_type,
        owner_id=owner_id,
        # New fields
        partner_name=partner_name,
        partner_email=normalized_partner_email,
        partner_email_hash=partner_email_hash,
        pronouns=pronouns,
        partner_pronouns=partner_pronouns,
        date_of_birth=date_of_birth,
        partner_date_of_birth=partner_date_of_birth,
        marital_status=marital_status,
        embryo_count=embryo_count,
        pgs_tested=pgs_tested,
        egg_source=egg_source,
        sperm_source=sperm_source,
        trust_provider_name=trust_provider_name,
        trust_primary_contact_name=trust_primary_contact_name,
        trust_email=trust_email,
        trust_phone=trust_phone,
        trust_address_line1=trust_address_line1,
        trust_address_line2=trust_address_line2,
        trust_city=trust_city,
        trust_state=trust_state,
        trust_postal=trust_postal,
        trust_case_reference=trust_case_reference,
        trust_funding_status=trust_funding_status,
        trust_portal_url=trust_portal_url,
        trust_notes=trust_notes,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        postal=postal,
        ip_clinic_name=ip_clinic_name,
        ip_clinic_address_line1=ip_clinic_address_line1,
        ip_clinic_address_line2=ip_clinic_address_line2,
        ip_clinic_city=ip_clinic_city,
        ip_clinic_state=ip_clinic_state,
        ip_clinic_postal=ip_clinic_postal,
        ip_clinic_phone=ip_clinic_phone,
        ip_clinic_fax=ip_clinic_fax,
        ip_clinic_email=ip_clinic_email,
    )
    db.add(ip)
    db.flush()

    # Record initial status in history
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_stage_id=None,
        new_stage_id=default_stage.id,
        old_status=None,
        new_status=default_stage.stage_key,
        reason="Initial creation",
        effective_at=now,
        recorded_at=now,
    )
    db.add(history)
    db.commit()
    db.refresh(ip)
    return ip


def update_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
    *,
    updates: dict[str, object],
) -> IntendedParent:
    """Update intended parent fields and bump last_activity."""
    if "full_name" in updates:
        full_name = updates["full_name"]
        if isinstance(full_name, str) and full_name:
            ip.full_name = full_name
            ip.full_name_normalized = normalize_search_text(full_name)
    if "email" in updates:
        email = updates["email"]
        if isinstance(email, str) and email:
            normalized_email = normalize_email(email)
            ip.email = normalized_email
            ip.email_hash = hash_email(normalized_email)
            ip.email_domain = extract_email_domain(normalized_email)
    if "phone" in updates:
        phone = updates["phone"]
        normalized_phone = normalize_phone(phone) if phone else None
        ip.phone = normalized_phone
        ip.phone_hash = hash_phone(normalized_phone) if normalized_phone else None
        ip.phone_last4 = extract_phone_last4(normalized_phone)
    if "state" in updates:
        ip.state = updates["state"]
    if "budget" in updates:
        ip.budget = updates["budget"]
    if "notes_internal" in updates:
        ip.notes_internal = updates["notes_internal"]
    if "owner_type" in updates:
        ip.owner_type = updates["owner_type"]
    if "owner_id" in updates:
        ip.owner_id = updates["owner_id"]

    if "partner_name" in updates:
        ip.partner_name = updates["partner_name"]
    if "partner_email" in updates:
        partner_email = updates["partner_email"]
        normalized_partner_email = normalize_email(partner_email) if partner_email else None
        ip.partner_email = normalized_partner_email
        ip.partner_email_hash = (
            hash_email(normalized_partner_email) if normalized_partner_email else None
        )

    if "pronouns" in updates:
        ip.pronouns = updates["pronouns"]
    if "partner_pronouns" in updates:
        ip.partner_pronouns = updates["partner_pronouns"]
    if "date_of_birth" in updates:
        ip.date_of_birth = updates["date_of_birth"]
    if "partner_date_of_birth" in updates:
        ip.partner_date_of_birth = updates["partner_date_of_birth"]
    if "marital_status" in updates:
        ip.marital_status = updates["marital_status"]
    if "embryo_count" in updates:
        ip.embryo_count = updates["embryo_count"]
    if "pgs_tested" in updates:
        ip.pgs_tested = updates["pgs_tested"]
    if "egg_source" in updates:
        ip.egg_source = updates["egg_source"]
    if "sperm_source" in updates:
        ip.sperm_source = updates["sperm_source"]
    if "trust_provider_name" in updates:
        ip.trust_provider_name = updates["trust_provider_name"]
    if "trust_primary_contact_name" in updates:
        ip.trust_primary_contact_name = updates["trust_primary_contact_name"]
    if "trust_email" in updates:
        ip.trust_email = updates["trust_email"]
    if "trust_phone" in updates:
        ip.trust_phone = updates["trust_phone"]
    if "trust_address_line1" in updates:
        ip.trust_address_line1 = updates["trust_address_line1"]
    if "trust_address_line2" in updates:
        ip.trust_address_line2 = updates["trust_address_line2"]
    if "trust_city" in updates:
        ip.trust_city = updates["trust_city"]
    if "trust_state" in updates:
        ip.trust_state = updates["trust_state"]
    if "trust_postal" in updates:
        ip.trust_postal = updates["trust_postal"]
    if "trust_case_reference" in updates:
        ip.trust_case_reference = updates["trust_case_reference"]
    if "trust_funding_status" in updates:
        ip.trust_funding_status = updates["trust_funding_status"]
    if "trust_portal_url" in updates:
        ip.trust_portal_url = updates["trust_portal_url"]
    if "trust_notes" in updates:
        ip.trust_notes = updates["trust_notes"]

    if "address_line1" in updates:
        ip.address_line1 = updates["address_line1"]
    if "address_line2" in updates:
        ip.address_line2 = updates["address_line2"]
    if "city" in updates:
        ip.city = updates["city"]
    if "postal" in updates:
        ip.postal = updates["postal"]

    if "ip_clinic_name" in updates:
        ip.ip_clinic_name = updates["ip_clinic_name"]
    if "ip_clinic_address_line1" in updates:
        ip.ip_clinic_address_line1 = updates["ip_clinic_address_line1"]
    if "ip_clinic_address_line2" in updates:
        ip.ip_clinic_address_line2 = updates["ip_clinic_address_line2"]
    if "ip_clinic_city" in updates:
        ip.ip_clinic_city = updates["ip_clinic_city"]
    if "ip_clinic_state" in updates:
        ip.ip_clinic_state = updates["ip_clinic_state"]
    if "ip_clinic_postal" in updates:
        ip.ip_clinic_postal = updates["ip_clinic_postal"]
    if "ip_clinic_phone" in updates:
        ip.ip_clinic_phone = updates["ip_clinic_phone"]
    if "ip_clinic_fax" in updates:
        ip.ip_clinic_fax = updates["ip_clinic_fax"]
    if "ip_clinic_email" in updates:
        ip.ip_clinic_email = updates["ip_clinic_email"]

    ip.last_activity = datetime.now(timezone.utc)
    ip.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(ip)
    return ip


# =============================================================================
# Status Management
# =============================================================================


def change_status(
    db: Session,
    ip: IntendedParent,
    new_stage,
    user_id: UUID,
    user_role: Role | str | None,
    reason: str | None = None,
    effective_at: datetime | None = None,
) -> StatusChangeResult:
    """
    Change intended parent status with backdating and regression support.

    - Backdating (past date): Requires reason, applies immediately
    - Regression (earlier status): Requires reason + admin approval
    - Undo within 5-min grace period: Bypasses admin approval
    """
    from app.services import intended_parent_status_service

    return intended_parent_status_service.change_status(
        db=db,
        ip=ip,
        new_stage=new_stage,
        user_id=user_id,
        user_role=user_role,
        reason=reason,
        effective_at=effective_at,
    )


def get_ip_status_history(db: Session, ip_id: UUID) -> list[IntendedParentStatusHistory]:
    """Get status history for an intended parent."""
    return (
        db.query(IntendedParentStatusHistory)
        .filter(IntendedParentStatusHistory.intended_parent_id == ip_id)
        .order_by(IntendedParentStatusHistory.recorded_at.desc())
        .all()
    )


# =============================================================================
# Archive / Restore
# =============================================================================


def archive_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
) -> IntendedParent:
    """Soft delete (archive) an intended parent without mutating its live pipeline stage."""
    from app.services import intended_parent_status_service

    now = datetime.now(timezone.utc)
    current_stage = intended_parent_status_service.get_current_stage(db, ip)
    ip.is_archived = True
    ip.archived_at = now
    ip.last_activity = now

    # Record in history
    history = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_stage_id=current_stage.id,
        new_stage_id=current_stage.id,
        old_status=current_stage.stage_key,
        new_status=IntendedParentStatus.ARCHIVED.value,
        reason="Archived",
        effective_at=now,
        recorded_at=now,
    )
    db.add(history)
    db.commit()
    db.refresh(ip)
    return ip


def restore_intended_parent(
    db: Session,
    ip: IntendedParent,
    user_id: UUID,
) -> IntendedParent:
    """Restore an archived intended parent without changing its live pipeline stage."""
    from app.services import intended_parent_status_service

    now = datetime.now(timezone.utc)
    current_stage = intended_parent_status_service.get_current_stage(db, ip)

    ip.is_archived = False
    ip.archived_at = None
    ip.last_activity = now

    history_entry = IntendedParentStatusHistory(
        intended_parent_id=ip.id,
        changed_by_user_id=user_id,
        old_stage_id=current_stage.id,
        new_stage_id=current_stage.id,
        old_status=IntendedParentStatus.ARCHIVED.value,
        new_status=current_stage.stage_key,
        reason="Restored from archive",
        effective_at=now,
        recorded_at=now,
    )
    db.add(history_entry)
    db.commit()
    db.refresh(ip)
    return ip


def delete_intended_parent(db: Session, ip: IntendedParent) -> None:
    """Hard delete an intended parent (must be archived first)."""
    if not ip.is_archived:
        raise ValueError("Cannot delete non-archived intended parent")
    db.delete(ip)
    db.commit()


# =============================================================================
# Stats
# =============================================================================


def get_ip_stats(db: Session, org_id: UUID) -> dict:
    """Get IP counts by status."""
    results = (
        db.query(IntendedParent.status, func.count(IntendedParent.id))
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.is_archived.is_(False),
        )
        .group_by(IntendedParent.status)
        .all()
    )

    by_status = {status: count for status, count in results}
    total = sum(by_status.values())

    return {"total": total, "by_status": by_status}


# =============================================================================
# Duplicate Check
# =============================================================================


def get_ip_by_email(db: Session, email: str, org_id: UUID) -> IntendedParent | None:
    """Check if an active IP with this email exists in the org."""
    return (
        db.query(IntendedParent)
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.email_hash == hash_email(email),
            IntendedParent.is_archived.is_(False),
        )
        .first()
    )
