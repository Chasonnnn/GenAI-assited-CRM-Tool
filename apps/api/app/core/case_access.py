"""Case access control - centralized permission checks for case operations.

Access is now owner-based (Salesforce-style):
- owner_type="queue": any case_manager+ can access/claim
- owner_type="user": owner, managers, or same-role users can access

Backward compatibility: if owner_type is null (pre-migration), falls back to status-based logic.
"""

from uuid import UUID
from fastapi import HTTPException, status

from app.db.enums import CaseStatus, Role, OwnerType
from app.db.models import Case


def check_case_access(
    case: Case,
    user_role: Role | str,
    user_id: UUID | None = None,
) -> None:
    """
    Check if user can access this case based on ownership.
    
    New logic (owner-based):
    - queue-owned: any case_manager+ can see
    - user-owned: owner, or managers can see
    - intake_specialist: only if they own it or it's in an intake queue
    
    Backward compat: falls back to status-based if owner_type is null
    
    Args:
        case: The case being accessed
        user_role: The user's role from session
        user_id: The user's ID (for ownership check)
        
    Raises:
        HTTPException: 403 if access denied
    """
    # Normalize role to string
    role_str = user_role.value if hasattr(user_role, 'value') else user_role
    
    # Managers/developers can access everything
    if role_str in [Role.MANAGER.value, Role.DEVELOPER.value]:
        return
    
    # If owner fields are set, use owner-based access
    if case.owner_type is not None:
        _check_owner_based_access(case, role_str, user_id)
    else:
        # Fallback to status-based (backward compat for pre-migration cases)
        _check_status_based_access(case, role_str)


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


def _check_status_based_access(case: Case, role_str: str) -> None:
    """Legacy status-based access check (backward compat)."""
    if role_str == Role.INTAKE_SPECIALIST.value:
        if case.status in [s.value for s in CaseStatus.case_manager_only()]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This case is no longer accessible to intake specialists"
            )


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
        return role_str in [Role.MANAGER.value, Role.DEVELOPER.value]
    
    # Manager+ can always modify
    if role_str in [Role.MANAGER.value, Role.DEVELOPER.value]:
        return True
    
    # Owner can modify
    if case.owner_id == user_uuid:
        return True
    
    # Case managers can modify non-archived cases
    if role_str == Role.CASE_MANAGER.value:
        return True
    
    # Intake specialists: only their own, and not handed off
    if role_str == Role.INTAKE_SPECIALIST.value:
        # If owner-based
        if case.owner_type is not None:
            return case.owner_id == user_uuid
        # Fallback: status-based
        if case.status in [s.value for s in CaseStatus.case_manager_only()]:
            return False
        return case.created_by_user_id == user_uuid
    
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
