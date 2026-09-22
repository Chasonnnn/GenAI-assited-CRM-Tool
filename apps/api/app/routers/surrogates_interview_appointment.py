"""Surrogate initial interview appointment routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.interview_appointment import (
    InterviewAppointmentRead,
    InterviewGoogleSyncCheck,
    InterviewSlotRead,
    InterviewSlotsRead,
    InterviewStageRead,
    SurrogateInterviewAppointmentAction,
    SurrogateInterviewAppointmentState,
)
from app.services import (
    appointment_google_sync_service,
    appointment_service,
    permission_service,
    pipeline_service,
    surrogate_interview_appointment_service,
    surrogate_service,
)
from app.services.calendar_binding_service import CalendarAvailabilityUnavailable

router = APIRouter()


def _state(db: Session, surrogate, session: UserSession) -> SurrogateInterviewAppointmentState:
    appointment = surrogate_interview_appointment_service.get_latest(
        db, session.org_id, surrogate.id
    )
    stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id) if surrogate.stage_id else None
    scheduled = (
        pipeline_service.get_stage_by_key(db, stage.pipeline_id, "interview_scheduled")
        if stage
        else None
    )
    reschedule = (
        pipeline_service.get_stage_by_key(db, stage.pipeline_id, "reschedule_needed")
        if stage
        else None
    )
    modifiable = can_modify_surrogate(
        surrogate, session.user_id, session.role, db=db, org_id=session.org_id
    )
    role = session.role.value if hasattr(session.role, "value") else session.role
    modifiable = modifiable and all(
        permission_service.check_permission(db, session.org_id, session.user_id, role, permission)
        for permission in (
            POLICIES["appointments"].default,
            POLICIES["surrogates"].actions["change_status"],
        )
    )
    owner_ok = (
        not appointment or role in {"admin", "developer"} or appointment.user_id == session.user_id
    )
    sensible_stage = bool(
        stage
        and pipeline_service.get_stage_semantic_key(stage)
        in {"interview_scheduled", "reschedule_needed"}
    )
    appointment_read = (
        InterviewAppointmentRead.model_validate(appointment, from_attributes=True)
        if appointment
        else None
    )
    if appointment_read and settings.SCHEDULING_V2_ENABLED:
        appointment_read.scheduling = appointment_service.scheduling_read(
            db,
            appointment,
            can_edit=modifiable and owner_ok and sensible_stage and not surrogate.is_archived,
        )
    return SurrogateInterviewAppointmentState(
        appointment=appointment_read,
        can_manage=modifiable and owner_ok and sensible_stage and not surrogate.is_archived,
        external_sync_status=appointment_google_sync_service.status(db, appointment),
        scheduled_stage=InterviewStageRead.model_validate(scheduled, from_attributes=True)
        if scheduled and scheduled.is_active
        else None,
        reschedule_stage=InterviewStageRead.model_validate(reschedule, from_attributes=True)
        if reschedule and reschedule.is_active
        else None,
    )


def _load(db: Session, session: UserSession, surrogate_id: UUID):
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if surrogate is None:
        raise HTTPException(404, "Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    return surrogate


@router.get(
    "/{surrogate_id:uuid}/interview-appointment", response_model=SurrogateInterviewAppointmentState
)
def get_interview_appointment(
    surrogate_id: UUID,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].default)
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    return _state(db, _load(db, session, surrogate_id), session)


@router.get(
    "/{surrogate_id:uuid}/interview-appointment/slots",
    response_model=InterviewSlotsRead,
    dependencies=[Depends(require_permission(POLICIES["appointments"].default))],
)
def get_interview_slots(
    surrogate_id: UUID,
    date_start: Annotated[date, Query(alias="date")],
    client_timezone: Annotated[str | None, Query()] = None,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
) -> InterviewSlotsRead:
    surrogate = _load(db, session, surrogate_id)
    if surrogate.is_archived or not can_modify_surrogate(
        surrogate, session.user_id, session.role, db=db, org_id=session.org_id
    ):
        raise HTTPException(403, "You cannot manage this interview")
    appointment = surrogate_interview_appointment_service.get_latest(
        db, session.org_id, surrogate_id
    )
    role = session.role.value if hasattr(session.role, "value") else session.role
    if (
        appointment
        and role not in {"admin", "developer"}
        and appointment.user_id != session.user_id
    ):
        raise HTTPException(403, "Only the appointment owner can manage this interview")
    try:
        timezone, slots = surrogate_interview_appointment_service.preview_slots(
            db,
            surrogate=surrogate,
            org_id=session.org_id,
            actor_user_id=session.user_id,
            date_start=date_start,
            client_timezone=client_timezone,
        )
    except CalendarAvailabilityUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return InterviewSlotsRead(
        timezone=timezone,
        slots=[InterviewSlotRead(start=slot.start, end=slot.end) for slot in slots],
    )


@router.post(
    "/{surrogate_id:uuid}/interview-appointment",
    response_model=SurrogateInterviewAppointmentState,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["appointments"].default)),
    ],
)
def manage_interview_appointment(
    surrogate_id: UUID,
    data: SurrogateInterviewAppointmentAction,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    surrogate = _load(db, session, surrogate_id)
    if not can_modify_surrogate(
        surrogate, session.user_id, session.role, db=db, org_id=session.org_id
    ):
        raise HTTPException(403, "You cannot modify this surrogate")
    try:
        surrogate = surrogate_interview_appointment_service.manage(
            db,
            org_id=session.org_id,
            surrogate_id=surrogate_id,
            actor_user_id=session.user_id,
            actor_role=session.role,
            data=data,
        )
    except surrogate_interview_appointment_service.InterviewAppointmentError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return _state(db, surrogate, session)


@router.post(
    "/{surrogate_id:uuid}/interview-appointment/sync/retry",
    response_model=SurrogateInterviewAppointmentState,
    dependencies=[
        Depends(require_csrf_header),
        Depends(require_permission(POLICIES["appointments"].default)),
    ],
)
def retry_interview_google_sync(
    surrogate_id: UUID,
    data: InterviewGoogleSyncCheck,
    session: Annotated[UserSession, "fastapi_param"] = Depends(
        require_permission(POLICIES["surrogates"].actions["change_status"])
    ),
    db: Annotated[Session, "fastapi_param"] = Depends(get_db),
):
    surrogate = _load(db, session, surrogate_id)
    if not can_modify_surrogate(
        surrogate, session.user_id, session.role, db=db, org_id=session.org_id
    ):
        raise HTTPException(403, "You cannot modify this surrogate")
    db.refresh(surrogate, with_for_update=True)
    if surrogate.is_archived:
        raise HTTPException(403, "Archived surrogates cannot manage appointments")
    appointment = surrogate_interview_appointment_service.get_latest(
        db, session.org_id, surrogate_id
    )
    if appointment is None or appointment.id != data.expected_appointment_id:
        raise HTTPException(409, "Interview appointment changed; refresh and try again")
    db.refresh(appointment, with_for_update=True)
    if appointment.id != data.expected_appointment_id:
        raise HTTPException(409, "Interview appointment changed; refresh and try again")
    if appointment.user_id != session.user_id and session.role not in {"admin", "developer"}:
        raise HTTPException(403, "Only the appointment owner can manage this interview")
    try:
        appointment_google_sync_service.retry(db, appointment)
    except appointment_google_sync_service.GoogleLinkError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    return _state(db, surrogate, session)
