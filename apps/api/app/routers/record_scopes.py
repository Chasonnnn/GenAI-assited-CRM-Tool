"""Staff record scope settings and Intake collaborators."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_csrf_header
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.schemas.record_scope import (
    CheckRecordAccessRequest,
    CollaboratorCreate,
    CollaboratorOption,
    CollaboratorRead,
    HandoffMigrationReviewRequest,
    LegacyPoolResolutionRequest,
    RecordAccessExplanation,
    RecordKind,
    RecordModule,
    RecordScopeAdditionCreate,
    RecordScopeAdditionRead,
    RecordScopeRule,
)
from app.services import record_scope_service

router = APIRouter(prefix="/record-scopes", tags=["Record scope"])
DB = Annotated[Session, Depends(get_db)]
Staff = Annotated[UserSession, Depends(get_current_session)]


def _admin(session):
    if session.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(
            status_code=403, detail="Only admins and developers can configure record scope"
        )


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/roles/{role}", response_model=dict[str, RecordScopeRule])
def get_role_scopes(role: Role, db: DB, session: Staff):
    _admin(session)
    return {
        module: record_scope_service.get_role_scope(db, session.org_id, role, module)
        for module in record_scope_service.MODULE_KINDS
    }


@router.put(
    "/roles/{role}/{module}",
    response_model=RecordScopeRule,
    dependencies=[Depends(require_csrf_header)],
)
def update_role_scope(
    role: Role, module: RecordModule, body: RecordScopeRule, db: DB, session: Staff
):
    return _call(record_scope_service.save_role_scope, db, session, role, module, body)


@router.get("/members/{user_id}/additions", response_model=list[RecordScopeAdditionRead])
def get_member_additions(user_id: UUID, db: DB, session: Staff):
    _admin(session)
    return _call(record_scope_service.list_scope_additions, db, session.org_id, user_id)


@router.post(
    "/members/{user_id}/additions",
    response_model=RecordScopeAdditionRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def add_member_scope(user_id: UUID, body: RecordScopeAdditionCreate, db: DB, session: Staff):
    return _call(record_scope_service.add_scope_addition, db, session, user_id, body)


@router.delete(
    "/members/{user_id}/additions/{addition_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_member_scope(user_id: UUID, addition_id: UUID, db: DB, session: Staff) -> Response:
    _call(record_scope_service.remove_scope_addition, db, session, user_id, addition_id)
    return Response(status_code=204)


@router.get("/records/{kind}/{record_id}/collaborators", response_model=list[CollaboratorRead])
def get_collaborators(kind: RecordKind, record_id: UUID, db: DB, session: Staff):
    return _call(record_scope_service.collaborator_details, db, session, kind, record_id)


@router.get(
    "/records/{kind}/{record_id}/collaborator-options", response_model=list[CollaboratorOption]
)
def get_collaborator_options(kind: RecordKind, record_id: UUID, db: DB, session: Staff):
    return _call(record_scope_service.collaborator_options, db, session, kind, record_id)


@router.post(
    "/records/{kind}/{record_id}/collaborators",
    response_model=CollaboratorRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)
def add_collaborator(
    kind: RecordKind, record_id: UUID, body: CollaboratorCreate, db: DB, session: Staff
):
    return _call(
        record_scope_service.grant_collaborator, db, session, kind, record_id, body.user_id
    )


@router.delete(
    "/records/{kind}/{record_id}/collaborators/{user_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_header)],
)
def delete_collaborator(
    kind: RecordKind, record_id: UUID, user_id: UUID, db: DB, session: Staff
) -> Response:
    _call(record_scope_service.remove_collaborator, db, session, kind, record_id, user_id)
    return Response(status_code=204)


@router.post(
    "/check", response_model=RecordAccessExplanation, dependencies=[Depends(require_csrf_header)]
)
def check_record_scope(body: CheckRecordAccessRequest, db: DB, session: Staff):
    _admin(session)
    return _call(record_scope_service.explain_member_access, db, session.org_id, body)


@router.get("/migration-review")
def migration_review(db: DB, session: Staff) -> dict[str, object]:
    _admin(session)
    return record_scope_service.get_policy_scope_snapshot(db, session.org_id)


@router.post(
    "/migration-review/records/{kind}/{record_id}", dependencies=[Depends(require_csrf_header)]
)
def review_handoff(
    kind: RecordKind, record_id: UUID, body: HandoffMigrationReviewRequest, db: DB, session: Staff
) -> dict[str, str | bool]:
    return _call(record_scope_service.resolve_handoff_migration, db, session, kind, record_id, body)


@router.post(
    "/migration-review/pool-grants/{grant_id}", dependencies=[Depends(require_csrf_header)]
)
def review_legacy_pool(
    grant_id: UUID, body: LegacyPoolResolutionRequest, db: DB, session: Staff
) -> dict[str, bool]:
    return _call(record_scope_service.resolve_legacy_pool_grant, db, session, grant_id, body)
