"""Surrogate access control - centralized permission checks for surrogate operations."""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import and_, false, func, literal, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.enums import OwnerType, Role, SurrogateStatus
from app.db.models import PipelineStage, Surrogate, SurrogateStatusHistory

PRIORITY_MANAGER_ROLES = {Role.ADMIN.value, Role.DEVELOPER.value}


def _role_value(user_role: Role | str | None) -> str | None:
    return user_role.value if hasattr(user_role, "value") else user_role


def _case_manager_approved_onward_filter(surrogate_model=Surrogate) -> ColumnElement[bool]:
    """SQL filter for records at the effective `approved` stage or later."""
    current_stage = PipelineStage.__table__.alias("current_stage_access")
    paused_stage = PipelineStage.__table__.alias("paused_stage_access")
    approved_stage = PipelineStage.__table__.alias("approved_stage_access")
    effective_order = func.coalesce(paused_stage.c.order, current_stage.c.order)
    return (
        select(literal(1))
        .select_from(
            current_stage.outerjoin(
                paused_stage,
                paused_stage.c.id == surrogate_model.paused_from_stage_id,
            ).join(
                approved_stage,
                and_(
                    approved_stage.c.pipeline_id == current_stage.c.pipeline_id,
                    approved_stage.c.stage_key == SurrogateStatus.APPROVED.value,
                    approved_stage.c.is_active.is_(True),
                ),
            )
        )
        .where(
            current_stage.c.id == surrogate_model.stage_id,
            current_stage.c.is_active.is_(True),
            effective_order >= approved_stage.c.order,
        )
        .exists()
    )


def case_manager_approved_onward_joined_filter(
    surrogate_table,
    stage_table,
) -> ColumnElement[bool]:
    """SQL filter for aliases where the current stage table is already joined."""
    paused_stage = PipelineStage.__table__.alias("paused_stage_joined_access")
    approved_stage = PipelineStage.__table__.alias("approved_stage_joined_access")
    paused_order = (
        select(paused_stage.c.order)
        .where(paused_stage.c.id == surrogate_table.c.paused_from_stage_id)
        .scalar_subquery()
    )
    approved_order = (
        select(approved_stage.c.order)
        .where(
            approved_stage.c.pipeline_id == stage_table.c.pipeline_id,
            approved_stage.c.stage_key == SurrogateStatus.APPROVED.value,
            approved_stage.c.is_active.is_(True),
        )
        .scalar_subquery()
    )
    return and_(
        stage_table.c.id.isnot(None),
        func.coalesce(paused_order, stage_table.c.order) >= approved_order,
    )


def build_surrogate_visibility_filter(
    db: Session,
    org_id: UUID,
    user_role: Role | str | None,
    user_id: UUID | None,
    *,
    surrogate_model=Surrogate,
    include_unassigned_queue: bool = True,
) -> ColumnElement[bool]:
    """Build the row-level surrogate visibility filter for list/count queries."""
    role_str = _role_value(user_role)
    if role_str in (Role.ADMIN.value, Role.DEVELOPER.value):
        return true()
    if not user_id:
        return false()
    if role_str == Role.CASE_MANAGER.value:
        return _case_manager_approved_onward_filter(surrogate_model)
    if role_str != Role.INTAKE_SPECIALIST.value:
        return false()

    from app.services import intake_pool_access_service, queue_service

    owner_ids = {
        user_id,
        *intake_pool_access_service.get_source_user_ids_for_grantee(db, org_id, user_id),
    }
    owned_clause = and_(
        surrogate_model.owner_type == OwnerType.USER.value,
        surrogate_model.owner_id.in_(owner_ids),
    )
    followed_ids = (
        select(SurrogateStatusHistory.surrogate_id)
        .join(PipelineStage, SurrogateStatusHistory.to_stage_id == PipelineStage.id)
        .where(
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.changed_by_user_id == user_id,
            PipelineStage.stage_key == SurrogateStatus.APPROVED.value,
        )
    )
    clauses = [owned_clause, surrogate_model.id.in_(followed_ids)]

    if include_unassigned_queue:
        default_queue = queue_service.get_or_create_default_queue(db, org_id)
        clauses.append(
            and_(
                surrogate_model.owner_type == OwnerType.QUEUE.value,
                surrogate_model.owner_id == default_queue.id,
            )
        )

    return or_(*clauses)


def check_surrogate_access(
    surrogate: Surrogate,
    user_role: Role | str,
    user_id: UUID | None = None,
    db: Session | None = None,
    org_id: UUID | None = None,
) -> None:
    """
    Check if user can access this surrogate based on ownership and permissions.

    Access rules:
    - Developer: always allowed (no DB check)
    - Post-approval stages: requires view_post_approval_surrogates permission
    - Queue-owned: case_manager+ can see
    - User-owned: owner, or managers can see
    - Intake specialists: only their own surrogates

    Args:
        surrogate: The surrogate being accessed
        user_role: The user's role from session
        user_id: The user's ID (for ownership check)
        db: Database session (required for permission checks)
        org_id: Organization ID (required for permission checks)

    Raises:
        HTTPException: 403 if access denied
    """
    role_str = _role_value(user_role)

    # Developers bypass all checks (immutable super-admin)
    if role_str == Role.DEVELOPER.value:
        return

    if surrogate.is_archived and role_str != Role.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this surrogate",
        )

    # Permission-based check for post-approval surrogates (applies to all roles including Manager)
    if db and org_id and user_id and surrogate.stage_id:
        _check_post_approval_access(db, org_id, user_id, role_str, surrogate)

    # Manager bypass for ownership checks (but NOT for permission checks above)
    if role_str == Role.ADMIN.value:
        return

    # Owner fields are required for all surrogates
    if surrogate.owner_type is None or surrogate.owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Surrogate ownership is not set",
        )

    if not db or not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this surrogate",
        )

    if not has_surrogate_record_access(db, surrogate, role_str, user_id, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this surrogate",
        )


