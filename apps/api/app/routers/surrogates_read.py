"""Surrogates read-only routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_session, get_db, require_permission
from app.core.policies import POLICIES
from app.core.surrogate_access import check_surrogate_access
from app.db.enums import AuditEventType, Role, SurrogateSource
from app.db.models import User
from app.schemas.auth import UserSession
from app.schemas.surrogate import (
    SurrogateActivityRead,
    SurrogateActivityResponse,
    SurrogateListResponse,
    SurrogateRead,
    SurrogateStats,
    SurrogateStatusHistoryRead,
)
from app.services import surrogate_service
from app.utils.pagination import DEFAULT_PER_PAGE, MAX_PER_PAGE

from .surrogates_shared import _surrogate_to_list_item, _surrogate_to_read

router = APIRouter()


@router.get("/stats", response_model=SurrogateStats)
def get_surrogate_stats(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    pipeline_id: UUID | None = Query(None, description="Filter by pipeline UUID"),
    owner_id: UUID | None = Query(None, description="Filter by owner UUID"),
):
    """Get aggregated surrogate statistics for dashboard with period comparisons."""
    if (
        owner_id
        and owner_id != session.user_id
        and session.role not in (Role.ADMIN, Role.DEVELOPER)
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view other users' stats")

    stats = surrogate_service.get_surrogate_stats(
        db,
        session.org_id,
        pipeline_id=pipeline_id,
        owner_id=owner_id,
    )

    return SurrogateStats(
        total=stats["total"],
        by_status=stats["by_status"],
        this_week=stats["this_week"],
        last_week=stats["last_week"],
        week_change_pct=stats["week_change_pct"],
        this_month=stats["this_month"],
        last_month=stats["last_month"],
        month_change_pct=stats["month_change_pct"],
        pending_tasks=stats["pending_tasks"],
    )


@router.get("/assignees")
def get_assignees(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get list of org members who can be assigned surrogates."""
    return surrogate_service.list_assignees(db, session.org_id)


