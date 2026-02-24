"""Surrogate access control - centralized permission checks for surrogate operations.

Access is now owner-based (Salesforce-style):
- owner_type="queue": any case_manager+ can access/claim
- owner_type="user": owner, managers, or same-role users can access

Permission-based filtering:
- view_post_approval_surrogates: controls access to post_approval stage surrogates
"""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.enums import OwnerType, Role, SurrogateStatus
from app.db.models import Surrogate


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
    # Normalize role to string
    role_str = user_role.value if hasattr(user_role, "value") else user_role

    # Developers bypass all checks (immutable super-admin)
    if role_str == Role.DEVELOPER.value:
        return

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

    _check_owner_based_access(surrogate, role_str, user_id, db=db, org_id=org_id)


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
    from app.services import pipeline_service, permission_service

    stage = pipeline_service.get_stage_by_id(db, surrogate.stage_id)

    # No stage or not post_approval = no restriction
    if not stage or stage.stage_type != "post_approval":
        return

    # Owners can always view their own surrogates even after post-approval
    if (
        surrogate.owner_type == OwnerType.USER.value
        and surrogate.owner_id == user_id
    ):
        return

    # Check permission
    if not permission_service.check_permission(
        db, org_id, user_id, role_str, "view_post_approval_surrogates"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to post-approval surrogates",
        )


def _check_owner_based_access(
    surrogate: Surrogate,
    role_str: str,
    user_id: UUID | None,
    *,
    db: Session | None = None,
    org_id: UUID | None = None,
) -> None:
    """Owner-based access check."""

    # Queue-owned surrogates: case_manager+ can access
    if surrogate.owner_type == OwnerType.QUEUE.value:
        if role_str == Role.CASE_MANAGER.value:
            return  # Case managers can see queue items
        if role_str == Role.INTAKE_SPECIALIST.value:
            # Intake can see the system Unassigned queue and surrogates they follow.
            if not db or not org_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this surrogate",
                )
            from app.services import queue_service

            default_queue = queue_service.get_or_create_default_queue(db, org_id)
            if default_queue and surrogate.owner_id == default_queue.id:
                return
            if _intake_has_follow_access(db, surrogate, org_id, user_id):
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this surrogate",
            )
        return

    # User-owned surrogates
    if surrogate.owner_type == OwnerType.USER.value:
        # Owner can always access
        if user_id and surrogate.owner_id == user_id:
            return

        # Case managers can see other case manager's surrogates
        if role_str == Role.CASE_MANAGER.value:
            return

        # Intake specialists can see their own surrogates and surrogates they follow.
        if role_str == Role.INTAKE_SPECIALIST.value:
            if user_id and surrogate.owner_id == user_id:
                return
            if db and org_id and _intake_has_follow_access(db, surrogate, org_id, user_id):
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this surrogate",
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
            PipelineStage.slug == SurrogateStatus.APPROVED.value,
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
    - Manager+ can always modify
    - Owner can modify
    - Case managers can modify any non-archived surrogate
    - Intake specialists can modify their own surrogates and surrogates they follow

    Returns:
        True if user can modify, False otherwise
    """
    # Normalize
    role_str = user_role.value if hasattr(user_role, "value") else user_role
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

    # Archived surrogates: only managers
    if surrogate.is_archived:
        return role_str in [Role.ADMIN.value, Role.DEVELOPER.value]

    # Manager+ can always modify
    if role_str in [Role.ADMIN.value, Role.DEVELOPER.value]:
        return True

    # Owner can modify
    if surrogate.owner_id == user_uuid:
        return True

    # Case managers can modify non-archived surrogates
    if role_str == Role.CASE_MANAGER.value:
        return True

    # Intake specialists: only their own, and not handed off
    if role_str == Role.INTAKE_SPECIALIST.value:
        if db and org_id and _intake_has_follow_access(db, surrogate, org_id, user_uuid):
            return True
        return surrogate.owner_type == OwnerType.USER.value and surrogate.owner_id == user_uuid

    return False


def can_access_surrogate(
    surrogate: Surrogate,
    user_role: Role | str,
    user_id: UUID | None = None,
) -> bool:
    """
    Non-raising version of check_surrogate_access for filtering.

    Returns True if user can access, False otherwise.
    """
    try:
        check_surrogate_access(surrogate, user_role, user_id)
        return True
    except HTTPException:
        return False
