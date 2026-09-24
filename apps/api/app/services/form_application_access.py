"""Scoped form metadata for a surrogate's application panel."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import FormLeadKind, FormStatus
from app.db.models import Form, FormIntakeLink
from app.schemas.auth import UserSession
from app.services import (
    form_intake_service,
    form_submission_access,
    org_service,
    permission_policy_service,
    permission_service,
    record_access_service,
)


def require_email_send(db: Session, session: UserSession) -> None:
    if permission_policy_service.is_enabled(
        db, session.org_id
    ) and not permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, "send_email"
    ):
        raise HTTPException(status_code=403, detail="Missing permission: send_email")


def _require_application_record(
    db: Session, session: UserSession, surrogate_id: UUID, *, write: bool = False
) -> None:
    if not permission_policy_service.is_enabled(db, session.org_id):
        raise HTTPException(status_code=404, detail="Scoped application access is unavailable")
    form_submission_access.require_action(db, session)
    record_access_service.get_record_with_access(
        db,
        session,
        "surrogate",
        surrogate_id,
        action="edit" if write else "view",
        allow_archived=not write,
    )
    if write:
        require_email_send(db, session)


def _published_surrogate_forms(db: Session, org_id: UUID):
    return db.query(Form).filter(
        Form.organization_id == org_id,
        Form.status == FormStatus.PUBLISHED.value,
        Form.lead_kind == FormLeadKind.SURROGATE.value,
    )


def list_application_forms(
    db: Session, session: UserSession, surrogate_id: UUID
) -> tuple[list[Form], UUID | None]:
    _require_application_record(db, session, surrogate_id)
    forms = (
        _published_surrogate_forms(db, session.org_id)
        .order_by(Form.updated_at.desc(), Form.id)
        .all()
    )
    org = org_service.get_org_by_id(db, session.org_id)
    return forms, org.default_surrogate_application_form_id if org else None


def list_application_intake_links(
    db: Session, session: UserSession, surrogate_id: UUID, form_id: UUID
) -> list[FormIntakeLink]:
    _require_application_record(db, session, surrogate_id, write=True)
    if not settings.FORMS_SHARED_INTAKE:
        raise HTTPException(status_code=404, detail="Shared intake is disabled")
    form = _published_surrogate_forms(db, session.org_id).filter(Form.id == form_id).first()
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return [
        link
        for link in form_intake_service.list_intake_links(
            db, org_id=session.org_id, form_id=form.id, include_inactive=False
        )
        if form_intake_service._is_link_publicly_available(link)
    ]