def can_manage_surrogate_priority(user_role: Role | str) -> bool:
    """Return True when the role can change the priority flag on a lead."""
    role_str = user_role.value if hasattr(user_role, "value") else user_role
    return role_str in PRIORITY_MANAGER_ROLES


def ensure_can_manage_surrogate_priority(user_role: Role | str) -> None:
    """Raise when the current role is not allowed to change lead priority."""
    if can_manage_surrogate_priority(user_role):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only admins and developers can manage lead priority",
    )


def has_surrogate_record_access(
    db: Session,
    surrogate: Surrogate,
    user_role: Role | str | None,
    user_id: UUID | None,
    org_id: UUID,
) -> bool:
    """Return whether the user can view this specific surrogate record."""
    role_str = _role_value(user_role)
    if role_str in (Role.ADMIN.value, Role.DEVELOPER.value):
        return True
    if not user_id:
        return False
    if surrogate.is_archived:
        return False

    if role_str == Role.CASE_MANAGER.value:
        return _is_approved_onward(db, surrogate)

    if role_str != Role.INTAKE_SPECIALIST.value:
        return False

    if surrogate.owner_type == OwnerType.USER.value:
        if surrogate.owner_id == user_id:
            return True
        from app.services import intake_pool_access_service

        if intake_pool_access_service.has_pool_access(
            db,
            org_id,
            source_user_id=surrogate.owner_id,
            grantee_user_id=user_id,
        ):
            return True

    if surrogate.owner_type == OwnerType.QUEUE.value:
        from app.services import queue_service

        default_queue = queue_service.get_or_create_default_queue(db, org_id)
        if surrogate.owner_id == default_queue.id:
            return True

    return _intake_has_follow_access(db, surrogate, org_id, user_id)


def _is_approved_onward(db: Session, surrogate: Surrogate) -> bool:
    """Return whether the surrogate's effective stage is at or after approved."""
    from app.services import pipeline_service, surrogate_stage_context

    stage = surrogate_stage_context.get_stage_context(db, surrogate).effective_stage
    if not stage:
        return False
    approved_stage = pipeline_service.get_stage_by_key(
        db,
        stage.pipeline_id,
        SurrogateStatus.APPROVED.value,
    )
    if not approved_stage:
        approved_stage = pipeline_service.get_stage_by_system_role(
            db,
            stage.pipeline_id,
            "approval_gate",
        )
    return bool(approved_stage and stage.order >= approved_stage.order)


def _check_post_approval_access(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    role_str: str,
    surrogate: Surrogate,
) -> None:
    """
    Check view_post_approval_surrogates permission if surrogate is in a post_approval stage.

    Treats missing/null stage as non-post-approval (fail open for deleted stages).
    """
    from app.services import permission_service, surrogate_stage_context

    stage = surrogate_stage_context.get_stage_context(db, surrogate).effective_stage

    # No stage or not post_approval = no restriction
    if not stage or stage.stage_type != "post_approval":
        return

    # Owners can always view their own surrogates even after post-approval
    if surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id == user_id:
        return

    # Check permission
    if not permission_service.check_permission(
        db, org_id, user_id, role_str, "view_post_approval_surrogates"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to post-approval surrogates",
        )


def _intake_has_follow_access(
    db: Session,
    surrogate: Surrogate,
    org_id: UUID,
    user_id: UUID | None,
) -> bool:
    """
    Allow intake to follow surrogates they moved to `approved`.

    Uses status history instead of activity log JSON to stay robust across ownership transfers.
    """
    if not (db and user_id):
        return False

    from app.db.models import PipelineStage, SurrogateStatusHistory

    approved_by_user = (
        db.query(SurrogateStatusHistory.id)
        .join(PipelineStage, SurrogateStatusHistory.to_stage_id == PipelineStage.id)
        .filter(
            SurrogateStatusHistory.surrogate_id == surrogate.id,
            SurrogateStatusHistory.organization_id == org_id,
            SurrogateStatusHistory.changed_by_user_id == user_id,
            PipelineStage.stage_key == SurrogateStatus.APPROVED.value,
        )
        .first()
    )
    return approved_by_user is not None


def can_modify_surrogate(
    surrogate: Surrogate,
    user_id: UUID | str,
    user_role: Role | str,
    *,
    db: Session | None = None,
    org_id: UUID | None = None,
) -> bool:
    """
    Check if user can modify this surrogate.

    Rules:
    - Admin/developer can modify any non-archived surrogate
    - Case managers can modify approved-onward surrogates they can access
    - Intake specialists can modify owned, followed, or granted-pool surrogates

    Returns:
        True if user can modify, False otherwise
    """
    role_str = _role_value(user_role)
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

    # Archived surrogates: only admins/developers
    if surrogate.is_archived:
        return role_str in [Role.ADMIN.value, Role.DEVELOPER.value]

    # Admin/developer can always modify active cases.
    if role_str in [Role.ADMIN.value, Role.DEVELOPER.value]:
        return True

    if db and org_id:
        return has_surrogate_record_access(db, surrogate, role_str, user_uuid, org_id)

    return False


def can_access_surrogate(
    surrogate: Surrogate,
    user_role: Role | str,
    user_id: UUID | None = None,
    *,
    db: Session | None = None,
    org_id: UUID | None = None,
) -> bool:
    """
    Non-raising version of check_surrogate_access for filtering.

    Returns True if user can access, False otherwise.
    """
    try:
        check_surrogate_access(surrogate, user_role, user_id, db=db, org_id=org_id)
        return True
    except HTTPException:
        return False
