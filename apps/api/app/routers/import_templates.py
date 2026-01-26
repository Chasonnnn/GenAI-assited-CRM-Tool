"""Import template endpoints for CSV imports."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.schemas.auth import UserSession
from app.schemas.import_template import (
    ImportTemplateCreate,
    ImportTemplateRead,
    ImportTemplateUpdate,
)
from app.services import import_template_service


class ImportTemplateCloneRequest(BaseModel):
    name: str


router = APIRouter(
    prefix="/import-templates",
    tags=["import-templates"],
    dependencies=[Depends(require_permission(POLICIES["surrogates"].actions["import"]))],
)


@router.get("", response_model=list[ImportTemplateRead])
def list_templates(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    return import_template_service.list_templates(db, session.org_id)


@router.post(
    "",
    response_model=ImportTemplateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def create_template(
    body: ImportTemplateCreate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    template = import_template_service.create_template(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        encoding=body.encoding,
        delimiter=body.delimiter,
        has_header=body.has_header,
        column_mappings=[m.model_dump() for m in body.column_mappings],
        transformations=body.transformations,
        unknown_column_behavior=body.unknown_column_behavior,
    )
    return template


@router.get("/{template_id:uuid}", response_model=ImportTemplateRead)
def get_template(
    template_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    template = import_template_service.get_template(db, session.org_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Import template not found")
    return template


@router.patch(
    "/{template_id:uuid}",
    response_model=ImportTemplateRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_template(
    template_id: UUID,
    body: ImportTemplateUpdate,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    template = import_template_service.get_template(db, session.org_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Import template not found")
    template = import_template_service.update_template(
        db=db,
        template=template,
        name=body.name,
        description=body.description,
        is_default=body.is_default,
        encoding=body.encoding,
        delimiter=body.delimiter,
        has_header=body.has_header,
        column_mappings=[m.model_dump() for m in body.column_mappings]
        if body.column_mappings is not None
        else None,
        transformations=body.transformations,
        unknown_column_behavior=body.unknown_column_behavior,
    )
    return template


@router.post(
    "/{template_id:uuid}/clone",
    response_model=ImportTemplateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def clone_template(
    template_id: UUID,
    body: ImportTemplateCloneRequest,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    template = import_template_service.get_template(db, session.org_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Import template not found")
    clone = import_template_service.clone_template(
        db=db,
        template=template,
        name=body.name,
        user_id=session.user_id,
    )
    return clone


@router.delete(
    "/{template_id:uuid}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_template(
    template_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    template = import_template_service.get_template(db, session.org_id, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Import template not found")
    import_template_service.delete_template(db, template)
