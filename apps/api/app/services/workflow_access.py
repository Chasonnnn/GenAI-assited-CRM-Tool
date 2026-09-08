"""Centralized permission checks for workflows.

This module provides permission helpers for workflow operations:
- Org workflows: require manage_automation permission to create/edit
- Personal workflows: any user can create, only owner can edit

Admins can view (but not edit) other users' personal workflows.
"""

from sqlalchemy.orm import Session

from app.core.permissions import PermissionKey as P
from app.db.enums import Role
from app.db.models import AutomationWorkflow
from app.schemas.auth import UserSession
from app.services import permission_policy_service, permission_service

DONOR_SUBJECT_TYPES = frozenset({"donor", "egg_donor", "sperm_donor"})


def _has_manage_automation(db: Session, session: UserSession) -> bool:
    """Internal helper to check manage_automation permission."""
    return permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, P.AUTOMATION_MANAGE.value
    )


def _v2_can_manage(db: Session, session: UserSession, scope: str) -> bool:
    keys = ["manage_automation"]
    if scope == "org":
        keys.append("manage_org_workflows")
    return all(
        permission_service.check_permission(
            db, session.org_id, session.user_id, session.role.value, key
        )
        for key in keys
    )


def can_inspect_personal(db: Session, session: UserSession) -> bool:
    if permission_policy_service.is_enabled(db, session.org_id):
        return session.role in {Role.ADMIN, Role.DEVELOPER}
    return _has_manage_automation(db, session)


def can_view_subject(db: Session, session: UserSession, subject_type: str | None) -> bool:
    """Check access to subject-specific workflow data."""
    if subject_type not in DONOR_SUBJECT_TYPES:
        return True
    return permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        P.DONORS_VIEW.value,
    )


def can_edit_subject(db: Session, session: UserSession, subject_type: str | None) -> bool:
    """Check write access to subject-specific workflow behavior."""
    if subject_type not in DONOR_SUBJECT_TYPES:
        return True
    if not can_view_subject(db, session, subject_type):
        return False
    return permission_service.check_permission(
        db,
        session.org_id,
        session.user_id,
        session.role.value,
        P.DONORS_EDIT.value,
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
    if permission_policy_service.is_enabled(db, session.org_id):
        return _v2_can_manage(db, session, scope)
    if scope == "org":
        # Org workflows require manage_automation permission
        return _has_manage_automation(db, session)
    # Any authenticated user can create personal workflows
    return True


def can_edit(
    db: Session,
    session: UserSession,
    workflow: AutomationWorkflow,
    effective_subject_type: str | None = None,
) -> bool:
    """
    Check if user can edit this workflow.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can edit this workflow
    """
    if workflow.organization_id != session.org_id:
        return False
    if permission_policy_service.is_enabled(db, session.org_id):
        subject = (
            effective_subject_type if effective_subject_type is not None else workflow.subject_type
        )
        return (
            can_view_subject(db, session, subject)
            and _v2_can_manage(db, session, workflow.scope)
            and (
                workflow.scope == "org"
                or workflow.owner_user_id == session.user_id
                or session.role in {Role.ADMIN, Role.DEVELOPER}
            )
        )
    if not can_edit_subject(
        db,
        session,
        effective_subject_type if effective_subject_type is not None else workflow.subject_type,
    ):
        return False

    if workflow.scope == "org":
        # Org workflows require manage_automation permission
        return _has_manage_automation(db, session)

    # Personal workflows: only the owner can edit
    return workflow.owner_user_id == session.user_id


def can_view(
    db: Session,
    session: UserSession,
    workflow: AutomationWorkflow,
    effective_subject_type: str | None = None,
) -> bool:
    """
    Check if user can view this workflow.

    Args:
        db: Database session
        session: User session
        workflow: The workflow to check

    Returns:
        True if user can view this workflow
    """
    if workflow.organization_id != session.org_id:
        return False
    if permission_policy_service.is_enabled(db, session.org_id):
        subject = (
            effective_subject_type if effective_subject_type is not None else workflow.subject_type
        )
        return can_view_subject(db, session, subject) and (
            workflow.scope == "org"
            or workflow.owner_user_id == session.user_id
            or session.role in {Role.ADMIN, Role.DEVELOPER}
        )
    if not can_view_subject(
        db,
        session,
        effective_subject_type if effective_subject_type is not None else workflow.subject_type,
    ):
        return False

    if workflow.scope == "org":
        # All users in the org can view org workflows
        return True

    # Personal workflows: owner can always view
    if workflow.owner_user_id == session.user_id:
        return True

    # Admins can view (but not edit) other users' personal workflows
    return _has_manage_automation(db, session)


def can_delete(
    db: Session,
    session: UserSession,
    workflow: AutomationWorkflow,
    effective_subject_type: str | None = None,
) -> bool:
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
    return can_edit(db, session, workflow, effective_subject_type)


def can_toggle(
    db: Session,
    session: UserSession,
    workflow: AutomationWorkflow,
    effective_subject_type: str | None = None,
) -> bool:
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
    return can_edit(db, session, workflow, effective_subject_type)


def can_duplicate(
    db: Session,
    session: UserSession,
    workflow: AutomationWorkflow,
    effective_subject_type: str | None = None,
) -> bool:
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
    if permission_policy_service.is_enabled(db, session.org_id):
        # Peer personal transfer is outside the published organization-copy flow.
        return can_edit(db, session, workflow, effective_subject_type) and (
            workflow.scope == "org" or workflow.owner_user_id == session.user_id
        )
    # Must be able to view the source workflow
    subject_type = (
        effective_subject_type if effective_subject_type is not None else workflow.subject_type
    )
    if not can_view(db, session, workflow, subject_type):
        return False
    if not can_edit_subject(db, session, subject_type):
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
    if can_create(db, session, "org"):
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
