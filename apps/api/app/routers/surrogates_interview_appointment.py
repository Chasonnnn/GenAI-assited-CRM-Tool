"""Surrogate initial interview appointment routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.schemas.auth import UserSession
from app.schemas.interview_appointment import (
    InterviewAppointmentRead,
    InterviewStageRead,
    SurrogateInterviewAppointmentAction,
    SurrogateInterviewAppointmentState,
)
from app.services import (
    permission_service,
    pipeline_service,
    surrogate_interview_appointment_service,
    surrogate_service,
)

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
    return SurrogateInterviewAppointmentState(
        appointment=InterviewAppointmentRead.model_validate(appointment, from_attributes=True)
        if appointment
        else None,
        can_manage=modifiable and owner_ok and sensible_stage and not surrogate.is_archived,
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