def list_surrogates(
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    cursor: str | None = Query(None, description="Cursor for keyset pagination"),
    stage_id: UUID | None = None,
    source: SurrogateSource | None = None,
    owner_id: UUID | None = None,
    q: str | None = Query(None, max_length=100),
    include_archived: bool = False,
    queue_id: UUID | None = None,
    owner_type: str | None = Query(None, pattern="^(user|queue)$"),
    created_from: str | None = Query(None, description="Filter by creation date from (ISO format)"),
    created_to: str | None = Query(None, description="Filter by creation date to (ISO format)"),
    sort_by: str | None = Query(None, description="Column to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
) -> SurrogateListResponse:
    """List surrogates with filters and pagination."""
    from app.services import audit_service, permission_service
    from app.db.models import SurrogateActivityLog
    from sqlalchemy import func

    exclude_stage_types = []
    if not permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        "view_post_approval_surrogates",
    ):
        exclude_stage_types.append("post_approval")

    try:
        surrogates, total, next_cursor = surrogate_service.list_surrogates(
            db=db,
            org_id=session.org_id,
            page=page,
            per_page=per_page,
            cursor=cursor,
            stage_id=stage_id,
            source=source,
            owner_id=owner_id,
            q=q,
            include_archived=include_archived,
            role_filter=session.role,
            user_id=session.user_id,
            owner_type=owner_type,
            queue_id=queue_id,
            created_from=created_from,
            created_to=created_to,
            exclude_stage_types=exclude_stage_types if exclude_stage_types else None,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    q_type = None
    if q:
        if "@" in q:
            q_type = "email"
        else:
            digit_count = sum(1 for ch in q if ch.isdigit())
            q_type = "phone" if digit_count >= 7 else "text"

    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate_list",
        target_id=None,
        request=request,
        details={
            "count": len(surrogates),
            "page": page,
            "per_page": per_page,
            "include_archived": include_archived,
            "stage_id": str(stage_id) if stage_id else None,
            "owner_id": str(owner_id) if owner_id else None,
            "owner_type": owner_type,
            "queue_id": str(queue_id) if queue_id else None,
            "source": source.value if source else None,
            "q_type": q_type,
            "created_from": created_from,
            "created_to": created_to,
        },
    )
    db.commit()

    surrogate_ids = [surrogate.id for surrogate in surrogates]
    last_activity_map = {}
    if surrogate_ids:
        last_activity_rows = (
            db.query(
                SurrogateActivityLog.surrogate_id,
                func.max(SurrogateActivityLog.created_at),
            )
            .filter(
                SurrogateActivityLog.organization_id == session.org_id,
                SurrogateActivityLog.surrogate_id.in_(surrogate_ids),
            )
            .group_by(SurrogateActivityLog.surrogate_id)
            .all()
        )
        last_activity_map = {row[0]: row[1] for row in last_activity_rows}

    return SurrogateListResponse(
        items=[
            _surrogate_to_list_item(s, db, last_activity_at=last_activity_map.get(s.id))
            for s in surrogates
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        next_cursor=next_cursor,
    )


@router.get("/claim-queue", response_model=SurrogateListResponse)
def list_claim_queue(
    session: UserSession = Depends(
        require_permission(POLICIES["surrogates"].actions["view_post_approval"])
    ),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """List approved surrogates in Surrogate Pool (ready for claim)."""
    surrogates, total = surrogate_service.list_claim_queue(
        db=db,
        org_id=session.org_id,
        page=page,
        per_page=per_page,
    )

    pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return SurrogateListResponse(
        items=[_surrogate_to_list_item(s, db) for s in surrogates],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{surrogate_id:uuid}", response_model=SurrogateRead)
def get_surrogate(
    surrogate_id: UUID,
    request: Request,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get surrogate by ID (respects permission-based access)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    from app.services import audit_service

    audit_service.log_event(
        db=db,
        org_id=session.org_id,
        event_type=AuditEventType.DATA_VIEW_SURROGATE,
        actor_user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
    )
    audit_service.log_phi_access(
        db=db,
        org_id=session.org_id,
        user_id=session.user_id,
        target_type="surrogate",
        target_id=surrogate.id,
        request=request,
        details={"view": "surrogate_detail"},
    )
    db.commit()

    return _surrogate_to_read(surrogate, db)


@router.get("/{surrogate_id:uuid}/history", response_model=list[SurrogateStatusHistoryRead])
def get_surrogate_history(
    surrogate_id: UUID,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get status change history for a surrogate."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    history = surrogate_service.get_status_history(db, surrogate_id, session.org_id)

    user_ids = {h.changed_by_user_id for h in history if h.changed_by_user_id}
    users_by_id: dict[UUID, str | None] = {}
    if user_ids:
        users_by_id = {
            user.id: user.display_name
            for user in db.query(User).filter(User.id.in_(user_ids)).all()
        }

    result = []
    for h in history:
        changed_by_name = users_by_id.get(h.changed_by_user_id)

        result.append(
            SurrogateStatusHistoryRead(
                id=h.id,
                from_stage_id=h.from_stage_id,
                to_stage_id=h.to_stage_id,
                from_label_snapshot=h.from_label_snapshot,
                to_label_snapshot=h.to_label_snapshot,
                changed_by_user_id=h.changed_by_user_id,
                changed_by_name=changed_by_name,
                reason=h.reason,
                changed_at=h.changed_at,
            )
        )

    return result


@router.get("/{surrogate_id:uuid}/activity", response_model=SurrogateActivityResponse)
def get_surrogate_activity(
    surrogate_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Get comprehensive activity log for a surrogate (paginated)."""
    surrogate = surrogate_service.get_surrogate(db, session.org_id, surrogate_id)
    if not surrogate:
        raise HTTPException(status_code=404, detail="Surrogate not found")

    check_surrogate_access(surrogate, session.role, session.user_id, db=db, org_id=session.org_id)

    items_data, total = surrogate_service.list_surrogate_activity(
        db=db,
        org_id=session.org_id,
        surrogate_id=surrogate_id,
        page=page,
        per_page=per_page,
    )
    pages = (total + per_page - 1) // per_page if total > 0 else 1

    items = [
        SurrogateActivityRead(
            id=item["id"],
            activity_type=item["activity_type"],
            actor_user_id=item["actor_user_id"],
            actor_name=item["actor_name"],
            details=item["details"],
            created_at=item["created_at"],
        )
        for item in items_data
    ]

    return SurrogateActivityResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )
