"""Donor HTTP endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_session,
    get_db,
    require_csrf_header,
    require_permission,
)
from app.core.permissions import PermissionKey
from app.core.policies import POLICIES
from app.db.enums import AuditEventType, EntityType, Role
from app.schemas.activity import EntityActivityRead, EntityActivityResponse
from app.schemas.auth import UserSession
from app.schemas.donor import (
    DonorCreate,
    DonorListResponse,
    DonorRead,
    DonorStatusChangeResponse,
    DonorStatusHistoryRead,
    DonorStatusUpdate,
    DonorUpdate,
)
from app.schemas.entity_note import EntityNoteCreate, EntityNoteListItem, EntityNoteRead
from app.services import (
    audit_service,
    donor_service,
    entity_activity_service,
    note_service,
    permission_service,
    phi_access_service,
    user_service,
)

router = APIRouter(
    prefix="/donors",
    tags=["Donors"],
    dependencies=[Depends(require_permission(POLICIES["donors"].default))],
)


def _get_or_404(db: Session, org_id: UUID, donor_id: UUID):
    donor = donor_service.get_donor(db, org_id, donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor not found")
    return donor


def _raise_domain_error(exc: ValueError) -> None:
    status_code = (
        status.HTTP_409_CONFLICT
        if isinstance(exc, donor_service.DonorConflictError)
        else status.HTTP_400_BAD_REQUEST
    )
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("", response_model=DonorListResponse)
def list_donors(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
    donor_type: Literal["egg", "sperm"] | None = None,
    stage_id: UUID | None = None,
    state: str | None = None,
    q: str | None = None,
    owner_id: UUID | None = None,
    dynamic_filter: Literal["attention_stuck"] | None = None,
    created_from: Annotated[
        str | None,
        Query(description="Filter by creation date from (ISO format)"),
    ] = None,
    created_to: Annotated[
        str | None,
        Query(description="Filter by creation date to (ISO format)"),
    ] = None,
    sort_by: Literal[
        "donor_number",
        "full_name",
        "state",
        "education",
        "stage",
        "created_at",
    ]
    | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
    include_archived: bool = False,
    archived_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DonorListResponse:
    try:
        items, total = donor_service.list_donors(
            db,
            session.org_id,
            donor_type=donor_type,
            stage_id=stage_id,
            state=state,
            q=q,
            owner_id=owner_id,
            dynamic_filter=dynamic_filter,
            created_from=created_from,
            created_to=created_to,
            sort_by=sort_by,
            sort_order=sort_order,
            include_archived=include_archived,
            archived_only=archived_only,
            page=page,
            per_page=per_page,
        )
    except ValueError as exc:
        _raise_domain_error(exc)
    phi_access_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="donor_list",
        target_id=None,
        request=request,
        query=q,
        details={"count": len(items), "donor_type": donor_type},
    )
    return DonorListResponse(
        items=[DonorRead.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.post(
    "",
    response_model=DonorRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_donor(
    request: Request,
    data: DonorCreate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["edit"])),
    ],
) -> DonorRead:
    try:
        donor = donor_service.create_donor(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            data=data,
            request=request,
        )
    except ValueError as exc:
        _raise_domain_error(exc)
    return DonorRead.model_validate(donor)


@router.get("/{donor_id}", response_model=DonorRead)
def get_donor(
    donor_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> DonorRead:
    donor = _get_or_404(db, session.org_id, donor_id)
    phi_access_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="donor",
        target_id=donor.id,
        request=request,
        details={"view": "donor_detail"},
    )
    return DonorRead.model_validate(donor)


@router.patch(
    "/{donor_id}",
    response_model=DonorRead,
    dependencies=[Depends(require_csrf_header)],
)
def update_donor(
    donor_id: UUID,
    request: Request,
    data: DonorUpdate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["edit"])),
    ],
) -> DonorRead:
    donor = _get_or_404(db, session.org_id, donor_id)
    try:
        updated = donor_service.update_donor(db, donor, session.user_id, data, request)
    except ValueError as exc:
        _raise_domain_error(exc)
    return DonorRead.model_validate(updated)


@router.post(
    "/{donor_id}/archive",
    response_model=DonorRead,
    dependencies=[Depends(require_csrf_header)],
)
def archive_donor(
    donor_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["archive"])),
    ],
) -> DonorRead:
    donor = _get_or_404(db, session.org_id, donor_id)
    try:
        archived = donor_service.archive_donor(db, donor, session.user_id, request)
    except ValueError as exc:
        _raise_domain_error(exc)
    return DonorRead.model_validate(archived)


@router.post(
    "/{donor_id}/restore",
    response_model=DonorRead,
    dependencies=[Depends(require_csrf_header)],
)
def restore_donor(
    donor_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["archive"])),
    ],
) -> DonorRead:
    donor = _get_or_404(db, session.org_id, donor_id)
    try:
        restored = donor_service.restore_donor(db, donor, session.user_id, request)
    except ValueError as exc:
        _raise_domain_error(exc)
    return DonorRead.model_validate(restored)


@router.patch(
    "/{donor_id}/status",
    response_model=DonorStatusChangeResponse,
    dependencies=[Depends(require_csrf_header)],
)
def update_donor_status(
    donor_id: UUID,
    request: Request,
    data: DonorStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["change_status"])),
    ],
) -> DonorStatusChangeResponse:
    donor = _get_or_404(db, session.org_id, donor_id)
    try:
        result = donor_service.change_status(
            db,
            donor,
            data.stage_id,
            session.user_id,
            reason=data.reason,
            effective_at=data.effective_at,
            request=request,
            user_role=session.role,
        )
    except ValueError as exc:
        _raise_domain_error(exc)
    return DonorStatusChangeResponse(
        status=result["status"],
        donor=DonorRead.model_validate(result["donor"]) if result["donor"] else None,
        history=(
            DonorStatusHistoryRead.model_validate(result["history"]) if result["history"] else None
        ),
        request_id=result["request_id"],
        message=result["message"],
    )


@router.get("/{donor_id}/history", response_model=list[DonorStatusHistoryRead])
def get_donor_history(
    donor_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> list[DonorStatusHistoryRead]:
    _get_or_404(db, session.org_id, donor_id)
    history = donor_service.get_status_history(db, session.org_id, donor_id)
    user_ids = {
        user_id
        for item in history
        for user_id in (item.changed_by_user_id, item.approved_by_user_id)
        if user_id
    }
    display_names = user_service.get_display_names_by_ids(db, user_ids)
    return [
        DonorStatusHistoryRead(
            id=item.id,
            donor_id=item.donor_id,
            changed_by_user_id=item.changed_by_user_id,
            changed_by_name=display_names.get(item.changed_by_user_id),
            old_stage_id=item.old_stage_id,
            new_stage_id=item.new_stage_id,
            old_status=item.old_status,
            new_status=item.new_status,
            old_label_snapshot=item.old_label_snapshot,
            new_label_snapshot=item.new_label_snapshot,
            reason=item.reason,
            effective_at=item.effective_at,
            recorded_at=item.recorded_at,
            requested_at=item.requested_at,
            approved_by_user_id=item.approved_by_user_id,
            approved_by_name=display_names.get(item.approved_by_user_id),
            approved_at=item.approved_at,
            is_undo=item.is_undo,
            request_id=item.request_id,
        )
        for item in history
    ]


@router.get("/{donor_id}/activity", response_model=EntityActivityResponse)
def get_donor_activity(
    donor_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EntityActivityResponse:
    donor = _get_or_404(db, session.org_id, donor_id)
    can_view_task_previews = permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        PermissionKey.TASKS_VIEW.value,
    )
    items, total = entity_activity_service.list_entity_activity(
        db,
        org_id=session.org_id,
        entity_type="donor",
        entity_id=donor.id,
        page=page,
        per_page=per_page,
        include_note_previews=True,
        include_task_previews=can_view_task_previews,
    )
    note_preview_count = sum(
        1
        for item in items
        if item["activity_type"] in {"note_added", "note_deleted"}
        and isinstance(item["details"], dict)
        and "preview" in item["details"]
    )
    task_preview_count = sum(
        1
        for item in items
        if item["activity_type"].startswith("task_")
        and isinstance(item["details"], dict)
        and "title" in item["details"]
    )
    if note_preview_count:
        audit_service.log_event(
            db=db,
            org_id=session.org_id,
            event_type=AuditEventType.DATA_VIEW_NOTE,
            actor_user_id=session.user_id,
            target_type="donor",
            target_id=donor.id,
            details={"view": "activity", "notes_count": note_preview_count},
            request=request,
        )
        audit_service.log_phi_access(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            target_type="donor",
            target_id=donor.id,
            request=request,
            details={"view": "activity_notes", "notes_count": note_preview_count},
        )
    if task_preview_count:
        audit_service.log_phi_access(
            db=db,
            org_id=session.org_id,
            user_id=session.user_id,
            target_type="donor",
            target_id=donor.id,
            request=request,
            details={"view": "activity_tasks", "tasks_count": task_preview_count},
        )
    if note_preview_count or task_preview_count:
        db.commit()
    return EntityActivityResponse(
        items=[EntityActivityRead(**item) for item in items],
        total=total,
        page=page,
        pages=(total + per_page - 1) // per_page if total else 1,
    )


@router.get("/{donor_id}/notes", response_model=list[EntityNoteListItem])
def list_donor_notes(
    donor_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession, Depends(get_current_session)],
) -> list[EntityNoteListItem]:
    donor = _get_or_404(db, session.org_id, donor_id)
    notes = note_service.list_notes(db, session.org_id, EntityType.DONOR, donor.id)
    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_VIEW_NOTE,
        actor_user_id=session.user_id,
        target_type="donor",
        target_id=donor.id,
        details={"notes_count": len(notes)},
        request=request,
    )
    phi_access_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="donor",
        target_id=donor.id,
        request=request,
        details={"view": "notes", "notes_count": len(notes)},
    )
    db.commit()
    return [EntityNoteListItem.model_validate(note) for note in notes]


@router.post(
    "/{donor_id}/notes",
    response_model=EntityNoteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_header)],
)
def create_donor_note(
    donor_id: UUID,
    data: EntityNoteCreate,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["edit"])),
    ],
) -> EntityNoteRead:
    donor = _get_or_404(db, session.org_id, donor_id)
    note = note_service.create_note(
        db=db,
        org_id=session.org_id,
        entity_type=EntityType.DONOR,
        entity_id=donor.id,
        author_id=session.user_id,
        content=data.content,
    )
    return EntityNoteRead.model_validate(note)


@router.delete(
    "/{donor_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_donor_note(
    donor_id: UUID,
    note_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[
        UserSession,
        Depends(require_permission(POLICIES["donors"].actions["edit"])),
    ],
) -> Response:
    donor = _get_or_404(db, session.org_id, donor_id)
    note = note_service.get_note(db, note_id, session.org_id)
    if not note or note.entity_type != EntityType.DONOR.value or note.entity_id != donor.id:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.author_id != session.user_id and session.role not in (
        Role.ADMIN,
        Role.DEVELOPER,
    ):
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    note_service.delete_note(db, note, actor_user_id=session.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
