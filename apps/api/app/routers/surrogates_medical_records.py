"""Surrogate medical record routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header
from app.core.policies import POLICIES
from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.db.models import Surrogate
from app.routers.medical_records_shared import raise_medical_record_error
from app.schemas.auth import UserSession
from app.schemas.medical_record import (
    MedicalRecordArchive,
    MedicalRecordCreate,
    MedicalRecordListResponse,
    MedicalRecordRestore,
    MedicalRecordSection,
    MedicalRecordUpdate,
)
from app.services import (
    audit_service,
    medical_record_service,
    permission_service,
    surrogate_service,
)
from app.services.medical_record_service import RecordOwner

router = APIRouter()


def _readable_surrogate(db: Session, session: UserSession, surrogate_id: UUID) -> Surrogate:
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")
    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)
    return surrogate


def _editable_surrogate(db: Session, session: UserSession, surrogate_id: UUID) -> Surrogate:
    surrogate = _readable_surrogate(db, session, surrogate_id)
    edit_permission = POLICIES["surrogates"].actions["edit"].value
    if not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, edit_permission
    ):
        raise HTTPException(status_code=403, detail=f"Missing permission: {edit_permission}")
    if not can_modify_surrogate(
        surrogate, str(session.user_id), session.role, db=db, org_id=session.org_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized to update this surrogate")
    return surrogate


def _committed_list(db: Session, owner: RecordOwner) -> MedicalRecordListResponse:
    db.commit()
    return medical_record_service.list_records(db, owner)


@router.get("/{surrogate_id:uuid}/medical-records", response_model=MedicalRecordListResponse)
def list_medical_records(
    surrogate_id: UUID,
    request: Request,
    response: Response,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordListResponse:
    surrogate = _readable_surrogate(db, session, surrogate_id)
    response.headers["Cache-Control"] = "no-store"
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
        details={"view": "surrogate_medical_records"},
    )
    return _committed_list(db, RecordOwner.for_surrogate(surrogate))


@router.post(
    "/{surrogate_id:uuid}/medical-records",
    response_model=MedicalRecordListResponse,
    dependencies=[Depends(require_csrf_header)],
)
def create_medical_record(
    surrogate_id: UUID,
    data: MedicalRecordCreate,
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordListResponse:
    owner = RecordOwner.for_surrogate(_editable_surrogate(db, session, surrogate_id))
    try:
        with db.begin_nested():
            medical_record_service.create_record(db, owner, session.user_id, data, request=request)
    except medical_record_service.MedicalRecordError as exc:
        raise_medical_record_error(exc)
    return _committed_list(db, owner)


@router.patch(
    "/{surrogate_id:uuid}/medical-records/{record_id:uuid}",
    response_model=MedicalRecordListResponse,
    dependencies=[Depends(require_csrf_header)],
)
def correct_medical_record(
    surrogate_id: UUID,
    record_id: UUID,
    data: MedicalRecordUpdate,
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordListResponse:
    owner = RecordOwner.for_surrogate(_editable_surrogate(db, session, surrogate_id))
    try:
        with db.begin_nested():
            medical_record_service.correct_record(
                db, owner, session.user_id, record_id, data, request=request
            )
    except medical_record_service.MedicalRecordError as exc:
        raise_medical_record_error(exc)
    return _committed_list(db, owner)


@router.post(
    "/{surrogate_id:uuid}/medical-records/{record_id:uuid}/archive",
    response_model=MedicalRecordListResponse,
    dependencies=[Depends(require_csrf_header)],
)
def archive_medical_record(
    surrogate_id: UUID,
    record_id: UUID,
    data: MedicalRecordArchive,
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordListResponse:
    owner = RecordOwner.for_surrogate(_editable_surrogate(db, session, surrogate_id))
    try:
        with db.begin_nested():
            medical_record_service.archive_record(
                db, owner, session.user_id, record_id, data.expected_revision, request=request
            )
    except medical_record_service.MedicalRecordError as exc:
        raise_medical_record_error(exc)
    return _committed_list(db, owner)


@router.post(
    "/{surrogate_id:uuid}/medical-records/sections/{section}/restore",
    response_model=MedicalRecordListResponse,
    dependencies=[Depends(require_csrf_header)],
)
def restore_medical_section(
    surrogate_id: UUID,
    section: MedicalRecordSection,
    data: MedicalRecordRestore,
    request: Request,
    session: Annotated[UserSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordListResponse:
    owner = RecordOwner.for_surrogate(_editable_surrogate(db, session, surrogate_id))
    try:
        with db.begin_nested():
            medical_record_service.restore_section(
                db, owner, session.user_id, section, data.idempotency_key, request=request
            )
    except medical_record_service.MedicalRecordError as exc:
        raise_medical_record_error(exc)
    return _committed_list(db, owner)
