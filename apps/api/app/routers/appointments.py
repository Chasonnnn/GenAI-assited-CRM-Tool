"""Appointments router - API endpoints for appointment management.

Internal authenticated endpoints for staff to manage:
- Appointment types
- Availability rules and overrides
- Booking links
- Appointment approval/management
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
)
from app.db.enums import AppointmentStatus
from app.db.models import User
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
    AppointmentListItem,
    AppointmentListResponse,
    AppointmentReschedule,
    AppointmentCancel,
)
from app.services import appointment_service, appointment_email_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE
from app.core.config import settings

router = APIRouter()


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


def _appointment_to_read(appt, db: Session) -> AppointmentRead:
    """Convert Appointment model to read schema."""
    appt_type_name = None
    if appt.appointment_type:
        appt_type_name = appt.appointment_type.name
    
    approved_by_name = None
    if appt.approved_by_user_id:
        user = db.query(User).filter(User.id == appt.approved_by_user_id).first()
        approved_by_name = user.display_name if user else None
    
    return AppointmentRead(
        id=appt.id,
        user_id=appt.user_id,
        appointment_type_id=appt.appointment_type_id,
        appointment_type_name=appt_type_name,
        client_name=appt.client_name,
        client_email=appt.client_email,
        client_phone=appt.client_phone,
        client_timezone=appt.client_timezone,
        client_notes=appt.client_notes,
        scheduled_start=appt.scheduled_start,
        scheduled_end=appt.scheduled_end,
        duration_minutes=appt.duration_minutes,
        meeting_mode=appt.meeting_mode,
        status=appt.status,
        pending_expires_at=appt.pending_expires_at,
        approved_at=appt.approved_at,
        approved_by_user_id=appt.approved_by_user_id,
        approved_by_name=approved_by_name,
        cancelled_at=appt.cancelled_at,
        cancelled_by_client=appt.cancelled_by_client,
        cancellation_reason=appt.cancellation_reason,
        zoom_join_url=appt.zoom_join_url,
        google_event_id=appt.google_event_id,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


def _appointment_to_list_item(appt) -> AppointmentListItem:
    """Convert Appointment model to list item schema."""
    appt_type_name = None
    if appt.appointment_type:
        appt_type_name = appt.appointment_type.name
    
    return AppointmentListItem(
        id=appt.id,
        appointment_type_name=appt_type_name,
        client_name=appt.client_name,
        client_email=appt.client_email,
        client_phone=appt.client_phone,
        scheduled_start=appt.scheduled_start,
        scheduled_end=appt.scheduled_end,
        duration_minutes=appt.duration_minutes,
        meeting_mode=appt.meeting_mode,
        status=appt.status,
        created_at=appt.created_at,
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
    rules = appointment_service.set_availability_rules(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        rules=[r.model_dump() for r in data.rules],
        timezone_name=data.timezone,
    )
    return [_rule_to_read(r) for r in rules]


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
    from app.core.config import settings
    
    link = appointment_service.get_or_create_booking_link(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
    )
    base_url = settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else ""
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
    from app.core.config import settings
    
    link = appointment_service.regenerate_booking_link(
        db=db,
        user_id=session.user_id,
    )
    if not link:
        raise HTTPException(status_code=404, detail="Booking link not found")
    
    base_url = settings.FRONTEND_URL if hasattr(settings, 'FRONTEND_URL') else ""
    return _link_to_read(link, base_url)


# =============================================================================
# Appointments
# =============================================================================

@router.get("", response_model=AppointmentListResponse)
def list_appointments(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    status: str | None = None,
    date_start: date | None = None,
    date_end: date | None = None,
):
    """List appointments for the current user."""
    offset = (page - 1) * per_page
    appointments, total = appointment_service.list_appointments(
        db=db,
        user_id=session.user_id,
        org_id=session.org_id,
        status=status,
        date_start=date_start,
        date_end=date_end,
        limit=per_page,
        offset=offset,
    )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return AppointmentListResponse(
        items=[_appointment_to_list_item(a) for a in appointments],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(
    appointment_id: UUID,
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
    
    return _appointment_to_read(appt, db)


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
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_confirmed(db, appt, base_url)
        
        return _appointment_to_read(appt, db)
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
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_rescheduled(db, appt, old_start, base_url)
        
        return _appointment_to_read(appt, db)
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
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_cancelled(db, appt, base_url)
        
        return _appointment_to_read(appt, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
