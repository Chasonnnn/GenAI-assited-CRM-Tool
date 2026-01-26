"""Custom field endpoints for org-scoped field definitions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.custom_field import CustomFieldCreate, CustomFieldRead, CustomFieldUpdate
from app.services import custom_field_service


router = APIRouter(
    prefix="/custom-fields",
    tags=["custom-fields"],
    dependencies=[Depends(require_permission(POLICIES["org_settings"].default))],
)


@router.get("", response_model=list[CustomFieldRead])
def list_custom_fields(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    fields = custom_field_service.list_custom_fields(db, session.org_id)
    return fields


@router.post(
    "",
    response_model=CustomFieldRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_custom_field(
    body: CustomFieldCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    try:
        field = custom_field_service.create_custom_field(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            key=body.key,
            label=body.label,
            field_type=body.field_type,
            options=body.options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return field


@router.patch(
    "/{field_id:uuid}",
    response_model=CustomFieldRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_custom_field(
    field_id: UUID,
    body: CustomFieldUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    field = custom_field_service.get_custom_field(db, session.org_id, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    field = custom_field_service.update_custom_field(
        db=db,
        field=field,
        label=body.label,
        options=body.options,
        is_active=body.is_active,
    )
    return field


@router.delete(
    "/{field_id:uuid}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_custom_field(
    field_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    field = custom_field_service.get_custom_field(db, session.org_id, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    custom_field_service.delete_custom_field(db, field)
