"""Subject authorization shared by record capabilities."""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.policies import POLICIES
from app.core.surrogate_access import can_modify_surrogate, check_surrogate_access
from app.db.models import Donor, IntendedParent, Surrogate
from app.schemas.auth import UserSession
from app.services import permission_service

RecordKind = Literal["surrogate", "intended_parent", "donor"]
RecordAction = Literal["view", "edit"]

_RECORDS = {
    "surrogate": (Surrogate, "surrogates", "Surrogate"),
    "intended_parent": (IntendedParent, "intended_parents", "Intended parent"),
    "donor": (Donor, "donors", "Donor"),
}


def get_record_with_access(
    db: Session,
    session: UserSession,
    kind: RecordKind,
    record_id: UUID,
    *,
    action: RecordAction = "view",
    allow_archived: bool = False,
) -> Surrogate | IntendedParent | Donor:
    """Resolve under authenticated organization scope and enforce the subject policy.

    Capability-specific rules, such as attachment uploader ownership, remain with
    that capability. This operation does not commit or change the record.
    """
    definition = _RECORDS.get(kind)
    if definition is None or action not in {"view", "edit"}:
        raise HTTPException(status_code=404, detail="Record not found")
    model, resource, label = definition
    policy = POLICIES[resource]
    required = [policy.default]
    if action == "edit":
        required.append(policy.actions["edit"])
    for permission in required:
        if not permission_service.check_permission(
            db,
            session.org_id,
            session.user_id,
            session.role.value,
            permission.value,
        ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission.value}")

    record = (
        db.query(model)
        .filter(
            model.organization_id == session.org_id,
            model.id == record_id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    from app.services import permission_policy_service, record_scope_service

    if permission_policy_service.is_enabled(db, session.org_id):
        if not record_scope_service.can_access_record(
            db, session, kind, record, allow_archived=allow_archived and action == "view"
        ):
            raise HTTPException(status_code=403, detail=f"You don't have access to this {kind}")
        return record
    if isinstance(record, Surrogate):
        check_surrogate_access(
            record,
            session.role,
            session.user_id,
            db=db,
            org_id=session.org_id,
            allow_archived=allow_archived and action == "view",
        )
        if action == "edit" and not can_modify_surrogate(
            record,
            session.user_id,
            session.role,
            db=db,
            org_id=session.org_id,
        ):
            raise HTTPException(status_code=403, detail="Not authorized to modify this surrogate")
    return record
