"""Case access control - centralized permission checks for case operations."""

from fastapi import HTTPException, status

from app.db.enums import CaseStatus, Role
from app.db.models import Case


def check_case_access(case: Case, user_role: Role) -> None:
    """
    Check if user can access this case based on role + status.
    
    Raises 403 Forbidden if:
    - User is intake_specialist AND case is in CASE_MANAGER_ONLY statuses
    
    Case managers+ can access all cases.
    
    Args:
        case: The case being accessed
        user_role: The user's role (Role enum) from session
        
    Raises:
        HTTPException: 403 if access denied
    """
    if user_role == Role.INTAKE_SPECIALIST:
        if case.status in CaseStatus.case_manager_only():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This case is no longer accessible to intake specialists"
            )


def can_modify_case(case: Case, user_id: str, user_role: Role) -> bool:
    """
    Check if user can modify this case.
    
    Rules:
    - Manager+ can always modify
    - Case managers can modify cases in their visible statuses
    - Intake specialists can only modify cases in INTAKE_VISIBLE statuses
    - After handoff (status in CASE_MANAGER_ONLY), even creator cannot modify
    
    Returns:
        True if user can modify, False otherwise
    """
    # Manager+ can always modify
    if user_role in [Role.MANAGER, Role.DEVELOPER]:
        return True
    
    # Case managers can modify all non-archived cases
    if user_role == Role.CASE_MANAGER:
        return not case.is_archived
    
    # Intake specialists: block if case has been handed off
    if user_role == Role.INTAKE_SPECIALIST:
        if case.status in CaseStatus.case_manager_only():
            return False
        return not case.is_archived
    
    return False
