"""Shared authorization for editing organization and personal email templates.

Callers must load templates and drafts within the authenticated organization.
HTTP error status and disclosure remain the caller's responsibility.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.policies import POLICIES
from app.db.enums import Role
from app.schemas.auth import UserSession
from app.services import permission_service


def can_edit_personal_template(*, owner_user_id: UUID | None, user_id: UUID, role: Role) -> bool:
    return owner_user_id == user_id or role in (Role.ADMIN, Role.DEVELOPER)


def has_manage_permission(db: Session, session: UserSession) -> bool:
    manage_permission = POLICIES["email_templates"].actions["manage"]
    permission_key = (
        manage_permission.value if hasattr(manage_permission, "value") else str(manage_permission)
    )
    return permission_service.check_permission(
        db, session.org_id, session.user_id, session.role.value, permission_key
    )


def can_edit_template(
    db: Session,
    session: UserSession,
    *,
    scope: str,
    owner_user_id: UUID | None,
) -> bool:
    if scope == "org":
        return has_manage_permission(db, session)
    return can_edit_personal_template(
        owner_user_id=owner_user_id, user_id=session.user_id, role=session.role
    )
