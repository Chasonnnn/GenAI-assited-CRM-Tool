"""Centralized permission checks for workflows.

This module provides permission helpers for workflow operations:
- Org workflows: require manage_automation permission to create/edit
- Personal workflows: any user can create, only owner can edit

Admins can view (but not edit) other users' personal workflows.
"""

from sqlalchemy.orm import Session

from app.core.permissions import PermissionKey as P
from app.db.models import AutomationWorkflow
from app.schemas.auth import UserSession
from app.services import permission_service


def _has_manage_automation(db: Session, session: UserSession) -> bool:
    """Internal helper to check manage_automation permission."""
    return permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
    )


def can_create(db: Session, session: UserSession, scope: str) -> bool:
    """
    Check if user can create a workflow with the given scope.

    Args:
        db: Database session
        session: User session
        scope: Workflow scope ('org' or 'personal')

    Returns:
        True if user can create a workflow with this scope
    """
    if scope == "org":
        # Org workflows require manage_automation permission
        return _has_manage_automation(db, session)
    # Any authenticated user can create personal workflows
    return True


def can_edit(db: Session, session: UserSession, workflow: AutomationWorkflow) -> bool:
    """
    Check if user can edit this workflow.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can edit this workflow
    """
    if workflow.scope == "org":
        # Org workflows require manage_automation permission
        return _has_manage_automation(db, session)

    # Personal workflows: only the owner can edit
    return workflow.owner_user_id == session.user_id


def can_view(db: Session, session: UserSession, workflow: AutomationWorkflow) -> bool:
    """
    Check if user can view this workflow.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can view this workflow
    """
    if workflow.scope == "org":
        # All users in the org can view org workflows
        return True

    # Personal workflows: owner can always view
    if workflow.owner_user_id == session.user_id:
        return True

    # Admins can view (but not edit) other users' personal workflows
    return _has_manage_automation(db, session)


def can_delete(db: Session, session: UserSession, workflow: AutomationWorkflow) -> bool:
    """
    Check if user can delete this workflow.

    Same rules as can_edit.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can delete this workflow
    """
    return can_edit(db, session, workflow)


def can_toggle(db: Session, session: UserSession, workflow: AutomationWorkflow) -> bool:
    """
    Check if user can toggle (enable/disable) this workflow.

    Same rules as can_edit.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can toggle this workflow
    """
    return can_edit(db, session, workflow)


def can_duplicate(db: Session, session: UserSession, workflow: AutomationWorkflow) -> bool:
    """
    Check if user can duplicate this workflow.

    Users can duplicate any workflow they can view, but the duplicate
    will be created with the same scope rules:
    - Duplicating an org workflow requires manage_automation
    - Duplicating a personal workflow creates a personal copy owned by the user

    Args:
        db: Database session
        session: User session
        workflow: The workflow to duplicate

    Returns:
        True if user can duplicate this workflow
    """
    # Must be able to view the source workflow
    if not can_view(db, session, workflow):
        return False

    # For org workflows, need manage_automation to create the duplicate
    if workflow.scope == "org":
        return _has_manage_automation(db, session)

    # Anyone can duplicate a personal workflow (creates their own copy)
    return True


def get_editable_scope(db: Session, session: UserSession) -> str:
    """
    Get the scope that user can create workflows in by default.

    Used for UI to determine which scope option to show first.

    Args:
        db: Database session
        session: User session

    Returns:
        'org' if user has manage_automation, else 'personal'
    """
    if _has_manage_automation(db, session):
        return "org"
    return "personal"


def has_manage_permission(db: Session, session: UserSession) -> bool:
    """
    Check if user has manage_automation permission.

    Args:
        db: Database session
        session: User session

    Returns:
        True if user has manage_automation permission
    """
    return _has_manage_automation(db, session)
