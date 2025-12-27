"""Public booking router - API endpoints for public appointment booking.

Unauthenticated endpoints for clients to:
- View available appointment types
- View available time slots
- Submit booking requests
- Reschedule/cancel via tokens
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.schemas.appointment import (
    AppointmentTypeRead,
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel,
    TimeSlotRead,
    AvailableSlotsResponse,
    StaffInfoRead,
    PublicBookingPageRead,
)
from app.core.rate_limit import limiter
from app.services import appointment_service, appointment_email_service, user_service, org_service
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


def _appointment_to_public_read(appt, db: Session) -> dict:
    """Convert Appointment to public-safe read format."""
    appt_type_name = None
    if appt.appointment_type:
        appt_type_name = appt.appointment_type.name
    
    user = user_service.get_user_by_id(db, appt.user_id)
    staff_name = user.display_name if user else None
    
    return {
        "id": str(appt.id),
        "appointment_type_name": appt_type_name,
        "staff_name": staff_name,
        "client_name": appt.client_name,
        "scheduled_start": appt.scheduled_start.isoformat(),
        "scheduled_end": appt.scheduled_end.isoformat(),
        "duration_minutes": appt.duration_minutes,
        "meeting_mode": appt.meeting_mode,
        "status": appt.status,
        "client_timezone": appt.client_timezone,
        "zoom_join_url": appt.zoom_join_url if appt.status == "confirmed" else None,
    }


# =============================================================================
# Public Booking Page
# =============================================================================

@router.get("/{public_slug}")
def get_booking_page(
    public_slug: str,
    db: Session = Depends(get_db),
):
    """
    Get public booking page data.
    
    Returns staff info and available appointment types.
    """
    link = appointment_service.get_booking_link_by_slug(db, public_slug)
    if not link:
        raise HTTPException(status_code=404, detail="Booking page not found")
    
    # Get staff info
    user = user_service.get_user_by_id(db, link.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    # Get org name
    org = org_service.get_org_by_id(db, link.organization_id)
    org_name = org.name if org else None
    org_timezone = org.timezone if org else None
    
    # Get appointment types
    types = appointment_service.list_appointment_types(
        db=db,
        user_id=link.user_id,
        org_id=link.organization_id,
        active_only=True,
    )
    
    return PublicBookingPageRead(
        staff=StaffInfoRead(
            user_id=user.id,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        ),
        appointment_types=[_type_to_read(t) for t in types],
        org_name=org_name,
        org_timezone=org_timezone,
    )


@router.get("/{public_slug}/slots")
def get_available_slots(
    public_slug: str,
    appointment_type_id: UUID,
    date_start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_end: date = Query(None, description="End date (defaults to start + 7 days)"),
    client_timezone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get available time slots for booking.
    
    Returns slots for the specified date range.
    """
    link = appointment_service.get_booking_link_by_slug(db, public_slug)
    if not link:
        raise HTTPException(status_code=404, detail="Booking page not found")
    
    # Default to 7-day window
    if not date_end:
        date_end = date_start + timedelta(days=7)
    
    # Limit range to 30 days
    if (date_end - date_start).days > 30:
        date_end = date_start + timedelta(days=30)
    
    # Get appointment type
    appt_type = appointment_service.get_appointment_type(
        db, appointment_type_id, link.organization_id
    )
    if not appt_type or not appt_type.is_active:
        raise HTTPException(status_code=404, detail="Appointment type not found")
    
    if appt_type.user_id != link.user_id:
        raise HTTPException(status_code=400, detail="Appointment type mismatch")
    
    # Default timezone to org if not provided
    if not client_timezone:
        org = org_service.get_org_by_id(db, link.organization_id)
        client_timezone = org.timezone if org else "America/Los_Angeles"

    # Get slots
    query = appointment_service.SlotQuery(
        user_id=link.user_id,
        org_id=link.organization_id,
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


@router.post("/{public_slug}/book")
@limiter.limit("10/minute")
def create_booking(
    public_slug: str,
    data: AppointmentCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Submit a booking request.
    
    Creates a pending appointment that requires staff approval.
    Rate limited to prevent spam.
    """
    # Verify booking link
    link = appointment_service.get_booking_link_by_slug(db, public_slug)
    if not link:
        raise HTTPException(status_code=404, detail="Booking page not found")
    
    # Verify appointment type
    appt_type = appointment_service.get_appointment_type(
        db, data.appointment_type_id, link.organization_id
    )
    if not appt_type or not appt_type.is_active:
        raise HTTPException(status_code=400, detail="Appointment type not found")
    
    if appt_type.user_id != link.user_id:
        raise HTTPException(status_code=400, detail="Appointment type mismatch")
    
    try:
        appt = appointment_service.create_booking(
            db=db,
            org_id=link.organization_id,
            user_id=link.user_id,
            appointment_type_id=data.appointment_type_id,
            client_name=data.client_name,
            client_email=data.client_email,
            client_phone=data.client_phone,
            client_timezone=data.client_timezone,
            scheduled_start=data.scheduled_start,
            client_notes=data.client_notes,
            idempotency_key=data.idempotency_key,
        )
        
        # Send confirmation email to client
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_request_received(db, appt, base_url)
        
        return _appointment_to_public_read(appt, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Self-Service (Token-based)
# =============================================================================

@router.get("/self-service/reschedule/{token}")
def get_appointment_for_reschedule(
    token: str,
    db: Session = Depends(get_db),
):
    """Get appointment details for reschedule form."""
    appt = appointment_service.get_appointment_by_token(db, token, "reschedule")
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return _appointment_to_public_read(appt, db)


@router.get("/self-service/reschedule/{token}/slots")
def get_reschedule_slots(
    token: str,
    date_start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    date_end: date = Query(None, description="End date (defaults to start date)"),
    client_timezone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Get available time slots for rescheduling.
    
    Uses the appointment's existing settings to determine availability.
    """
    appt = appointment_service.get_appointment_by_token(db, token, "reschedule")
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    if not appt.appointment_type_id:
        raise HTTPException(status_code=400, detail="Appointment type not found")
    
    # Default to single day
    if not date_end:
        date_end = date_start
    
    # Limit range to 14 days
    if (date_end - date_start).days > 14:
        date_end = date_start + timedelta(days=14)
    
    # Use client timezone from request or fallback to appointment's timezone
    tz = client_timezone or appt.client_timezone or "America/Los_Angeles"
    
    # Get slots using appointment's user and type
    query = appointment_service.SlotQuery(
        user_id=appt.user_id,
        org_id=appt.organization_id,
        appointment_type_id=appt.appointment_type_id,
        date_start=date_start,
        date_end=date_end,
        client_timezone=tz,
    )
    
    slots = appointment_service.get_available_slots(
        db, query,
        exclude_appointment_id=appt.id,  # Exclude this appointment from conflict check
    )
    
    # Get appointment type for response
    appt_type = appointment_service.get_appointment_type(
        db, appt.appointment_type_id, appt.organization_id
    )
    
    return AvailableSlotsResponse(
        slots=[TimeSlotRead(start=s.start, end=s.end) for s in slots],
        appointment_type=_type_to_read(appt_type) if appt_type else None,
    )


@router.post("/self-service/reschedule/{token}")
@limiter.limit("10/minute")
def reschedule_by_token(
    token: str,
    data: AppointmentReschedule,
    request: Request,
    db: Session = Depends(get_db),
):
    """Reschedule an appointment using self-service token."""
    appt = appointment_service.get_appointment_by_token(db, token, "reschedule")
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    try:
        old_start = appt.scheduled_start  # Save for email
        appt = appointment_service.reschedule_booking(
            db=db,
            appointment=appt,
            new_start=data.scheduled_start,
            by_client=True,
            token=token,
        )
        
        # Send reschedule notification email
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_rescheduled(db, appt, old_start, base_url)
        
        return _appointment_to_public_read(appt, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/self-service/cancel/{token}")
def get_appointment_for_cancel(
    token: str,
    db: Session = Depends(get_db),
):
    """Get appointment details for cancel confirmation."""
    appt = appointment_service.get_appointment_by_token(db, token, "cancel")
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return _appointment_to_public_read(appt, db)


@router.post("/self-service/cancel/{token}")
@limiter.limit("10/minute")
def cancel_by_token(
    token: str,
    data: AppointmentCancel,
    request: Request,
    db: Session = Depends(get_db),
):
    """Cancel an appointment using self-service token."""
    appt = appointment_service.get_appointment_by_token(db, token, "cancel")
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    try:
        appt = appointment_service.cancel_booking(
            db=db,
            appointment=appt,
            reason=data.reason,
            by_client=True,
            token=token,
        )
        
        # Send cancellation notification email
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        appointment_email_service.send_cancelled(db, appt, base_url)
        
        return _appointment_to_public_read(appt, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
