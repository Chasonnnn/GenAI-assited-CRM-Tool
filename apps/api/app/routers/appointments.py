"""Appointments router - API endpoints for appointment management.

Internal authenticated endpoints for staff to manage:
- Appointment types
- Availability rules and overrides
- Booking links
- Appointment approval/management
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.appointment import (
    AppointmentTypeCreate,
    AppointmentTypeRead,
    AppointmentTypeUpdate,
    AvailabilityRulesSet,
    AvailabilityRuleRead,
    AvailabilityOverrideCreate,
    AvailabilityOverrideRead,
    BookingLinkRead,
    AppointmentRead,
    AppointmentListResponse,
    AppointmentLinkUpdate,
    AppointmentReschedule,
    AppointmentCancel,
    PublicBookingPageRead,
    StaffInfoRead,
    TimeSlotRead,
    AvailableSlotsResponse,
)
from app.services import (
    appointment_service,
    appointment_email_service,
    audit_service,
    media_service,
    user_service,
    org_service,
)
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

router = APIRouter(dependencies=[Depends(require_permission(POLICIES["appointments"].default))])


# =============================================================================
# Helper Functions
# =============================================================================


def _type_to_read(appt_type) -> AppointmentTypeRead:
    """Convert AppointmentType model to read schema."""
    return AppointmentTypeRead(
        id=appt_type.id,
        user_id=appt_type.user_id,
        name=appt_type.name,
        slug=appt_type.slug,
        description=appt_type.description,
        duration_minutes=appt_type.duration_minutes,
        buffer_before_minutes=appt_type.buffer_before_minutes,
        buffer_after_minutes=appt_type.buffer_after_minutes,
        meeting_mode=appt_type.meeting_mode,
        meeting_modes=appt_type.meeting_modes or [appt_type.meeting_mode],
        meeting_location=appt_type.meeting_location,
        dial_in_number=appt_type.dial_in_number,
        auto_approve=appt_type.auto_approve,
        reminder_hours_before=appt_type.reminder_hours_before,
        is_active=appt_type.is_active,
        created_at=appt_type.created_at,
        updated_at=appt_type.updated_at,
    )


def _rule_to_read(rule) -> AvailabilityRuleRead:
    """Convert AvailabilityRule model to read schema."""
    return AvailabilityRuleRead(
        id=rule.id,
        day_of_week=rule.day_of_week,
        start_time=rule.start_time,
        end_time=rule.end_time,
        timezone=rule.timezone,
    )


def _override_to_read(override) -> AvailabilityOverrideRead:
    """Convert AvailabilityOverride model to read schema."""
    return AvailabilityOverrideRead(
        id=override.id,
        override_date=override.override_date,
        is_unavailable=override.is_unavailable,
        start_time=override.start_time,
        end_time=override.end_time,
        reason=override.reason,
        created_at=override.created_at,
    )


def _link_to_read(link, base_url: str = "") -> BookingLinkRead:
    """Convert BookingLink model to read schema."""
    return BookingLinkRead(
        id=link.id,
        user_id=link.user_id,
        public_slug=link.public_slug,
        is_active=link.is_active,
        full_url=f"{base_url}/book/{link.public_slug}" if base_url else None,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


# =============================================================================
# Appointment Types
# =============================================================================


@router.get("/types", response_model=list[AppointmentTypeRead])
def list_appointment_types(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    active_only: bool = Query(True),
):
    """List appointment types for the current user."""
    types = appointment_service.list_appointment_types(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        active_only=active_only,
    )
    return [_type_to_read(t) for t in types]


@router.post(
    "/types",
    response_model=AppointmentTypeRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_appointment_type(
    data: AppointmentTypeCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create a new appointment type."""
    try:
        appt_type = appointment_service.create_appointment_type(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            name=data.name,
            description=data.description,
            duration_minutes=data.duration_minutes,
            buffer_before_minutes=data.buffer_before_minutes,
            buffer_after_minutes=data.buffer_after_minutes,
            meeting_mode=data.meeting_mode,
            meeting_modes=data.meeting_modes,
            meeting_location=data.meeting_location,
            dial_in_number=data.dial_in_number,
            auto_approve=data.auto_approve,
            reminder_hours_before=data.reminder_hours_before,
        )
        return _type_to_read(appt_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/types/{type_id}",
    response_model=AppointmentTypeRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_appointment_type(
    type_id: UUID,
    data: AppointmentTypeUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update an appointment type."""
    appt_type = appointment_service.get_appointment_type(db, type_id, session.org_id)
    if not appt_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    # Verify ownership
    if appt_type.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    appt_type = appointment_service.update_appointment_type(
        db=db,
        appt_type=appt_type,
        **data.model_dump(exclude_unset=True),
    )
    return _type_to_read(appt_type)


@router.delete(
    "/types/{type_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def deactivate_appointment_type(
    type_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Deactivate an appointment type (soft delete)."""
    appt_type = appointment_service.get_appointment_type(db, type_id, session.org_id)
    if not appt_type:
        raise HTTPException(status_code=404, detail="Appointment type not found")

    if appt_type.user_id != session.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    appointment_service.update_appointment_type(db, appt_type, is_active=False)
    return None


# =============================================================================
# Availability Rules
# =============================================================================


@router.get("/availability", response_model=list[AvailabilityRuleRead])
def get_availability_rules(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get availability rules for the current user."""
    rules = appointment_service.get_availability_rules(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    return [_rule_to_read(r) for r in rules]


@router.put(
    "/availability",
    response_model=list[AvailabilityRuleRead],
    dependencies=[Depends(require_csrf_header)],
)
def set_availability_rules(
    data: AvailabilityRulesSet,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Replace all availability rules for the current user."""
    try:
        rules = appointment_service.set_availability_rules(
            db=db,
            user_id=session.user_id,
            org_id=session.org_id,
            rules=[r.model_dump() for r in data.rules],
            timezone_name=data.timezone,
        )
        return [_rule_to_read(r) for r in rules]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Availability Overrides
# =============================================================================


@router.get("/overrides", response_model=list[AvailabilityOverrideRead])
def get_availability_overrides(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    date_start: date | None = None,
    date_end: date | None = None,
):
    """Get availability overrides for the current user."""
    overrides = appointment_service.get_availability_overrides(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        date_start=date_start,
        date_end=date_end,
    )
    return [_override_to_read(o) for o in overrides]


@router.post(
    "/overrides",
    response_model=AvailabilityOverrideRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_availability_override(
    data: AvailabilityOverrideCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Create or update an availability override."""
    from datetime import time as dt_time

    start_time = dt_time.fromisoformat(data.start_time) if data.start_time else None
    end_time = dt_time.fromisoformat(data.end_time) if data.end_time else None

    try:
        override = appointment_service.set_availability_override(
            db=db,
            user_id=session.user_id,
            org_id=session.org_id,
            override_date=data.override_date,
            is_unavailable=data.is_unavailable,
            start_time=start_time,
            end_time=end_time,
            reason=data.reason,
        )
        return _override_to_read(override)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/overrides/{override_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_availability_override(
    override_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Delete an availability override."""
    success = appointment_service.delete_availability_override(
        db=db,
        override_id=override_id,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Override not found")
    return None


# =============================================================================
# Booking Link
# =============================================================================


@router.get("/booking-link", response_model=BookingLinkRead)
def get_booking_link(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get or create booking link for the current user."""
    link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    return _link_to_read(link, base_url)


@router.post(
    "/booking-link/regenerate",
    response_model=BookingLinkRead,
    dependencies=[Depends(require_csrf_header)],
)
def regenerate_booking_link(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Regenerate booking link with a new slug."""
    link = appointment_service.regenerate_booking_link(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    if not link:
        raise HTTPException(status_code=404, detail="Booking link not found")

    org = org_service.get_org_by_id(db, session.org_id)
    base_url = org_service.get_org_portal_base_url(org)
    return _link_to_read(link, base_url)


# =============================================================================
# Booking Preview (Authenticated)
# =============================================================================


@router.get("/booking-preview", response_model=PublicBookingPageRead)
def get_booking_preview(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Preview booking page data for the current user."""
    user = user_service.get_user_by_id(db, session.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Staff not found")

    org = org_service.get_org_by_id(db, session.org_id)
    org_name = org_service.get_org_display_name(org) if org else None
    org_timezone = org.timezone if org else None

    types = appointment_service.list_appointment_types(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        active_only=True,
    )

    return PublicBookingPageRead(
        staff=StaffInfoRead(
            user_id=user.id,
            display_name=user.display_name,
            avatar_url=media_service.get_signed_media_url(user.avatar_url),
        ),
        appointment_types=[_type_to_read(t) for t in types],
        org_name=org_name,
        org_timezone=org_timezone,
    )


@router.get("/booking-preview/slots", response_model=AvailableSlotsResponse)
def get_booking_preview_slots(
    appointment_type_id: UUID,
    date_start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_end: date = Query(None, description="End date (defaults to start + 7 days)"),
    client_timezone: str | None = Query(None),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Preview available slots for the current user's booking page."""
    appt_type = appointment_service.get_appointment_type(db, appointment_type_id, session.org_id)
    if not appt_type or not appt_type.is_active:
        raise HTTPException(status_code=404, detail="Appointment type not found")
    if appt_type.user_id != session.user_id:
        raise HTTPException(status_code=400, detail="Appointment type mismatch")

    if not date_end:
        date_end = date_start + timedelta(days=7)

    if (date_end - date_start).days > 30:
        date_end = date_start + timedelta(days=30)

    if not client_timezone:
        org = org_service.get_org_by_id(db, session.org_id)
        client_timezone = org.timezone if org else "America/Los_Angeles"

    try:
        appointment_service.validate_timezone_name(client_timezone, "client timezone")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    query = appointment_service.SlotQuery(
        user_id=session.user_id,
        org_id=session.org_id,
        appointment_type_id=appointment_type_id,
        date_start=date_start,
        date_end=date_end,
        client_timezone=client_timezone,
    )

    slots = appointment_service.get_available_slots(db, query)

    return AvailableSlotsResponse(
        slots=[TimeSlotRead(start=s.start, end=s.end) for s in slots],
        appointment_type=_type_to_read(appt_type),
    )


# =============================================================================
# Appointments
# =============================================================================


@router.get("", response_model=AppointmentListResponse)
def list_appointments(
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    status: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
    surrogate_id: UUID | None = None,
    intended_parent_id: UUID | None = None,
):
    """List appointments for the current user.

    Optionally filter by surrogate_id and/or intended_parent_id for match-scoped views.
    When both are provided, returns appointments matching EITHER.
    """
    offset = (page - 1) * per_page
    appointments, total = appointment_service.list_appointments(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        status=status,
        date_start=date_start,
        date_end=date_end,
        surrogate_id=surrogate_id,
        intended_parent_id=intended_parent_id,
        limit=per_page,
        offset=offset,
    )

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    context = appointment_service.get_appointment_context(db, appointments)
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="appointment_list",
        target_id=None,
        request=request,
        details={
            "status": status,
            "count": len(appointments),
            "surrogate_id": str(surrogate_id) if surrogate_id else None,
            "intended_parent_id": str(intended_parent_id) if intended_parent_id else None,
        },
    )
    db.commit()
    return AppointmentListResponse(
        items=[appointment_service.to_appointment_list_item(a, context) for a in appointments],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get appointment details."""
    appt = appointment_service.get_appointment(db, appointment_id, session.org_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Verify ownership or admin
    if appt.user_id != session.user_id and session.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    context = appointment_service.get_appointment_context(db, [appt])
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="appointment",
        target_id=appt.id,
        request=request,
        details={"surrogate_id": str(appt.surrogate_id) if appt.surrogate_id else None},
    )
    db.commit()
    return appointment_service.to_appointment_read(appt, context)


@router.patch(
    "/{appointment_id}/link",
    response_model=AppointmentRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_appointment_link(
    appointment_id: UUID,
    data: AppointmentLinkUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update surrogate/intended parent linkage for an appointment."""
    from app.core.surrogate_access import check_surrogate_access
    from app.services import surrogate_service, ip_service

    appt = appointment_service.get_appointment(db, appointment_id, session.org_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.user_id != session.user_id and session.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    if "surrogate_id" in data.model_fields_set:
        if data.surrogate_id is None:
            appt.surrogate_id = None
        else:
            surrogate = surrogate_service.get_surrogate(db, session.org_id, data.surrogate_id)
            if not surrogate:
                raise HTTPException(status_code=404, detail="Surrogate not found")
            check_surrogate_access(
                surrogate, session.role, session.user_id, db=db, org_id=session.org_id
            )
            appt.surrogate_id = surrogate.id

    if "intended_parent_id" in data.model_fields_set:
        if data.intended_parent_id is None:
            appt.intended_parent_id = None
        else:
            ip = ip_service.get_intended_parent(db, data.intended_parent_id, session.org_id)
            if not ip:
                raise HTTPException(status_code=404, detail="Intended parent not found")
            appt.intended_parent_id = ip.id

    db.commit()
    db.refresh(appt)
    context = appointment_service.get_appointment_context(db, [appt])
    return appointment_service.to_appointment_read(appt, context)


@router.post(
    "/{appointment_id}/approve",
    response_model=AppointmentRead,
    dependencies=[Depends(require_csrf_header)],
)
def approve_appointment(
    appointment_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Approve a pending appointment."""
    appt = appointment_service.get_appointment(db, appointment_id, session.org_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.user_id != session.user_id and session.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        appt = appointment_service.approve_booking(
            db=db,
            appointment=appt,
            approved_by_user_id=session.user_id,
        )

        # Send confirmation email to client
        org = org_service.get_org_by_id(db, appt.organization_id)
        base_url = org_service.get_org_portal_base_url(org)
        appointment_email_service.send_confirmed(db, appt, base_url)

        context = appointment_service.get_appointment_context(db, [appt])
        return appointment_service.to_appointment_read(appt, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentRead,
    dependencies=[Depends(require_csrf_header)],
)
def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentReschedule,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Reschedule an appointment (staff action)."""
    appt = appointment_service.get_appointment(db, appointment_id, session.org_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.user_id != session.user_id and session.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        old_start = appt.scheduled_start  # Save for email
        appt = appointment_service.reschedule_booking(
            db=db,
            appointment=appt,
            new_start=data.scheduled_start,
            by_client=False,
        )

        # Send reschedule notification email
        org = org_service.get_org_by_id(db, appt.organization_id)
        base_url = org_service.get_org_portal_base_url(org)
        appointment_email_service.send_rescheduled(db, appt, old_start, base_url)

        context = appointment_service.get_appointment_context(db, [appt])
        return appointment_service.to_appointment_read(appt, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    dependencies=[Depends(require_csrf_header)],
)
def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancel,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Cancel an appointment (staff action)."""
    appt = appointment_service.get_appointment(db, appointment_id, session.org_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.user_id != session.user_id and session.role not in ["admin", "developer"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        appt = appointment_service.cancel_booking(
            db=db,
            appointment=appt,
            reason=data.reason,
            by_client=False,
        )

        # Send cancellation notification email
        org = org_service.get_org_by_id(db, appt.organization_id)
        base_url = org_service.get_org_portal_base_url(org)
        appointment_email_service.send_cancelled(db, appt, base_url)

        context = appointment_service.get_appointment_context(db, [appt])
        return appointment_service.to_appointment_read(appt, context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
