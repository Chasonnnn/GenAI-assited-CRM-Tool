"""Case access control - centralized permission checks for case operations.

Access is now owner-based (Salesforce-style):
- owner_type="queue": any case_manager+ can access/claim
- owner_type="user": owner, managers, or same-role users can access

Permission-based filtering:
- view_post_approval_cases: controls access to post_approval stage cases
"""

from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.enums import Role, OwnerType
from app.db.models import Case


def check_case_access(
    case: Case,
    user_role: Role | str,
    user_id: UUID | None = None,
    db: Session | None = None,
    org_id: UUID | None = None,
) -> None:
    """
    Check if user can access this case based on ownership and permissions.
    
    Access rules:
    - Developer: always allowed (no DB check)
    - Post-approval stages: requires view_post_approval_cases permission
    - Queue-owned: case_manager+ can see
    - User-owned: owner, or managers can see
    - Intake specialists: only their own cases
    
    Args:
        case: The case being accessed
        user_role: The user's role from session
        user_id: The user's ID (for ownership check)
        db: Database session (required for permission checks)
        org_id: Organization ID (required for permission checks)
        
    Raises:
        HTTPException: 403 if access denied
    """
    # Normalize role to string
    role_str = user_role.value if hasattr(user_role, 'value') else user_role
    
    # Developers bypass all checks (immutable super-admin)
    if role_str == Role.DEVELOPER.value:
        return
    
    # Permission-based check for post-approval cases (applies to all roles including Manager)
    if db and org_id and user_id and case.stage_id:
        _check_post_approval_access(db, org_id, user_id, role_str, case)
    
    # Manager bypass for ownership checks (but NOT for permission checks above)
    if role_str == Role.ADMIN.value:
        return
    
    # Owner fields are required for all cases
    if case.owner_type is None or case.owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Case ownership is not set",
        )

    _check_owner_based_access(case, role_str, user_id)


def _check_post_approval_access(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    role_str: str,
    case: Case,
) -> None:
    """
    Check view_post_approval_cases permission if case is in a post_approval stage.
    
    Treats missing/null stage as non-post-approval (fail open for deleted stages).
    """
    from app.services import pipeline_service, permission_service
    
    stage = pipeline_service.get_stage_by_id(db, case.stage_id)
    
    # No stage or not post_approval = no restriction
    if not stage or stage.stage_type != "post_approval":
        return
    
    # Check permission
    if not permission_service.check_permission(
        db, org_id, user_id, role_str, "view_post_approval_cases"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to post-approval cases"
        )


def _check_owner_based_access(case: Case, role_str: str, user_id: UUID | None) -> None:
    """Owner-based access check."""
    
    # Queue-owned cases: case_manager+ can access
    if case.owner_type == OwnerType.QUEUE.value:
        if role_str == Role.CASE_MANAGER.value:
            return  # Case managers can see queue items
        if role_str == Role.INTAKE_SPECIALIST.value:
            # Intake can only see queue cases if specifically allowed (future: queue membership)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This case is in a case manager queue"
            )
        return
    
    # User-owned cases
    if case.owner_type == OwnerType.USER.value:
        # Owner can always access
        if user_id and case.owner_id == user_id:
            return
        
        # Case managers can see other case manager's cases
        if role_str == Role.CASE_MANAGER.value:
            return
        
        # Intake specialists can only see their own cases
        if role_str == Role.INTAKE_SPECIALIST.value:
            if not user_id or case.owner_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this case"
                )
            return


def can_modify_case(
    case: Case,
    user_id: UUID | str,
    user_role: Role | str,
) -> bool:
    """
    Check if user can modify this case.
    
    Rules:
    - Manager+ can always modify
    - Owner can modify
    - Case managers can modify any non-archived case
    - Intake specialists can only modify their own non-handed-off cases
    
    Returns:
        True if user can modify, False otherwise
    """
    # Normalize
    role_str = user_role.value if hasattr(user_role, 'value') else user_role
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
    
    # Archived cases: only managers
    if case.is_archived:
        return role_str in [Role.ADMIN.value, Role.DEVELOPER.value]
    
    # Manager+ can always modify
    if role_str in [Role.ADMIN.value, Role.DEVELOPER.value]:
        return True
    
    # Owner can modify
    if case.owner_id == user_uuid:
        return True
    
    # Case managers can modify non-archived cases
    if role_str == Role.CASE_MANAGER.value:
        return True
    
    # Intake specialists: only their own, and not handed off
    if role_str == Role.INTAKE_SPECIALIST.value:
        return case.owner_type == OwnerType.USER.value and case.owner_id == user_uuid
    
    return False


def can_access_case(
    case: Case,
    user_role: Role | str,
    user_id: UUID | None = None,
) -> bool:
    """
    Non-raising version of check_case_access for filtering.
    
    Returns True if user can access, False otherwise.
    """
    try:
        check_case_access(case, user_role, user_id)
        return True
    except HTTPException:
        return False
